"""
Download SEC filings (10-K, 10-Q, 8-K) for S&P 500 companies and upload to S3.

Uses sec-edgar-downloader with multiprocessing to download filings directly to S3
without saving to disk first.
"""

import sys
import logging
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed
from io import BytesIO
import tempfile
import shutil
import time
import random
import re

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.utils import get_s3_client

logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


def download_filing_to_s3(
    ticker: str,
    filing_type: str,
    s3_client,
    company_name: str = "DataThon2025",
    email: str = "user@example.com",
    limit: int = 1
) -> Dict[str, Any]:
    """
    Download a filing and upload directly to S3.
    
    Args:
        ticker: Stock ticker symbol
        filing_type: Filing type ('10-K', '10-Q', '8-K')
        s3_client: S3Client instance
        company_name: Company name for SEC user-agent
        email: Email for SEC user-agent
        limit: Maximum number of filings to download (default: 1 for latest)
        
    Returns:
        Dict with success status and file info
    """
    try:
        from sec_edgar_downloader import Downloader
        
        # Create temporary directory for sec-edgar-downloader (it needs disk space)
        # We'll read from it and delete immediately
        temp_dir = tempfile.mkdtemp(prefix=f"sec_edgar_{ticker}_")
        
        try:
            # Initialize downloader with temp directory
            dl = Downloader(company_name, email, temp_dir)
            
            # Add small random delay to respect SEC rate limits
            # SEC recommends delays between requests
            time.sleep(random.uniform(0.1, 0.5))
            
            # Download filing (will save to temp_dir)
            # Note: sec-edgar-downloader saves to disk, we'll read and upload immediately
            # Using limit parameter to get latest filing only
            count = dl.get(filing_type, ticker, limit=limit)
            
            if count == 0:
                logger.warning(f"[WARN] No {filing_type} filings found for {ticker}")
                return {
                    'ticker': ticker,
                    'filing_type': filing_type,
                    'success': False,
                    'error': 'No filings found'
                }
            
            # Find the downloaded file(s)
            # sec-edgar-downloader structure: sec-edgar-filings/{ticker}/{filing_type}/{accession_number}/
            ticker_dir = Path(temp_dir) / "sec-edgar-filings" / ticker / filing_type
            if not ticker_dir.exists():
                return {
                    'ticker': ticker,
                    'filing_type': filing_type,
                    'success': False,
                    'error': 'Download directory not found'
                }
            
            # Get the most recent filing (if multiple)
            filing_dirs = sorted(ticker_dir.iterdir(), key=lambda x: x.name, reverse=True)
            if not filing_dirs:
                return {
                    'ticker': ticker,
                    'filing_type': filing_type,
                    'success': False,
                    'error': 'No filing directories found'
                }
            
            latest_filing_dir = filing_dirs[0]
            
            # Find files in the filing directory
            # Priority: .html files, then full-submission.txt
            html_files = list(latest_filing_dir.glob("*.html"))
            txt_files = list(latest_filing_dir.glob("*.txt"))
            
            if html_files:
                filing_file = html_files[0]
            elif txt_files:
                # Use full-submission.txt (contains HTML content)
                filing_file = latest_filing_dir / "full-submission.txt"
                if not filing_file.exists():
                    filing_file = txt_files[0]
            else:
                return {
                    'ticker': ticker,
                    'filing_type': filing_type,
                    'success': False,
                    'error': 'No HTML or TXT file found in filing'
                }
            
            # Read file content
            with open(filing_file, 'rb') as f:
                file_content = f.read()
            
            # Extract filing date from SEC header
            # The header contains "FILED AS OF DATE: YYYYMMDD" which is the actual filing date
            filing_date = None
            try:
                # Read first 10KB to find the header (date info is usually at the top)
                header_content = file_content[:10000].decode('utf-8', errors='ignore')
                
                # Look for "FILED AS OF DATE: YYYYMMDD"
                date_match = re.search(r'FILED AS OF DATE:\s*(\d{8})', header_content, re.IGNORECASE)
                if date_match:
                    date_str = date_match.group(1)
                    # Convert YYYYMMDD to YYYY-MM-DD
                    filing_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
                    logger.debug(f"[DEBUG] Extracted filing date: {filing_date} from header")
                
                # Fallback: Try ACCEPTANCE-DATETIME if FILED AS OF DATE not found
                if not filing_date:
                    date_match = re.search(r'<ACCEPTANCE-DATETIME>(\d{8})', header_content, re.IGNORECASE)
                    if date_match:
                        date_str = date_match.group(1)
                        filing_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
                        logger.debug(f"[DEBUG] Extracted filing date: {filing_date} from ACCEPTANCE-DATETIME")
                
            except Exception as e:
                logger.warning(f"[WARN] Could not extract filing date from header: {e}")
            
            # Final fallback: Use accession number year
            if not filing_date:
                accession = latest_filing_dir.name
                if len(accession) >= 15 and '-' in accession:
                    parts = accession.split('-')
                    if len(parts) >= 2:
                        try:
                            year_suffix = int(parts[1])
                            year = 2000 + year_suffix
                            filing_date = f"{year}-01-01"  # Approximate
                            logger.warning(f"[WARN] Using approximate date from accession: {filing_date}")
                        except ValueError:
                            pass
                
                # Ultimate fallback: today's date
                if not filing_date:
                    filing_date = datetime.now().strftime('%Y-%m-%d')
                    logger.warning(f"[WARN] Using today's date as fallback: {filing_date}")
            
            # Determine file extension based on actual file
            file_ext = filing_file.suffix if filing_file.suffix else '.html'
            
            # Generate S3 key
            # Format: input/filings/{ticker}/{filing_date}-{filing_type}-{ticker}{ext}
            s3_key = f"input/filings/{ticker}/{filing_date}-{filing_type.lower()}-{ticker}{file_ext}"
            
            # Upload directly to S3
            success = s3_client.write_content(file_content, s3_key)
            
            if success:
                logger.info(f"[OK] Downloaded and uploaded {filing_type} for {ticker}: {s3_key}")
                return {
                    'ticker': ticker,
                    'filing_type': filing_type,
                    'filing_date': filing_date,
                    's3_key': s3_key,
                    'size_bytes': len(file_content),
                    'success': True
                }
            else:
                return {
                    'ticker': ticker,
                    'filing_type': filing_type,
                    'success': False,
                    'error': 'S3 upload failed'
                }
                
        finally:
            # Cleanup temp directory
            if Path(temp_dir).exists():
                shutil.rmtree(temp_dir)
                
    except Exception as e:
        logger.error(f"[ERROR] Failed to download {filing_type} for {ticker}: {e}")
        return {
            'ticker': ticker,
            'filing_type': filing_type,
            'success': False,
            'error': str(e)
        }


def download_ticker_filings(
    ticker: str,
    filing_types: List[str],
    s3_client,
    company_name: str = "DataThon2025",
    email: str = "user@example.com"
) -> Dict[str, Any]:
    """
    Download all filing types for a ticker.
    
    Args:
        ticker: Stock ticker symbol
        filing_types: List of filing types to download
        s3_client: S3Client instance
        company_name: Company name for SEC user-agent
        email: Email for SEC user-agent
        
    Returns:
        Dict with results for each filing type
    """
    results = {
        'ticker': ticker,
        'filings': {}
    }
    
    for filing_type in filing_types:
        result = download_filing_to_s3(
            ticker=ticker,
            filing_type=filing_type,
            s3_client=s3_client,
            company_name=company_name,
            email=email,
            limit=1  # Get latest filing only
        )
        results['filings'][filing_type] = result
    
    return results


def worker_download_ticker(args):
    """
    Worker function for multiprocessing.
    
    Args:
        args: Tuple of (ticker, filing_types, s3_bucket, s3_region, company_name, email)
        
    Returns:
        Dict with download results
    """
    ticker, filing_types, s3_bucket, s3_region, company_name, email = args
    
    # Create S3 client in worker process (boto3 is thread-safe but process-safe too)
    from src.utils.s3_client import S3Client
    s3_client = S3Client(bucket_name=s3_bucket, region=s3_region)
    
    return download_ticker_filings(
        ticker=ticker,
        filing_types=filing_types,
        s3_client=s3_client,
        company_name=company_name,
        email=email
    )


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Download SEC filings for S&P 500 companies and upload to S3"
    )
    
    parser.add_argument(
        '--csv',
        type=str,
        default='data/initial-dataset/2025-08-15_composition_sp500.csv',
        help='Path to S&P 500 composition CSV'
    )
    
    parser.add_argument(
        '--filing-types',
        type=str,
        nargs='+',
        default=['10-K', '10-Q', '8-K'],
        help='Filing types to download (default: 10-K 10-Q 8-K)'
    )
    
    parser.add_argument(
        '--workers',
        type=int,
        default=4,
        help='Number of parallel worker processes (default: 4)'
    )
    
    parser.add_argument(
        '--max-tickers',
        type=int,
        help='Maximum number of tickers to process (for testing)'
    )
    
    parser.add_argument(
        '--company-name',
        type=str,
        default='DataThon2025',
        help='Company name for SEC user-agent'
    )
    
    parser.add_argument(
        '--email',
        type=str,
        default='datathon@example.com',
        help='Email for SEC user-agent'
    )
    
    args = parser.parse_args()
    
    # Load S&P 500 tickers
    csv_path = Path(args.csv)
    if not csv_path.exists():
        logger.error(f"[ERROR] CSV file not found: {csv_path}")
        return
    
    logger.info(f"[INFO] Loading tickers from {csv_path}")
    df = pd.read_csv(csv_path)
    
    # Extract tickers (handle European decimal format and special cases)
    tickers = df['Symbol'].str.strip().str.upper().tolist()
    
    # Fix tickers with comma issues (e.g., "BRK,B" -> "BRK.B")
    tickers = [ticker.replace(',', '.') for ticker in tickers]
    
    # Remove any tickers with spaces (invalid)
    tickers = [ticker for ticker in tickers if ' ' not in ticker and len(ticker) > 0]
    
    logger.info(f"[INFO] Loaded {len(tickers)} valid tickers")
    
    if args.max_tickers:
        tickers = tickers[:args.max_tickers]
        logger.info(f"[INFO] Processing first {args.max_tickers} tickers (testing mode)")
    
    logger.info(f"[INFO] Found {len(tickers)} tickers")
    logger.info(f"[INFO] Filing types: {args.filing_types}")
    logger.info(f"[INFO] Workers: {args.workers}")
    
    # Get S3 client
    s3_client = get_s3_client()
    if not s3_client:
        logger.error("[ERROR] S3 client not available. Check AWS credentials.")
        return
    
    # Prepare arguments for workers
    worker_args = [
        (
            ticker,
            args.filing_types,
            s3_client.bucket_name,
            s3_client.region,
            args.company_name,
            args.email
        )
        for ticker in tickers
    ]
    
    # Process with multiprocessing
    logger.info(f"[INFO] Starting download with {args.workers} workers...")
    
    results = []
    successful = 0
    failed = 0
    
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        # Submit all tasks
        futures = {executor.submit(worker_download_ticker, args): args[0] for args in worker_args}
        
        # Process completed tasks
        for future in as_completed(futures):
            ticker = futures[future]
            try:
                result = future.result()
                results.append(result)
                
                # Count successes/failures
                ticker_success = any(
                    f.get('success', False) 
                    for f in result.get('filings', {}).values()
                )
                
                if ticker_success:
                    successful += 1
                else:
                    failed += 1
                
                # Log progress
                processed = successful + failed
                if processed % 10 == 0:
                    logger.info(f"[INFO] Progress: {processed}/{len(tickers)} ({successful} successful, {failed} failed)")
                    
            except Exception as e:
                logger.error(f"[ERROR] Worker failed for {ticker}: {e}")
                failed += 1
    
    # Summary
    logger.info("="*60)
    logger.info("[INFO] Download Summary")
    logger.info("="*60)
    logger.info(f"Total tickers processed: {len(tickers)}")
    logger.info(f"Successful: {successful}")
    logger.info(f"Failed: {failed}")
    
    # Count by filing type
    filing_counts = {}
    for result in results:
        for filing_type, filing_result in result.get('filings', {}).items():
            if filing_result.get('success'):
                filing_counts[filing_type] = filing_counts.get(filing_type, 0) + 1
    
    logger.info("\nFiling counts by type:")
    for filing_type, count in filing_counts.items():
        logger.info(f"  {filing_type}: {count}")
    
    logger.info("\n[OK] Download complete!")


if __name__ == "__main__":
    main()

