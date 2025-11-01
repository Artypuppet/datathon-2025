#!/usr/bin/env python
"""
Batch parsing script - supports both local and S3 modes.

Usage:
    # Parse local files
    python parse_batch.py --local --input data/ --output output/

    # Parse files from S3
    python parse_batch.py --s3 --input-prefix input/filings/ --output-prefix parsed/

    # Parse local files and upload to S3
    python parse_batch.py --local --input data/ --upload-to-s3

    # Parse S3 files and save locally
    python parse_batch.py --s3 --input-prefix input/filings/ --save-local
"""

import argparse
import logging
from pathlib import Path
import json
from dotenv import load_dotenv

from src.parsers.parser_runner import ParserRunner
from src.utils.s3_client import get_s3_client

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)


def parse_local_batch(args):
    """Parse files from local directory."""
    input_dir = Path(args.input)
    
    if not input_dir.exists():
        logger.error(f"[ERROR] Input directory not found: {input_dir}")
        return
    
    # Initialize runner
    s3_client = get_s3_client() if args.upload_to_s3 else None
    runner = ParserRunner(
        s3_client=s3_client,
        local_output_dir=Path(args.output) if args.output else None
    )
    
    # Run batch processing
    logger.info(f"[INFO] Starting batch processing of: {input_dir}")
    results = runner.batch_parse_local(
        input_dir=input_dir,
        save_to_s3=args.upload_to_s3,
        s3_output_prefix=args.output_prefix,
        file_pattern=args.pattern
    )
    
    # Print summary
    print("\n" + "="*60)
    print("BATCH PROCESSING SUMMARY")
    print("="*60)
    print(f"Total files: {results['total_files']}")
    print(f"Successful: {results['successful']}")
    print(f"Failed: {results['failed']}")
    print(f"Success rate: {results['successful']/results['total_files']*100:.1f}%")
    
    # Save detailed results
    results_file = Path(args.output) / "batch_results.json"
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nDetailed results saved to: {results_file}")


def parse_s3_batch(args):
    """Parse files from S3."""
    # Initialize runner
    s3_client = get_s3_client()
    if not s3_client:
        logger.error("[ERROR] S3 not configured. Check environment variables.")
        return
    
    runner = ParserRunner(
        s3_client=s3_client,
        local_output_dir=Path(args.output) if args.output else None
    )
    
    # Run batch processing
    logger.info(f"[INFO] Starting S3 batch processing: {args.input_prefix}")
    results = runner.batch_parse_s3(
        s3_input_prefix=args.input_prefix,
        s3_output_prefix=args.output_prefix,
        suffix_filter=args.suffix,
        save_locally=args.save_local
    )
    
    # Print summary
    print("\n" + "="*60)
    print("S3 BATCH PROCESSING SUMMARY")
    print("="*60)
    print(f"Total files: {results['total_files']}")
    print(f"Successful: {results['successful']}")
    print(f"Failed: {results['failed']}")
    print(f"Success rate: {results['successful']/results['total_files']*100:.1f}%")
    
    # Save detailed results
    if args.save_local:
        results_file = Path(args.output) / "batch_results.json"
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nDetailed results saved to: {results_file}")


def main():
    parser = argparse.ArgumentParser(
        description='Batch parse files from local or S3',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    # Mode selection
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument('--local', action='store_true',
                           help='Parse local files')
    mode_group.add_argument('--s3', action='store_true',
                           help='Parse files from S3')
    
    # Input options
    parser.add_argument('--input', type=str,
                       help='Local input directory (for --local mode)')
    parser.add_argument('--input-prefix', type=str,
                       help='S3 input prefix (for --s3 mode, e.g., "input/filings/")')
    
    # Output options
    parser.add_argument('--output', type=str, default='output',
                       help='Local output directory (default: output/)')
    parser.add_argument('--output-prefix', type=str, default='parsed/',
                       help='S3 output prefix (default: parsed/)')
    
    # Additional options
    parser.add_argument('--pattern', type=str, default='*',
                       help='File pattern for local mode (default: *)')
    parser.add_argument('--suffix', type=str, default='',
                       help='File suffix filter for S3 mode (e.g., .html)')
    parser.add_argument('--upload-to-s3', action='store_true',
                       help='Upload local results to S3')
    parser.add_argument('--save-local', action='store_true',
                       help='Save S3 results locally')
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.local and not args.input:
        parser.error("--local requires --input")
    if args.s3 and not args.input_prefix:
        parser.error("--s3 requires --input-prefix")
    
    # Run appropriate mode
    try:
        if args.local:
            parse_local_batch(args)
        else:
            parse_s3_batch(args)
    except KeyboardInterrupt:
        logger.info("\n[INFO] Interrupted by user")
    except Exception as e:
        logger.error(f"[ERROR] Fatal error: {e}", exc_info=True)


if __name__ == '__main__':
    main()

