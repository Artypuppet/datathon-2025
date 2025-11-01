"""
Pytest configuration and shared fixtures.
"""

import pytest
import logging


@pytest.fixture(autouse=True)
def setup_logging():
    """Configure logging for tests."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


@pytest.fixture
def sample_tickers():
    """Common ticker symbols for testing."""
    return ['AAPL', 'MSFT', 'GOOGL', 'NVDA', 'TSLA']

