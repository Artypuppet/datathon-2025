"""
S3 client utilities for reading and writing files.
"""

import boto3
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
import json
from io import BytesIO, StringIO
import os
from dotenv import load_dotenv
logger = logging.getLogger(__name__)

load_dotenv()

class S3Client:
    """
    Client for interacting with AWS S3.
    
    Environment Variables Required:
        AWS_ACCESS_KEY_ID: AWS access key
        AWS_SECRET_ACCESS_KEY: AWS secret key
        AWS_REGION: AWS region (default: us-east-1)
        S3_BUCKET: Default S3 bucket name
    """
    
    def __init__(self, bucket_name: Optional[str] = None, region: Optional[str] = None):
        """
        Initialize S3 client.
        
        Args:
            bucket_name: S3 bucket name (if None, uses S3_BUCKET env var)
            region: AWS region (if None, uses AWS_REGION env var or us-east-1)
        """
        self.bucket_name = bucket_name or os.getenv('S3_BUCKET')
        self.region = region or os.getenv('AWS_REGION', 'us-east-1')
        
        if not self.bucket_name:
            raise ValueError("S3_BUCKET must be set in environment or passed to constructor")
        
        # Initialize boto3 client
        self.s3 = boto3.client('s3', region_name=self.region)
        
        logger.info(f"[INFO] S3Client initialized for bucket: {self.bucket_name}")
    
    def upload_file(self, local_path: Path, s3_key: str) -> bool:
        """
        Upload a local file to S3.
        
        Args:
            local_path: Path to local file
            s3_key: S3 key (path) where file will be stored
            
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"[INFO] Uploading {local_path.name} to s3://{self.bucket_name}/{s3_key}")
            
            self.s3.upload_file(
                str(local_path),
                self.bucket_name,
                s3_key
            )
            
            logger.info(f"[OK] Upload successful")
            return True
            
        except Exception as e:
            logger.error(f"[ERROR] Upload failed: {e}", exc_info=True)
            return False
    
    def download_file(self, s3_key: str, local_path: Path) -> bool:
        """
        Download a file from S3 to local disk.
        
        Args:
            s3_key: S3 key (path) of file to download
            local_path: Local path where file will be saved
            
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"[INFO] Downloading s3://{self.bucket_name}/{s3_key} to {local_path}")
            
            # Create parent directory if needed
            local_path.parent.mkdir(parents=True, exist_ok=True)
            
            self.s3.download_file(
                self.bucket_name,
                s3_key,
                str(local_path)
            )
            
            logger.info(f"[OK] Download successful")
            return True
            
        except Exception as e:
            logger.error(f"[ERROR] Download failed: {e}", exc_info=True)
            return False
    
    def read_file_content(self, s3_key: str, timeout: int = 60) -> Optional[bytes]:
        """
        Read file content from S3 directly into memory (no disk IO).
        Uses get_object which is faster than download_file for in-memory processing.
        
        Args:
            s3_key: S3 key (path) of file to read
            timeout: Request timeout in seconds (default: 60)
            
        Returns:
            File content as bytes, or None if failed
        """
        try:
            import time
            start_time = time.time()
            logger.info(f"[INFO] Reading {s3_key} from S3 (timeout: {timeout}s)")
            
            response = self.s3.get_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            
            # Read content with progress indication for large files
            content = response['Body'].read()
            elapsed = time.time() - start_time
            
            size_mb = len(content) / 1024 / 1024
            speed_mbps = size_mb / elapsed if elapsed > 0 else 0
            logger.info(f"[OK] Read {len(content):,} bytes ({size_mb:.2f} MB) from {s3_key} in {elapsed:.2f}s ({speed_mbps:.2f} MB/s)")
            
            # Check if file is suspiciously large (might indicate an issue)
            if len(content) > 100 * 1024 * 1024:  # 100 MB
                logger.warning(f"[WARN] Large file detected: {size_mb:.2f} MB")
            
            return content
            
        except self.s3.exceptions.NoSuchKey:
            logger.error(f"[ERROR] File not found: {s3_key}")
            return None
        except Exception as e:
            logger.error(f"[ERROR] Failed to read {s3_key}: {e}", exc_info=True)
            return None
    
    def read_text_file(self, s3_key: str, encoding: str = 'utf-8') -> Optional[str]:
        """
        Read text file from S3.
        
        Args:
            s3_key: S3 key (path) of file to read
            encoding: Text encoding (default: utf-8)
            
        Returns:
            File content as string, or None if failed
        """
        content = self.read_file_content(s3_key)
        if content:
            try:
                return content.decode(encoding)
            except Exception as e:
                logger.error(f"[ERROR] Decode failed: {e}")
                return None
        return None
    
    def read_json(self, s3_key: str) -> Optional[Dict[str, Any]]:
        """
        Read JSON file from S3.
        
        Args:
            s3_key: S3 key (path) of JSON file to read
            
        Returns:
            Parsed JSON data as dictionary, or None if failed
        """
        try:
            text_content = self.read_text_file(s3_key, encoding='utf-8')
            if text_content:
                import json
                data = json.loads(text_content)
                logger.debug(f"[DEBUG] Read JSON from {s3_key}")
                return data
            else:
                logger.warning(f"[WARN] Could not read text content from {s3_key}")
                return None
        except json.JSONDecodeError as e:
            logger.error(f"[ERROR] JSON decode failed for {s3_key}: {e}")
            return None
        except Exception as e:
            logger.error(f"[ERROR] Failed to read JSON from {s3_key}: {e}")
            return None
    
    def write_content(self, content: bytes, s3_key: str) -> bool:
        """
        Write content directly to S3 from memory (no disk IO).
        
        Args:
            content: Content to write (as bytes)
            s3_key: S3 key (path) where content will be stored
            
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"[INFO] Writing to s3://{self.bucket_name}/{s3_key}")
            
            self.s3.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=content
            )
            
            logger.info(f"[OK] Write successful")
            return True
            
        except Exception as e:
            logger.error(f"[ERROR] Write failed: {e}", exc_info=True)
            return False
    
    def write_text(self, content: str, s3_key: str, encoding: str = 'utf-8') -> bool:
        """
        Write text content to S3.
        
        Args:
            content: Text content to write
            s3_key: S3 key (path) where content will be stored
            encoding: Text encoding (default: utf-8)
            
        Returns:
            True if successful, False otherwise
        """
        return self.write_content(content.encode(encoding), s3_key)
    
    def write_json(self, data: Dict[Any, Any], s3_key: str, indent: Optional[int] = None) -> bool:
        """
        Write JSON data to S3.
        
        Args:
            data: Dictionary to serialize as JSON
            s3_key: S3 key (path) where JSON will be stored
            indent: JSON indentation (default: 2)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # ensure_ascii=False preserves UTF-8 characters (e.g., é, ü, 法)
            # Use minified JSON by default (indent=None) to save space
            # Set indent=2 or other value if formatting is needed for debugging
            json_str = json.dumps(data, indent=indent, ensure_ascii=False, separators=(',', ':'))
            return self.write_text(json_str, s3_key)
        except Exception as e:
            logger.error(f"[ERROR] JSON serialization failed: {e}")
            return False
    
    def list_files(self, prefix: str = '', suffix: str = '') -> List[str]:
        """
        List files in S3 bucket with optional prefix and suffix filters.
        
        Args:
            prefix: Only list files starting with this prefix (e.g., 'input/filings/')
            suffix: Only list files ending with this suffix (e.g., '.html')
            
        Returns:
            List of S3 keys matching the filters
        """
        try:
            logger.info(f"[INFO] Listing files with prefix='{prefix}' suffix='{suffix}'")
            
            files = []
            paginator = self.s3.get_paginator('list_objects_v2')
            
            for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix):
                if 'Contents' in page:
                    for obj in page['Contents']:
                        key = obj['Key']
                        if suffix and not key.endswith(suffix):
                            continue
                        files.append(key)
            
            logger.info(f"[OK] Found {len(files)} files")
            return files
            
        except Exception as e:
            logger.error(f"[ERROR] List failed: {e}", exc_info=True)
            return []
    
    def file_exists(self, s3_key: str) -> bool:
        """
        Check if a file exists in S3.
        
        Args:
            s3_key: S3 key (path) to check
            
        Returns:
            True if file exists, False otherwise
        """
        try:
            self.s3.head_object(Bucket=self.bucket_name, Key=s3_key)
            return True
        except:
            return False
    
    def delete_file(self, s3_key: str) -> bool:
        """
        Delete a file from S3.
        
        Args:
            s3_key: S3 key (path) of file to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"[INFO] Deleting s3://{self.bucket_name}/{s3_key}")
            
            self.s3.delete_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            
            logger.info(f"[OK] Delete successful")
            return True
            
        except Exception as e:
            logger.error(f"[ERROR] Delete failed: {e}", exc_info=True)
            return False
    
    def get_file_size(self, s3_key: str) -> Optional[int]:
        """
        Get size of a file in S3.
        
        Args:
            s3_key: S3 key (path) of file
            
        Returns:
            File size in bytes, or None if file doesn't exist
        """
        try:
            response = self.s3.head_object(Bucket=self.bucket_name, Key=s3_key)
            return response['ContentLength']
        except:
            return None


def get_s3_client(bucket_name: Optional[str] = None) -> Optional[S3Client]:
    """
    Factory function to get S3 client.
    Returns None if S3 is not configured (for local-only mode).
    
    Args:
        bucket_name: Optional bucket name override
        
    Returns:
        S3Client instance or None if not configured
    """
    try:
        return S3Client(bucket_name)
    except ValueError as e:
        logger.warning(f"[WARN] S3 not configured: {e}")
        return None

