"""
Combined Parse and Aggregate stage: Parse all raw filings for a ticker and aggregate in one step.
Skips saving intermediate parsed files to S3.
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

from ..parsers import ParserRunner
from ..parsers.base import DocumentType
from ..utils import get_s3_client, S3Client
from .stage_aggregate import CompanyAggregator

logger = logging.getLogger(__name__)


class ParseAndAggregateStage:
    """Combined stage: Parse all filings for a ticker and aggregate immediately."""
    
    def __init__(self, s3_client: Optional[S3Client] = None):
        """
        Initialize combined parse and aggregate stage.
        
        Args:
            s3_client: S3 client instance (optional, auto-created if None)
        """
        self.s3_client = s3_client or get_s3_client()
        self.runner = None
        self.aggregator = None
        
        if self.s3_client:
            from ..parsers import ParserRunner
            self.runner = ParserRunner(s3_client=self.s3_client)
            self.aggregator = CompanyAggregator(s3_client=self.s3_client, use_metadata_enrichment=True)
            logger.info("[INFO] ParseAndAggregateStage initialized with S3")
        else:
            logger.warning("[WARN] ParseAndAggregateStage initialized without S3")
    
    def execute_for_ticker(self, ticker: str) -> Dict[str, Any]:
        """
        Parse all raw filings for a ticker and aggregate them in one step.
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            Updated context with aggregation results
        """
        ticker = ticker.upper().strip()
        logger.info(f"[INFO] ParseAndAggregateStage: Processing all filings for {ticker}")
        
        if not self.s3_client or not self.runner or not self.aggregator:
            raise RuntimeError("S3 client, parser runner, or aggregator not configured")
        
        # Discover all raw filing files for this ticker
        raw_filings = self._discover_raw_filings(ticker)
        
        if not raw_filings:
            logger.warning(f"[WARN] No raw filings found for {ticker}")
            # Return empty aggregation
            aggregated = self.aggregator._empty_aggregation(ticker)
            output_key = f"aggregated/companies/{ticker}.json"
            self.s3_client.write_json(aggregated, output_key)
            return {
                'status': 'success',
                'ticker': ticker,
                'aggregated_key': output_key,
                'filings_processed': 0,
                'message': 'No raw filings found'
            }
        
        logger.info(f"[INFO] Found {len(raw_filings)} raw filing(s) for {ticker}")
        
        # Parse all filings in memory (don't save to S3)
        parsed_filings = []
        for filing_key in raw_filings:
            try:
                logger.info(f"[INFO] Parsing {filing_key}")
                # Parse directly from S3 without saving intermediate result
                parsed_data = self._parse_file_in_memory(filing_key)
                if parsed_data and parsed_data.get('document_type') == 'html_filing':
                    parsed_filings.append(parsed_data)
                    logger.debug(f"[DEBUG] Parsed filing: {filing_key} -> {parsed_data.get('filing_type')}")
                else:
                    logger.warning(f"[WARN] Skipping non-filing document: {filing_key}")
            except Exception as e:
                logger.error(f"[ERROR] Failed to parse {filing_key}: {e}")
                continue
        
        if not parsed_filings:
            logger.warning(f"[WARN] No valid filings parsed for {ticker}")
            aggregated = self.aggregator._empty_aggregation(ticker)
            output_key = f"aggregated/companies/{ticker}.json"
            self.s3_client.write_json(aggregated, output_key)
            return {
                'status': 'success',
                'ticker': ticker,
                'aggregated_key': output_key,
                'filings_processed': 0,
                'message': 'No valid filings parsed'
            }
        
        logger.info(f"[INFO] Successfully parsed {len(parsed_filings)} filing(s) for {ticker}")
        
        # Aggregate all parsed filings directly (we already have them in memory)
        aggregated = self.aggregator._merge_filings(ticker, parsed_filings)
        
        # Enrich with external metadata
        if self.aggregator.metadata_cache:
            try:
                aggregated = self.aggregator.metadata_cache.enrich_company_data(ticker, aggregated)
            except Exception as e:
                logger.warning(f"[WARN] Metadata enrichment failed: {e}")
        
        # Save aggregated result to S3
        output_key = f"aggregated/companies/{ticker}.json"
        success = self.s3_client.write_json(aggregated, output_key)
        
        if success:
            logger.info(f"[OK] Saved aggregated data to {output_key}")
            return {
                'status': 'success',
                'ticker': ticker,
                'aggregated_key': output_key,
                'filings_processed': len(parsed_filings),
                'filing_types': {
                    '10-K': len([f for f in parsed_filings if '10-K' in f.get('filing_type', '')]),
                    '10-Q': len([f for f in parsed_filings if '10-Q' in f.get('filing_type', '')]),
                    '8-K': len([f for f in parsed_filings if '8-K' in f.get('filing_type', '')]),
                }
            }
        else:
            raise Exception(f"Failed to save aggregated data to {output_key}")
    
    def _discover_raw_filings(self, ticker: str) -> List[str]:
        """
        Discover all raw filing files for a ticker in S3.
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            List of S3 keys to raw filing files
        """
        if not self.s3_client:
            return []
        
        ticker_upper = ticker.upper()
        filing_keys = []
        
        # Look in input/filings/{ticker}/ directory
        prefix = f"input/filings/{ticker_upper}/"
        files = self.s3_client.list_files(prefix=prefix)
        
        # Filter for filing files (html, txt)
        for file_key in files:
            if any(file_key.lower().endswith(ext) for ext in ['.html', '.txt']):
                # Verify it's a filing for this ticker (check filename pattern)
                filename = Path(file_key).name.lower()
                if ticker_upper.lower() in filename and any(ftype in filename for ftype in ['10-k', '10-q', '8-k', '10k', '10q', '8k']):
                    filing_keys.append(file_key)
        
        # Sort by filename (most recent first typically)
        filing_keys.sort(reverse=True)
        
        logger.info(f"[INFO] Discovered {len(filing_keys)} raw filing(s) for {ticker}")
        return filing_keys
    
    def _parse_file_in_memory(self, s3_key: str) -> Optional[Dict[str, Any]]:
        """
        Parse a file from S3 in memory without saving intermediate results.
        
        Args:
            s3_key: S3 key of file to parse
            
        Returns:
            Parsed data dictionary or None if failed
        """
        if not self.s3_client or not self.runner:
            return None
        
        try:
            # Determine document type from filename
            document_type = None
            filename = Path(s3_key).name.lower()
            if 'legislation' in s3_key.lower():
                document_type = DocumentType.HTML_LEGISLATION
            elif any(ftype in filename for ftype in ['10-k', '10-q', '8-k', '10k', '10q', '8k']):
                document_type = DocumentType.HTML_FILING
            
            # Parse directly (this downloads to temp, parses, and returns data without saving to S3)
            # We need to modify parse_s3_file to have a save_to_s3=False option
            # For now, let's use the runner's parse_s3_file but intercept the result
            data = self.runner.parse_s3_file(
                s3_key=s3_key,
                save_to_s3=False,  # Don't save intermediate parsed files
                s3_output_prefix="",  # Not used since save_to_s3=False
                save_locally=False,
                document_type=document_type
            )
            
            return data
            
        except Exception as e:
            logger.error(f"[ERROR] Failed to parse {s3_key}: {e}")
            return None
    
    def can_execute(self, ticker: str) -> bool:
        """
        Check if this stage can execute for a ticker.
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            True if stage can execute
        """
        return (
            self.s3_client is not None and
            self.runner is not None and
            self.aggregator is not None
        )

