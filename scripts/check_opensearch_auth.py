#!/usr/bin/env python3
"""
Debug script to check OpenSearch authentication configuration.
Run this inside the Docker container to verify credentials are set correctly.
"""

import os
import sys

print("[INFO] ==========================================")
print("[INFO] OpenSearch Authentication Debug")
print("[INFO] ==========================================")
print()

# Check endpoint
endpoint = os.getenv('OPENSEARCH_ENDPOINT')
if endpoint:
    print(f"[OK] OPENSEARCH_ENDPOINT: {endpoint}")
else:
    print("[ERROR] OPENSEARCH_ENDPOINT not set")
    sys.exit(1)

# Check auth method
use_iam = os.getenv('OPENSEARCH_USE_IAM_AUTH', 'false').lower() == 'true'
print(f"[INFO] OPENSEARCH_USE_IAM_AUTH: {use_iam}")

if use_iam:
    print("[INFO] Using IAM authentication")
    print()
    
    # Check AWS credentials
    aws_key = os.getenv('AWS_ACCESS_KEY_ID')
    aws_secret = os.getenv('AWS_SECRET_ACCESS_KEY')
    aws_region = os.getenv('AWS_REGION') or os.getenv('AWS_DEFAULT_REGION')
    
    if aws_key:
        print(f"[OK] AWS_ACCESS_KEY_ID: {aws_key[:10]}... (truncated)")
    else:
        print("[ERROR] AWS_ACCESS_KEY_ID not set")
    
    if aws_secret:
        print(f"[OK] AWS_SECRET_ACCESS_KEY: {'*' * 10}... (hidden)")
    else:
        print("[ERROR] AWS_SECRET_ACCESS_KEY not set")
    
    if aws_region:
        print(f"[OK] AWS_REGION: {aws_region}")
    else:
        print("[WARN] AWS_REGION not set (defaults to us-east-1)")
    
    # Test boto3 credentials
    try:
        import boto3
        session = boto3.Session()
        creds = session.get_credentials()
        if creds:
            print(f"[OK] boto3 can access credentials")
            print(f"[INFO] Credentials from: {session.get_available_profiles() or 'default'}")
        else:
            print("[ERROR] boto3 cannot get credentials")
    except Exception as e:
        print(f"[ERROR] boto3 error: {e}")
else:
    print("[INFO] Using basic authentication (username/password)")
    print()
    
    username = os.getenv('OPENSEARCH_USERNAME')
    password = os.getenv('OPENSEARCH_PASSWORD')
    
    if username:
        print(f"[OK] OPENSEARCH_USERNAME: {username}")
    else:
        print("[ERROR] OPENSEARCH_USERNAME not set")
    
    if password:
        print(f"[OK] OPENSEARCH_PASSWORD: {'*' * len(password)} (hidden)")
    else:
        print("[ERROR] OPENSEARCH_PASSWORD not set")
    
    if not username or not password:
        print("[ERROR] Missing credentials for basic auth")
        sys.exit(1)

print()
print("[INFO] ==========================================")
print("[INFO] Testing OpenSearch Connection")
print("[INFO] ==========================================")
print()

# Try to connect
try:
    from opensearchpy import OpenSearch
    
    use_ssl = endpoint.startswith('https://')
    host = endpoint.replace('https://', '').replace('http://', '')
    
    if use_iam:
        from opensearchpy import RequestsHttpConnection
        from requests_aws4auth import AWS4Auth
        import boto3
        
        region = aws_region or 'us-east-1'
        credentials = boto3.Session().get_credentials()
        
        if not credentials:
            print("[ERROR] Cannot get AWS credentials from boto3")
            sys.exit(1)
        
        aws_auth = AWS4Auth(
            credentials.access_key,
            credentials.secret_key,
            region,
            'es',
            session_token=credentials.token
        )
        
        client = OpenSearch(
            hosts=[{'host': host, 'port': 443 if use_ssl else 80}],
            http_auth=None,
            aws_auth=aws_auth,
            use_ssl=use_ssl,
            verify_certs=True,
            connection_class=RequestsHttpConnection
        )
    else:
        client = OpenSearch(
            hosts=[{'host': host, 'port': 443 if use_ssl else 80}],
            http_auth=(username, password),
            use_ssl=use_ssl,
            verify_certs=True
        )
    
    # Test connection
    info = client.info()
    print(f"[OK] Successfully connected to OpenSearch!")
    print(f"[INFO] Cluster name: {info.get('cluster_name', 'unknown')}")
    print(f"[INFO] Version: {info.get('version', {}).get('number', 'unknown')}")
    
except Exception as e:
    print(f"[ERROR] Failed to connect to OpenSearch: {e}")
    print()
    print("[INFO] Troubleshooting:")
    print("  1. Verify endpoint URL is correct")
    print("  2. Check credentials are correct")
    print("  3. Verify network connectivity to OpenSearch")
    print("  4. Check OpenSearch domain access policy allows your IP/credentials")
    sys.exit(1)

print()
print("[OK] All checks passed!")

