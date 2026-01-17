"""
Stage 4: Store embeddings in vector database.

Stores:
- Company filing embeddings (with sentence references for explainability)
- Legislation embeddings

Uses vector database operations for efficient storage and querying.
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional

from ..vectordb import get_vectordb_client, VectorDBClient
from ..utils import get_s3_client, S3Client

logger = logging.getLogger(__name__)


class VectorDBStage:
    """Stage for storing embeddings in vector database."""
    
    def __init__(
        self,
        s3_client: Optional[S3Client] = None,
        vectordb_client: Optional[VectorDBClient] = None,
        backend: str = "auto"
    ):
        """
        Initialize VectorDB stage.
        
        Args:
            s3_client: S3 client instance (optional, auto-created if None)
            vectordb_client: VectorDB client instance (optional, auto-created if None)
            backend: Vector DB backend ("chroma", "opensearch", or "auto")
        """
        self.s3_client = s3_client or get_s3_client()
        self.vectordb = vectordb_client or get_vectordb_client(backend=backend)
        
        logger.info("[INFO] VectorDBStage initialized")
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute VectorDB stage - store embeddings.
        
        Args:
            context: Pipeline context with embedding_key
            
        Returns:
            Updated context with vectordb status
        """
        embedding_key = context.get('embedding_key')
        aggregated_key = context.get('aggregated_key')
        
        if not embedding_key:
            logger.warning("[WARN] No embedding_key in context, skipping VectorDB storage")
            context['vectordb_status'] = 'skipped'
            return context
        
        logger.info(f"[INFO] VectorDBStage: Storing embeddings from {embedding_key}")
        
        try:
            # Download embeddings JSON
            import tempfile
            import json
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp_file:
                tmp_path = Path(tmp_file.name)
            
            success = self.s3_client.download_file(embedding_key, tmp_path)
            if not success:
                raise Exception(f"Failed to download {embedding_key} from S3")
            
            # Load embeddings
            with open(tmp_path, 'r', encoding='utf-8') as f:
                embeddings_data = json.load(f)
            
            # Load aggregated data for metadata (if available)
            aggregated_data = None
            if aggregated_key:
                try:
                    aggregated_data = self.s3_client.read_json(aggregated_key)
                except Exception as e:
                    logger.warning(f"[WARN] Could not load aggregated data: {e}")
            
            # Extract ticker and company name
            chunks = embeddings_data.get('chunks', [])
            if not chunks:
                logger.warning("[WARN] No chunks in embeddings data")
                context['vectordb_status'] = 'skipped'
                return context
            
            # Get ticker from first chunk, aggregated data, or context
            ticker = (
                chunks[0].get('ticker') or 
                (aggregated_data.get('ticker') if aggregated_data else None) or
                context.get('ticker')
            )
            company_name = (
                chunks[0].get('company_name') or 
                (aggregated_data.get('company_name') if aggregated_data else None) or
                context.get('company_name')
            )
            
            if not ticker:
                logger.warning("[WARN] No ticker found, skipping VectorDB storage")
                context['vectordb_status'] = 'skipped'
                return context
            
            logger.info(f"[INFO] Storing embeddings for {ticker} ({company_name})")
            
            # Delete existing embeddings for this company (if any)
            # This ensures we don't have duplicates if re-running
            deleted_count = self.vectordb.delete_company_embeddings(ticker)
            if deleted_count > 0:
                logger.info(f"[INFO] Deleted {deleted_count} existing embeddings for {ticker}")
            
            # Store company embeddings
            stored_count = self.vectordb.store_company_embeddings(
                ticker=ticker,
                company_name=company_name or ticker,
                chunks=chunks
            )
            
            logger.info(f"[OK] Stored {stored_count} embeddings for {ticker}")
            
            # Update context
            context.update({
                'vectordb_status': 'success',
                'vectordb_stored_count': stored_count,
                'vectordb_deleted_count': deleted_count,
                'ticker': ticker
            })
            
            # Cleanup
            if tmp_path.exists():
                tmp_path.unlink()
            
            return context
            
        except Exception as e:
            logger.error(f"[ERROR] VectorDBStage failed: {e}", exc_info=True)
            context.update({
                'vectordb_status': 'failed',
                'vectordb_error': str(e)
            })
            # Don't raise - allow pipeline to continue
            return context
    
    def store_legislation(
        self,
        legislation_id: str,
        legislation_text: str,
        legislation_embedding: Any,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Store legislation embedding in vector DB.
        
        Args:
            legislation_id: Unique identifier for legislation
            legislation_text: Original legislation text
            legislation_embedding: Embedding vector
            metadata: Additional metadata
            
        Returns:
            Document ID
        """
        logger.info(f"[INFO] Storing legislation: {legislation_id}")
        
        doc_id = self.vectordb.store_legislation_embedding(
            legislation_id=legislation_id,
            legislation_text=legislation_text,
            embedding=legislation_embedding,
            metadata=metadata
        )
        
        logger.info(f"[OK] Stored legislation: {legislation_id}")
        return doc_id
    
    def can_execute(self, context: Dict[str, Any]) -> bool:
        """
        Check if this stage can execute.
        
        Args:
            context: Pipeline context
            
        Returns:
            True if stage can execute
        """
        return 'embedding_key' in context or 'aggregated_key' in context

