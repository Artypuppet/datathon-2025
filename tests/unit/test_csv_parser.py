"""
Unit tests for CSV Parser.
"""

import pytest
from pathlib import Path
import pandas as pd

from src.parsers.csv_parser import CSVParser
from src.parsers.base import DocumentType


class TestCSVParser:
    """Test suite for CSV parser."""
    
    @pytest.fixture
    def parser(self):
        """Create CSV parser instance."""
        return CSVParser()
    
    @pytest.fixture
    def composition_csv(self, tmp_path):
        """Create a sample composition CSV file."""
        csv_content = """#,Company,Symbol,Weight,Price
1,Nvidia,NVDA,"0,0765","181,99"
2,Microsoft,MSFT,"0,0667","520,99"
3,"Apple Inc,",AAPL,"0,0597","233,28"
"""
        csv_file = tmp_path / "2025-08-15_composition_sp500.csv"
        csv_file.write_text(csv_content)
        return csv_file
    
    @pytest.fixture
    def performance_csv(self, tmp_path):
        """Create a sample performance CSV file."""
        csv_content = """Symbol,Company Name,Market Cap,Revenue,Op. Income,Net Income,EPS,FCF
AAPL,Apple Inc.,3791126029400,408625000000,130214000000,99280000000,6.59,96184000000
MSFT,Microsoft Corporation,3801767276203,281724000000,128528000000,101832000000,13.64,71611000000
NVDA,NVIDIA Corporation,4338391930000,165218000000,95981000000,86597000000,3.52,72023000000
"""
        csv_file = tmp_path / "2025-09-26_stocks-performance.csv"
        csv_file.write_text(csv_content)
        return csv_file
    
    def test_can_parse_csv(self, parser, composition_csv):
        """Test that parser recognizes CSV files."""
        assert parser.can_parse(composition_csv) is True
    
    def test_cannot_parse_non_csv(self, parser, tmp_path):
        """Test that parser rejects non-CSV files."""
        html_file = tmp_path / "test.html"
        html_file.write_text("<html></html>")
        assert parser.can_parse(html_file) is False
    
    def test_get_document_type(self, parser):
        """Test document type identification."""
        assert parser.get_document_type() == DocumentType.CSV_FINANCIAL
    
    def test_parse_composition_csv(self, parser, composition_csv):
        """Test parsing S&P 500 composition CSV."""
        result = parser.parse(composition_csv)
        
        # Check success
        assert result.success is True
        assert result.error is None
        
        # Check data structure
        assert result.data['document_type'] == 'csv_financial'
        assert result.data['data_type'] == 'composition'
        assert result.data['snapshot_date'] == '2025-08-15'
        
        # Check companies
        companies = result.data['companies']
        assert len(companies) == 3
        
        # Check first company
        nvda = companies[0]
        assert nvda['ticker'] == 'NVDA'
        assert nvda['company'] == 'Nvidia'
        assert 'weight' in nvda['metrics']
        assert 'price' in nvda['metrics']
        
        # Check European decimal conversion
        assert nvda['metrics']['weight'] == pytest.approx(0.0765, rel=1e-4)
        assert nvda['metrics']['price'] == pytest.approx(181.99, rel=1e-2)
    
    def test_parse_performance_csv(self, parser, performance_csv):
        """Test parsing stock performance CSV."""
        result = parser.parse(performance_csv)
        
        # Check success
        assert result.success is True
        assert result.error is None
        
        # Check data structure
        assert result.data['data_type'] == 'performance'
        assert result.data['snapshot_date'] == '2025-09-26'
        
        # Check companies
        companies = result.data['companies']
        assert len(companies) == 3
        
        # Check Apple data
        aapl = companies[0]
        assert aapl['ticker'] == 'AAPL'
        assert aapl['company'] == 'Apple Inc.'
        assert aapl['metrics']['market_cap'] == pytest.approx(3.79e12, rel=1e-2)
        assert aapl['metrics']['eps'] == pytest.approx(6.59, rel=1e-2)
        assert aapl['metrics']['fcf'] > 0
    
    def test_parse_empty_csv(self, parser, tmp_path):
        """Test parsing empty CSV file."""
        empty_csv = tmp_path / "empty.csv"
        empty_csv.write_text("Symbol,Company\n")
        
        result = parser.parse(empty_csv)
        
        # Should succeed but with no companies
        assert result.success is True
        assert len(result.data['companies']) == 0
    
    def test_parse_malformed_csv(self, parser, tmp_path):
        """Test handling of malformed CSV."""
        bad_csv = tmp_path / "bad.csv"
        bad_csv.write_text("This is not a valid CSV\nRandom text")
        
        result = parser.parse(bad_csv)
        
        # Should either succeed with empty data or fail gracefully
        if not result.success:
            assert result.error is not None
        else:
            assert isinstance(result.data['companies'], list)
    
    def test_parse_missing_file(self, parser):
        """Test parsing non-existent file."""
        result = parser.parse(Path("/nonexistent/file.csv"))
        
        assert result.success is False
        assert result.error is not None
    
    def test_safe_float_conversion(self, parser):
        """Test European decimal format conversion."""
        assert parser._safe_float("0,0765") == pytest.approx(0.0765)
        assert parser._safe_float("181,99") == pytest.approx(181.99)
        assert parser._safe_float("1234.56") == pytest.approx(1234.56)
        assert parser._safe_float(42) == 42.0
        assert parser._safe_float("invalid") == 0.0
        assert parser._safe_float(None) == 0.0
    
    def test_date_extraction(self, parser):
        """Test date extraction from filename."""
        assert parser._extract_date_from_filename(
            "2025-09-26_stocks-performance.csv"
        ) == "2025-09-26"
        
        assert parser._extract_date_from_filename(
            "2025-08-15_composition_sp500.csv"
        ) == "2025-08-15"
        
        assert parser._extract_date_from_filename(
            "no_date_file.csv"
        ) == ""
    
    def test_metadata_populated(self, parser, composition_csv):
        """Test that metadata is properly populated."""
        result = parser.parse(composition_csv)
        
        assert 'metadata' in result.data
        metadata = result.data['metadata']
        
        assert 'parsed_at' in metadata
        assert 'parser_version' in metadata
        assert 'total_companies' in metadata
        assert 'columns' in metadata
        
        assert metadata['total_companies'] == 3
        assert metadata['parser_version'] == '1.0.0'


class TestCSVParserEdgeCases:
    """Test edge cases and error handling."""
    
    @pytest.fixture
    def parser(self):
        return CSVParser()
    
    def test_csv_with_missing_columns(self, parser, tmp_path):
        """Test CSV with missing expected columns."""
        csv_content = """Ticker,Name
AAPL,Apple
MSFT,Microsoft
"""
        # Use proper filename pattern
        csv_file = tmp_path / "2024-01-01-composition-minimal.csv"
        csv_file.write_text(csv_content)
        
        result = parser.parse(csv_file)
        
        # Should handle gracefully
        assert result.success is True
        companies = result.data['companies']
        assert len(companies) > 0
    
    def test_csv_with_special_characters(self, parser, tmp_path):
        """Test CSV with special characters in company names."""
        # Use expected column names: #, Company, Symbol, Weight, Price
        csv_content = """#,Company,Symbol,Weight,Price
1,Johnson & Johnson,JNJ,5.5,150.00
2,"Berkshire Hathaway Inc., Class B",BRK.B,3.8,380.00
"""
        # Use proper filename pattern
        csv_file = tmp_path / "2024-01-01-composition-special.csv"
        csv_file.write_text(csv_content)
        
        result = parser.parse(csv_file)
        
        assert result.success is True
        companies = result.data['companies']
        assert len(companies) == 2
        assert '&' in companies[0]['company'] or 'Johnson' in companies[0]['company']

