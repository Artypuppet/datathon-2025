"""
Unit tests for TextProcessor.
"""

import pytest
from pathlib import Path
from src.embeddings.text_processor import TextProcessor


@pytest.fixture
def processor():
    """Create TextProcessor instance."""
    return TextProcessor(use_spacy=False, normalize_text=False)


class TestTextProcessor:
    """Test suite for TextProcessor."""
    
    def test_clean_html(self, processor):
        """Test HTML cleanup."""
        html = "<html><body><p>Hello <b>world</b>!</p></body></html>"
        result = processor.clean_html(html)
        assert "world" in result
        assert "<b>" not in result
        assert "<body>" not in result
    
    def test_normalize(self, processor):
        """Test text normalization."""
        text = "  This   is    messy   TEXT  !"
        result = processor.normalize(text)
        assert result == "This is messy TEXT !"
    
    def test_normalize_with_lowercase(self):
        """Test text normalization with lowercase."""
        processor = TextProcessor(normalize_text=True)
        text = "  This   is    messy   TEXT  !"
        result = processor.normalize(text)
        assert result == "this is messy text !"
    
    def test_chunk_text_simple(self, processor):
        """Test simple text chunking."""
        text = "First. Second. Third. " * 100
        chunks = processor.chunk_text(text, metadata={"test": True})
        
        assert len(chunks) > 0
        assert "test" in chunks[0]
        assert "chunk_index" in chunks[0]
        assert "total_chunks" in chunks[0]
    
    def test_process_filing_document(self, processor):
        """Test processing filing document."""
        data = {
            "document_type": "html_filing",
            "source_file": "test.html",
            "ticker": "AAPL",
            "filing_type": "10-K",
            "sections": [
                {
                    "title": "Risk Factors",
                    "text": "We depend on limited suppliers. This is a risk."
                },
                {
                    "title": "MD&A",
                    "text": "Revenue increased due to strong demand."
                }
            ]
        }
        
        chunks = processor.process_document(data)
        
        assert len(chunks) > 0
        assert chunks[0]["document_type"] == "html_filing"
        assert chunks[0]["ticker"] == "AAPL"
        assert "Risk Factors" in [c.get("section_title") for c in chunks]
    
    def test_process_legislation_document(self, processor):
        """Test processing legislation document."""
        data = {
            "document_type": "html_legislation",
            "source_file": "directive.html",
            "title": "EU AI Act",
            "jurisdiction": "EU",
            "language": "en",
            "sections": [
                {
                    "title": "Article 1",
                    "text": "This Regulation lays down harmonised rules."
                }
            ]
        }
        
        chunks = processor.process_document(data)
        
        assert len(chunks) > 0
        assert chunks[0]["document_type"] == "html_legislation"
        assert chunks[0]["jurisdiction"] == "EU"
        assert "Article 1" in [c.get("section_title") for c in chunks]
    
    def test_process_csv_document(self, processor):
        """Test processing CSV document."""
        data = {
            "document_type": "csv_financial",
            "source_file": "composition.csv",
            "snapshot_date": "2025-08-15",
            "data_type": "composition",
            "companies": [
                {
                    "ticker": "AAPL",
                    "company": "Apple Inc.",
                    "metrics": {
                        "weight": 0.0597,
                        "price": 233.28
                    }
                },
                {
                    "ticker": "MSFT",
                    "company": "Microsoft Corp.",
                    "metrics": {
                        "weight": 0.0667,
                        "price": 380.50
                    }
                }
            ]
        }
        
        chunks = processor.process_document(data)
        
        assert len(chunks) == 2
        assert chunks[0]["ticker"] == "AAPL"
        assert chunks[1]["ticker"] == "MSFT"
        assert all("Apple Inc." in c["text"] or "Microsoft Corp." in c["text"] for c in chunks)

