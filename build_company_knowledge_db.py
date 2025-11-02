"""
Build Company Knowledge Database from S&P 500 filings.

Processes all available filings and extracts company-specific knowledge:
- Regions of operation
- Types of operations
- Risk types
- Sectors

Usage:
    python build_company_knowledge_db.py --input data/initial-dataset/fillings/
    python build_company_knowledge_db.py --s3 --bucket datathon-2025-bucket --prefix parsed/
"""

import sys
import logging
import argparse
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.knowledge import CompanyKnowledgeDB
from src.parsers import ParserFactory, ParserRunner
from src.utils import get_s3_client
from src.knowledge.data_providers import CompanyDataProvider

logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


def build_from_local_files(
    input_dir: Path,
    db_path: Path = None,
    max_files: int = None
) -> CompanyKnowledgeDB:
    """
    Build knowledge database from local filing files.
    
    Args:
        input_dir: Directory containing filing HTML files
        db_path: Path to knowledge DB JSON file
        max_files: Maximum number of files to process (None = all)
        
    Returns:
        Populated CompanyKnowledgeDB
    """
    logger.info(f"[INFO] Building knowledge DB from local files: {input_dir}")
    
    db = CompanyKnowledgeDB(db_path=db_path)
    factory = ParserFactory()
    
    # Find all filing HTML files
    filing_files = list(input_dir.rglob("*.html"))
    
    if max_files:
        filing_files = filing_files[:max_files]
        logger.info(f"[INFO] Processing first {max_files} files")
    
    logger.info(f"[INFO] Found {len(filing_files)} filing files")
    
    processed = 0
    errors = 0
    
    for file_path in filing_files:
        try:
            # Parse filing
            result = factory.parse_file(file_path)
            
            if not result.success:
                logger.warning(f"[WARN] Failed to parse {file_path.name}: {result.error}")
                errors += 1
                continue
            
            # Update knowledge DB
            db.update_from_filing(result.data, source_file=file_path.name)
            processed += 1
            
            if processed % 10 == 0:
                logger.info(f"[INFO] Processed {processed}/{len(filing_files)} filings...")
                
        except Exception as e:
            logger.error(f"[ERROR] Error processing {file_path.name}: {e}")
            errors += 1
            continue
    
    # Save database
    db.save()
    
    logger.info(f"[OK] Knowledge DB built: {processed} companies processed, {errors} errors")
    
    # Print statistics
    stats = db.get_statistics()
    logger.info(f"[INFO] Database statistics:")
    logger.info(f"  Total companies: {stats['total_companies']}")
    logger.info(f"  Avg regions per company: {stats['avg_regions']:.1f}")
    logger.info(f"  Avg operations per company: {stats['avg_operations']:.1f}")
    logger.info(f"  Avg risk types per company: {stats['avg_risk_types']:.1f}")
    
    return db


def build_from_s3(
    bucket: str,
    prefix: str = "parsed/",
    db_path: Path = None,
    max_files: int = None
) -> CompanyKnowledgeDB:
    """
    Build knowledge database from S3 parsed JSON files.
    
    Args:
        bucket: S3 bucket name
        prefix: S3 prefix for parsed files (e.g., "parsed/")
        db_path: Path to knowledge DB JSON file
        max_files: Maximum number of files to process (None = all)
        
    Returns:
        Populated CompanyKnowledgeDB
    """
    logger.info(f"[INFO] Building knowledge DB from S3: s3://{bucket}/{prefix}")
    
    s3_client = get_s3_client()
    if not s3_client:
        raise RuntimeError("S3 client not available. Check AWS credentials.")
    
    db = CompanyKnowledgeDB(db_path=db_path)
    
    # List all parsed JSON files in S3
    files = s3_client.list_files(prefix=prefix)
    filing_files = [f for f in files if f.endswith('.json') and '10k' in f.lower()]
    
    if max_files:
        filing_files = filing_files[:max_files]
        logger.info(f"[INFO] Processing first {max_files} files")
    
    logger.info(f"[INFO] Found {len(filing_files)} parsed filing files")
    
    processed = 0
    errors = 0
    
    for s3_key in filing_files:
        try:
            # Read parsed JSON from S3
            filing_data = s3_client.read_json(s3_key)
            
            if not filing_data:
                logger.warning(f"[WARN] Failed to read {s3_key}")
                errors += 1
                continue
            
            # Only process HTML filings
            if filing_data.get('document_type') != 'html_filing':
                continue
            
            # Update knowledge DB
            db.update_from_filing(filing_data, source_file=s3_key)
            processed += 1
            
            if processed % 10 == 0:
                logger.info(f"[INFO] Processed {processed}/{len(filing_files)} filings...")
                db.save()  # Periodic save
            
        except Exception as e:
            logger.error(f"[ERROR] Error processing {s3_key}: {e}")
            errors += 1
            continue
    
    # Final save
    db.save()
    
    logger.info(f"[OK] Knowledge DB built: {processed} companies processed, {errors} errors")
    
    # Print statistics
    stats = db.get_statistics()
    logger.info(f"[INFO] Database statistics:")
    logger.info(f"  Total companies: {stats['total_companies']}")
    logger.info(f"  Avg regions per company: {stats['avg_regions']:.1f}")
    logger.info(f"  Avg operations per company: {stats['avg_operations']:.1f}")
    logger.info(f"  Avg risk types per company: {stats['avg_risk_types']:.1f}")
    
    return db


def build_from_external_data(
    tickers: List[str] = None,
    sp500_csv: Path = None,
    db_path: Path = None
) -> CompanyKnowledgeDB:
    """
    Build knowledge database from external data providers (Yahoo Finance, etc.).
    
    Args:
        tickers: Optional list of ticker symbols to fetch
        sp500_csv: Optional path to S&P 500 composition CSV to extract tickers
        db_path: Path to knowledge DB JSON file
        
    Returns:
        Populated CompanyKnowledgeDB
    """
    logger.info("[INFO] Building knowledge DB from external data providers")
    
    db = CompanyKnowledgeDB(db_path=db_path, use_external_data=True)
    
    # Get list of tickers
    if tickers:
        ticker_list = tickers
    elif sp500_csv and Path(sp500_csv).exists():
        # Parse S&P 500 CSV to get tickers
        try:
            import pandas as pd
            df = pd.read_csv(sp500_csv)
            ticker_list = df['Symbol'].tolist() if 'Symbol' in df.columns else df['Ticker'].tolist()
            logger.info(f"[INFO] Loaded {len(ticker_list)} tickers from {sp500_csv}")
        except Exception as e:
            logger.error(f"[ERROR] Failed to parse CSV: {e}")
            return db
    else:
        logger.error("[ERROR] Must provide either tickers list or sp500_csv path")
        return db
    
    logger.info(f"[INFO] Fetching data for {len(ticker_list)} companies...")
    
    processed = 0
    errors = 0
    
    for ticker in ticker_list:
        try:
            ticker = ticker.strip().upper()
            if not ticker:
                continue
            
            # Fetch from external provider
            success = db.update_from_external_data(ticker)
            
            if success:
                processed += 1
                if processed % 50 == 0:
                    logger.info(f"[INFO] Processed {processed}/{len(ticker_list)} companies...")
                    db.save()  # Periodic save
            else:
                errors += 1
                
        except Exception as e:
            logger.warning(f"[WARN] Error processing {ticker}: {e}")
            errors += 1
            continue
    
    # Final save
    db.save()
    
    logger.info(f"[OK] Knowledge DB built: {processed} companies processed, {errors} errors")
    
    # Print statistics
    stats = db.get_statistics()
    logger.info(f"[INFO] Database statistics:")
    logger.info(f"  Total companies: {stats['total_companies']}")
    logger.info(f"  Avg regions per company: {stats['avg_regions']:.1f}")
    logger.info(f"  Avg operations per company: {stats['avg_operations']:.1f}")
    
    return db


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Build Company Knowledge Database from filings"
    )
    
    parser.add_argument(
        '--input',
        type=str,
        help='Local directory containing filing HTML files'
    )
    
    parser.add_argument(
        '--s3',
        action='store_true',
        help='Build from S3 instead of local files'
    )
    
    parser.add_argument(
        '--bucket',
        type=str,
        help='S3 bucket name (required if --s3)'
    )
    
    parser.add_argument(
        '--prefix',
        type=str,
        default='parsed/',
        help='S3 prefix for parsed files (default: parsed/)'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        default='data/company_knowledge.json',
        help='Output path for knowledge DB JSON (default: data/company_knowledge.json)'
    )
    
    parser.add_argument(
        '--max-files',
        type=int,
        help='Maximum number of files to process (for testing)'
    )
    
    parser.add_argument(
        '--external',
        action='store_true',
        help='Build from external data providers (Yahoo Finance, etc.) instead of filings'
    )
    
    parser.add_argument(
        '--sp500-csv',
        type=str,
        help='Path to S&P 500 composition CSV (for --external mode)'
    )
    
    parser.add_argument(
        '--tickers',
        type=str,
        nargs='+',
        help='List of ticker symbols to fetch (for --external mode)'
    )
    
    args = parser.parse_args()
    
    db_path = Path(args.output)
    
    if args.external:
        build_from_external_data(
            tickers=args.tickers,
            sp500_csv=Path(args.sp500_csv) if args.sp500_csv else None,
            db_path=db_path
        )
    elif args.s3:
        if not args.bucket:
            parser.error("--bucket is required when using --s3")
        build_from_s3(
            bucket=args.bucket,
            prefix=args.prefix,
            db_path=db_path,
            max_files=args.max_files
        )
    elif args.input:
        input_dir = Path(args.input)
        if not input_dir.exists():
            parser.error(f"Input directory does not exist: {input_dir}")
        build_from_local_files(
            input_dir=input_dir,
            db_path=db_path,
            max_files=args.max_files
        )
    else:
        parser.error("Either --input or --s3 must be specified")


if __name__ == "__main__":
    main()

