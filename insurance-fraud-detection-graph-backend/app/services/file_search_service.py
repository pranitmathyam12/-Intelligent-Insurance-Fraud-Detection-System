"""
Gemini File Search Service for RAG on uploaded insurance documents

This service manages:
1. File Search store creation and management
2. Document upload and indexing
3. Query processing with session management
"""

import os
import time
import structlog
from typing import Dict, Any, Optional, List
from google import genai
from google.genai import types

log = structlog.get_logger()


class FileSearchService:
    """
    Service for managing Gemini File Search RAG system
    """
    
    def __init__(self):
        """Initialize the File Search service with Gemini API"""
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in environment variables")
        
        self.client = genai.Client(api_key=api_key)
        # File Search requires gemini-2.5-flash or compatible model
        # gemini-2.0-flash-exp does NOT support File Search
        self.model = os.getenv('GENAI_MODEL', 'gemini-2.5-flash')
        self.file_search_store_name = None
        self._initialize_store()
    
    def _initialize_store(self):
        """
        Initialize or get existing File Search store
        Uses a persistent store name for the insurance fraud detection system
        """
        store_display_name = 'insurance-fraud-documents'
        
        try:
            # Try to list existing stores and find ours
            log.info("file_search.listing_stores")
            existing_stores = list(self.client.file_search_stores.list())
            
            for store in existing_stores:
                if store.display_name == store_display_name:
                    self.file_search_store_name = store.name
                    log.info("file_search.store_found", 
                            store_name=self.file_search_store_name,
                            display_name=store_display_name)
                    return
            
            # Create new store if not found
            log.info("file_search.creating_store", display_name=store_display_name)
            file_search_store = self.client.file_search_stores.create(
                config={'display_name': store_display_name}
            )
            self.file_search_store_name = file_search_store.name
            log.info("file_search.store_created", 
                    store_name=self.file_search_store_name,
                    display_name=store_display_name)
            
        except Exception as e:
            log.error("file_search.store_init_failed", error=str(e))
            raise
    
    def upload_document(self, 
                       pdf_data: bytes, 
                       claim_id: str,
                       doc_type: str) -> Dict[str, Any]:
        """
        Upload a PDF document to the File Search store
        
        Args:
            pdf_data: Raw PDF bytes
            claim_id: Transaction/Claim ID for tracking
            doc_type: Type of insurance document
            
        Returns:
            Dict with upload status and metadata
        """
        try:
            # Create a temporary file for upload
            import tempfile
            
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
                tmp_file.write(pdf_data)
                tmp_file_path = tmp_file.name
            
            try:
                # Upload to File Search store with metadata
                display_name = f"{claim_id}_{doc_type}"
                
                log.info("file_search.uploading_document", 
                        claim_id=claim_id,
                        doc_type=doc_type,
                        display_name=display_name)
                
                upload_start = time.time()
                
                # Upload and wait for completion
                operation = self.client.file_search_stores.upload_to_file_search_store(
                    file=tmp_file_path,
                    file_search_store_name=self.file_search_store_name,
                    config={
                        'display_name': display_name,
                    }
                )
                
                # Wait for the upload operation to complete
                max_wait_time = 60  # 60 seconds max
                wait_interval = 2   # Check every 2 seconds
                elapsed = 0
                
                while not operation.done and elapsed < max_wait_time:
                    time.sleep(wait_interval)
                    elapsed += wait_interval
                    operation = self.client.operations.get(operation)
                    log.info("file_search.upload_progress", 
                            claim_id=claim_id,
                            elapsed_seconds=elapsed)
                
                upload_time_ms = (time.time() - upload_start) * 1000
                
                if not operation.done:
                    raise TimeoutError(f"Upload timed out after {max_wait_time} seconds")
                
                log.info("file_search.upload_complete",
                        claim_id=claim_id,
                        upload_time_ms=upload_time_ms)
                
                return {
                    'success': True,
                    'claim_id': claim_id,
                    'doc_type': doc_type,
                    'display_name': display_name,
                    'store_name': self.file_search_store_name,
                    'upload_time_ms': upload_time_ms
                }
                
            finally:
                # Clean up temporary file
                os.unlink(tmp_file_path)
                
        except Exception as e:
            log.error("file_search.upload_failed", 
                     claim_id=claim_id,
                     error=str(e))
            return {
                'success': False,
                'claim_id': claim_id,
                'error': str(e)
            }
    
    def query_documents(self, 
                       user_message: str,
                       session_id: Optional[str] = None,
                       chat_history: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
        """
        Query the File Search store with a user message
        
        Args:
            user_message: User's question about the documents
            session_id: Optional session ID for tracking conversations
            chat_history: Optional list of previous messages [{"role": "user/model", "content": "..."}]
            
        Returns:
            Dict with answer, citations, and metadata
        """
        try:
            log.info("file_search.query_start",
                    session_id=session_id,
                    message_length=len(user_message))
            
            query_start = time.time()
            
            if not self.file_search_store_name:
                raise ValueError("File Search store not initialized. Please check logs for initialization errors.")
            
            # Build the conversation history
            contents = []
            
            # Add chat history if provided
            if chat_history:
                for msg in chat_history:
                    role = msg.get('role', 'user')
                    content = msg.get('content', '')
                    if role == 'user':
                        contents.append(types.Content(role='user', parts=[types.Part(text=content)]))
                    elif role == 'model':
                        contents.append(types.Content(role='model', parts=[types.Part(text=content)]))
            
            # Add the current user message
            contents.append(types.Content(role='user', parts=[types.Part(text=user_message)]))
            
            # Debug logging
            log.info("file_search.api_call_config",
                    store_name=self.file_search_store_name,
                    model=self.model,
                    message_preview=user_message[:50])
            
            # Generate content with File Search tool
            # Match the exact structure from official documentation
            response = self.client.models.generate_content(
                model=self.model,
                contents=contents,
                config=types.GenerateContentConfig(
                    tools=[
                        types.Tool(
                            file_search=types.FileSearch(
                                file_search_store_names=[self.file_search_store_name]
                            )
                        )
                    ],
                    temperature=0.2
                )
            )
            
            query_time_ms = (time.time() - query_start) * 1000
            
            # Extract response text
            answer = response.text if response.text else "I couldn't find relevant information to answer your question."
            
            # Extract citations and grounding metadata
            citations = []
            grounding_metadata = None
            
            if response.candidates and len(response.candidates) > 0:
                candidate = response.candidates[0]
                if hasattr(candidate, 'grounding_metadata') and candidate.grounding_metadata:
                    grounding_metadata = candidate.grounding_metadata
                    
                    # Extract citation information
                    if hasattr(grounding_metadata, 'grounding_chunks'):
                        for chunk in grounding_metadata.grounding_chunks:
                            citation_info = {
                                'text': getattr(chunk, 'text', ''),
                            }
                            
                            # Extract file information if available
                            if hasattr(chunk, 'retrieved_context'):
                                retrieved = chunk.retrieved_context
                                if hasattr(retrieved, 'title'):
                                    citation_info['document'] = retrieved.title
                                if hasattr(retrieved, 'uri'):
                                    citation_info['uri'] = retrieved.uri
                            
                            citations.append(citation_info)
            
            # Extract usage metadata
            usage_metadata = None
            if hasattr(response, 'usage_metadata'):
                usage_metadata = {
                    'prompt_token_count': getattr(response.usage_metadata, 'prompt_token_count', 0),
                    'candidates_token_count': getattr(response.usage_metadata, 'candidates_token_count', 0),
                    'total_token_count': getattr(response.usage_metadata, 'total_token_count', 0),
                }
            
            log.info("file_search.query_complete",
                    session_id=session_id,
                    query_time_ms=query_time_ms,
                    citations_found=len(citations),
                    answer_length=len(answer))
            
            return {
                'success': True,
                'session_id': session_id,
                'answer': answer,
                'citations': citations,
                'usage': usage_metadata,
                'query_time_ms': query_time_ms,
                'model': self.model
            }
            
        except Exception as e:
            log.error("file_search.query_failed",
                     session_id=session_id,
                     error=str(e))
            return {
                'success': False,
                'session_id': session_id,
                'error': str(e),
                'answer': f"An error occurred while processing your query: {str(e)}"
            }
    
    def get_store_info(self) -> Dict[str, Any]:
        """
        Get information about the current File Search store
        
        Returns:
            Dict with store metadata
        """
        try:
            if not self.file_search_store_name:
                return {
                    'success': False,
                    'error': 'File Search store not initialized'
                }
            
            store = self.client.file_search_stores.get(name=self.file_search_store_name)
            
            return {
                'success': True,
                'store_name': store.name,
                'display_name': store.display_name,
                'create_time': str(store.create_time) if hasattr(store, 'create_time') else None,
                'update_time': str(store.update_time) if hasattr(store, 'update_time') else None,
            }
            
        except Exception as e:
            log.error("file_search.get_store_info_failed", error=str(e))
            return {
                'success': False,
                'error': str(e)
            }
    
    def list_documents(self) -> Dict[str, Any]:
        """
        List all documents in the File Search store
        
        Returns:
            Dict with list of documents
        """
        try:
            log.info("file_search.list_documents", 
                    store_name=self.file_search_store_name)
            
            # List files in the store
            files = list(self.client.files.list())
            
            # Filter files that belong to this store
            store_files = []
            for file in files:
                if hasattr(file, 'file_search_store_name') and file.file_search_store_name == self.file_search_store_name:
                    store_files.append({
                        'name': file.name,
                        'display_name': file.display_name if hasattr(file, 'display_name') else None,
                        'size_bytes': file.size_bytes if hasattr(file, 'size_bytes') else None,
                        'create_time': str(file.create_time) if hasattr(file, 'create_time') else None
                    })
            
            return {
                'success': True,
                'store_name': self.file_search_store_name,
                'files': store_files,
                'count': len(store_files)
            }
            
        except Exception as e:
            log.error("file_search.list_documents_failed", error=str(e))
            return {
                'success': False,
                'error': str(e)
            }
    
    def delete_all_documents(self) -> Dict[str, Any]:
        """
        Delete all documents from the File Search store
        
        Returns:
            Dict with deletion status
        """
        try:
            log.info("file_search.deleting_all_documents", 
                    store_name=self.file_search_store_name)
            
            # Delete the entire store and recreate it
            if self.file_search_store_name:
                try:
                    self.client.file_search_stores.delete(name=self.file_search_store_name)
                    log.info("file_search.store_deleted", store_name=self.file_search_store_name)
                except Exception as delete_error:
                    log.warning("file_search.store_delete_warning", error=str(delete_error))
            
            # Reinitialize the store (creates a new empty one)
            self._initialize_store()
            
            log.info("file_search.all_documents_deleted", new_store=self.file_search_store_name)
            
            return {
                'success': True,
                'message': 'All documents deleted and store recreated',
                'new_store_name': self.file_search_store_name
            }
            
        except Exception as e:
            log.error("file_search.delete_all_failed", error=str(e))
            return {
                'success': False,
                'error': str(e)
            }
    
    def upload_fraud_analysis(self,
                             claim_id: str,
                             fraud_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Upload fraud analysis results as a text file to the File Search store
        
        Args:
            claim_id: Transaction/Claim ID
            fraud_analysis: Dict containing fraud analysis results from graph and LLM
            
        Returns:
            Dict with upload status
        """
        try:
            import tempfile
            import json
            
            # Create a formatted text document with fraud analysis
            fraud_text = f"""Fraud Analysis Report for Claim {claim_id}
===========================================

CLAIM INFORMATION
-----------------
Transaction ID: {claim_id}

GRAPH-BASED FRAUD DETECTION
---------------------------
{json.dumps(fraud_analysis.get('graph_analysis', {}), indent=2)}

LLM FRAUD ANALYSIS
------------------
{json.dumps(fraud_analysis.get('llm_analysis', {}), indent=2)}

FRAUD SCORE: {fraud_analysis.get('fraud_score', 'N/A')}
FRAUD VERDICT: {fraud_analysis.get('fraud_verdict', 'N/A')}

DETAILED REASONING
------------------
{fraud_analysis.get('reasoning', 'No reasoning provided')}

RISK FACTORS
------------
{json.dumps(fraud_analysis.get('risk_factors', []), indent=2)}

RECOMMENDATIONS
---------------
{json.dumps(fraud_analysis.get('recommendations', []), indent=2)}
"""
            
            # Create a temporary text file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as tmp_file:
                tmp_file.write(fraud_text)
                tmp_file_path = tmp_file.name
            
            try:
                display_name = f"{claim_id}_fraud_analysis"
                
                log.info("file_search.uploading_fraud_analysis",
                        claim_id=claim_id,
                        display_name=display_name)
                
                upload_start = time.time()
                
                # Upload fraud analysis to File Search store
                operation = self.client.file_search_stores.upload_to_file_search_store(
                    file=tmp_file_path,
                    file_search_store_name=self.file_search_store_name,
                    config={
                        'display_name': display_name,
                    }
                )
                
                # Wait for upload completion
                max_wait_time = 30
                wait_interval = 2
                elapsed = 0
                
                while not operation.done and elapsed < max_wait_time:
                    time.sleep(wait_interval)
                    elapsed += wait_interval
                    operation = self.client.operations.get(operation)
                
                upload_time_ms = (time.time() - upload_start) * 1000
                
                if not operation.done:
                    raise TimeoutError(f"Fraud analysis upload timed out after {max_wait_time} seconds")
                
                log.info("file_search.fraud_analysis_uploaded",
                        claim_id=claim_id,
                        upload_time_ms=upload_time_ms)
                
                return {
                    'success': True,
                    'claim_id': claim_id,
                    'display_name': display_name,
                    'upload_time_ms': upload_time_ms
                }
                
            finally:
                # Clean up temporary file
                os.unlink(tmp_file_path)
                
        except Exception as e:
            log.error("file_search.fraud_analysis_upload_failed",
                     claim_id=claim_id,
                     error=str(e))
            return {
                'success': False,
                'claim_id': claim_id,
                'error': str(e)
            }


# Singleton instance
_file_search_service: Optional[FileSearchService] = None


def get_file_search_service() -> FileSearchService:
    """
    Get or create the singleton FileSearchService instance
    
    Returns:
        FileSearchService instance
    """
    global _file_search_service
    
    if _file_search_service is None:
        _file_search_service = FileSearchService()
    
    return _file_search_service
