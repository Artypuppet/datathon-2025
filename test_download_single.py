"""
Test script to download a single filing and verify the process works.
"""

import sys
from pathlib import Path
import tempfile
import shutil

sys.path.insert(0, str(Path(__file__).parent))

from src.utils import get_s3_client
from download_sec_filings import download_filing_to_s3

def test_download():
    """Test downloading a single filing for AAPL."""
    print("\n=== TESTING SEC FILING DOWNLOAD ===\n")
    
    # Get S3 client
    s3_client = get_s3_client()
    if not s3_client:
        print("[ERROR] S3 client not available")
        return
    
    print("[INFO] Testing download for AAPL 10-K...")
    
    result = download_filing_to_s3(
        ticker='AAPL',
        filing_type='10-K',
        s3_client=s3_client,
        company_name='DataThon2025',
        email='datathon@example.com',
        limit=1
    )
    
    print("\n=== RESULT ===")
    print(f"Success: {result.get('success')}")
    if result.get('success'):
        print(f"S3 Key: {result.get('s3_key')}")
        print(f"Size: {result.get('size_bytes', 0) / 1024:.1f} KB")
        print(f"Filing Date: {result.get('filing_date')}")
    else:
        print(f"Error: {result.get('error')}")
    
    print("\n[OK] Test complete!")

if __name__ == "__main__":
    test_download()

