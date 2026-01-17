#!/usr/bin/env python
"""
SageMaker Entry Point for Batch Embedding Generation

This is the entry point script that SageMaker will execute.
It handles environment setup and calls the main batch processing script.
"""

import os
import sys
import logging
from pathlib import Path

# Add scripts to path
scripts_dir = Path(__file__).parent
sys.path.insert(0, str(scripts_dir.parent))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

logger = logging.getLogger(__name__)


def main():
    """SageMaker entry point."""
    logger.info("=" * 80)
    logger.info("SageMaker Batch Embedding Job Starting")
    logger.info("=" * 80)
    
    # Log environment
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Working directory: {os.getcwd()}")
    
    # SageMaker environment variables
    if 'SM_MODEL_DIR' in os.environ:
        logger.info(f"SageMaker model directory: {os.environ['SM_MODEL_DIR']}")
    
    if 'SM_OUTPUT_DATA_DIR' in os.environ:
        logger.info(f"SageMaker output directory: {os.environ['SM_OUTPUT_DATA_DIR']}")
    
    if 'SM_INPUT_DATA_DIR' in os.environ:
        logger.info(f"SageMaker input directory: {os.environ['SM_INPUT_DATA_DIR']}")
    
    # Parse command line arguments (passed from SageMaker job)
    import argparse
    parser = argparse.ArgumentParser()
    
    # Import and call batch processor
    from batch_embed_all_tickers import main as batch_main
    
    # Execute batch processing
    # Arguments should be passed from SageMaker job configuration
    exit_code = batch_main()
    
    logger.info("=" * 80)
    logger.info(f"SageMaker Batch Embedding Job Complete (exit code: {exit_code})")
    logger.info("=" * 80)
    
    return exit_code


if __name__ == "__main__":
    sys.exit(main())

