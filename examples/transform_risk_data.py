#!/usr/bin/env python
"""
Example script to transform test results to risk dashboard format.

This script demonstrates how to convert test results JSON files
into the format expected by the risk dashboard.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.dashboard.data_transformer import RiskDataTransformer


def main():
    """Transform test results to dashboard format."""
    
    # Example: Transform AAPL test results
    input_file = Path("output/AAPL_opensearch_test_results.json")
    output_file = Path("output/risk_data.json")
    
    if not input_file.exists():
        print(f"[ERROR] Input file not found: {input_file}")
        print(f"[INFO] Please run vector similarity tests first")
        return
    
    print(f"[INFO] Transforming {input_file} to dashboard format...")
    
    transformer = RiskDataTransformer()
    profiles = transformer.transform_from_test_results(
        input_file,
        output_path=output_file
    )
    
    print(f"[OK] Transformed {len(profiles)} company profiles")
    print(f"[OK] Saved to {output_file}")
    print("\n[INFO] You can now load this file in the risk dashboard:")
    print(f"  streamlit run risk_dashboard.py")


if __name__ == "__main__":
    main()

