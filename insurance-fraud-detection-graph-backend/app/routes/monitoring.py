"""
Monitoring API endpoints for FraudGuardAI
Provides real-time monitoring metrics and log streaming
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import Dict, Any, List
import structlog
import asyncio
import os
from datetime import datetime, timedelta

from app.db.snowflake_utils import (
    get_monitoring_metrics,
    get_token_usage_timeline
)

log = structlog.get_logger()
router = APIRouter()


@router.get("/monitoring/metrics")
async def get_monitoring_top_metrics() -> Dict[str, Any]:
    """
    Get top-level monitoring metrics for the dashboard
    
    Returns:
    - tokens_used: Total LLM tokens consumed
    - api_cost: Total API cost in USD
    - avg_time: Average processing time in seconds
    - total_requests: Total number of requests processed
    """
    
    try:
        log.info("monitoring.metrics.fetch_start")
        
        # Fetch metrics from Snowflake
        metrics = get_monitoring_metrics()
        
        response = {
            "tokens_used": metrics.get('total_tokens', 0),
            "api_cost": round(metrics.get('total_cost', 0.0), 2),
            "avg_time": round(metrics.get('avg_time', 0.0), 2),  # in seconds
            "total_requests": metrics.get('total_requests', 0)
        }
        
        log.info("monitoring.metrics.fetch_complete", 
                 tokens=response['tokens_used'],
                 requests=response['total_requests'])
        
        return response
        
    except Exception as e:
        log.error("monitoring.metrics.fetch_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch monitoring metrics: {str(e)}"
        )


@router.get("/monitoring/token-usage")
async def get_token_usage_graph(days: int = 7) -> Dict[str, Any]:
    """
    Get LLM token usage and cost timeline for graph visualization
    
    Args:
    - days: Number of days to look back (default: 7)
    
    Returns:
    - timeline: Array of data points with date, tokens, and cost
    """
    
    try:
        log.info("monitoring.token_usage.fetch_start", days=days)
        
        # Fetch timeline data from Snowflake
        timeline = get_token_usage_timeline(days=days)
        
        response = {
            "timeline": timeline,
            "metadata": {
                "days": days,
                "data_points": len(timeline),
                "total_tokens": sum(point.get('tokens', 0) for point in timeline),
                "total_cost": round(sum(point.get('cost', 0.0) for point in timeline), 2)
            }
        }
        
        log.info("monitoring.token_usage.fetch_complete", 
                 data_points=len(timeline))
        
        return response
        
    except Exception as e:
        log.error("monitoring.token_usage.fetch_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch token usage data: {str(e)}"
        )


@router.get("/monitoring/logs")
async def get_recent_logs(limit: int = 50) -> Dict[str, Any]:
    """
    Get recent log entries from the backend application
    
    This is a polling-based endpoint that returns the last N log entries.
    Frontend should poll this endpoint periodically (e.g., every 2-3 seconds).
    
    Args:
    - limit: Number of recent log entries to return (default: 50, max: 200)
    
    Returns:
    - logs: Array of parsed log entries
    - count: Number of logs returned
    
    Example frontend usage:
    ```javascript
    // Poll every 3 seconds
    setInterval(async () => {
        const response = await fetch('/v1/monitoring/logs?limit=50');
        const data = await response.json();
        updateLogDisplay(data.logs);
    }, 3000);
    ```
    """
    import json
    
    # Limit the number of logs to prevent memory issues
    limit = min(limit, 200)
    
    log_file_path = "/Users/aakashbelide/Aakash/Higher Studies/Course/Sem-3/DAMG 7374/insurance-fraud-detection-graph-backend/app.log"
    
    try:
        # Check if log file exists
        if not os.path.exists(log_file_path):
            return {
                "logs": [{
                    'level': 'ERROR',
                    'message': 'Log file not found',
                    'timestamp': datetime.utcnow().isoformat(),
                    'location': ''
                }],
                "count": 1,
                "error": "Log file not found"
            }
        
        # Read the last N lines from the log file
        logs = []
        
        with open(log_file_path, 'r') as log_file:
            # Read all lines and get the last N
            all_lines = log_file.readlines()
            recent_lines = all_lines[-limit:] if len(all_lines) > limit else all_lines
            
            # Parse each line
            for line in recent_lines:
                if line.strip():  # Skip empty lines
                    try:
                        parsed_log = json.loads(parse_log_line(line))
                        logs.append(parsed_log)
                    except Exception as parse_error:
                        # If parsing fails, add as raw log
                        logs.append({
                            'level': 'RAW',
                            'message': line.strip(),
                            'timestamp': datetime.utcnow().isoformat(),
                            'location': ''
                        })
        
        return {
            "logs": logs,
            "count": len(logs),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        log.error("monitoring.logs.fetch_failed", error=str(e))
        return {
            "logs": [{
                'level': 'ERROR',
                'message': f'Error reading logs: {str(e)}',
                'timestamp': datetime.utcnow().isoformat(),
                'location': ''
            }],
            "count": 1,
            "error": str(e)
        }


def parse_log_line(line: str) -> str:
    """
    Parse a log line and extract structured information
    
    Expected format: [timestamp]{filename funcName:lineno threadName} LEVEL - message
    Example: [2024-12-07 14:23:01]{fraud.py analyze_fraud:123 MainThread} INFO - Request received
    """
    import json
    import re
    
    try:
        # Try to match the structured log format
        pattern = r'\[([^\]]+)\]\{([^}]+)\}\s+(\w+)\s+-\s+(.+)'
        match = re.match(pattern, line.strip())
        
        if match:
            timestamp, location, level, message = match.groups()
            
            # Determine color/style based on level
            level_map = {
                'DEBUG': 'DEBUG',
                'INFO': 'INFO',
                'WARNING': 'WARN',
                'ERROR': 'ERROR',
                'CRITICAL': 'ERROR'
            }
            
            return json.dumps({
                'timestamp': timestamp,
                'level': level_map.get(level, level),
                'location': location,
                'message': message
            })
        else:
            # Fallback for unstructured logs
            return json.dumps({
                'timestamp': datetime.utcnow().isoformat(),
                'level': 'INFO',
                'message': line.strip()
            })
            
    except Exception as e:
        # If all parsing fails, return raw
        return json.dumps({
            'timestamp': datetime.utcnow().isoformat(),
            'level': 'RAW',
            'message': line.strip()
        })
