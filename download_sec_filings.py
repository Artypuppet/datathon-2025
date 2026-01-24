"""
Download SEC filings (10-K, 10-Q, 8-K) for companies and save locally.

Uses sec-edgar-downloader with multiprocessing to download filings to local disk.
Files are saved to data/filings/{ticker}/{date}-{type}.html
"""

import sys
import logging
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed
import tempfile
import shutil
import time
import random
import re

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


def download_filing_local(
    ticker: str,
    filing_type: str,
    output_dir: Path,
    company_name: str = "DataThon2025",
    email: str = "user@example.com",
    limit: int = 1
) -> Dict[str, Any]:
    """
    Download a filing and save to local disk.
    
    Args:
        ticker: Stock ticker symbol
        filing_type: Filing type ('10-K', '10-Q', '8-K')
        output_dir: Base output directory (files saved to output_dir/filings/{ticker}/)
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
            
            # Create output directory structure: data/filings/{ticker}/
            ticker_output_dir = output_dir / "filings" / ticker
            ticker_output_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate filename: {filing_date}-{filing_type}-{ticker}{ext}
            filename = f"{filing_date}-{filing_type.lower()}-{ticker}{file_ext}"
            output_path = ticker_output_dir / filename
            
            # Save file locally
            with open(output_path, 'wb') as f:
                f.write(file_content)
            
            logger.info(f"[OK] Downloaded and saved {filing_type} for {ticker}: {output_path}")
            return {
                'ticker': ticker,
                'filing_type': filing_type,
                'filing_date': filing_date,
                'local_path': str(output_path),
                'size_bytes': len(file_content),
                'success': True
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
    output_dir: Path,
    company_name: str = "DataThon2025",
    email: str = "user@example.com"
) -> Dict[str, Any]:
    """
    Download all filing types for a ticker.
    
    Args:
        ticker: Stock ticker symbol
        filing_types: List of filing types to download
        output_dir: Base output directory
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
        result = download_filing_local(
            ticker=ticker,
            filing_type=filing_type,
            output_dir=output_dir,
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
        args: Tuple of (ticker, filing_types, output_dir, company_name, email)
        
    Returns:
        Dict with download results
    """
    ticker, filing_types, output_dir_str, company_name, email = args
    output_dir = Path(output_dir_str)
    
    return download_ticker_filings(
        ticker=ticker,
        filing_types=filing_types,
        output_dir=output_dir,
        company_name=company_name,
        email=email
    )


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Download SEC filings for companies and save locally"
    )
    
    parser.add_argument(
        '--output-dir',
        type=str,
        default='data',
        help='Output directory for filings (default: data)'
    )
    
    parser.add_argument(
        '--tickers',
        type=str,
        help='Comma-separated list of tickers to download (e.g., "AAPL,MSFT,GOOGL")'
    )
    
    parser.add_argument(
        '--csv',
        type=str,
        help='Path to CSV file with tickers (alternative to --tickers). CSV must have a "Symbol" column.'
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
        help='Maximum number of tickers to process (for testing, only applies when using --csv)'
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
    
    # Get tickers from either --tickers argument or --csv file
    tickers = []
    
    if args.tickers:
        # Parse comma-separated tickers
        tickers = [t.strip().upper() for t in args.tickers.split(',')]
        tickers = [t for t in tickers if t and ' ' not in t]  # Remove empty and invalid tickers
        logger.info(f"[INFO] Using {len(tickers)} tickers from --tickers argument: {', '.join(tickers)}")
    
    elif args.csv:
        # Load tickers from CSV file
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
        
        logger.info(f"[INFO] Loaded {len(tickers)} valid tickers from CSV")
        
        if args.max_tickers:
            tickers = tickers[:args.max_tickers]
            logger.info(f"[INFO] Processing first {args.max_tickers} tickers (testing mode)")
    
    else:
        logger.error("[ERROR] Must provide either --tickers or --csv argument")
        parser.print_help()
        return
    
    if not tickers:
        logger.error("[ERROR] No valid tickers found")
        return
    
    logger.info(f"[INFO] Found {len(tickers)} tickers")
    logger.info(f"[INFO] Filing types: {args.filing_types}")
    logger.info(f"[INFO] Workers: {args.workers}")
    logger.info(f"[INFO] Output directory: {args.output_dir}")
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Prepare arguments for workers
    worker_args = [
        (
            ticker,
            args.filing_types,
            str(output_dir),
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

