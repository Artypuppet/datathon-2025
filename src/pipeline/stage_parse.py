"""
Stage 1: Parse uploaded files and extract structured data.
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional

from ..parsers import ParserRunner
from ..utils import get_s3_client, S3Client

logger = logging.getLogger(__name__)


class ParseStage:
    """Parse stage: Converts raw files to structured JSON."""
    
    def __init__(self, s3_client: Optional[S3Client] = None):
        """
        Initialize parse stage.
        
        Args:
            s3_client: S3 client instance (optional, auto-created if None)
        """
        self.s3_client = s3_client or get_s3_client()
        self.runner = None
        
        if self.s3_client:
            from ..parsers import ParserRunner
            self.runner = ParserRunner(s3_client=self.s3_client)
            logger.info("[INFO] ParseStage initialized with S3")
        else:
            logger.warning("[WARN] ParseStage initialized without S3")
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute parse stage.
        
        Args:
            context: Pipeline context containing 'file_key'
            
        Returns:
            Updated context with parse results
        """
        file_key = context.get('file_key')
        if not file_key:
            raise ValueError("file_key is required in context")
        
        logger.info(f"[INFO] ParseStage: Processing {file_key}")
        
        if not self.s3_client:
            raise RuntimeError("S3 client not configured")
        
        if not self.runner:
            raise RuntimeError("ParserRunner not initialized")
        
        # Determine output key
        input_filename = Path(file_key).stem
        parsed_key = f"parsed/{input_filename}.json"
        
        # Parse the file from S3
        try:
            data = self.runner.parse_s3_file(
                s3_key=file_key,
                save_to_s3=True,
                s3_output_prefix="parsed/",
                save_locally=False
            )
            
            if data:
                logger.info(f"[OK] Parsed successfully: {parsed_key}")
                
                # Update context
                context.update({
                    'parse_status': 'success',
                    'parsed_key': parsed_key,
                    'document_type': data.get('document_type'),
                    'metadata': {
                        'parser_version': data.get('metadata', {}).get('parser_version'),
                        'parse_duration': data.get('metadata', {}).get('parse_duration_seconds', 0),
                    }
                })
                
                return context
            else:
                raise Exception("Parser returned no data")
                
        except Exception as e:
            logger.error(f"[ERROR] ParseStage failed: {e}", exc_info=True)
            context.update({
                'parse_status': 'failed',
                'parse_error': str(e)
            })
            raise
    
    def can_execute(self, context: Dict[str, Any]) -> bool:
        """
        Check if this stage can execute.
        
        Args:
            context: Pipeline context
            
        Returns:
            True if stage can execute
        """
        return (
            self.s3_client is not None and
            self.runner is not None and
            'file_key' in context
        )

