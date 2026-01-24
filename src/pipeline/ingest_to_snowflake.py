"""
Snowflake ingestion pipeline for SEC filings.

Reads local filings, parses them, chunks text, and stores in Snowflake with embeddings.
"""

import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.parsers.html_filing_parser import HTMLFilingParser
from src.embeddings.text_processor import TextProcessor
from src.db.snowflake_client import SnowflakeClient

logger = logging.getLogger(__name__)


class SnowflakeIngestionPipeline:
    """
    Pipeline for ingesting SEC filings into Snowflake.
    
    Steps:
    1. Read local filing files
    2. Parse using HTMLFilingParser
    3. Process text into chunks using TextProcessor
    4. Store chunks in Snowflake
    5. Generate embeddings using Cortex
    """
    
    def __init__(
        self,
        snowflake_client: Optional[SnowflakeClient] = None,
        chunk_size: int = 400,
        chunk_overlap: int = 50
    ):
        """
        Initialize ingestion pipeline.
        
        Args:
            snowflake_client: SnowflakeClient instance (creates new if None)
            chunk_size: Target chunk size in tokens
            chunk_overlap: Overlap between chunks
        """
        self.snowflake_client = snowflake_client or SnowflakeClient()
        self.parser = HTMLFilingParser()
        self.text_processor = TextProcessor(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            use_spacy=False,  # Keep it simple for now
            normalize_text=False  # Preserve original text for embeddings
        )
        
        logger.info("[OK] SnowflakeIngestionPipeline initialized")
    
    def ingest_filing(
        self,
        filing_path: Path,
        ticker: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Ingest a single filing into Snowflake.
        
        Args:
            filing_path: Path to filing HTML file
            ticker: Optional ticker (extracted from filename if not provided)
        
        Returns:
            Dictionary with ingestion results
        """
        logger.info(f"[INFO] Ingesting filing: {filing_path.name}")
        
        if not filing_path.exists():
            logger.error(f"[ERROR] Filing not found: {filing_path}")
            return {
                'success': False,
                'error': 'File not found'
            }
        
        try:
            # Step 1: Parse filing
            parse_result = self.parser.parse(filing_path)
            
            if not parse_result.success:
                logger.error(f"[ERROR] Parsing failed: {parse_result.error}")
                return {
                    'success': False,
                    'error': f'Parsing failed: {parse_result.error}'
                }
            
            parsed_data = parse_result.data
            ticker = ticker or parsed_data.get('ticker', '')
            company_name = parsed_data.get('company', '')
            
            if not ticker:
                logger.error("[ERROR] Could not extract ticker from filing")
                return {
                    'success': False,
                    'error': 'Ticker not found'
                }
            
            # Step 2: Process into chunks
            chunks = self.text_processor.process_document(parsed_data)
            
            if not chunks:
                logger.warning(f"[WARN] No chunks generated for {ticker}")
                return {
                    'success': False,
                    'error': 'No chunks generated'
                }
            
            # Step 3: Format chunks for Snowflake
            formatted_chunks = []
            for chunk in chunks:
                # Extract section info from metadata
                section_type = chunk.get('section_title', 'unknown')
                # Map section titles to section types
                if 'Item 1A' in section_type or 'Risk Factors' in section_type:
                    section_type = 'item_1a'
                elif 'Item 1' in section_type or 'Business' in section_type:
                    section_type = 'item_1'
                elif 'Item 7' in section_type or 'MD&A' in section_type:
                    section_type = 'item_7'
                else:
                    section_type = 'other'
                
                formatted_chunk = {
                    'text': chunk.get('text', ''),
                    'section_type': section_type,
                    'section_title': chunk.get('section_title', ''),
                    'filing_type': parsed_data.get('filing_type', 'N/A'),
                    'filing_date': parsed_data.get('filing_date', ''),
                    'sentence_idx': chunk.get('chunk_index', 0),
                    'total_sentences': chunk.get('total_chunks', 0),
                    'original_sentence': chunk.get('text', '')
                }
                formatted_chunks.append(formatted_chunk)
            
            # Step 4: Store in Snowflake
            stored_count = self.snowflake_client.store_filing_chunks(
                ticker=ticker,
                company_name=company_name,
                chunks=formatted_chunks
            )
            
            logger.info(f"[OK] Ingested {stored_count} chunks for {ticker}")
            
            return {
                'success': True,
                'ticker': ticker,
                'company_name': company_name,
                'chunks_stored': stored_count,
                'total_chunks': len(formatted_chunks),
                'filing_type': parsed_data.get('filing_type'),
                'filing_date': parsed_data.get('filing_date')
            }
            
        except Exception as e:
            logger.error(f"[ERROR] Ingestion failed: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    def ingest_ticker_filings(
        self,
        ticker: str,
        filings_dir: Path
    ) -> Dict[str, Any]:
        """
        Ingest all filings for a ticker.
        
        Args:
            ticker: Company ticker
            filings_dir: Directory containing filings (e.g., data/filings/{ticker}/)
        
        Returns:
            Dictionary with results for each filing
        """
        logger.info(f"[INFO] Ingesting all filings for {ticker}")
        
        if not filings_dir.exists():
            logger.error(f"[ERROR] Filings directory not found: {filings_dir}")
            return {
                'success': False,
                'error': 'Directory not found'
            }
        
        # Find all HTML files
        filing_files = list(filings_dir.glob("*.html")) + list(filings_dir.glob("*.txt"))
        
        if not filing_files:
            logger.warning(f"[WARN] No filings found in {filings_dir}")
            return {
                'success': False,
                'error': 'No filings found'
            }
        
        results = {
            'ticker': ticker,
            'filings': {},
            'total_stored': 0
        }
        
        for filing_file in filing_files:
            result = self.ingest_filing(filing_file, ticker=ticker)
            filing_type = result.get('filing_type', 'unknown')
            results['filings'][filing_type] = result
            
            if result.get('success'):
                results['total_stored'] += result.get('chunks_stored', 0)
        
        logger.info(f"[OK] Ingested {len([f for f in results['filings'].values() if f.get('success')])} filings for {ticker}")
        return results
    
    def ingest_all_companies(
        self,
        base_dir: Path
    ) -> Dict[str, Any]:
        """
        Ingest filings for all companies in a directory.
        
        Args:
            base_dir: Base directory containing company subdirectories (e.g., data/filings/)
        
        Returns:
            Dictionary with results for each company
        """
        logger.info(f"[INFO] Ingesting filings for all companies in {base_dir}")
        
        if not base_dir.exists():
            logger.error(f"[ERROR] Base directory not found: {base_dir}")
            return {}
        
        # Find all company directories
        company_dirs = [d for d in base_dir.iterdir() if d.is_dir()]
        
        if not company_dirs:
            logger.warning(f"[WARN] No company directories found in {base_dir}")
            return {}
        
        results = {}
        
        for company_dir in company_dirs:
            ticker = company_dir.name.upper()
            result = self.ingest_ticker_filings(ticker, company_dir)
            results[ticker] = result
        
        logger.info(f"[OK] Ingested filings for {len(results)} companies")
        return results


def main():
    """CLI entry point for ingestion."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Ingest SEC filings into Snowflake"
    )
    
    parser.add_argument(
        '--input-dir',
        type=str,
        default='data/filings',
        help='Input directory containing filings (default: data/filings)'
    )
    
    parser.add_argument(
        '--ticker',
        type=str,
        help='Process only this ticker (optional)'
    )
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='[%(levelname)s] %(message)s'
    )
    
    # Initialize pipeline
    pipeline = SnowflakeIngestionPipeline()
    
    input_dir = Path(args.input_dir)
    
    if args.ticker:
        # Process single ticker
        ticker_dir = input_dir / args.ticker.upper()
        result = pipeline.ingest_ticker_filings(args.ticker.upper(), ticker_dir)
        print(f"\nResults for {args.ticker}:")
        print(f"  Chunks stored: {result.get('total_stored', 0)}")
    else:
        # Process all companies
        results = pipeline.ingest_all_companies(input_dir)
        print(f"\nIngestion complete for {len(results)} companies")
        for ticker, result in results.items():
            print(f"  {ticker}: {result.get('total_stored', 0)} chunks stored")


if __name__ == "__main__":
    main()
