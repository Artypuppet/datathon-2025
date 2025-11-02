"""
Embedding generation using sentence-transformers.
"""

import logging
from typing import List, Dict, Any, Optional
import numpy as np

try:
    from sentence_transformers import SentenceTransformer
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False
    logging.warning("[WARN] sentence-transformers not available")

logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    """
    Generate embeddings from text using sentence-transformers.
    
    Supports GPU acceleration and batch processing for efficiency.
    """
    
    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        device: Optional[str] = None,
        batch_size: int = 32
    ):
        """
        Initialize embedding generator.
        
        Args:
            model_name: HuggingFace model name (default: all-MiniLM-L6-v2)
            device: Device to use ('cuda', 'cpu', or None for auto-detect)
            batch_size: Batch size for embedding generation
        """
        if not HAS_SENTENCE_TRANSFORMERS:
            raise ImportError("sentence-transformers is required for embedding generation")
        
        self.model_name = model_name
        self.batch_size = batch_size
        
        # Auto-detect device if not specified
        if device is None:
            try:
                import torch
                self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
            except ImportError:
                self.device = 'cpu'
        else:
            self.device = device
        
        logger.info(f"[INFO] Loading model: {model_name}")
        logger.info(f"[INFO] Using device: {self.device}")
        
        # Load model
        try:
            self.model = SentenceTransformer(model_name, device=self.device)
            logger.info(f"[OK] Model loaded successfully")
        except Exception as e:
            logger.error(f"[ERROR] Failed to load model: {e}")
            raise
        
        # Get embedding dimension
        self.embedding_dim = self.model.get_sentence_embedding_dimension()
        logger.info(f"[INFO] Embedding dimension: {self.embedding_dim}")
    
    def generate_embeddings(
        self,
        texts: List[str],
        batch_size: Optional[int] = None
    ) -> np.ndarray:
        """
        Generate embeddings for a list of texts.
        
        Args:
            texts: List of text strings to embed
            batch_size: Batch size (uses instance default if None)
            
        Returns:
            NumPy array of embeddings (n_samples x embedding_dim)
        """
        if not texts:
            logger.warning("[WARN] Empty text list, returning empty array")
            return np.array([])
        
        batch_size = batch_size or self.batch_size
        
        logger.info(f"[INFO] Generating embeddings for {len(texts)} texts")
        
        try:
            embeddings = self.model.encode(
                texts,
                batch_size=batch_size,
                show_progress_bar=False,  # Disable for cleaner logs
                convert_to_numpy=True
            )
            
            logger.info(f"[OK] Generated {len(embeddings)} embeddings")
            return embeddings
            
        except Exception as e:
            logger.error(f"[ERROR] Embedding generation failed: {e}")
            raise
    
    def embed_chunks(
        self,
        chunks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Generate embeddings for processed chunks.
        
        Args:
            chunks: List of chunk dictionaries with 'text' field
            
        Returns:
            List of chunks with added 'embedding' field
        """
        # Extract texts
        texts = [chunk["text"] for chunk in chunks]
        
        # Generate embeddings
        embeddings = self.generate_embeddings(texts)
        
        # Attach embeddings to chunks
        for i, chunk in enumerate(chunks):
            chunk["embedding"] = embeddings[i].tolist()
        
        logger.info(f"[OK] Embedded {len(chunks)} chunks")
        
        return chunks
    
    def embed_document(
        self,
        processed_chunks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Generate embeddings for a complete document (all chunks).
        
        Args:
            processed_chunks: Processed chunks from TextProcessor
            
        Returns:
            Dictionary with embeddings and metadata
        """
        logger.info(f"[INFO] Embedding document with {len(processed_chunks)} chunks")
        
        # Generate embeddings
        chunks_with_embeddings = self.embed_chunks(processed_chunks)
        
        # Build document result
        result = {
            "chunks": chunks_with_embeddings,
            "total_chunks": len(chunks_with_embeddings),
            "embedding_dim": self.embedding_dim,
            "model_name": self.model_name
        }
        
        # Extract document-level metadata from first chunk
        if chunks_with_embeddings:
            first_chunk = chunks_with_embeddings[0]
            result["metadata"] = {
                "document_type": first_chunk.get("document_type"),
                "source_file": first_chunk.get("source_file")
            }
            
            # Add document-specific metadata
            if "ticker" in first_chunk:
                result["metadata"]["ticker"] = first_chunk["ticker"]
            if "jurisdiction" in first_chunk:
                result["metadata"]["jurisdiction"] = first_chunk["jurisdiction"]
        
        return result

