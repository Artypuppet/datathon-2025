"""
Stage 2: Generate embeddings from parsed data.
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional

from ..embeddings import TextProcessor, EmbeddingGenerator
from ..utils import get_s3_client, S3Client

logger = logging.getLogger(__name__)


class EmbeddingStage:
    """Embedding stage: Converts parsed JSON to embeddings."""
    
    def __init__(
        self,
        s3_client: Optional[S3Client] = None,
        model_name: str = "all-MiniLM-L6-v2",
        use_spacy: bool = False,
        normalize_text: bool = False,
        use_contextual_enrichment: bool = False
    ):
        """
        Initialize embedding stage.
        
        Args:
            s3_client: S3 client instance (optional, auto-created if None)
            model_name: Sentence transformer model name
            use_spacy: Whether to use spaCy NLP
            normalize_text: Whether to normalize text (lowercase, etc.)
            use_contextual_enrichment: Whether to add domain context
        """
        self.s3_client = s3_client or get_s3_client()
        
        # Load knowledge database if contextual enrichment is enabled
        knowledge_db = None
        if use_contextual_enrichment:
            try:
                from ..knowledge import CompanyKnowledgeDB
                knowledge_db = CompanyKnowledgeDB()
                logger.info("[INFO] Company knowledge database loaded")
            except Exception as e:
                logger.warning(f"[WARN] Failed to load knowledge database: {e}")
                knowledge_db = None
        
        # Initialize processors
        self.processor = TextProcessor(
            use_spacy=use_spacy,
            normalize_text=normalize_text,
            use_contextual_enrichment=use_contextual_enrichment,
            knowledge_db=knowledge_db
        )
        
        self.generator = EmbeddingGenerator(model_name=model_name)
        
        logger.info("[INFO] EmbeddingStage initialized")
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute embedding stage.
        
        Args:
            context: Pipeline context containing 'parsed_key'
            
        Returns:
            Updated context with embedding results
        """
        parsed_key = context.get('parsed_key')
        if not parsed_key:
            logger.warning("[WARN] No parsed_key in context, skipping embeddings")
            context['embedding_status'] = 'skipped'
            return context
        
        logger.info(f"[INFO] EmbeddingStage: Processing {parsed_key}")
        
        if not self.s3_client:
            logger.warning("[WARN] S3 client not configured, skipping embeddings")
            context['embedding_status'] = 'skipped'
            return context
        
        try:
            # Download parsed JSON
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp_file:
                tmp_path = Path(tmp_file.name)
            
            success = self.s3_client.download_file(parsed_key, tmp_path)
            if not success:
                raise Exception(f"Failed to download {parsed_key} from S3")
            
            # Load and process
            import json
            with open(tmp_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Process and embed
            chunks = self.processor.process_document(data)
            result = self.generator.embed_document(chunks)
            
            # Determine output key
            input_filename = Path(parsed_key).stem
            embedding_key = f"embeddings/{input_filename}_embedded.json"
            
            # Upload embeddings to S3
            self.s3_client.write_json(result, embedding_key)
            
            logger.info(f"[OK] Embeddings generated: {embedding_key}")
            
            # Update context
            context.update({
                'embedding_status': 'success',
                'embedding_key': embedding_key,
                'total_chunks': result['total_chunks'],
                'embedding_dim': result['embedding_dim']
            })
            
            # Cleanup
            if tmp_path.exists():
                tmp_path.unlink()
            
            return context
            
        except Exception as e:
            logger.error(f"[ERROR] EmbeddingStage failed: {e}", exc_info=True)
            context.update({
                'embedding_status': 'failed',
                'embedding_error': str(e)
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
            'parsed_key' in context
        )

