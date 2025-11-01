#!/usr/bin/env python
"""
Example: Parse a single file (local or S3).
"""

import sys
from pathlib import Path
import json
import logging
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.parsers.parser_runner import ParserRunner
from src.utils.s3_client import get_s3_client

# Load environment
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')


def example_parse_local():
    """Example: Parse a local file."""
    print("\n" + "="*60)
    print("EXAMPLE 1: Parse Local File")
    print("="*60)
    
    # Initialize runner
    runner = ParserRunner()
    
    # Parse a local CSV file
    file_path = Path("data/2024-01-01-composition-TEST.csv")
    
    if not file_path.exists():
        print(f"[SKIP] File not found: {file_path}")
        return
    
    data = runner.parse_local_file(file_path, save_to_s3=False)
    
    if data:
        print(f"\n[OK] Parsed successfully!")
        print(f"Document type: {data['document_type']}")
        print(f"Output saved to: output/{file_path.stem}.json")


def example_parse_local_and_upload():
    """Example: Parse local file and upload to S3."""
    print("\n" + "="*60)
    print("EXAMPLE 2: Parse Local File and Upload to S3")
    print("="*60)
    
    # Check S3 configuration
    s3_client = get_s3_client()
    if not s3_client:
        print("[SKIP] S3 not configured")
        return
    
    # Initialize runner with S3
    runner = ParserRunner(s3_client=s3_client)
    
    # Parse and upload
    file_path = Path("data/2024-01-01-composition-TEST.csv")
    
    if not file_path.exists():
        print(f"[SKIP] File not found: {file_path}")
        return
    
    data = runner.parse_local_file(
        file_path, 
        save_to_s3=True,
        s3_output_prefix="parsed/"
    )
    
    if data:
        print(f"\n[OK] Parsed and uploaded!")
        print(f"Local: output/{file_path.stem}.json")
        print(f"S3: s3://{s3_client.bucket_name}/parsed/{file_path.stem}.json")


def example_parse_from_s3():
    """Example: Parse a file from S3."""
    print("\n" + "="*60)
    print("EXAMPLE 3: Parse File from S3")
    print("="*60)
    
    # Check S3 configuration
    s3_client = get_s3_client()
    if not s3_client:
        print("[SKIP] S3 not configured")
        return
    
    # Initialize runner
    runner = ParserRunner(s3_client=s3_client)
    
    # Parse from S3
    s3_key = "input/filings/2024-09-30-10k-AAPL.html"
    
    data = runner.parse_s3_file(
        s3_key,
        save_to_s3=True,
        s3_output_prefix="parsed/",
        save_locally=True
    )
    
    if data:
        print(f"\n[OK] Parsed from S3!")
        print(f"Input: s3://{s3_client.bucket_name}/{s3_key}")
        print(f"Output: s3://{s3_client.bucket_name}/parsed/2024-09-30-10k-AAPL.json")


def example_direct_s3_operations():
    """Example: Direct S3 file operations."""
    print("\n" + "="*60)
    print("EXAMPLE 4: Direct S3 Operations")
    print("="*60)
    
    s3_client = get_s3_client()
    if not s3_client:
        print("[SKIP] S3 not configured")
        return
    
    # Upload a file
    print("\n[INFO] Uploading file...")
    local_file = Path("data/sample.csv")
    if local_file.exists():
        s3_client.upload_file(local_file, "test/sample.csv")
    
    # List files
    print("\n[INFO] Listing files in 'test/' prefix...")
    files = s3_client.list_files(prefix="test/")
    for f in files:
        print(f"  - {f}")
    
    # Read file content
    if files:
        print(f"\n[INFO] Reading content of {files[0]}...")
        content = s3_client.read_text_file(files[0])
        if content:
            print(f"First 100 chars: {content[:100]}")
    
    # Write JSON
    print("\n[INFO] Writing JSON to S3...")
    test_data = {"message": "Hello from S3!", "timestamp": "2024-11-01"}
    s3_client.write_json(test_data, "test/hello.json")
    
    print("\n[OK] S3 operations complete!")


def main():
    """Run all examples."""
    print("\n" + "="*60)
    print("PARSER + S3 INTEGRATION EXAMPLES")
    print("="*60)
    
    example_parse_local()
    example_parse_local_and_upload()
    example_parse_from_s3()
    example_direct_s3_operations()
    
    print("\n" + "="*60)
    print("ALL EXAMPLES COMPLETE")
    print("="*60)


if __name__ == '__main__':
    main()

