"""
Dashboard API endpoint for FraudGuardAI
Provides comprehensive dashboard data in a single API call
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import structlog

from app.db.neo4j_utils import get_dashboard_stats
from app.db.snowflake_utils import (
    get_avg_processing_time,
    get_risk_distribution,
    get_claims_timeline,
    get_high_risk_alerts
)

log = structlog.get_logger()
router = APIRouter()


@router.get("/dashboard")
async def get_dashboard_data(timeline_days: int = 30, alerts_limit: int = 10) -> Dict[str, Any]:
    """
    Get comprehensive dashboard data in a single API call
    
    Returns:
    - total_claims: Total number of claims from Neo4j graph
    - fraud_detected: Number of fraudulent claims detected
    - estimated_fraud_value: Total value of fraudulent claims
    - avg_processing_time: Average processing time in seconds from Snowflake
    - claims_timeline: Daily breakdown of legitimate vs fraudulent claims
    - risk_distribution: Distribution of claims by risk level (low/medium/high)
    - high_risk_alerts: Table of high-risk claims for review
    """
    
    try:
        log.info("dashboard.fetch_start", timeline_days=timeline_days, alerts_limit=alerts_limit)
        
        # Fetch data from Neo4j (graph statistics)
        graph_stats = get_dashboard_stats()
        
        # Fetch data from Snowflake (processing metrics and detailed data)
        avg_processing = get_avg_processing_time()
        risk_dist = get_risk_distribution()
        timeline = get_claims_timeline(days=timeline_days)
        alerts = get_high_risk_alerts(limit=alerts_limit)
        
        # Construct comprehensive response
        dashboard_data = {
            # Top metrics
            "metrics": {
                "total_claims": graph_stats.get('total_claims', 0),
                "fraud_detected": graph_stats.get('fraud_detected', 0),
                "estimated_fraud_value": graph_stats.get('estimated_fraud_value', 0.0),
                "avg_processing_time": avg_processing
            },
            
            # Charts data
            "charts": {
                "claims_timeline": timeline,
                "risk_distribution": risk_dist
            },
            
            # Table data
            "high_risk_alerts": alerts,
            
            # Metadata
            "metadata": {
                "timeline_days": timeline_days,
                "alerts_shown": len(alerts),
                "data_sources": {
                    "graph": "neo4j",
                    "metrics": "snowflake"
                }
            }
        }
        
        log.info("dashboard.fetch_complete", 
                 total_claims=graph_stats.get('total_claims', 0),
                 fraud_detected=graph_stats.get('fraud_detected', 0))
        
        return dashboard_data
        
    except Exception as e:
        log.error("dashboard.fetch_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch dashboard data: {str(e)}"
        )
