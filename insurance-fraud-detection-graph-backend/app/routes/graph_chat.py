"""
Graph Chat API Routes

Natural language interface to Neo4j fraud detection graph.
Users can ask questions about fraud patterns, claims, and relationships.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from app.services.graph_chat_service import get_graph_chat_service
import structlog

router = APIRouter(prefix="/v1/graph-chat", tags=["Graph Chat"])
log = structlog.get_logger()


class GraphQueryRequest(BaseModel):
    """Request model for graph query"""
    user_message: str = Field(..., description="User's natural language question about the graph")
    session_id: Optional[str] = Field(None, description="Session ID for conversation tracking")
    include_history: bool = Field(True, description="Whether to include chat history in context")


class GraphQueryResponse(BaseModel):
    """Response model for graph query"""
    success: bool
    session_id: str
    answer: str
    cypher_query: Optional[str] = None
    results: List[Dict[str, Any]] = []
    result_count: int = 0
    query_time_ms: float
    model: str = ""
    error: Optional[str] = None


@router.post("/query", response_model=GraphQueryResponse)
async def query_graph(request: GraphQueryRequest):
    """
    Query the Neo4j graph using natural language
    
    The system will:
    1. Convert your question to a Cypher query
    2. Execute it on the Neo4j graph database
    3. Interpret the results
    4. Provide a natural language answer
    
    Example questions:
    - "Show me high risk claims"
    - "Who are the most frequent claimants?"
    - "Find claims with shared SSNs"
    - "What fraud patterns exist in the data?"
    - "Which agents handle the most claims?"
    - "Show me claims involving asset recycling"
    
    Args:
        request: GraphQueryRequest with user message and optional session
        
    Returns:
        GraphQueryResponse with answer, Cypher query, and results
    """
    try:
        log.info("graph_chat.query_request",
                session_id=request.session_id,
                message_preview=request.user_message[:100])
        
        graph_chat_service = get_graph_chat_service()
        
        result = graph_chat_service.query(
            user_message=request.user_message,
            session_id=request.session_id,
            include_history=request.include_history
        )
        
        return GraphQueryResponse(**result)
        
    except Exception as e:
        log.error("graph_chat.query_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Graph query failed: {str(e)}")


@router.get("/session/{session_id}/history")
async def get_session_history(session_id: str):
    """
    Get conversation history for a specific session
    
    Args:
        session_id: Session ID
        
    Returns:
        Dict with session history
    """
    try:
        graph_chat_service = get_graph_chat_service()
        history = graph_chat_service.get_session_history(session_id)
        
        return {
            'success': True,
            'session_id': session_id,
            'message_count': len(history),
            'messages': history
        }
        
    except Exception as e:
        log.error("graph_chat.history_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get history: {str(e)}")


@router.delete("/session/{session_id}")
async def clear_session(session_id: str):
    """
    Clear conversation history for a specific session
    
    Args:
        session_id: Session ID to clear
        
    Returns:
        Dict with deletion status
    """
    try:
        graph_chat_service = get_graph_chat_service()
        success = graph_chat_service.clear_session(session_id)
        
        if success:
            return {
                'success': True,
                'session_id': session_id,
                'message': 'Session cleared successfully'
            }
        else:
            return {
                'success': False,
                'session_id': session_id,
                'message': 'Session not found'
            }
        
    except Exception as e:
        log.error("graph_chat.clear_session_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to clear session: {str(e)}")


@router.get("/health")
async def graph_chat_health():
    """
    Health check for Graph Chat system
    
    Returns:
        Health status including Neo4j connection and active sessions
    """
    try:
        from app.db.neo4j_utils import Neo4jConnection
        
        # Test Neo4j connection
        neo4j = Neo4jConnection()
        neo4j_connected = neo4j.connect()
        if neo4j_connected:
            neo4j.close()
        
        graph_chat_service = get_graph_chat_service()
        active_sessions = len(graph_chat_service._sessions)
        
        return {
            'status': 'healthy' if neo4j_connected else 'degraded',
            'message': 'Graph Chat system operational' if neo4j_connected else 'Neo4j connection issue',
            'neo4j_connected': neo4j_connected,
            'active_sessions': active_sessions,
            'model': graph_chat_service.model
        }
        
    except Exception as e:
        log.error("graph_chat.health_check_error", error=str(e))
        return {
            'status': 'unhealthy',
            'message': f'Health check failed: {str(e)}',
            'neo4j_connected': False,
            'active_sessions': 0
        }


@router.get("/schema")
async def get_schema_info():
    """
    Get information about the Neo4j graph schema
    
    Returns:
        Dict with schema information
    """
    try:
        graph_chat_service = get_graph_chat_service()
        
        return {
            'success': True,
            'schema': {
                'nodes': [
                    'Person (customer_id, name, age, marital_status, employment_status, etc.)',
                    'SSN (value)',
                    'Address (address_key, line1, city, state, postal_code)',
                    'Policy (policy_number, type, premium, effective_date, etc.)',
                    'Claim (transaction_id, amount, loss_date, severity, status, etc.)',
                    'Agent (agent_id)',
                    'Vendor (vendor_id)',
                    'Asset (value, type)'
                ],
                'relationships': [
                    'Person -[:HAS_SSN]-> SSN',
                    'Person -[:LIVES_AT]-> Address',
                    'Person -[:OWNS_POLICY]-> Policy',
                    'Person -[:FILED]-> Claim',
                    'Claim -[:COVERED_BY]-> Policy',
                    'Agent -[:HANDLED]-> Claim',
                    'Claim -[:REPAIRED_BY]-> Vendor',
                    'Agent -[:WORKS_WITH]-> Vendor',
                    'Claim -[:INVOLVES]-> Asset'
                ],
                'fraud_patterns': [
                    'Shared PII Rings (multiple people, same SSN)',
                    'Collusive Provider Rings (agent-vendor collusion)',
                    'Asset Recycling (same VIN/IMEI, multiple claims)',
                    'Velocity Fraud (multiple rapid claims)',
                    'Double Dipping (duplicate claims)',
                    'Multiple Claimants at Same Address'
                ]
            },
            'example_questions': [
                'Show me high risk claims',
                'Who are the most frequent claimants?',
                'Find claims with shared SSNs',
                'What fraud patterns exist?',
                'Which agents handle the most claims?',
                'Show me asset recycling cases',
                'Find agent-vendor collusion patterns',
                'What claims are from the same address?'
            ]
        }
        
    except Exception as e:
        log.error("graph_chat.schema_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get schema: {str(e)}")
