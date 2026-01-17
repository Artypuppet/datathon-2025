"""
Embedding generation using transformer models optimized for SEC filings.

Supports:
- llmware/industry-bert-sec-v0.1: BERT model fine-tuned on SEC filings (recommended)
- Other HuggingFace transformer models
"""

import logging
from typing import List, Dict, Any, Optional
import numpy as np

try:
    from transformers import AutoModel, AutoTokenizer
    import torch
    HAS_TRANSFORMERS = True
except ImportError:
    HAS_TRANSFORMERS = False
    logging.warning("[WARN] transformers not available")

logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    """
    Generate embeddings from text using transformer models.
    
    Default: llmware/industry-bert-sec-v0.1 (BERT fine-tuned on SEC filings)
    
    Supports GPU acceleration and batch processing for efficiency.
    """
    
    def __init__(
        self,
        model_name: str = "llmware/industry-bert-sec-v0.1",
        device: Optional[str] = None,
        batch_size: int = 32,  # BERT can handle larger batches
        max_length: int = 512  # BERT's standard context window
    ):
        """
        Initialize embedding generator.
        
        Args:
            model_name: HuggingFace model name (default: llmware/industry-bert-sec-v0.1)
            device: Device to use ('cuda', 'cpu', or None for auto-detect)
            batch_size: Batch size for embedding generation (default: 32 for BERT)
            max_length: Maximum sequence length (default: 512 for BERT)
        """
        if not HAS_TRANSFORMERS:
            raise ImportError("transformers is required for embedding generation")
        
        self.model_name = model_name
        self.batch_size = batch_size
        self.max_length = max_length
        
        # Auto-detect device if not specified
        if device is None:
            try:
                self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
            except ImportError:
                self.device = 'cpu'
        else:
            self.device = device
        
        logger.info(f"[INFO] Loading model: {model_name}")
        logger.info(f"[INFO] Using device: {self.device}")
        logger.info(f"[INFO] Max sequence length: {max_length}")
        
        # Load tokenizer and model
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModel.from_pretrained(model_name)
            self.model.to(self.device)
            self.model.eval()  # Set to evaluation mode
            logger.info(f"[OK] Model loaded successfully")
        except Exception as e:
            logger.error(f"[ERROR] Failed to load model: {e}")
            raise
        
        # Get embedding dimension from model config
        self.embedding_dim = self.model.config.hidden_size
        logger.info(f"[INFO] Embedding dimension: {self.embedding_dim}")
    
    def _mean_pooling(self, model_output, attention_mask):
        """
        Mean pooling over token embeddings, weighted by attention mask.
        
        Args:
            model_output: Model outputs containing last_hidden_state
            attention_mask: Attention mask to exclude padding tokens
            
        Returns:
            Pooled embeddings tensor
        """
        token_embeddings = model_output.last_hidden_state
        input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
        # Sum embeddings, weighted by attention mask, and divide by sum of mask
        sum_embeddings = torch.sum(token_embeddings * input_mask_expanded, 1)
        sum_mask = torch.clamp(input_mask_expanded.sum(1), min=1e-9)
        return sum_embeddings / sum_mask
    
    def generate_embeddings(
        self,
        texts: List[str],
        batch_size: Optional[int] = None
    ) -> np.ndarray:
        """
        Generate embeddings for a list of texts using Longformer.
        
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
            all_embeddings = []
            
            # Process in batches
            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i:i + batch_size]
                
                # Tokenize with truncation up to max_length
                encoded_input = self.tokenizer(
                    batch_texts,
                    padding=True,
                    truncation=True,
                    max_length=self.max_length,
                    return_tensors='pt'
                )
                
                # Move to device
                encoded_input = {k: v.to(self.device) for k, v in encoded_input.items()}
                
                # Generate embeddings
                with torch.no_grad():
                    model_output = self.model(**encoded_input)
                
                # Mean pooling to get sentence embeddings
                sentence_embeddings = self._mean_pooling(
                    model_output,
                    encoded_input['attention_mask']
                )
                
                # Normalize embeddings (L2 norm)
                sentence_embeddings = torch.nn.functional.normalize(
                    sentence_embeddings,
                    p=2,
                    dim=1
                )
                
                # Convert to numpy and add to list
                all_embeddings.append(sentence_embeddings.cpu().numpy())
            
            # Concatenate all batches
            embeddings = np.vstack(all_embeddings)
            
            logger.info(f"[OK] Generated {len(embeddings)} embeddings (shape: {embeddings.shape})")
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

