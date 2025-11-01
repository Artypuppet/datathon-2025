#!/usr/bin/env python
"""
Test S3 connection and credentials.
Run after configuring .env file.
"""

import sys
from pathlib import Path
from dotenv import load_dotenv
import os

# Load environment
load_dotenv()

print("="*60)
print("S3 CONNECTION TEST")
print("="*60)
print()

# Step 1: Check environment variables
print("[TEST 1] Environment Variables")
print("-"*60)

required_vars = ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_REGION', 'S3_BUCKET']
missing_vars = []

for var in required_vars:
    value = os.getenv(var)
    if value:
        # Mask sensitive values
        if 'SECRET' in var or 'KEY' in var:
            display = value[:4] + '*' * (len(value) - 8) + value[-4:] if len(value) > 8 else '***'
        else:
            display = value
        print(f"  [OK] {var}: {display}")
    else:
        print(f"  [ERROR] {var}: Not set")
        missing_vars.append(var)

if missing_vars:
    print()
    print("[ERROR] Missing required environment variables!")
    print("Please set in .env file:")
    for var in missing_vars:
        print(f"  {var}=your_value_here")
    sys.exit(1)

print()

# Step 2: Test boto3 import
print("[TEST 2] Import boto3")
print("-"*60)
try:
    import boto3
    print(f"  [OK] boto3 version: {boto3.__version__}")
except ImportError as e:
    print(f"  [ERROR] boto3 not installed: {e}")
    print("  Install with: conda install boto3")
    sys.exit(1)

print()

# Step 3: Initialize S3 client
print("[TEST 3] Initialize S3 Client")
print("-"*60)
try:
    from src.utils import get_s3_client
    s3 = get_s3_client()
    if s3:
        print(f"  [OK] S3 client initialized")
        print(f"  [OK] Bucket: {s3.bucket_name}")
        print(f"  [OK] Region: {s3.region}")
    else:
        print("  [ERROR] Failed to initialize S3 client")
        sys.exit(1)
except Exception as e:
    print(f"  [ERROR] {e}")
    sys.exit(1)

print()

# Step 4: Test bucket access
print("[TEST 4] Test Bucket Access")
print("-"*60)
try:
    files = s3.list_files()
    print(f"  [OK] Bucket accessible")
    print(f"  [INFO] Current file count: {len(files)}")
    if files:
        print(f"  [INFO] First few files:")
        for f in files[:5]:
            print(f"    - {f}")
except Exception as e:
    print(f"  [ERROR] Cannot access bucket: {e}")
    print()
    print("  Common causes:")
    print("  1. Bucket doesn't exist - create it in AWS Console")
    print("  2. Wrong bucket name in .env")
    print("  3. IAM user lacks S3 permissions")
    print("  4. Wrong AWS region")
    sys.exit(1)

print()

# Step 5: Test write/read/delete
print("[TEST 5] Test Upload/Download/Delete")
print("-"*60)
try:
    test_key = "test/connection_test.txt"
    test_content = "S3 connection test successful!"
    
    # Write
    print(f"  [INFO] Uploading test file to {test_key}...")
    success = s3.write_text(test_content, test_key)
    if not success:
        raise Exception("Upload failed")
    print(f"  [OK] Upload successful")
    
    # Read
    print(f"  [INFO] Reading test file...")
    read_content = s3.read_text_file(test_key)
    if read_content != test_content:
        raise Exception("Content mismatch")
    print(f"  [OK] Download successful")
    
    # Delete
    print(f"  [INFO] Deleting test file...")
    success = s3.delete_file(test_key)
    if not success:
        raise Exception("Delete failed")
    print(f"  [OK] Delete successful")
    
except Exception as e:
    print(f"  [ERROR] {e}")
    print()
    print("  Check IAM permissions:")
    print("  - s3:PutObject")
    print("  - s3:GetObject")
    print("  - s3:DeleteObject")
    print("  - s3:ListBucket")
    sys.exit(1)

print()

# Summary
print("="*60)
print("ALL TESTS PASSED!")
print("="*60)
print()
print("Your S3 setup is working correctly!")
print()
print("Next steps:")
print("  1. Upload dataset:")
print("     python parse_batch.py --local --input data/initial-dataset/ --upload-to-s3")
print()
print("  2. Parse from S3:")
print("     python parse_batch.py --s3 --input-prefix input/financial/ --output-prefix parsed/")
print()
print("  3. Check results:")
print("     python -c \"from src.utils import get_s3_client; s3 = get_s3_client(); print(s3.list_files(prefix='parsed/'))\"")
print()

