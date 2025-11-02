#!/usr/bin/env python
"""
Test the MVP pipeline locally.
"""

import sys
from pathlib import Path
import logging
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)

sys.path.insert(0, str(Path(__file__).parent))

from src.pipeline import PipelineOrchestrator, PipelineConfig


def test_pipeline_dry_run():
    """Test pipeline in dry run mode."""
    print("\n" + "="*60)
    print("TEST: Pipeline Dry Run")
    print("="*60)
    
    config = PipelineConfig(dry_run=True, skip_embeddings=True)
    orchestrator = PipelineOrchestrator(config=config)
    
    event = {
        'file_key': 'input/financial/2025-08-15_composition_sp500.csv',
        'timestamp': '2024-11-01T12:00:00Z',
        'dry_run': True
    }
    
    result = orchestrator.execute(event)
    
    print("\nResult:")
    print(f"  Status: {result['status']}")
    print(f"  File: {result['file_key']}")
    print(f"  Dry Run: {result['dry_run']}")
    
    return result['status'] == 'dry_run'


def test_pipeline_actual():
    """Test pipeline with actual S3 file."""
    print("\n" + "="*60)
    print("TEST: Pipeline Actual Processing")
    print("="*60)
    
    # Check if S3 has any files
    from src.utils import get_s3_client
    s3 = get_s3_client()
    if s3:
        files = s3.list_files()
        if not files:
            print("[SKIP] No files in S3 bucket to test with")
            print("[INFO] Upload some files first:")
            print("       python parse_batch.py --local --input data/initial-dataset/ --upload-to-s3")
            return True  # Not a failure, just skip
    else:
        print("[SKIP] S3 not configured")
        return True  # Not a failure, just skip
    
    config = PipelineConfig(dry_run=False, skip_embeddings=True)
    orchestrator = PipelineOrchestrator(config=config)
    
    # Use first available file in S3
    test_file = files[0] if files else None
    if not test_file:
        print("[SKIP] No files to test with")
        return True
    
    event = {
        'file_key': test_file,
        'timestamp': '2024-11-01T12:00:00Z',
        'dry_run': False
    }
    
    result = orchestrator.execute(event)
    
    print("\nResult:")
    print(f"  Status: {result['status']}")
    print(f"  File: {result['file_key']}")
    print(f"  Parsed: {result.get('parsed_key')}")
    print(f"  Document Type: {result.get('document_type')}")
    
    if 'stages' in result:
        print("\nStage Status:")
        for stage, status in result['stages'].items():
            print(f"  {stage}: {status}")
    
    return result['status'] == 'success'


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("PIPELINE TEST SUITE")
    print("="*60)
    
    try:
        # Test dry run
        dry_run_ok = test_pipeline_dry_run()
        
        # Test actual processing
        actual_ok = test_pipeline_actual()
        
        # Summary
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)
        print(f"Dry Run: {'[OK]' if dry_run_ok else '[FAIL]'}")
        print(f"Actual:  {'[OK]' if actual_ok else '[FAIL]'}")
        
        if dry_run_ok and actual_ok:
            print("\n[SUCCESS] All tests passed!")
            return 0
        else:
            print("\n[FAILURE] Some tests failed")
            return 1
    
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())

