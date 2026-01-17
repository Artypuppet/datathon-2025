"""
Embedding runner for batch processing documents.
"""

import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import json

from .text_processor import TextProcessor
from .embedding_generator import EmbeddingGenerator

logger = logging.getLogger(__name__)


class EmbeddingRunner:
    """
    Orchestrate text processing and embedding generation.
    
    Handles:
    - Loading parsed JSON files
    - Processing and chunking text
    - Generating embeddings
    - Saving results
    """
    
    def __init__(
        self,
        model_name: str = "llmware/industry-bert-sec-v0.1",
        use_spacy: bool = False,
        normalize_text: bool = True,
        device: Optional[str] = None
    ):
        """
        Initialize embedding runner.
        
        Args:
            model_name: Transformer model name (default: llmware/industry-bert-sec-v0.1)
            use_spacy: Whether to use spaCy NLP
            normalize_text: Whether to normalize text
            device: Device for embeddings (auto-detect if None)
        """
        self.processor = TextProcessor(
            use_spacy=use_spacy,
            normalize_text=normalize_text
        )
        
        self.generator = EmbeddingGenerator(
            model_name=model_name,
            device=device
        )
        
        logger.info("[INFO] EmbeddingRunner initialized")
    
    def process_and_embed_file(
        self,
        json_file: Path
    ) -> Optional[Dict[str, Any]]:
        """
        Load, process, and embed a single JSON file.
        
        Args:
            json_file: Path to parsed JSON file
            
        Returns:
            Dictionary with embeddings and metadata
        """
        logger.info(f"[INFO] Processing file: {json_file.name}")
        
        try:
            # Load JSON
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Process text
            chunks = self.processor.process_document(data)
            
            if not chunks:
                logger.warning(f"[WARN] No chunks generated from {json_file.name}")
                return None
            
            # Generate embeddings
            result = self.generator.embed_document(chunks)
            
            logger.info(f"[OK] Successfully processed {json_file.name}: {len(chunks)} chunks")
            
            return result
            
        except Exception as e:
            logger.error(f"[ERROR] Failed to process {json_file.name}: {e}", exc_info=True)
            return None
    
    def process_directory(
        self,
        input_dir: Path,
        output_dir: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        Process all JSON files in a directory.
        
        Args:
            input_dir: Directory containing parsed JSON files
            output_dir: Optional output directory for embedded results
            
        Returns:
            Statistics dictionary
        """
        input_dir = Path(input_dir)
        
        if not input_dir.exists():
            logger.error(f"[ERROR] Directory not found: {input_dir}")
            return {"error": f"Directory not found: {input_dir}"}
        
        # Find all JSON files
        json_files = list(input_dir.glob("*.json"))
        logger.info(f"[INFO] Found {len(json_files)} JSON files in {input_dir}")
        
        if output_dir:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
        
        # Process each file
        results = {
            "total_files": len(json_files),
            "successful": 0,
            "failed": 0,
            "total_chunks": 0,
            "processed_files": []
        }
        
        for json_file in json_files:
            result = self.process_and_embed_file(json_file)
            
            if result:
                results["successful"] += 1
                results["total_chunks"] += result["total_chunks"]
                
                file_info = {
                    "file": json_file.name,
                    "chunks": result["total_chunks"],
                    "metadata": result.get("metadata", {})
                }
                results["processed_files"].append(file_info)
                
                # Save output if directory specified
                if output_dir:
                    output_file = output_dir / f"{json_file.stem}_embedded.json"
                    with open(output_file, 'w', encoding='utf-8') as f:
                        json.dump(result, f, indent=2, ensure_ascii=False)
                    logger.info(f"[OK] Saved: {output_file}")
            else:
                results["failed"] += 1
        
        logger.info(f"[OK] Processing complete: {results['successful']}/{results['total_files']} successful")
        
        return results
    
    def process_s3_batch(
        self,
        s3_client,
        s3_prefix: str,
        output_prefix: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process JSON files from S3.
        
        Args:
            s3_client: S3Client instance
            s3_prefix: S3 prefix containing JSON files
            output_prefix: Optional S3 prefix for outputs
            
        Returns:
            Statistics dictionary
        """
        logger.info(f"[INFO] Processing S3 prefix: {s3_prefix}")
        
        # List files
        json_files = s3_client.list_files(prefix=s3_prefix, suffix='.json')
        logger.info(f"[INFO] Found {len(json_files)} JSON files")
        
        results = {
            "total_files": len(json_files),
            "successful": 0,
            "failed": 0,
            "total_chunks": 0,
            "processed_files": []
        }
        
        for s3_key in json_files:
            try:
                # Download JSON
                import tempfile
                with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp_file:
                    tmp_path = Path(tmp_file.name)
                
                success = s3_client.download_file(s3_key, tmp_path)
                if not success:
                    logger.error(f"[ERROR] Failed to download {s3_key}")
                    results["failed"] += 1
                    continue
                
                # Process
                result = self.process_and_embed_file(tmp_path)
                
                if result:
                    results["successful"] += 1
                    results["total_chunks"] += result["total_chunks"]
                    
                    # Upload results
                    if output_prefix:
                        output_key = f"{output_prefix}/{Path(s3_key).stem}_embedded.json"
                        s3_client.write_json(result, output_key)
                        logger.info(f"[OK] Uploaded embeddings: {output_key}")
                    
                    file_info = {
                        "file": Path(s3_key).name,
                        "chunks": result["total_chunks"],
                        "metadata": result.get("metadata", {})
                    }
                    results["processed_files"].append(file_info)
                else:
                    results["failed"] += 1
                
                # Cleanup
                if tmp_path.exists():
                    tmp_path.unlink()
                    
            except Exception as e:
                logger.error(f"[ERROR] Failed to process {s3_key}: {e}")
                results["failed"] += 1
        
        logger.info(f"[OK] S3 processing complete: {results['successful']}/{results['total_files']} successful")
        
        return results

