#!/usr/bin/env python3
"""
Minimal test to parse a single filing and measure timing at each step.
"""

import time
import logging
from pathlib import Path
from src.utils import get_s3_client
from src.parsers.html_filing_parser import HTMLFilingParser

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

def test_parse_timing():
    """Test parsing a single filing with detailed timing."""
    
    print("="*80)
    print("MINIMAL PARSING TIMING TEST")
    print("="*80)
    
    # Get S3 client
    s3_client = get_s3_client()
    if not s3_client:
        print("ERROR: S3 client not available")
        return
    
    # Test file - use a real filing from S3
    test_key = 'input/filings/A/2024-12-20-10-k-A.txt'
    print(f"\nTest file: {test_key}")
    
    # Step 1: Read from S3
    print("\n[1] Reading from S3...")
    read_start = time.time()
    file_content = s3_client.read_file_content(test_key)
    read_elapsed = time.time() - read_start
    
    if not file_content:
        print(f"ERROR: Failed to read file (took {read_elapsed:.2f}s)")
        return
    
    size_mb = len(file_content) / 1024 / 1024
    print(f"  ✓ Read {size_mb:.2f} MB in {read_elapsed:.2f}s ({size_mb/read_elapsed:.2f} MB/s)")
    
    # Step 2: Write to temp file
    print("\n[2] Writing to temp file...")
    import tempfile
    temp_dir = Path(tempfile.gettempdir()) / "datathon_parser_test"
    temp_dir.mkdir(exist_ok=True)
    temp_file = temp_dir / Path(test_key).name
    
    write_start = time.time()
    with open(temp_file, 'wb') as f:
        f.write(file_content)
    write_elapsed = time.time() - write_start
    print(f"  ✓ Wrote to {temp_file} in {write_elapsed:.2f}s")
    
    # Step 3: Initialize parser
    print("\n[3] Initializing parser...")
    init_start = time.time()
    parser = HTMLFilingParser()
    init_elapsed = time.time() - init_start
    print(f"  ✓ Parser initialized in {init_elapsed:.2f}s")
    
    # Step 4: Parse the file
    print("\n[4] Parsing file...")
    parse_start = time.time()
    result = parser.parse(temp_file, s3_key=test_key)
    parse_elapsed = time.time() - parse_start
    
    if result.success:
        print(f"  ✓ Parse successful in {parse_elapsed:.2f}s")
        print(f"    Company: {result.data.get('company', 'N/A')}")
        print(f"    CIK: {result.data.get('cik', 'N/A')}")
        print(f"    Filing type: {result.data.get('filing_type', 'N/A')}")
        print(f"    Sections found: {len(result.data.get('sections', []))}")
        
        for i, section in enumerate(result.data.get('sections', [])[:5]):
            print(f"      Section {i+1}: {section.get('section_id')} - {section.get('title', '')[:50]}")
            print(f"        Words: {section.get('word_count', 0):,}")
    else:
        print(f"  ✗ Parse failed in {parse_elapsed:.2f}s")
        print(f"    Error: {result.error}")
    
    # Cleanup
    if temp_file.exists():
        temp_file.unlink()
    
    # Summary
    total_time = read_elapsed + write_elapsed + init_elapsed + parse_elapsed
    print("\n" + "="*80)
    print("TIMING SUMMARY")
    print("="*80)
    print(f"  S3 read:      {read_elapsed:6.2f}s ({read_elapsed/total_time*100:5.1f}%)")
    print(f"  File write:   {write_elapsed:6.2f}s ({write_elapsed/total_time*100:5.1f}%)")
    print(f"  Parser init:  {init_elapsed:6.2f}s ({init_elapsed/total_time*100:5.1f}%)")
    print(f"  Parse:        {parse_elapsed:6.2f}s ({parse_elapsed/total_time*100:5.1f}%)")
    print(f"  {'-'*30}")
    print(f"  TOTAL:        {total_time:6.2f}s")
    
    # Check metadata for detailed parse timing
    if result.success and result.metadata:
        parse_duration = result.data.get('metadata', {}).get('parse_duration_seconds', 0)
        if parse_duration > 0:
            print(f"\n  Parse duration from metadata: {parse_duration:.2f}s")

if __name__ == "__main__":
    test_parse_timing()

