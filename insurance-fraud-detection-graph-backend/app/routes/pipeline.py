from fastapi import APIRouter, UploadFile, File, HTTPException, Query
import structlog
import os
import tempfile
from typing import Optional

from app.pipelines.csv_pipeline import (
    load_csv_to_snowflake,
    build_graph_from_snowflake,
    quick_fraud_check
)
from app.db.neo4j_utils import get_graph_stats, detect_fraud_patterns

log = structlog.get_logger()
router = APIRouter()

@router.post("/upload-csv")
async def upload_csv(
    file: UploadFile = File(...),
):
    """
    Upload CSV file and load into Snowflake
    
    Accepts: CSV file with insurance claim data
    Returns: Status and number of rows loaded
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=415, detail="Only CSV files accepted")
    
    # Save uploaded file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name
    
    try:
        # Load to Snowflake
        success, rows, error = load_csv_to_snowflake(tmp_path)
        
        # Clean up temp file
        os.unlink(tmp_path)
        
        if success:
            return {
                "status": "success",
                "message": f"Loaded {rows} rows to Snowflake",
                "rows_loaded": rows,
                "table": "claims_raw"
            }
        else:
            raise HTTPException(status_code=500, detail=error or "Failed to load CSV")
            
    except Exception as e:
        # Clean up temp file
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/build-graph")
async def build_graph(
    limit: Optional[int] = Query(None, description="Max records to process (None = all)")
):
    """
    Build Neo4j graph from Snowflake data
    
    Reads claims from Snowflake and creates:
    - Person nodes (customers)
    - Claim nodes
    - Policy nodes
    - Address nodes
    - Agent nodes
    - Vendor nodes
    - Relationships between them
    """
    try:
        success, nodes, error = build_graph_from_snowflake(limit=limit)
        
        if success:
            return {
                "status": "success",
                "message": f"Graph built with {nodes} claims",
                "nodes_created": nodes,
                "database": "fraud-graph"
            }
        else:
            raise HTTPException(status_code=500, detail=error or "Failed to build graph")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/graph/stats")
async def graph_statistics():
    """
    Get statistics about the Neo4j graph
    
    Returns counts of nodes by type
    """
    try:
        stats = get_graph_stats()
        return {
            "status": "success",
            "statistics": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/detect-fraud")
async def detect_fraud():
    """
    Run fraud detection algorithms on the graph
    
    Detects patterns like:
    - Multiple claims by same person
    - Multiple people at same address
    - High value claims
    - Suspicious claim clusters
    """
    try:
        patterns = detect_fraud_patterns()
        
        return {
            "status": "success",
            "patterns_found": len(patterns),
            "fraud_indicators": patterns
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/fraud-check/{customer_id}")
async def check_customer(customer_id: str):
    """
    Check fraud indicators for a specific customer
    
    Args:
        customer_id: Customer ID to investigate
    """
    try:
        result = quick_fraud_check(customer_id=customer_id)
        
        if not result or "error" in result:
            raise HTTPException(status_code=404, detail="Customer not found in graph")
        
        # Determine risk level
        claims = result.get('claims', 0)
        others_at_address = result.get('others_at_address', 0)
        
        risk = "LOW"
        if claims > 2 or others_at_address > 2:
            risk = "HIGH"
        elif claims > 1 or others_at_address > 0:
            risk = "MEDIUM"
        
        return {
            "status": "success",
            "customer_id": customer_id,
            "customer_name": result.get('name'),
            "total_claims": claims,
            "total_claimed": result.get('total'),
            "address": result.get('address'),
            "others_at_same_address": others_at_address,
            "risk_level": risk
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))