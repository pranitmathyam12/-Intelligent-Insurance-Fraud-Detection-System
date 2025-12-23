"""
Enhanced extract.py route with Neo4j fraud detection
Keeps all existing functionality + adds fraud detection + graph saving
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from typing import Optional
import structlog
import time
import json
import base64
from datetime import datetime, timezone

from app.config import settings
from app.classifiers.doc_type import classify
from app.llm.usage import LlmUsage, record_usage
from app.extractors import extractor as common_extractor
from app.claim_types.registry import REGISTRY
from app.db.snowflake_utils import save_claim_to_snowflake
from app.db.neo4j_utils import check_claim_fraud_risk, load_claim_to_graph, detect_fraud_patterns, get_graph_stats
from app.services.file_search_service import get_file_search_service

log = structlog.get_logger()
router = APIRouter()


def flatten_claim_data(payload: dict) -> dict:
    """
    Flatten nested claim data structures for Neo4j
    Different document types have different structures - normalize them
    """
    flat = {
        'transaction_id': payload.get('transaction_id'),
        'company_name': payload.get('company_name'),
        'notes': payload.get('notes'),
        'summary': payload.get('summary')
    }
    
    # Flatten policyholder_info (if exists)
    if 'policyholder_info' in payload:
        ph = payload['policyholder_info']
        flat.update({
            'customer_id': ph.get('customer_id'),
            'customer_name': ph.get('customer_name'),
            'policy_number': ph.get('policy_number'),
            'insurance_type': ph.get('insurance_type'),
            'ssn': ph.get('ssn')
        })
    
    # Flatten claim_summary (if exists)
    if 'claim_summary' in payload:
        cs = payload['claim_summary']
        # Remove $ and commas from amount
        amount_str = str(cs.get('amount', '0')).replace('$', '').replace(',', '')
        try:
            flat['claim_amount'] = float(amount_str)
        except:
            flat['claim_amount'] = 0.0
        flat['report_date'] = cs.get('reported_date')
    
    # Flatten deceased_details (Life insurance)
    if 'deceased_details' in payload:
        dd = payload['deceased_details']
        flat.update({
            'deceased_name': dd.get('deceased_name'),
            'date_of_death': dd.get('date_of_death'),
            'cause_of_death': dd.get('cause_of_death')
        })
    
    # Flatten beneficiary_details (Life insurance)
    if 'beneficiary_details' in payload:
        bd = payload['beneficiary_details']
        flat.update({
            'primary_beneficiary': bd.get('primary_beneficiary'),
            'beneficiary_relationship': bd.get('relationship'),
            'payout_method': bd.get('payout_method')
        })

    # Flatten vehicle_details (Motor insurance)
    if 'vehicle_details' in payload:
        vd = payload['vehicle_details']
        flat['vin'] = vd.get('vin')

    # Flatten device_details (Mobile insurance)
    if 'device_details' in payload:
        dd = payload['device_details']
        flat['imei'] = dd.get('imei')

    # Flatten property_details (Property insurance)
    if 'property_details' in payload:
        pd = payload['property_details']
        flat['property_address'] = pd.get('property_address')
    
    # Handle other doc types that might have flat structure
    # Copy any top-level fields that don't exist yet
    for key in ['customer_id', 'customer_name', 'policy_number', 'insurance_type', 
                'claim_amount', 'ssn_masked', 'ssn', 'agent_id', 'vendor_id',
                'address_line1', 'address_line2', 'city', 'state', 'postal_code',
                'age', 'marital', 'employed', 'education']:
        if key not in flat and key in payload:
            flat[key] = payload[key]
    
    return flat


@router.post("/extract")
async def extract_claim(
    file: UploadFile = File(...),
    doc_type: Optional[str] = None,
    classify_if_missing: bool = True,
    enable_fraud_check: bool = Query(False, description="Enable Neo4j fraud detection"),
    save_to_graph: bool = Query(False, description="Save claim to Neo4j graph")
):
    """
    Extract claim data from PDF
    """
    
    # Start total timer
    t_start = time.time()
    upload_timestamp = datetime.now(timezone.utc).isoformat()
    
    log.info("extract.start", upload_filename=file.filename, content_type=file.content_type)
    
    timings = {
        'upload_received': upload_timestamp,
        'classification_ms': 0,
        'extraction_ms': 0,
        'graph_save_ms': 0,
        'fraud_check_ms': 0,
        'total_ms': 0
    }

    # ========== EXISTING VALIDATION (UNCHANGED) ==========
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        log.error("extract.invalid_file_type", content_type=file.content_type)
        raise HTTPException(status_code=415, detail="Unsupported file type")

    data = await file.read()
    if len(data) > settings.MAX_UPLOAD_MB * 1024 * 1024:
        log.error("extract.file_too_large", size=len(data))
        raise HTTPException(status_code=413, detail="File too large")

    # ========== DOCUMENT CLASSIFICATION ==========
    t_class_start = time.time()
    resolved_type = doc_type
    classification_source = "user"

    if not resolved_type:
        allowed = set(REGISTRY.keys())
        if not allowed:
            raise HTTPException(status_code=500, detail="No doc types enabled on server.")
        if len(allowed) == 1:
            resolved_type = next(iter(allowed))
            classification_source = "default"
        else:
            resolved_type = classify(data, allowed=allowed)
            classification_source = "auto"
            timings['classification_ms'] = (time.time() - t_class_start) * 1000

        if not resolved_type:
            log.error("extract.classification_failed")
            raise HTTPException(
                status_code=422,
                detail=f"Could not classify document. Provide doc_type explicitly ({', '.join(sorted(allowed))})."
            )

    log.info("extract.classified", doc_type=resolved_type, source=classification_source)

    if resolved_type not in REGISTRY:
        raise HTTPException(
            status_code=422,
            detail=f"doc_type '{resolved_type}' not enabled. Supported: {', '.join(sorted(REGISTRY.keys()))}"
        )

    # ========== EXTRACTION ==========
    t_extract_start = time.time()
    try:
        payload, in_tokens, out_tokens, cost, ok = common_extractor.extract(resolved_type, data)
        timings['extraction_ms'] = (time.time() - t_extract_start) * 1000
        
        # DEBUG LOG: Log the raw extraction payload to see what's missing
        log.info("extract.payload_raw", payload=json.dumps(payload, default=str))
        
    except ValueError as e:
        log.error("extract.extraction_failed", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))

    # ========== USAGE TRACKING ==========
    usage = LlmUsage(
        model=settings.GENAI_MODEL,
        input_tokens=in_tokens,
        output_tokens=out_tokens,
        total_tokens=in_tokens + out_tokens,
        cost=cost,
    )
    record_usage(req_id="-", usage=usage, doc_type=resolved_type, ok=ok)

    # ========== SNOWFLAKE SAVE ==========
    # Moved to end of function to capture all timings
    snowflake_saved = False
    
    # ========== SAVE TO NEO4J GRAPH ==========
    graph_saved = False
    flattened_data = flatten_claim_data(payload)
    
    # DEBUG LOG: Log flattened data to check if customer_id is present
    log.info("extract.flattened_data", 
             customer_id=flattened_data.get('customer_id'),
             transaction_id=flattened_data.get('transaction_id'),
             keys=list(flattened_data.keys()))
    
    if save_to_graph:
        t_graph_start = time.time()
        try:
            log.info("saving_to_neo4j_graph", 
                    customer_id=flattened_data.get('customer_id'),
                    transaction_id=flattened_data.get('transaction_id'))
            
            graph_saved = load_claim_to_graph(flattened_data)
            timings['graph_save_ms'] = (time.time() - t_graph_start) * 1000
            
            if graph_saved:
                log.info("neo4j_save_success", transaction_id=flattened_data.get('transaction_id'))
            else:
                log.warning("neo4j_save_failed_no_connection")
                
        except Exception as e:
            log.error("neo4j_save_error", error=str(e))
            # Propagate error if requested, but for graph save usually we might want to continue?
            # User asked to remove fallback responses in "fraud detection pipeline".
            # Graph save is part of it. Let's propagate.
            raise e
    
    # ========== FRAUD DETECTION ==========
    fraud_result = None
    if enable_fraud_check:
        t_fraud_start = time.time()
        # Remove try-except to allow errors to propagate as requested
        log.info("running_fraud_detection", customer_id=flattened_data.get('customer_id'))
        
        fraud_result = check_claim_fraud_risk(flattened_data)
        timings['fraud_check_ms'] = (time.time() - t_fraud_start) * 1000
        
        log.info(
            "fraud_detection_complete",
            is_fraudulent=fraud_result.get('is_fraudulent'),
            fraud_score=fraud_result.get('fraud_score'),
            recommendation=fraud_result.get('recommendation')
        )
    
    # Calculate total time
    timings['total_ms'] = (time.time() - t_start) * 1000

    # ========== SNOWFLAKE SAVE (Moved to end to capture timings) ==========
    try:
        save_claim_to_snowflake(
            extraction_result=payload,
            doc_type=resolved_type,
            model=settings.GENAI_MODEL,
            total_tokens=in_tokens + out_tokens,
            cost_usd=cost.total_cost_usd if cost else 0.0,
            timings=timings,
            upload_timestamp=upload_timestamp,
            fraud_data=None,  # Will be updated later by /v1/fraud/analyze
            pdf_base64=base64.b64encode(data).decode('utf-8')
        )
        snowflake_saved = True
        log.info("snowflake_save_success", transaction_id=payload.get('transaction_id'))
    except Exception as e:
        log.warning("snowflake_save_failed", error=str(e))
    
    # ========== FILE SEARCH UPLOAD (RAG Knowledge Base) ==========
    file_search_uploaded = False
    try:
        file_search_service = get_file_search_service()
        claim_id = payload.get('transaction_id', 'unknown')
        
        log.info("file_search.uploading_to_rag", 
                claim_id=claim_id,
                doc_type=resolved_type)
        
        upload_result = file_search_service.upload_document(
            pdf_data=data,
            claim_id=claim_id,
            doc_type=resolved_type
        )
        
        file_search_uploaded = upload_result.get('success', False)
        
        if file_search_uploaded:
            log.info("file_search.upload_success", 
                    claim_id=claim_id,
                    upload_time_ms=upload_result.get('upload_time_ms'))
        else:
            log.warning("file_search.upload_failed", 
                       claim_id=claim_id,
                       error=upload_result.get('error'))
    except Exception as e:
        log.warning("file_search.upload_error", 
                   claim_id=payload.get('transaction_id'),
                   error=str(e))

    
    # ========== ENHANCED RESPONSE ==========
    response = {
        "metadata": {
            "upload_timestamp": upload_timestamp,
            "timings": timings,
            "snowflake_saved": snowflake_saved,
            "neo4j_graph_saved": graph_saved,
            "file_search_uploaded": file_search_uploaded
        },
        "extraction": {
            "doc_type": resolved_type,
            "classification_source": classification_source,
            "model": settings.GENAI_MODEL,
            "usage": {
                "input_tokens": in_tokens,
                "output_tokens": out_tokens,
                "total_tokens": in_tokens + out_tokens,
            },
            "cost_estimate": (cost.__dict__ if cost else None),
            "data": payload
        }
    }
    
    # Add fraud detection if available
    if fraud_result:
        response["fraud_analysis"] = fraud_result
    
    return response


# ========== NEW ENDPOINTS ==========

@router.post("/fraud-check")
async def standalone_fraud_check(claim_data: dict):
    """
    Standalone fraud check for already extracted claims
    """
    try:
        result = check_claim_fraud_risk(claim_data)
        return {
            'success': True,
            'fraud_detection': result
        }
    except Exception as e:
        log.error("fraud_check_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/fraud-patterns")
async def get_fraud_patterns():
    """
    Get all detected fraud patterns from the graph
    """
    try:
        patterns = detect_fraud_patterns()
        return {
            'success': True,
            'patterns_found': len(patterns),
            'patterns': patterns
        }
    except Exception as e:
        log.error("fraud_patterns_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/graph-stats")
async def get_graph_statistics():
    """
    Get Neo4j graph statistics
    """
    try:
        stats = get_graph_stats()
        return {
            'success': True,
            'statistics': stats
        }
    except Exception as e:
        log.error("graph_stats_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health/neo4j")
async def neo4j_health_check():
    """Check Neo4j connection status"""
    import os
    
    # Check if credentials are configured
    uri = os.getenv('NEO4J_URI')
    password = os.getenv('NEO4J_PASSWORD')
    
    if not uri or not password:
        return {
            'status': 'unavailable',
            'message': 'Neo4j not configured. Set NEO4J_URI and NEO4J_PASSWORD in .env'
        }
    
    try:
        from app.db.neo4j_utils import Neo4jConnection
        
        neo4j = Neo4jConnection()
        result = neo4j.connect()
        
        if result:
            # Test with a simple query to verify it really works
            test = neo4j.execute_query('RETURN 1 as test')
            neo4j.close()
            
            return {
                'status': 'healthy',
                'message': 'Neo4j connection active',
                'uri': uri,
                'database': os.getenv('NEO4J_DATABASE', 'neo4j')
            }
        else:
            return {
                'status': 'error',
                'message': 'Failed to connect to Neo4j'
            }
            
    except Exception as e:
        log.error("neo4j_health_check_error", error=str(e))
        return {
            'status': 'error',
            'message': f'Neo4j error: {str(e)}'
        }