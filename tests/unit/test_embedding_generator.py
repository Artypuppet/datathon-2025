"""
Unit tests for EmbeddingGenerator.
"""

import pytest
import numpy as np


@pytest.fixture
def embedding_generator():
    """Create EmbeddingGenerator instance."""
    try:
        from src.embeddings.embedding_generator import EmbeddingGenerator
        return EmbeddingGenerator(model_name="all-MiniLM-L6-v2", device="cpu")
    except ImportError:
        pytest.skip("sentence-transformers not available")


class TestEmbeddingGenerator:
    """Test suite for EmbeddingGenerator."""
    
    def test_generate_embeddings(self, embedding_generator):
        """Test embedding generation."""
        texts = [
            "The quick brown fox jumps over the lazy dog",
            "Embeddings are numerical representations",
            "Machine learning models use embeddings"
        ]
        
        embeddings = embedding_generator.generate_embeddings(texts)
        
        assert embeddings.shape == (3, 384)  # all-MiniLM-L6-v2 has 384 dimensions
        assert isinstance(embeddings, np.ndarray)
    
    def test_generate_empty_list(self, embedding_generator):
        """Test embedding generation with empty list."""
        embeddings = embedding_generator.generate_embeddings([])
        assert embeddings.shape == (0,)
    
    def test_embed_chunks(self, embedding_generator):
        """Test chunk embedding."""
        chunks = [
            {"text": "First chunk", "chunk_index": 0},
            {"text": "Second chunk", "chunk_index": 1}
        ]
        
        embedded_chunks = embedding_generator.embed_chunks(chunks)
        
        assert len(embedded_chunks) == 2
        assert "embedding" in embedded_chunks[0]
        assert len(embedded_chunks[0]["embedding"]) == 384
    
    def test_embed_document(self, embedding_generator):
        """Test document embedding."""
        processed_chunks = [
            {
                "text": "Risk factors include supply chain disruptions",
                "chunk_index": 0,
                "total_chunks": 2,
                "document_type": "html_filing",
                "ticker": "AAPL"
            },
            {
                "text": "We depend on limited number of suppliers",
                "chunk_index": 1,
                "total_chunks": 2,
                "document_type": "html_filing",
                "ticker": "AAPL"
            }
        ]
        
        result = embedding_generator.embed_document(processed_chunks)
        
        assert result["total_chunks"] == 2
        assert result["embedding_dim"] == 384
        assert result["model_name"] == "all-MiniLM-L6-v2"
        assert "chunks" in result
        assert len(result["chunks"]) == 2
        assert result["metadata"]["document_type"] == "html_filing"
        assert result["metadata"]["ticker"] == "AAPL"

