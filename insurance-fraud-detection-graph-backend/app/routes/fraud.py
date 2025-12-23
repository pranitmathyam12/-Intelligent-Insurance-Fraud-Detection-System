from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from app.models.fraud import GraphIngestResponse, FraudAnalysisRequest, FraudAnalysisResponse
from app.db.neo4j_utils import load_claim_to_graph, check_claim_fraud_risk
from app.services.llm_fraud_analysis import analyze_fraud_with_llm
import structlog
import time
import os

router = APIRouter(prefix="/v1/fraud", tags=["Fraud Detection"])
log = structlog.get_logger()

@router.post("/ingest_to_graph", response_model=GraphIngestResponse)
async def ingest_claim_to_graph(claim_data: Dict[str, Any]):
    """
    Endpoint 1: Ingest extracted claim data into Neo4j graph and detect fraud patterns
    
    Takes the JSON output from /v1/extract endpoint and:
    1. Maps it to graph-compatible format
    2. Creates nodes and relationships in Neo4j
    3. Runs fraud detection queries
    4. Returns fraud detection results
    
    Args:
        claim_data: Extracted claim data (output from /v1/extract)
    
    Returns:
        GraphIngestResponse with fraud detection results
    """
    try:
        # Handle nested structure if coming from /extract
        from app.routes.extract import flatten_claim_data
        
        if 'extraction' in claim_data and 'data' in claim_data['extraction']:
            # New format: {'extraction': {'data': {...}}}
            data_to_load = flatten_claim_data(claim_data['extraction']['data'])
            claim_id = data_to_load.get('transaction_id')
        elif 'result' in claim_data:
            # Old format: {'result': {...}}
            data_to_load = flatten_claim_data(claim_data['result'])
            claim_id = data_to_load.get('transaction_id')
        else:
            # Direct payload or already flattened
            data_to_load = claim_data
            claim_id = claim_data.get('transaction_id') or claim_data.get('claim_id')

        log.info("fraud.ingest_request", claim_id=claim_id)
        
        # Track graph ingestion time
        ingest_start = time.time()
        
        # 1. Load to Graph
        graph_start = time.time()
        success = load_claim_to_graph(data_to_load)
        graph_load_ms = (time.time() - graph_start) * 1000
        
        # 2. Check Fraud
        fraud_start = time.time()
        fraud_result = check_claim_fraud_risk(data_to_load)
        fraud_check_ms = (time.time() - fraud_start) * 1000
        
        # 3. Fetch full graph data for visualization
        from app.db.neo4j_utils import get_claim_graph_data
        viz_start = time.time()
        full_graph_data = get_claim_graph_data(claim_id)
        viz_ms = (time.time() - viz_start) * 1000
        
        total_ingest_ms = (time.time() - ingest_start) * 1000
        
        # 4. Update Snowflake with graph ingestion timing
        try:
            import snowflake.connector
            conn = snowflake.connector.connect(
                account=os.getenv('SNOWFLAKE_ACCOUNT'),
                user=os.getenv('SNOWFLAKE_USER'),
                password=os.getenv('SNOWFLAKE_PASSWORD'),
                warehouse=os.getenv('SNOWFLAKE_WAREHOUSE'),
                database=os.getenv('SNOWFLAKE_DATABASE'),
                schema=os.getenv('SNOWFLAKE_SCHEMA')
            )
            cursor = conn.cursor()
            
            # Update graph ingestion timing (we'll create a new column for this)
            update_query = """
            UPDATE extracted_claims
            SET graph_ingest_ms = %s
            WHERE transaction_id = %s
            """
            
            cursor.execute(update_query, (total_ingest_ms, claim_id))
            conn.commit()
            cursor.close()
            conn.close()
            
            print(f"DEBUG: Updated graph_ingest_ms = {total_ingest_ms:.2f}ms for {claim_id}")
            log.info("fraud.ingest_timing_saved", claim_id=claim_id, graph_ingest_ms=total_ingest_ms)
        except Exception as e:
            log.warning("fraud.ingest_timing_save_failed", error=str(e))
            print(f"DEBUG: Failed to save graph ingest timing: {str(e)}")
        
        # 5. Construct Response
        # Extract graph visualization data
        graph_viz = fraud_result.get('graph_visualization', {})
        nodes_count = len(graph_viz.get('nodes', []))
        rels_count = len(graph_viz.get('edges', []))
        
        # Map flags to detected patterns
        patterns = []
        for flag in fraud_result.get('flags', []):
            patterns.append({
                "pattern_type": flag.get('rule', 'Unknown'),
                "confidence": flag.get('severity', 'MEDIUM'),
                "evidence": [flag.get('message', '')],
                "related_entities": {}
            })

        result = GraphIngestResponse(
            success=success,
            claim_id=claim_id,
            nodes_created=nodes_count,
            relationships_created=rels_count,
            is_fraudulent=fraud_result.get('is_fraudulent', False),
            fraud_score=fraud_result.get('fraud_score', 0) / 100.0, # Normalize to 0-1 for frontend
            detected_patterns=patterns,
            graph_summary=graph_viz,
            fraud_graph_output=full_graph_data,
            original_claim_data=claim_data
        )
        
        log.info("fraud.ingest_complete", 
                 claim_id=claim_id,
                 is_fraudulent=result.is_fraudulent,
                 total_ingest_ms=total_ingest_ms)
        
        return result
    
    except Exception as e:
        log.error("fraud.ingest_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to ingest claim: {str(e)}")


@router.post("/analyze", response_model=FraudAnalysisResponse)
async def analyze_fraud(request: Dict[str, Any]):
    """
    Endpoint 2: Use LLM to analyze fraud detection results and provide detailed reasoning
    
    Takes the FULL output from /v1/fraud/ingest_to_graph and intelligently extracts
    what's needed for LLM analysis. Works with any claim type.
    
    Args:
        request: Full response from /v1/fraud/ingest_to_graph
    
    Returns:
        FraudAnalysisResponse with LLM analysis
    """
    try:
        # Handle if this is the full ingest response or a structured request
        if 'claim_id' in request and 'is_fraudulent' in request:
            # This is the direct output from ingest_to_graph
            graph_results = GraphIngestResponse(**request)
            # Extract claim data from the original request if available
            claim_data = request.get('original_claim_data', {})
        elif 'graph_results' in request:
            # This is a structured FraudAnalysisRequest
            graph_results = GraphIngestResponse(**request['graph_results'])
            claim_data = request.get('claim_data', {})
        else:
            raise HTTPException(status_code=400, detail="Invalid request format")
        
        log.info("fraud.analyze_request", claim_id=graph_results.claim_id)
        
        # Track LLM analysis time
        llm_start = time.time()
        
        # Create the analysis request
        analysis_request = FraudAnalysisRequest(
            claim_data=claim_data,
            graph_results=graph_results
        )
        
        result = await analyze_fraud_with_llm(analysis_request)
        
        llm_time_ms = (time.time() - llm_start) * 1000
        
        log.info("fraud.analyze_complete",
                 claim_id=graph_results.claim_id,
                 is_fraudulent=result.is_fraudulent,
                 risk_score=result.risk_score,
                 llm_time_ms=llm_time_ms)
        
        # Update Snowflake with final LLM fraud analysis AND complete timing
        try:
            import snowflake.connector
            import json
            
            conn = snowflake.connector.connect(
                account=os.getenv('SNOWFLAKE_ACCOUNT'),
                user=os.getenv('SNOWFLAKE_USER'),
                password=os.getenv('SNOWFLAKE_PASSWORD'),
                warehouse=os.getenv('SNOWFLAKE_WAREHOUSE'),
                database=os.getenv('SNOWFLAKE_DATABASE'),
                schema=os.getenv('SNOWFLAKE_SCHEMA')
            )
            cursor = conn.cursor()
            
            # Create fraud_data JSON with LLM results
            fraud_data = {
                "is_fraudulent": result.is_fraudulent,
                "fraud_score": result.risk_score,  # This is 0-100 from LLM
                "recommendation": "REJECT" if result.risk_score >= 75 else ("MANUAL_REVIEW" if result.risk_score >= 40 else "APPROVE"),
                "confidence_level": result.confidence_level,
                "summary": result.summary,
                "red_flags": result.red_flags,
                "detailed_reasoning": result.detailed_reasoning
            }
            
            fraud_json = json.dumps(fraud_data)
            
            # Get existing timings and add LLM time
            get_timings_query = """
            SELECT classification_ms, extraction_ms, graph_save_ms, fraud_check_ms, graph_ingest_ms
            FROM extracted_claims
            WHERE transaction_id = %s
            """
            cursor.execute(get_timings_query, (graph_results.claim_id,))
            existing_timings = cursor.fetchone()
            
            if existing_timings:
                classification_ms = existing_timings[0] or 0
                extraction_ms = existing_timings[1] or 0
                graph_save_ms = existing_timings[2] or 0
                fraud_check_ms = existing_timings[3] or 0
                graph_ingest_ms = existing_timings[4] or 0
                
                # Calculate complete pipeline time
                complete_total_ms = classification_ms + extraction_ms + graph_save_ms + fraud_check_ms + graph_ingest_ms + llm_time_ms
                
                print(f"DEBUG: Pipeline timing breakdown:")
                print(f"  - Classification: {classification_ms:.2f}ms")
                print(f"  - Extraction: {extraction_ms:.2f}ms")
                print(f"  - Graph Save: {graph_save_ms:.2f}ms")
                print(f"  - Fraud Check: {fraud_check_ms:.2f}ms")
                print(f"  - Graph Ingest: {graph_ingest_ms:.2f}ms")
                print(f"  - LLM Analysis: {llm_time_ms:.2f}ms")
                print(f"  - TOTAL: {complete_total_ms:.2f}ms ({complete_total_ms/1000:.2f}s)")
            else:
                complete_total_ms = llm_time_ms
            
            # Update both fraud_data and total_ms
            update_query = """
            UPDATE extracted_claims
            SET fraud_data = TO_VARIANT(PARSE_JSON(%s)),
                total_ms = %s
            WHERE transaction_id = %s
            """
            
            print(f"DEBUG: Updating Snowflake with LLM analysis for claim_id: {graph_results.claim_id}")
            print(f"DEBUG: Fraud score: {result.risk_score}, Is fraudulent: {result.is_fraudulent}")
            print(f"DEBUG: Complete pipeline time: {complete_total_ms:.2f}ms ({complete_total_ms/1000:.2f}s)")
            
            cursor.execute(update_query, (fraud_json, complete_total_ms, graph_results.claim_id))
            conn.commit()
            
            print(f"DEBUG: Snowflake update successful!")
            
            cursor.close()
            conn.close()
            log.info("fraud.snowflake_updated", 
                    claim_id=graph_results.claim_id, 
                    risk_score=result.risk_score,
                    total_time_ms=complete_total_ms)
        except Exception as e:
            log.warning("fraud.snowflake_update_failed", error=str(e), claim_id=graph_results.claim_id)
            print(f"DEBUG: Snowflake update failed: {str(e)}")
        
        # ========== FILE SEARCH UPLOAD (Fraud Analysis) ==========
        # Upload fraud analysis results to File Search for RAG queries
        try:
            from app.services.file_search_service import get_file_search_service
            
            file_search_service = get_file_search_service()
            
            # Prepare comprehensive fraud analysis data
            fraud_analysis_data = {
                'claim_id': graph_results.claim_id,
                'fraud_score': result.risk_score,
                'fraud_verdict': 'FRAUDULENT' if result.is_fraudulent else 'LEGITIMATE',
                'graph_analysis': {
                    'detected_patterns': graph_results.detected_patterns,
                    'graph_fraud_score': graph_results.fraud_score,
                    'nodes_created': graph_results.nodes_created,
                    'relationships_created': graph_results.relationships_created
                },
                'llm_analysis': {
                    'summary': result.summary,
                    'confidence_level': result.confidence_level,
                    'red_flags': result.red_flags,
                    'detailed_reasoning': result.detailed_reasoning
                },
                'reasoning': result.detailed_reasoning,
                'risk_factors': result.red_flags,
                'recommendations': [f"Recommendation: {'REJECT' if result.risk_score >= 75 else ('MANUAL_REVIEW' if result.risk_score >= 40 else 'APPROVE')}"]
            }
            
            upload_result = file_search_service.upload_fraud_analysis(
                claim_id=graph_results.claim_id,
                fraud_analysis=fraud_analysis_data
            )
            
            if upload_result.get('success'):
                log.info("fraud.file_search_uploaded",
                        claim_id=graph_results.claim_id,
                        upload_time_ms=upload_result.get('upload_time_ms'))
            else:
                log.warning("fraud.file_search_upload_failed",
                           claim_id=graph_results.claim_id,
                           error=upload_result.get('error'))
                
        except Exception as file_search_error:
            # Don't fail the request if File Search upload fails
            log.warning("fraud.file_search_upload_error",
                       claim_id=graph_results.claim_id,
                       error=str(file_search_error))
        
        return result
    
    except Exception as e:
        log.error("fraud.analyze_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to analyze fraud: {str(e)}")


@router.get("/graph/{claim_id}")
async def get_claim_graph(claim_id: str):
    """
    Endpoint 3: Fetch graph visualization data for a specific claim
    
    Returns nodes and edges for the claim's neighborhood, including:
    - The claim itself
    - Related entities (Person, Policy, etc.)
    - Potential fraud rings
    
    Args:
        claim_id: Transaction ID of the claim
        
    Returns:
        Dict with 'nodes' and 'edges' lists
    """
    try:
        from app.db.neo4j_utils import get_claim_graph_data
        
        log.info("fraud.graph_request", claim_id=claim_id)
        
        graph_data = get_claim_graph_data(claim_id)
        
        log.info("fraud.graph_complete", 
                 claim_id=claim_id, 
                 nodes=len(graph_data.get('nodes', [])), 
                 edges=len(graph_data.get('edges', [])))
        
        return graph_data
        
    except Exception as e:
        log.error("fraud.graph_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to fetch graph data: {str(e)}")
