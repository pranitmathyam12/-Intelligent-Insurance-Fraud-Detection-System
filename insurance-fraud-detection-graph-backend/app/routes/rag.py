"""
RAG (Retrieval-Augmented Generation) endpoints for document Q&A

Provides endpoints for:
1. Querying uploaded documents using Gemini File Search
2. Managing chat sessions
3. Getting File Search store information
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import structlog
import uuid

from app.services.file_search_service import get_file_search_service

log = structlog.get_logger()
router = APIRouter(prefix="/v1/rag", tags=["RAG Document Q&A"])

# In-memory session storage (in production, use Redis or database)
chat_sessions: Dict[str, List[Dict[str, str]]] = {}


class ChatMessage(BaseModel):
    """Chat message model"""
    role: str = Field(..., description="Role: 'user' or 'model'")
    content: str = Field(..., description="Message content")


class QueryRequest(BaseModel):
    """Request model for document query"""
    user_message: str = Field(..., description="User's question about the documents")
    session_id: Optional[str] = Field(None, description="Session ID for conversation tracking")
    include_history: bool = Field(True, description="Whether to include chat history in context")


class QueryResponse(BaseModel):
    """Response model for document query"""
    success: bool
    session_id: str
    answer: str
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    usage: Optional[Dict[str, int]] = None
    query_time_ms: float
    model: str
    error: Optional[str] = None


class SessionHistoryResponse(BaseModel):
    """Response model for session history"""
    success: bool
    session_id: str
    message_count: int
    messages: List[ChatMessage]


@router.post("/query", response_model=QueryResponse)
async def query_documents(request: QueryRequest):
    """
    Query uploaded documents using RAG with Gemini File Search
    
    This endpoint allows users to ask questions about uploaded insurance documents.
    The system uses semantic search to find relevant information and generates
    contextual answers with citations.
    
    Args:
        request: QueryRequest with user message and optional session ID
        
    Returns:
        QueryResponse with answer, citations, and metadata
    """
    try:
        # Generate session ID if not provided
        session_id = request.session_id or str(uuid.uuid4())
        
        # Get chat history for this session if requested
        chat_history = None
        if request.include_history and session_id in chat_sessions:
            chat_history = chat_sessions[session_id]
        
        # Get File Search service
        file_search_service = get_file_search_service()
        
        # Query documents
        result = file_search_service.query_documents(
            user_message=request.user_message,
            session_id=session_id,
            chat_history=chat_history
        )
        
        # Store the conversation in session
        if session_id not in chat_sessions:
            chat_sessions[session_id] = []
        
        # Add user message
        chat_sessions[session_id].append({
            'role': 'user',
            'content': request.user_message
        })
        
        # Add model response
        if result.get('success'):
            chat_sessions[session_id].append({
                'role': 'model',
                'content': result.get('answer', '')
            })
        
        # Limit session history to last 20 messages (10 exchanges)
        if len(chat_sessions[session_id]) > 20:
            chat_sessions[session_id] = chat_sessions[session_id][-20:]
        
        log.info("rag.query_complete",
                session_id=session_id,
                success=result.get('success'),
                citations_count=len(result.get('citations', [])))
        
        # Filter out None values from usage to avoid Pydantic validation errors
        usage = result.get('usage', {})
        if usage:
            usage = {k: v for k, v in usage.items() if v is not None}
        
        return QueryResponse(
            success=result.get('success', False),
            session_id=session_id,
            answer=result.get('answer', ''),
            citations=result.get('citations', []),
            usage=usage if usage else None,
            query_time_ms=result.get('query_time_ms', 0),
            model=result.get('model', ''),
            error=result.get('error')
        )
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        log.error("rag.query_error", error=str(e), traceback=error_trace)
        print(f"RAG Query Error: {str(e)}")
        print(f"Traceback:\n{error_trace}")
        raise HTTPException(status_code=500, detail=f"Failed to query documents: {str(e)}")


@router.get("/session/{session_id}/history", response_model=SessionHistoryResponse)
async def get_session_history(session_id: str):
    """
    Get chat history for a specific session
    
    Args:
        session_id: Session ID to retrieve history for
        
    Returns:
        SessionHistoryResponse with message history
    """
    try:
        if session_id not in chat_sessions:
            return SessionHistoryResponse(
                success=True,
                session_id=session_id,
                message_count=0,
                messages=[]
            )
        
        messages = [
            ChatMessage(role=msg['role'], content=msg['content'])
            for msg in chat_sessions[session_id]
        ]
        
        return SessionHistoryResponse(
            success=True,
            session_id=session_id,
            message_count=len(messages),
            messages=messages
        )
        
    except Exception as e:
        log.error("rag.get_history_error", session_id=session_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get session history: {str(e)}")


@router.delete("/session/{session_id}")
async def clear_session(session_id: str):
    """
    Clear chat history for a specific session
    
    Args:
        session_id: Session ID to clear
        
    Returns:
        Success message
    """
    try:
        if session_id in chat_sessions:
            del chat_sessions[session_id]
            log.info("rag.session_cleared", session_id=session_id)
        
        return {
            'success': True,
            'session_id': session_id,
            'message': 'Session cleared successfully'
        }
        
    except Exception as e:
        log.error("rag.clear_session_error", session_id=session_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to clear session: {str(e)}")


@router.get("/store/info")
async def get_store_info():
    """
    Get information about the File Search store
    
    Returns:
        Store metadata and statistics
    """
    try:
        file_search_service = get_file_search_service()
        result = file_search_service.get_store_info()
        
        if not result.get('success'):
            raise HTTPException(status_code=500, detail=result.get('error', 'Unknown error'))
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        log.error("rag.get_store_info_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get store info: {str(e)}")


@router.get("/store/documents")
async def list_store_documents():
    """
    List documents in the File Search store
    
    Returns:
        List of documents
    """
    try:
        file_search_service = get_file_search_service()
        result = file_search_service.list_documents()
        
        return result
        
    except Exception as e:
        log.error("rag.list_documents_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to list documents: {str(e)}")


@router.delete("/store/documents")
async def delete_all_documents():
    """
    Delete all documents from the File Search store
    
    WARNING: This will permanently delete all documents and recreate the store
    
    Returns:
        Deletion status
    """
    try:
        file_search_service = get_file_search_service()
        result = file_search_service.delete_all_documents()
        
        if not result.get('success'):
            raise HTTPException(status_code=500, detail=result.get('error', 'Unknown error'))
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        log.error("rag.delete_all_documents_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to delete documents: {str(e)}")


@router.get("/health")
async def rag_health_check():
    """
    Check RAG system health
    
    Returns:
        Health status of File Search service
    """
    try:
        file_search_service = get_file_search_service()
        store_info = file_search_service.get_store_info()
        
        if store_info.get('success'):
            return {
                'status': 'healthy',
                'message': 'RAG system operational',
                'store_name': store_info.get('store_name'),
                'active_sessions': len(chat_sessions)
            }
        else:
            return {
                'status': 'degraded',
                'message': 'File Search store not accessible',
                'error': store_info.get('error')
            }
            
    except Exception as e:
        log.error("rag.health_check_error", error=str(e))
        return {
            'status': 'unhealthy',
            'message': f'RAG system error: {str(e)}'
        }
