"""
Manual test script for all parsers.
Run without pytest: python test_parsers_manual.py
"""

import sys
from pathlib import Path
import json
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s'
)

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.parsers import CSVParser, HTMLFilingParser, HTMLLegislationParser
from src.parsers.factory import ParserFactory


def create_test_files(test_dir: Path):
    """Create sample test files."""
    test_dir.mkdir(exist_ok=True)
    
    # Create sample CSV (matches actual composition file schema)
    csv_file = test_dir / "2024-01-01-composition-TEST.csv"
    csv_file.write_text(
        "#,Company,Symbol,Weight,Price\n"
        "1,Apple Inc.,AAPL,7.5,150.25\n"
        "2,Microsoft Corp.,MSFT,6.8,380.50\n"
        "3,NVIDIA Corp.,NVDA,5.2,495.75\n"
    )
    
    # Create sample 10-K
    filing_file = test_dir / "2024-09-30-10k-AAPL.html"
    filing_file.write_text(
        "<html><head><title>Apple 10-K</title></head><body>"
        "<div>CIK: 0000320193</div>"
        "<h2>Item 1. Business</h2>"
        "<p>Apple Inc. designs and manufactures consumer electronics.</p>"
        "<h2>Item 1A. Risk Factors</h2>"
        "<p>The Company faces various risks including economic conditions.</p>"
        "</body></html>"
    )
    
    # Create sample directive
    directives_dir = test_dir / "directives"
    directives_dir.mkdir(exist_ok=True)
    directive_file = directives_dir / "EU_AI_ACT.html"
    directive_file.write_text(
        "<html><head><title>REGULATION (EU) 2024/1689</title></head><body>"
        "<h1>REGULATION (EU) 2024/1689 OF THE EUROPEAN PARLIAMENT</h1>"
        "<section><h2>Article 1</h2>"
        "<p>This Regulation lays down harmonised rules on artificial intelligence.</p>"
        "</section>"
        "</body></html>"
    )
    
    return csv_file, filing_file, directive_file


def test_csv_parser(csv_file: Path):
    """Test CSV parser."""
    print("\n" + "="*60)
    print("TEST: CSV Parser")
    print("="*60)
    
    parser = CSVParser()
    
    print(f"File: {csv_file.name}")
    print(f"Can parse: {parser.can_parse(csv_file)}")
    
    result = parser.parse(csv_file)
    print(f"Success: {result.success}")
    
    if result.success:
        data = result.data
        print(f"Document type: {data['document_type']}")
        print(f"Date: {data['snapshot_date']}")
        print(f"Data type: {data['data_type']}")
        print(f"Companies: {len(data['companies'])}")
        print(f"\nFirst company sample:")
        if data['companies']:
            company = data['companies'][0]
            print(f"  Ticker: {company['ticker']}")
            print(f"  Company: {company['company']}")
            print(f"  Weight: {company['metrics']['weight']}")
            print(f"  Price: {company['metrics']['price']}")
        print("\n[OK] CSV Parser test passed!")
    else:
        print(f"[FAIL] Error: {result.error}")


def test_filing_parser(filing_file: Path):
    """Test HTML filing parser."""
    print("\n" + "="*60)
    print("TEST: HTML Filing Parser")
    print("="*60)
    
    parser = HTMLFilingParser()
    
    print(f"File: {filing_file.name}")
    print(f"Can parse: {parser.can_parse(filing_file)}")
    
    result = parser.parse(filing_file)
    print(f"Success: {result.success}")
    
    if result.success:
        data = result.data
        print(f"Document type: {data['document_type']}")
        print(f"Ticker: {data['ticker']}")
        print(f"Filing type: {data['filing_type']}")
        print(f"Filing date: {data['filing_date']}")
        print(f"CIK: {data['cik']}")
        print(f"Sections: {len(data['sections'])}")
        
        if data['sections']:
            print(f"\nFirst section:")
            section = data['sections'][0]
            print(f"  ID: {section['section_id']}")
            print(f"  Title: {section['title']}")
            print(f"  Text (first 100 chars): {section['text'][:100]}...")
        
        print("\n[OK] Filing Parser test passed!")
    else:
        print(f"[FAIL] Error: {result.error}")


def test_legislation_parser(directive_file: Path):
    """Test HTML legislation parser."""
    print("\n" + "="*60)
    print("TEST: HTML Legislation Parser")
    print("="*60)
    
    parser = HTMLLegislationParser()
    
    print(f"File: {directive_file.name}")
    print(f"Can parse: {parser.can_parse(directive_file)}")
    
    result = parser.parse(directive_file)
    print(f"Success: {result.success}")
    
    if result.success:
        data = result.data
        print(f"Document type: {data['document_type']}")
        print(f"Title: {data['title']}")
        print(f"Identifier: {data['identifier']}")
        print(f"Jurisdiction: {data['jurisdiction']}")
        print(f"Language: {data['language']}")
        print(f"Sections: {len(data['sections'])}")
        
        if data['sections']:
            print(f"\nFirst section:")
            section = data['sections'][0]
            print(f"  ID: {section['section_id']}")
            print(f"  Title: {section['title']}")
            print(f"  Text (first 100 chars): {section['text'][:100]}...")
        
        print("\n[OK] Legislation Parser test passed!")
    else:
        print(f"[FAIL] Error: {result.error}")


def test_factory(csv_file: Path, filing_file: Path, directive_file: Path):
    """Test parser factory."""
    print("\n" + "="*60)
    print("TEST: Parser Factory")
    print("="*60)
    
    factory = ParserFactory()
    
    test_files = [
        ("CSV", csv_file),
        ("10-K Filing", filing_file),
        ("EU Directive", directive_file),
    ]
    
    for name, file_path in test_files:
        print(f"\n{name}: {file_path.name}")
        parser = factory.get_parser(file_path)
        
        if parser:
            print(f"  Selected: {parser.__class__.__name__}")
            result = factory.parse_file(file_path)
            print(f"  Success: {result.success}")
        else:
            print(f"  [FAIL] No parser found")
    
    print("\n[OK] Factory test passed!")


def main():
    """Run all manual tests."""
    print("\n" + "="*60)
    print("PARSER MANUAL TEST SUITE")
    print("="*60)
    
    # Create test directory and files
    test_dir = Path(__file__).parent / "test_data_manual"
    csv_file, filing_file, directive_file = create_test_files(test_dir)
    
    try:
        # Run tests
        test_csv_parser(csv_file)
        test_filing_parser(filing_file)
        test_legislation_parser(directive_file)
        test_factory(csv_file, filing_file, directive_file)
        
        print("\n" + "="*60)
        print("ALL TESTS PASSED")
        print("="*60)
        
    finally:
        # Cleanup
        print("\n[INFO] Cleaning up test files...")
        import shutil
        if test_dir.exists():
            shutil.rmtree(test_dir)
        print("[OK] Cleanup complete")


if __name__ == "__main__":
    main()

