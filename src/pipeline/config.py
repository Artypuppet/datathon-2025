"""
Pipeline configuration.
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class PipelineConfig:
    """Configuration for the processing pipeline."""
    
    # S3 configuration
    input_prefix: str = "input/"
    parsed_prefix: str = "parsed/"
    embeddings_prefix: str = "embeddings/"
    
    # Processing flags
    dry_run: bool = False
    skip_embeddings: bool = True  # True for MVP (embeddings not implemented yet)
    
    # Error handling
    continue_on_error: bool = False
    max_retries: int = 3
    
    @classmethod
    def from_env(cls) -> 'PipelineConfig':
        """Load configuration from environment variables."""
        return cls(
            input_prefix=os.getenv('S3_INPUT_PREFIX', 'input/'),
            parsed_prefix=os.getenv('S3_PARSED_PREFIX', 'parsed/'),
            embeddings_prefix=os.getenv('S3_EMBEDDINGS_PREFIX', 'embeddings/'),
            dry_run=os.getenv('PIPELINE_DRY_RUN', 'false').lower() == 'true',
            skip_embeddings=os.getenv('SKIP_EMBEDDINGS', 'true').lower() == 'true',
        )
    
    @classmethod
    def from_event(cls, event: dict) -> 'PipelineConfig':
        """Load configuration from event (Lambda/SNS/etc)."""
        config = cls.from_env()
        
        # Override with event parameters
        if 'dry_run' in event:
            config.dry_run = bool(event['dry_run'])
        
        if 'skip_embeddings' in event:
            config.skip_embeddings = bool(event['skip_embeddings'])
        
        return config

