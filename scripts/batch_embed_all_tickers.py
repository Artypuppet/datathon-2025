#!/usr/bin/env python
"""
Batch Embedding Generation for All Tickers - SageMaker Compatible

This script generates embeddings for all S&P 500 companies and stores them in OpenSearch.
Designed to run on AWS SageMaker processing jobs.

Features:
- Processes all tickers from S&P 500 CSV or S3
- Generates embeddings using pipeline stages
- Stores in OpenSearch vector database
- Checkpoint/resume capability
- Detailed logging for SageMaker CloudWatch
- Error handling and retry logic
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.pipeline.stage_aggregate import CompanyAggregator
from src.pipeline.stage_embed import EmbeddingStage
from src.pipeline.stage_vectordb import VectorDBStage
from src.vectordb.client import VectorDBClient
from src.utils import get_s3_client, S3Client

# Configure logging for SageMaker
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.StreamHandler(sys.stderr)
    ]
)

logger = logging.getLogger(__name__)


class BatchEmbeddingProcessor:
    """
    Process embeddings for all tickers in batch.
    
    Designed for SageMaker execution with checkpointing and error recovery.
    """
    
    def __init__(
        self,
        s3_client: S3Client,
        vectordb_client: VectorDBClient,
        model_name: str = "llmware/industry-bert-sec-v0.1",
        use_contextual_enrichment: bool = False,
        sentence_level_chunking: bool = False,
        checkpoint_path: Optional[Path] = None
    ):
        """
        Initialize batch processor.
        
        Args:
            s3_client: S3 client for reading/writing data
            vectordb_client: VectorDB client for storing embeddings
            model_name: Transformer model name
            use_contextual_enrichment: Enable contextual enrichment
            sentence_level_chunking: Use sentence-level chunking
            checkpoint_path: Path to checkpoint file for resume capability
        """
        self.s3_client = s3_client
        self.vectordb_client = vectordb_client
        
        # Initialize pipeline stages
        self.aggregator = CompanyAggregator(s3_client=s3_client)
        
        self.embedding_stage = EmbeddingStage(
            s3_client=s3_client,
            model_name=model_name,
            use_contextual_enrichment=use_contextual_enrichment,
            sentence_level_chunking=sentence_level_chunking
        )
        
        self.vectordb_stage = VectorDBStage(
            s3_client=s3_client,
            vectordb_client=vectordb_client
        )
        
        self.checkpoint_path = checkpoint_path or Path("/tmp/embedding_checkpoint.json")
        
        logger.info("[INFO] BatchEmbeddingProcessor initialized")
    
    def load_tickers(
        self,
        sp500_csv_path: Optional[str] = None,
        s3_csv_key: Optional[str] = None,
        tickers_list: Optional[List[str]] = None
    ) -> List[str]:
        """
        Load list of tickers to process.
        
        Args:
            sp500_csv_path: Local path to S&P 500 CSV
            s3_csv_key: S3 key to S&P 500 CSV
            tickers_list: Direct list of tickers (overrides CSV)
            
        Returns:
            List of ticker symbols
        """
        if tickers_list:
            logger.info(f"[INFO] Using provided ticker list: {len(tickers_list)} tickers")
            return [t.upper().strip() for t in tickers_list]
        
        # Load from CSV
        csv_path = None
        if sp500_csv_path:
            csv_path = Path(sp500_csv_path)
        elif s3_csv_key:
            # Download from S3
            import tempfile
            csv_path = Path(tempfile.mktemp(suffix='.csv'))
            if not self.s3_client.download_file(s3_csv_key, csv_path):
                logger.error(f"[ERROR] Failed to download CSV from {s3_csv_key}")
                return []
        
        if csv_path and csv_path.exists():
            try:
                import pandas as pd
                df = pd.read_csv(csv_path)
                
                # Try common column names
                ticker_col = None
                for col in ['Symbol', 'Ticker', 'symbol', 'ticker']:
                    if col in df.columns:
                        ticker_col = col
                        break
                
                if not ticker_col:
                    logger.error("[ERROR] Could not find ticker column in CSV")
                    return []
                
                tickers = df[ticker_col].str.strip().str.upper().tolist()
                
                # Clean tickers
                tickers = [t.replace(',', '.') for t in tickers]  # Fix BRK,B -> BRK.B
                tickers = [t for t in tickers if ' ' not in t and len(t) > 0]
                
                logger.info(f"[OK] Loaded {len(tickers)} tickers from CSV")
                return tickers
                
            except Exception as e:
                logger.error(f"[ERROR] Failed to parse CSV: {e}")
                return []
        
        # Fallback: discover tickers from S3 parsed files
        logger.info("[INFO] Discovering tickers from S3 parsed files...")
        parsed_files = self.s3_client.list_files(prefix="parsed/", suffix='.json')
        
        # Extract tickers from filenames (assumes format like AAPL_10K_2024.json)
        tickers = set()
        for file_key in parsed_files:
            filename = Path(file_key).stem
            # Try to extract ticker (first part before underscore)
            parts = filename.split('_')
            if parts:
                ticker = parts[0].upper().strip()
                if len(ticker) > 0 and len(ticker) <= 5:
                    tickers.add(ticker)
        
        tickers_list = sorted(list(tickers))
        logger.info(f"[OK] Discovered {len(tickers_list)} tickers from S3")
        return tickers_list
    
    def load_checkpoint(self) -> Dict[str, Any]:
        """Load checkpoint to resume processing."""
        if not self.checkpoint_path.exists():
            return {
                'processed': [],
                'failed': [],
                'started_at': datetime.now().isoformat()
            }
        
        try:
            with open(self.checkpoint_path, 'r') as f:
                checkpoint = json.load(f)
            logger.info(f"[OK] Loaded checkpoint: {len(checkpoint.get('processed', []))} processed, "
                       f"{len(checkpoint.get('failed', []))} failed")
            return checkpoint
        except Exception as e:
            logger.warning(f"[WARN] Failed to load checkpoint: {e}")
            return {'processed': [], 'failed': []}
    
    def save_checkpoint(self, checkpoint: Dict[str, Any]) -> None:
        """Save checkpoint for resume capability."""
        try:
            checkpoint['last_updated'] = datetime.now().isoformat()
            with open(self.checkpoint_path, 'w') as f:
                json.dump(checkpoint, f, indent=2)
            logger.debug(f"[DEBUG] Checkpoint saved: {self.checkpoint_path}")
        except Exception as e:
            logger.warning(f"[WARN] Failed to save checkpoint: {e}")
    
    def process_ticker(self, ticker: str) -> Dict[str, Any]:
        """
        Process a single ticker: aggregate, embed, store.
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            Result dictionary with status and metadata
        """
        ticker = ticker.upper().strip()
        logger.info(f"[INFO] Processing ticker: {ticker}")
        
        result = {
            'ticker': ticker,
            'status': 'unknown',
            'error': None,
            'chunks_count': 0,
            'embeddings_stored': 0,
            'timestamp': datetime.now().isoformat()
        }
        
        try:
            # Step 1: Aggregate company filings
            logger.info(f"[INFO] Step 1: Aggregating filings for {ticker}")
            aggregated_data = self.aggregator.aggregate_company(ticker)
            
            if not aggregated_data or not aggregated_data.get('aggregated_sections'):
                logger.warning(f"[WARN] No aggregated data for {ticker}, skipping")
                result['status'] = 'skipped'
                result['error'] = 'No filings found'
                return result
            
            # Save aggregated data to S3 temporarily
            aggregated_key = f"aggregated/companies/{ticker}.json"
            self.s3_client.write_json(aggregated_data, aggregated_key)
            logger.info(f"[OK] Aggregated data saved: {aggregated_key}")
            
            # Step 2: Generate embeddings
            logger.info(f"[INFO] Step 2: Generating embeddings for {ticker}")
            context = {'aggregated_key': aggregated_key}
            context = self.embedding_stage.execute(context)
            
            if context.get('embedding_status') != 'success':
                logger.error(f"[ERROR] Embedding generation failed for {ticker}")
                result['status'] = 'failed'
                result['error'] = 'Embedding generation failed'
                return result
            
            embedding_key = context.get('embedding_key')
            chunks_count = context.get('total_chunks', 0)
            result['chunks_count'] = chunks_count
            logger.info(f"[OK] Generated {chunks_count} embeddings for {ticker}")
            
            # Step 3: Store in VectorDB
            logger.info(f"[INFO] Step 3: Storing embeddings in VectorDB for {ticker}")
            context = self.vectordb_stage.execute(context)
            
            if context.get('vectordb_status') != 'success':
                logger.error(f"[ERROR] VectorDB storage failed for {ticker}")
                result['status'] = 'failed'
                result['error'] = 'VectorDB storage failed'
                return result
            
            embeddings_stored = context.get('vectordb_stored_count', 0)
            result['embeddings_stored'] = embeddings_stored
            result['status'] = 'success'
            
            logger.info(f"[OK] Successfully processed {ticker}: {embeddings_stored} embeddings stored")
            
        except Exception as e:
            logger.error(f"[ERROR] Failed to process {ticker}: {e}", exc_info=True)
            result['status'] = 'failed'
            result['error'] = str(e)
        
        return result
    
    def process_all(
        self,
        tickers: List[str],
        resume: bool = True,
        max_tickers: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Process all tickers with checkpoint/resume support.
        
        Args:
            tickers: List of ticker symbols
            resume: Whether to resume from checkpoint
            max_tickers: Maximum number of tickers to process (for testing)
            
        Returns:
            Summary statistics
        """
        logger.info(f"[INFO] Starting batch processing for {len(tickers)} tickers")
        
        # Load checkpoint
        checkpoint = self.load_checkpoint() if resume else {'processed': [], 'failed': []}
        processed_set = set(checkpoint.get('processed', []))
        failed_set = set(checkpoint.get('failed', []))
        
        # Filter tickers to process
        remaining_tickers = [t for t in tickers if t not in processed_set]
        
        if resume and len(remaining_tickers) < len(tickers):
            logger.info(f"[INFO] Resuming: {len(remaining_tickers)} tickers remaining "
                       f"(skipping {len(processed_set)} already processed)")
        
        if max_tickers:
            remaining_tickers = remaining_tickers[:max_tickers]
            logger.info(f"[INFO] Limiting to {max_tickers} tickers")
        
        # Process each ticker
        results = {
            'total': len(remaining_tickers),
            'successful': 0,
            'failed': 0,
            'skipped': 0,
            'results': []
        }
        
        for i, ticker in enumerate(remaining_tickers, 1):
            logger.info(f"[INFO] Processing ticker {i}/{len(remaining_tickers)}: {ticker}")
            
            result = self.process_ticker(ticker)
            results['results'].append(result)
            
            if result['status'] == 'success':
                results['successful'] += 1
                processed_set.add(ticker)
            elif result['status'] == 'skipped':
                results['skipped'] += 1
            else:
                results['failed'] += 1
                failed_set.add(ticker)
            
            # Update checkpoint
            checkpoint['processed'] = sorted(list(processed_set))
            checkpoint['failed'] = sorted(list(failed_set))
            checkpoint['total_processed'] = len(processed_set)
            checkpoint['total_failed'] = len(failed_set)
            self.save_checkpoint(checkpoint)
            
            # Log progress
            if i % 10 == 0:
                logger.info(f"[INFO] Progress: {i}/{len(remaining_tickers)} "
                           f"({results['successful']} success, {results['failed']} failed)")
        
        logger.info(f"[OK] Batch processing complete: {results['successful']} successful, "
                   f"{results['failed']} failed, {results['skipped']} skipped")
        
        return results


def main():
    """Main entry point for SageMaker."""
    parser = argparse.ArgumentParser(
        description="Batch embedding generation for all S&P 500 tickers",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Data source arguments
    parser.add_argument(
        '--sp500-csv',
        type=str,
        help='Local path to S&P 500 composition CSV file'
    )
    
    parser.add_argument(
        '--s3-csv-key',
        type=str,
        help='S3 key to S&P 500 composition CSV file'
    )
    
    parser.add_argument(
        '--tickers',
        type=str,
        nargs='+',
        help='Direct list of tickers to process (overrides CSV)'
    )
    
    parser.add_argument(
        '--parsed-prefix',
        type=str,
        default='parsed/',
        help='S3 prefix for parsed filings (default: parsed/)'
    )
    
    parser.add_argument(
        '--aggregated-prefix',
        type=str,
        default='aggregated/companies/',
        help='S3 prefix for aggregated company data (default: aggregated/companies/)'
    )
    
    # Model configuration
    parser.add_argument(
        '--model-name',
        type=str,
        default='llmware/industry-bert-sec-v0.1',
        help='Transformer model name (default: llmware/industry-bert-sec-v0.1)'
    )
    
    parser.add_argument(
        '--use-contextual-enrichment',
        action='store_true',
        help='Enable contextual enrichment with knowledge database'
    )
    
    parser.add_argument(
        '--sentence-level-chunking',
        action='store_true',
        help='Use sentence-level chunking instead of section-level'
    )
    
    # VectorDB configuration
    parser.add_argument(
        '--opensearch-endpoint',
        type=str,
        help='OpenSearch endpoint URL (overrides OPENSEARCH_ENDPOINT env var)'
    )
    
    parser.add_argument(
        '--opensearch-index',
        type=str,
        default='company_embeddings',
        help='OpenSearch index name (default: company_embeddings)'
    )
    
    parser.add_argument(
        '--vectordb-backend',
        type=str,
        choices=['opensearch', 'chroma', 'auto'],
        default='auto',
        help='VectorDB backend (default: auto)'
    )
    
    # Processing options
    parser.add_argument(
        '--max-tickers',
        type=int,
        help='Maximum number of tickers to process (for testing)'
    )
    
    parser.add_argument(
        '--no-resume',
        action='store_true',
        help='Disable checkpoint/resume (start fresh)'
    )
    
    parser.add_argument(
        '--checkpoint-path',
        type=str,
        default='/tmp/embedding_checkpoint.json',
        help='Path to checkpoint file (default: /tmp/embedding_checkpoint.json)'
    )
    
    # Output options
    parser.add_argument(
        '--output-results',
        type=str,
        help='Path to save results JSON (optional)'
    )
    
    parser.add_argument(
        '--s3-results-key',
        type=str,
        help='S3 key to save results JSON (optional)'
    )
    
    args = parser.parse_args()
    
    # Initialize clients
    logger.info("[INFO] Initializing clients...")
    
    s3_client = get_s3_client()
    if not s3_client:
        logger.error("[ERROR] Failed to initialize S3 client")
        return 1
    
    # Initialize VectorDB client
    if args.opensearch_endpoint:
        import os
        os.environ['OPENSEARCH_ENDPOINT'] = args.opensearch_endpoint
    
    vectordb_client = VectorDBClient(
        backend=args.vectordb_backend,
        collection_name=args.opensearch_index
    )
    
    # Initialize processor
    processor = BatchEmbeddingProcessor(
        s3_client=s3_client,
        vectordb_client=vectordb_client,
        model_name=args.model_name,
        use_contextual_enrichment=args.use_contextual_enrichment,
        sentence_level_chunking=args.sentence_level_chunking,
        checkpoint_path=Path(args.checkpoint_path)
    )
    
    # Load tickers
    tickers = processor.load_tickers(
        sp500_csv_path=args.sp500_csv,
        s3_csv_key=args.s3_csv_key,
        tickers_list=args.tickers
    )
    
    if not tickers:
        logger.error("[ERROR] No tickers to process")
        return 1
    
    logger.info(f"[INFO] Will process {len(tickers)} tickers")
    
    # Process all tickers
    results = processor.process_all(
        tickers=tickers,
        resume=not args.no_resume,
        max_tickers=args.max_tickers
    )
    
    # Save results
    if args.output_results:
        output_path = Path(args.output_results)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)
        logger.info(f"[OK] Results saved to {output_path}")
    
    if args.s3_results_key:
        s3_client.write_json(results, args.s3_results_key)
        logger.info(f"[OK] Results saved to S3: {args.s3_results_key}")
    
    # Print summary
    logger.info("=" * 80)
    logger.info("BATCH PROCESSING SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Total tickers processed: {results['total']}")
    logger.info(f"Successful: {results['successful']}")
    logger.info(f"Failed: {results['failed']}")
    logger.info(f"Skipped: {results['skipped']}")
    logger.info("=" * 80)
    
    return 0 if results['failed'] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

