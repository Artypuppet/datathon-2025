"""
Parser runner that supports both local and S3 file processing.
"""

from pathlib import Path
from typing import Optional, Dict, Any, List
import logging
import tempfile
import json
from datetime import datetime

from .factory import ParserFactory
from .base import DocumentType
from ..utils.s3_client import S3Client, get_s3_client

logger = logging.getLogger(__name__)


class ParserRunner:
    """
    Orchestrates parsing with support for local and S3 storage.
    
    Workflow:
        1. Read input file (local or S3)
        2. Parse with appropriate parser
        3. Save JSON output (local or S3)
    """
    
    def __init__(
        self, 
        s3_client: Optional[S3Client] = None,
        local_output_dir: Optional[Path] = None
    ):
        """
        Initialize parser runner.
        
        Args:
            s3_client: S3 client for remote operations (optional)
            local_output_dir: Directory for local JSON output (default: output/)
        """
        self.factory = ParserFactory()
        self.s3_client = s3_client or get_s3_client()
        self.local_output_dir = local_output_dir or Path("output")
        self.local_output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"[INFO] ParserRunner initialized")
        logger.info(f"[INFO] S3 mode: {'enabled' if self.s3_client else 'disabled'}")
        logger.info(f"[INFO] Local output: {self.local_output_dir}")
    
    def parse_local_file(
        self, 
        file_path: Path, 
        save_to_s3: bool = False,
        s3_output_prefix: str = "parsed/"
    ) -> Optional[Dict[str, Any]]:
        """
        Parse a local file and optionally upload result to S3.
        
        Args:
            file_path: Path to local file
            save_to_s3: Whether to upload parsed JSON to S3
            s3_output_prefix: S3 prefix for output (e.g., 'parsed/')
            
        Returns:
            Parsed data dictionary or None if failed
        """
        logger.info(f"[INFO] Parsing local file: {file_path}")
        
        # Parse file
        result = self.factory.parse_file(file_path)
        
        if not result or not result.success:
            logger.error(f"[ERROR] Parse failed: {result.error if result else 'No parser found'}")
            return None
        
        # Save locally
        output_filename = f"{file_path.stem}.json"
        local_output_path = self.local_output_dir / output_filename
        
        with open(local_output_path, 'w', encoding='utf-8') as f:
            json.dump(result.data, f, indent=2)
        
        logger.info(f"[OK] Saved to: {local_output_path}")
        
        # Optionally upload to S3
        if save_to_s3 and self.s3_client:
            s3_key = f"{s3_output_prefix}{output_filename}"
            success = self.s3_client.write_json(result.data, s3_key)
            if success:
                logger.info(f"[OK] Uploaded to s3://{self.s3_client.bucket_name}/{s3_key}")
        
        return result.data
    
    def parse_s3_file(
        self,
        s3_key: str,
        save_to_s3: bool = True,
        s3_output_prefix: str = "parsed/",
        save_locally: bool = False,
        document_type: Optional[DocumentType] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Parse a file from S3.
        
        Args:
            s3_key: S3 key of input file
            save_to_s3: Whether to save result back to S3
            s3_output_prefix: S3 prefix for output
            save_locally: Whether to also save locally
            document_type: Optional explicit document type (for user-selected files)
            
        Returns:
            Parsed data dictionary or None if failed
        """
        if not self.s3_client:
            logger.error("[ERROR] S3 client not configured")
            return None
        
        logger.info(f"[INFO] Parsing S3 file: s3://{self.s3_client.bucket_name}/{s3_key}")
        
        # Download to temp file with original filename preserved
        # Extract original filename from S3 key
        original_filename = Path(s3_key).name
        # Create temp file in /tmp with original filename structure
        temp_dir = Path(tempfile.gettempdir()) / "datathon_parser"
        temp_dir.mkdir(exist_ok=True)
        tmp_path = temp_dir / original_filename
        
        try:
            # Download from S3
            success = self.s3_client.download_file(s3_key, tmp_path)
            if not success:
                return None
            
            # Parse - pass S3 key for metadata extraction
            # Store S3 key in a custom attribute that parsers can access
            result = self.factory.parse_file(tmp_path, document_type, s3_key=s3_key)
            
            if not result or not result.success:
                logger.error(f"[ERROR] Parse failed: {result.error if result else 'No parser found'}")
                return None
            
            # Generate output filename
            input_filename = Path(s3_key).stem
            output_filename = f"{input_filename}.json"
            
            # Save to S3
            if save_to_s3:
                s3_output_key = f"{s3_output_prefix}{output_filename}"
                success = self.s3_client.write_json(result.data, s3_output_key)
                if success:
                    logger.info(f"[OK] Uploaded to s3://{self.s3_client.bucket_name}/{s3_output_key}")
            
            # Save locally
            if save_locally:
                local_output_path = self.local_output_dir / output_filename
                with open(local_output_path, 'w', encoding='utf-8') as f:
                    json.dump(result.data, f, indent=2)
                logger.info(f"[OK] Saved to: {local_output_path}")
            
            return result.data
            
        finally:
            # Cleanup temp file
            if tmp_path.exists():
                tmp_path.unlink()
    
    def batch_parse_local(
        self,
        input_dir: Path,
        save_to_s3: bool = False,
        s3_output_prefix: str = "parsed/",
        file_pattern: str = "*"
    ) -> Dict[str, Any]:
        """
        Parse all files in a local directory.
        
        Args:
            input_dir: Directory containing files to parse
            save_to_s3: Whether to upload results to S3
            s3_output_prefix: S3 prefix for outputs
            file_pattern: Glob pattern for files (e.g., '*.html', '*.csv')
            
        Returns:
            Dictionary with statistics and results
        """
        logger.info(f"[INFO] Batch parsing local directory: {input_dir}")
        
        files = list(input_dir.rglob(file_pattern))
        logger.info(f"[INFO] Found {len(files)} files matching pattern '{file_pattern}'")
        
        results = {
            "total_files": len(files),
            "successful": 0,
            "failed": 0,
            "skipped": 0,
            "files": []
        }
        
        for file_path in files:
            if not file_path.is_file():
                continue
            
            try:
                data = self.parse_local_file(file_path, save_to_s3, s3_output_prefix)
                
                if data:
                    results["successful"] += 1
                    results["files"].append({
                        "file": file_path.name,
                        "status": "success",
                        "document_type": data.get("document_type")
                    })
                else:
                    results["failed"] += 1
                    results["files"].append({
                        "file": file_path.name,
                        "status": "failed"
                    })
                    
            except Exception as e:
                logger.error(f"[ERROR] Error processing {file_path.name}: {e}")
                results["failed"] += 1
                results["files"].append({
                    "file": file_path.name,
                    "status": "error",
                    "error": str(e)
                })
        
        logger.info(f"[OK] Batch complete: {results['successful']}/{results['total_files']} successful")
        return results
    
    def batch_parse_s3(
        self,
        s3_input_prefix: str,
        s3_output_prefix: str = "parsed/",
        suffix_filter: str = '',
        save_locally: bool = False
    ) -> Dict[str, Any]:
        """
        Parse all files in an S3 prefix (folder).
        
        Args:
            s3_input_prefix: S3 prefix containing files to parse (e.g., 'input/filings/')
            s3_output_prefix: S3 prefix for parsed outputs
            suffix_filter: Only process files with this suffix (e.g., '.html')
            save_locally: Whether to also save results locally
            
        Returns:
            Dictionary with statistics and results
        """
        if not self.s3_client:
            logger.error("[ERROR] S3 client not configured")
            return {"error": "S3 not configured"}
        
        logger.info(f"[INFO] Batch parsing S3 prefix: {s3_input_prefix}")
        
        # List files
        files = self.s3_client.list_files(prefix=s3_input_prefix, suffix=suffix_filter)
        logger.info(f"[INFO] Found {len(files)} files")
        
        results = {
            "total_files": len(files),
            "successful": 0,
            "failed": 0,
            "files": []
        }
        
        for s3_key in files:
            try:
                data = self.parse_s3_file(
                    s3_key,
                    save_to_s3=True,
                    s3_output_prefix=s3_output_prefix,
                    save_locally=save_locally
                )
                
                if data:
                    results["successful"] += 1
                    results["files"].append({
                        "file": s3_key,
                        "status": "success",
                        "document_type": data.get("document_type")
                    })
                else:
                    results["failed"] += 1
                    results["files"].append({
                        "file": s3_key,
                        "status": "failed"
                    })
                    
            except Exception as e:
                logger.error(f"[ERROR] Error processing {s3_key}: {e}")
                results["failed"] += 1
                results["files"].append({
                    "file": s3_key,
                    "status": "error",
                    "error": str(e)
                })
        
        logger.info(f"[OK] Batch complete: {results['successful']}/{results['total_files']} successful")
        return results

