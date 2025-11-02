"""
Pipeline orchestrator: Coordinates all pipeline stages.
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional

from .config import PipelineConfig
from .stage_parse import ParseStage
from .stage_embed import EmbeddingStage

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    """Orchestrates the complete processing pipeline."""
    
    def __init__(self, config: Optional[PipelineConfig] = None):
        """
        Initialize pipeline orchestrator.
        
        Args:
            config: Pipeline configuration (optional, uses env defaults if None)
        """
        self.config = config or PipelineConfig.from_env()
        
        # Initialize stages
        self.parse_stage = ParseStage()
        
        # Initialize embedding stage if not skipped
        self.embedding_stage = None
        if not self.config.skip_embeddings:
            self.embedding_stage = EmbeddingStage()
        
        logger.info(f"[INFO] PipelineOrchestrator initialized")
        logger.info(f"[INFO] Config: dry_run={self.config.dry_run}, skip_embeddings={self.config.skip_embeddings}")
    
    def execute(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the complete pipeline.
        
        Args:
            event: Event containing file_key and optional parameters
            
        Returns:
            Result dictionary with status and details
        """
        logger.info("="*60)
        logger.info("[INFO] Starting pipeline execution")
        logger.info("="*60)
        
        # Build initial context
        context = {
            'file_key': event.get('file_key'),
            'timestamp': event.get('timestamp'),
            'dry_run': self.config.dry_run,
        }
        
        # Pass through document_type if provided
        if 'document_type' in event:
            context['document_type'] = event['document_type']
        
        # Validate input
        if not context['file_key']:
            return self._error_result("file_key is required in event")
        
        logger.info(f"[INFO] Processing file: {context['file_key']}")
        logger.info(f"[INFO] Dry run mode: {context['dry_run']}")
        
        # Stage 1: Parse
        try:
            if self.config.dry_run:
                logger.info("[DRY RUN] Would execute Stage 1: Parse")
                context.update({
                    'parse_status': 'dry_run',
                    'parsed_key': f"parsed/{Path(context['file_key']).stem}.json (would be created)"
                })
            else:
                if not self.parse_stage.can_execute(context):
                    return self._error_result("Parse stage cannot execute (missing dependencies)")
                
                context = self.parse_stage.execute(context)
                
        except Exception as e:
            logger.error(f"[ERROR] Parse stage failed: {e}", exc_info=True)
            return self._error_result(f"Parse failed: {str(e)}", context)
        
        # Stage 2: Embeddings
        if self.config.skip_embeddings:
            logger.info("[INFO] Skipping embeddings (MVP mode)")
            context['embeddings_status'] = 'skipped'
        else:
            try:
                if self.config.dry_run:
                    logger.info("[DRY RUN] Would execute Stage 2: Embeddings")
                    context.update({
                        'embedding_status': 'dry_run',
                        'embedding_key': f"embeddings/{Path(context['parsed_key']).stem}_embedded.json (would be created)"
                    })
                else:
                    if not self.embedding_stage:
                        logger.warning("[WARN] Embedding stage not initialized")
                        context['embeddings_status'] = 'skipped'
                    elif not self.embedding_stage.can_execute(context):
                        logger.warning("[WARN] Embedding stage cannot execute (missing dependencies)")
                        context['embeddings_status'] = 'skipped'
                    else:
                        context = self.embedding_stage.execute(context)
                        
            except Exception as e:
                logger.error(f"[ERROR] Embedding stage failed: {e}", exc_info=True)
                # Don't fail entire pipeline if embeddings fail
                context['embeddings_status'] = 'failed'
                context['embedding_error'] = str(e)
        
        # Stage 3: Database update (skipped in MVP)
        if self.config.skip_embeddings:
            context['db_update_status'] = 'skipped'
        else:
            context['db_update_status'] = 'not_implemented'
        
        # Final result
        if self.config.dry_run:
            return self._dry_run_result(context)
        elif context.get('parse_status') == 'success':
            return self._success_result(context)
        else:
            return self._error_result("Unknown error", context)
    
    def _success_result(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Build success result."""
        logger.info("="*60)
        logger.info("[SUCCESS] Pipeline completed successfully")
        logger.info("="*60)
        
        return {
            'status': 'success',
            'file_key': context['file_key'],
            'parsed_key': context.get('parsed_key'),
            'document_type': context.get('document_type'),
            'stages': {
                'parse': 'success',
                'embeddings': context.get('embeddings_status', 'skipped'),
                'db_update': context.get('db_update_status', 'skipped'),
            },
            'metadata': context.get('metadata', {}),
            'dry_run': False
        }
    
    def _dry_run_result(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Build dry run result."""
        logger.info("="*60)
        logger.info("[DRY RUN] Pipeline dry run completed")
        logger.info("="*60)
        
        return {
            'status': 'dry_run',
            'file_key': context['file_key'],
            'parsed_key': context.get('parsed_key'),
            'document_type': context.get('document_type'),
            'message': 'Would process embeddings and update database',
            'stages': {
                'parse': 'would_execute',
                'embeddings': 'skipped',
                'db_update': 'skipped',
            },
            'dry_run': True
        }
    
    def _error_result(self, error_message: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Build error result."""
        logger.error("="*60)
        logger.error(f"[ERROR] Pipeline failed: {error_message}")
        logger.error("="*60)
        
        result = {
            'status': 'failed',
            'error': error_message,
            'stages': {
                'parse': 'failed',
                'embeddings': 'not_reached',
                'db_update': 'not_reached',
            },
            'dry_run': False
        }
        
        if context:
            result['file_key'] = context.get('file_key')
        
        return result

