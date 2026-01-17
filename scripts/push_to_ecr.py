#!/usr/bin/env python3
"""
Push Docker Image to ECR using boto3 (No AWS CLI Required)

This script handles ECR login and can optionally push the image.
Requires: Docker, boto3, and AWS credentials configured.

Credential Sources (in order of precedence):
1. Command-line arguments
2. Environment variables
3. .env file (loaded automatically)
4. AWS credentials file (~/.aws/credentials) - via boto3 default chain
"""

import subprocess
import sys
import os
import base64
import argparse
from pathlib import Path

# Load .env file if it exists
try:
    from dotenv import load_dotenv
    # Load from project root or script directory
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        print(f"[INFO] Loaded credentials from .env file: {env_path}")
    else:
        # Try script directory
        env_path = Path(__file__).parent / '.env'
        if env_path.exists():
            load_dotenv(env_path)
            print(f"[INFO] Loaded credentials from .env file: {env_path}")
        else:
            # Try current directory
            load_dotenv()  # Default: looks for .env in current directory
except ImportError:
    # dotenv is optional - script will use environment variables or AWS credentials file
    pass

try:
    import boto3
except ImportError:
    print("[ERROR] boto3 not installed. Install with: pip install boto3")
    sys.exit(1)


def get_ecr_token(region: str):
    """Get ECR authorization token using boto3."""
    try:
        # boto3 will use credentials from:
        # 1. Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
        # 2. .env file (loaded above)
        # 3. AWS credentials file (~/.aws/credentials)
        # 4. IAM role (if running on EC2/Lambda)
        ecr = boto3.client('ecr', region_name=region)
        token = ecr.get_authorization_token()
        auth_data = token['authorizationData'][0]
        
        # Decode password (format: AWS:base64token)
        password = base64.b64decode(auth_data['authorizationToken']).decode('utf-8').split(':')[1]
        
        return auth_data['proxyEndpoint'], password
    except Exception as e:
        print(f"[ERROR] Failed to get ECR token: {e}")
        print("[INFO] Credential sources checked (in order):")
        print("  1. Command-line arguments")
        print("  2. Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)")
        print("  3. .env file in project root or script directory")
        print("  4. AWS credentials file (~/.aws/credentials)")
        print("  5. IAM role (if running on EC2/Lambda)")
        sys.exit(1)


def docker_login(endpoint: str, password: str):
    """Login to ECR using Docker."""
    print("[INFO] Logging in to ECR...")
    # Docker login with --password-stdin expects password on stdin as bytes
    result = subprocess.run([
        'docker', 'login',
        '--username', 'AWS',
        '--password-stdin',
        endpoint
    ], input=password, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"[ERROR] Docker login failed: {result.stderr}")
        sys.exit(1)
    
    print("[OK] Logged in successfully")
    return True


def docker_tag(image_name: str, image_tag: str, ecr_uri: str):
    """Tag Docker image with ECR URI."""
    print(f"[INFO] Tagging image: {image_name}:{image_tag} -> {ecr_uri}:{image_tag}")
    result = subprocess.run([
        'docker', 'tag',
        f'{image_name}:{image_tag}',
        f'{ecr_uri}:{image_tag}'
    ], capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"[ERROR] Tag failed: {result.stderr}")
        sys.exit(1)
    
    print("[OK] Image tagged successfully")
    return True


def docker_push(ecr_uri: str, image_tag: str):
    """Push Docker image to ECR."""
    print(f"[INFO] Pushing image to ECR...")
    print(f"[INFO] This may take several minutes (pushing ~7 GB image)...")
    
    result = subprocess.run([
        'docker', 'push',
        f'{ecr_uri}:{image_tag}'
    ], text=True)
    
    if result.returncode != 0:
        print(f"[ERROR] Push failed")
        sys.exit(1)
    
    print(f"[OK] Image pushed successfully!")
    return True


def get_account_id():
    """Get AWS account ID from STS."""
    try:
        # boto3 will use credentials from environment/.env/AWS credentials file
        sts = boto3.client('sts')
        identity = sts.get_caller_identity()
        account_id = identity['Account']
        print(f"[INFO] Authenticated as: {identity.get('Arn', 'Unknown')}")
        return account_id
    except Exception as e:
        print(f"[ERROR] Failed to get account ID: {e}")
        print("[INFO] Make sure AWS credentials are configured")
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Push Docker image to ECR (no AWS CLI required)"
    )
    parser.add_argument(
        '--region',
        type=str,
        default=os.getenv('AWS_REGION') or os.getenv('AWS_DEFAULT_REGION', 'us-east-1'),
        help='AWS region (default: from AWS_REGION env var or us-east-1)'
    )
    parser.add_argument(
        '--account-id',
        type=str,
        default=None,
        help='AWS account ID (auto-detected if not provided)'
    )
    parser.add_argument(
        '--repo-name',
        type=str,
        default='sagemaker/batch-embedding-job',
        help='ECR repository name (default: sagemaker/batch-embedding-job)'
    )
    parser.add_argument(
        '--image-name',
        type=str,
        default='batch-embedding-job',
        help='Local Docker image name (default: batch-embedding-job)'
    )
    parser.add_argument(
        '--image-tag',
        type=str,
        default='latest',
        help='Image tag (default: latest)'
    )
    parser.add_argument(
        '--login-only',
        action='store_true',
        help='Only login to ECR, do not push'
    )
    parser.add_argument(
        '--skip-login',
        action='store_true',
        help='Skip login (assume already logged in)'
    )
    
    args = parser.parse_args()
    
    # Get account ID
    account_id = args.account_id or get_account_id()
    if not account_id:
        print("[ERROR] Could not determine AWS account ID. Please provide --account-id")
        sys.exit(1)
    
    print("[INFO] ==========================================")
    print("[INFO] ECR Push Script (No AWS CLI Required)")
    print("[INFO] ==========================================")
    print(f"[INFO] Region: {args.region}")
    print(f"[INFO] Account ID: {account_id}")
    print(f"[INFO] Repository: {args.repo_name}")
    print(f"[INFO] Image: {args.image_name}:{args.image_tag}")
    
    # Show credential source
    if os.getenv('AWS_ACCESS_KEY_ID'):
        print(f"[INFO] Credentials: From environment/.env file")
    else:
        print(f"[INFO] Credentials: Using AWS credentials file or IAM role")
    
    print("[INFO] ==========================================")
    print("")
    
    ecr_uri = f"{account_id}.dkr.ecr.{args.region}.amazonaws.com/{args.repo_name}"
    
    # Login to ECR
    if not args.skip_login:
        endpoint, password = get_ecr_token(args.region)
        docker_login(endpoint, password)
    
    if args.login_only:
        print("[OK] Login complete. You can now push manually with:")
        print(f"  docker tag {args.image_name}:{args.image_tag} {ecr_uri}:{args.image_tag}")
        print(f"  docker push {ecr_uri}:{args.image_tag}")
        return
    
    # Tag image
    docker_tag(args.image_name, args.image_tag, ecr_uri)
    
    # Push image
    docker_push(ecr_uri, args.image_tag)
    
    # Print summary
    print("")
    print("[INFO] ==========================================")
    print("[OK] Image Push Complete!")
    print("[INFO] ==========================================")
    print(f"[INFO] Image URI: {ecr_uri}:{args.image_tag}")
    print("")
    print("[INFO] Use this URI in SageMaker Console:")
    print(f"[INFO]   {ecr_uri}:{args.image_tag}")
    print("[INFO] ==========================================")


if __name__ == "__main__":
    main()

