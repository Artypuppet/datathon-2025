"""
Unit tests for HTMLFilingParser.
"""

import pytest
from pathlib import Path
from src.parsers.html_filing_parser import HTMLFilingParser
from src.parsers.base import DocumentType


@pytest.fixture
def sample_10k_html(tmp_path):
    """Create a sample 10-K HTML file."""
    content = """
    <html>
    <head>
        <title>Apple Inc. 10-K Annual Report</title>
        <meta name="company" content="Apple Inc.">
    </head>
    <body>
        <div class="header">
            <span>CIK: 0000320193</span>
        </div>
        <div class="section">
            <h2>Item 1. Business</h2>
            <p>
            Apple Inc. is a global technology company that designs, manufactures, 
            and markets smartphones, personal computers, tablets, wearables, and 
            accessories. The Company sells and delivers digital content and 
            applications through the iTunes Store, App Store, Mac App Store, 
            TV App Store, Book Store, and Apple Music. The Company's products 
            include iPhone, Mac, iPad, Apple Watch, AirPods, and Apple TV.
            </p>
        </div>
        <div class="section">
            <h2>Item 1A. Risk Factors</h2>
            <p>
            The Company's business, reputation, results of operations, financial 
            condition, and stock price can be affected by a number of factors, 
            whether currently known or unknown, including those described below. 
            Changes in global and regional economic conditions could materially 
            adversely affect the Company. Global and regional economic conditions 
            could materially adversely affect demand for the Company's products 
            and services. Adverse changes in these conditions could also negatively 
            affect the Company's suppliers, contract manufacturers, logistics 
            providers, distributors, cellular network carriers and other channel 
            partners, and developers.
            </p>
        </div>
        <div class="section">
            <h2>Item 7. Management's Discussion and Analysis</h2>
            <p>
            The following discussion and analysis should be read in conjunction 
            with the consolidated financial statements and the related notes 
            that appear elsewhere in this report. Net sales increased 7 percent 
            year over year. Products net sales increased 6 percent year over year 
            due to growth from iPhone partially offset by decreases from iPad.
            </p>
        </div>
    </body>
    </html>
    """
    file_path = tmp_path / "2024-09-30-10k-AAPL.html"
    file_path.write_text(content, encoding='utf-8')
    return file_path


@pytest.fixture
def sample_10q_html(tmp_path):
    """Create a sample 10-Q HTML file."""
    content = """
    <html>
    <head><title>Microsoft Corp. 10-Q</title></head>
    <body>
        <div>
            <h1>Microsoft Corporation</h1>
            <p>CIK: 0000789019</p>
        </div>
        <section>
            <h2>Condensed Consolidated Statements of Income</h2>
            <p>
            Revenue for the quarter was $52.9 billion. Operating income was 
            $24.3 billion. Net income was $20.1 billion.
            </p>
        </section>
        <section>
            <h2>Management's Discussion and Analysis</h2>
            <p>
            Our Intelligent Cloud segment consists of our public, private, 
            and hybrid server products and cloud services that can power 
            modern business and developers. This segment primarily comprises 
            Azure, SQL Server, Windows Server, Visual Studio, System Center, 
            and related Client Access Licenses, GitHub, and Enterprise Services.
            </p>
        </section>
    </body>
    </html>
    """
    file_path = tmp_path / "2024-06-30-10q-MSFT.html"
    file_path.write_text(content, encoding='utf-8')
    return file_path


@pytest.fixture
def malformed_html(tmp_path):
    """Create malformed HTML to test error handling."""
    content = "<html><body><h1>Incomplete"
    file_path = tmp_path / "2024-01-01-10k-TEST.html"
    file_path.write_text(content, encoding='utf-8')
    return file_path


@pytest.fixture
def parser():
    """Create parser instance."""
    return HTMLFilingParser()


class TestHTMLFilingParser:
    """Test suite for HTML filing parser."""
    
    def test_can_parse_valid_10k(self, parser, sample_10k_html):
        """Test parser identifies valid 10-K files."""
        assert parser.can_parse(sample_10k_html)
    
    def test_can_parse_valid_10q(self, parser, sample_10q_html):
        """Test parser identifies valid 10-Q files."""
        assert parser.can_parse(sample_10q_html)
    
    def test_cannot_parse_non_html(self, parser, tmp_path):
        """Test parser rejects non-HTML files."""
        txt_file = tmp_path / "document.txt"
        txt_file.write_text("Not HTML")
        assert not parser.can_parse(txt_file)
    
    def test_cannot_parse_wrong_pattern(self, parser, tmp_path):
        """Test parser rejects HTML with wrong filename pattern."""
        wrong_file = tmp_path / "random-file.html"
        wrong_file.write_text("<html></html>")
        assert not parser.can_parse(wrong_file)
    
    def test_get_document_type(self, parser):
        """Test document type is correct."""
        assert parser.get_document_type() == DocumentType.HTML_FILING
    
    def test_parse_10k_success(self, parser, sample_10k_html):
        """Test successful 10-K parsing."""
        result = parser.parse(sample_10k_html)
        
        assert result.success
        assert result.document_type == DocumentType.HTML_FILING
        assert result.data is not None
        
        data = result.data
        assert data["document_type"] == "html_filing"
        assert data["ticker"] == "AAPL"
        assert data["filing_type"] == "10K"
        assert data["filing_date"] == "2024-09-30"
        assert data["fiscal_year"] == 2024
        assert data["cik"] == "0000320193"
        assert "Apple" in data["company"]
        
        # Check sections
        assert len(data["sections"]) > 0
        assert data["metadata"]["total_sections"] == len(data["sections"])
        assert data["metadata"]["total_word_count"] > 0
    
    def test_parse_10q_success(self, parser, sample_10q_html):
        """Test successful 10-Q parsing."""
        result = parser.parse(sample_10q_html)
        
        assert result.success
        data = result.data
        
        assert data["ticker"] == "MSFT"
        assert data["filing_type"] == "10Q"
        assert data["filing_date"] == "2024-06-30"
        assert data["cik"] == "0000789019"
    
    def test_extract_ticker_from_filename(self, parser):
        """Test ticker extraction from filename."""
        assert parser._extract_ticker_from_filename("2024-01-01-10k-AAPL.html") == "AAPL"
        assert parser._extract_ticker_from_filename("2024-01-01-10q-msft.html") == "MSFT"
        assert parser._extract_ticker_from_filename("2024-01-01-10k-GOOGL.html") == "GOOGL"
    
    def test_extract_date_from_filename(self, parser):
        """Test date extraction from filename."""
        assert parser._extract_date_from_filename("2024-09-30-10k-AAPL.html") == "2024-09-30"
        assert parser._extract_date_from_filename("2023-12-31-10q-MSFT.html") == "2023-12-31"
    
    def test_extract_filing_type_from_filename(self, parser):
        """Test filing type extraction."""
        assert parser._extract_filing_type_from_filename("2024-01-01-10k-TEST.html") == "10K"
        assert parser._extract_filing_type_from_filename("2024-01-01-10q-TEST.html") == "10Q"
    
    def test_clean_text(self, parser):
        """Test text cleaning."""
        dirty = "  This  is   \n\n   messy  \t text  "
        clean = parser._clean_text(dirty)
        assert clean == "This is messy text"
        
        with_special = "Text with @#$% special chars"
        clean_special = parser._clean_text(with_special)
        assert "@" not in clean_special
    
    def test_section_extraction(self, parser, sample_10k_html):
        """Test that key sections are extracted."""
        result = parser.parse(sample_10k_html)
        data = result.data
        
        # Should extract at least some sections
        assert len(data["sections"]) > 0
        
        # Check section structure
        for section in data["sections"]:
            assert "section_id" in section
            assert "title" in section
            assert "text" in section
            assert "word_count" in section
    
    def test_malformed_html_handling(self, parser, malformed_html):
        """Test parser handles malformed HTML gracefully."""
        result = parser.parse(malformed_html)
        
        # Should still succeed with fallback
        assert result.success
        assert result.data is not None
    
    def test_empty_html(self, parser, tmp_path):
        """Test handling of empty HTML."""
        empty_file = tmp_path / "2024-01-01-10k-EMPTY.html"
        empty_file.write_text("<html></html>", encoding='utf-8')
        
        result = parser.parse(empty_file)
        assert result.success
        data = result.data
        
        # Should have minimal structure
        assert data["ticker"] == "EMPTY"
        assert data["filing_type"] == "10K"
    
    def test_metadata_completeness(self, parser, sample_10k_html):
        """Test that all required metadata is present."""
        result = parser.parse(sample_10k_html)
        data = result.data
        metadata = data["metadata"]
        
        required_keys = [
            "parsed_at",
            "parser_version",
            "parse_duration_seconds",
            "total_word_count",
            "total_sections"
        ]
        
        for key in required_keys:
            assert key in metadata
        
        assert metadata["parser_version"] == parser.parser_version
        assert metadata["parse_duration_seconds"] > 0

