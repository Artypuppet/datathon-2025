# Testing Guide

This guide covers all testing approaches for the PolyFinances Datathon 2025 project.

## Overview

We have multiple testing strategies:
1. **Unit Tests** - Test individual parser components (pytest)
2. **Manual Tests** - Quick verification without pytest
3. **Integration Tests** - Test parser + S3 integration
4. **End-to-End Tests** - Full workflow testing

## Quick Start

### Prerequisites

First, set up the environment (if not done):
```bash
# Create conda environment
conda env create -f environment-local.yml

# Activate environment
conda activate datathon-local

# Install PyTorch (choose your CUDA version)
./install_pytorch_gpu.sh

# Download spaCy model (use direct pip install to avoid 404 errors)
pip install https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.1/en_core_web_sm-3.7.1-py3-none-any.whl
```

### Run All Tests

```bash
# All unit tests
pytest tests/unit/ -v

# With coverage report
pytest tests/unit/ --cov=src --cov-report=html

# Specific parser tests
pytest tests/unit/test_csv_parser.py -v
pytest tests/unit/test_html_filing_parser.py -v
pytest tests/unit/test_html_legislation_parser.py -v
```

### Quick Manual Test (No Setup Required)

```bash
# Test all parsers without pytest
python test_parsers_manual.py

# Test CSV parser only
python test_csv_parser_manual.py
```

## Unit Tests

### Location
```
tests/
├── __init__.py
├── conftest.py                          # Pytest configuration and fixtures
└── unit/
    ├── test_csv_parser.py               # 10 tests for CSV parser
    ├── test_html_filing_parser.py       # 15 tests for filing parser
    └── test_html_legislation_parser.py  # 15 tests for legislation parser
```

### Running Unit Tests

**All tests:**
```bash
pytest tests/unit/ -v
```

**Specific test file:**
```bash
pytest tests/unit/test_csv_parser.py -v
```

**Specific test:**
```bash
pytest tests/unit/test_csv_parser.py::TestCSVParser::test_parse_composition_csv -v
```

**With output:**
```bash
pytest tests/unit/ -v -s
```

**Stop on first failure:**
```bash
pytest tests/unit/ -x
```

### Coverage Reports

**Terminal report:**
```bash
pytest tests/unit/ --cov=src/parsers --cov-report=term-missing
```

**HTML report:**
```bash
pytest tests/unit/ --cov=src/parsers --cov-report=html
# Open htmlcov/index.html in browser
```

**Generate coverage badge:**
```bash
pytest tests/unit/ --cov=src/parsers --cov-report=json
```

### Test Structure

Each parser has comprehensive tests:

**CSV Parser (10 tests):**
- Valid composition CSV parsing
- Valid performance CSV parsing
- European decimal format handling
- Malformed data handling
- Empty file handling
- Data type detection
- Date extraction
- Metadata completeness

**HTML Filing Parser (15 tests):**
- Valid 10-K parsing
- Valid 10-Q parsing
- File identification
- Ticker/CIK extraction
- Date extraction
- Section extraction
- Malformed HTML handling
- Empty file handling
- Metadata completeness

**Legislation Parser (15 tests):**
- EU directive parsing
- US bill (XML) parsing
- Chinese law parsing
- Jurisdiction detection (EU, US, CN)
- Language detection
- Official identifier extraction
- Section extraction
- Empty file handling
- Metadata completeness

## Manual Tests

### test_parsers_manual.py

Comprehensive manual test that works without pytest:

```bash
python test_parsers_manual.py
```

**What it does:**
1. Creates sample test files
2. Tests CSV parser
3. Tests filing parser
4. Tests legislation parser
5. Tests parser factory
6. Cleans up temp files

**Output:**
```
============================================================
PARSER MANUAL TEST SUITE
============================================================

============================================================
TEST: CSV Parser
============================================================
File: 2024-01-01-composition-TEST.csv
Can parse: True
Success: True
Document type: csv_financial
...
[OK] CSV Parser test passed!

============================================================
TEST: HTML Filing Parser
============================================================
...
[OK] Filing Parser test passed!

============================================================
ALL TESTS PASSED
============================================================
```

### test_csv_parser_manual.py

Focused CSV parser test:

```bash
python test_csv_parser_manual.py
```

Tests composition and performance CSVs with detailed output.

## Integration Tests

### Test Parsers with Local Files

**Step 1: Prepare test data**
```bash
mkdir -p data/test
# Add sample files to data/test/
```

**Step 2: Run batch parser**
```bash
python parse_batch.py --local --input data/test/ --output output/test/
```

**Step 3: Verify output**
```bash
ls output/test/
cat output/test/batch_results.json
```

### Test with S3 Integration

**Step 1: Configure S3**
```bash
cp .env.example .env
# Edit .env with your AWS credentials
```

**Step 2: Test S3 connection**
```python
from src.utils import get_s3_client

s3 = get_s3_client()
if s3:
    print("S3 connected!")
    files = s3.list_files()
    print(f"Files: {len(files)}")
```

**Step 3: Run examples**
```bash
python examples/parse_single_file.py
```

**Step 4: Test S3 batch parsing**
```bash
# Upload test files first
aws s3 cp data/test/ s3://your-bucket/input/test/ --recursive

# Parse from S3
python parse_batch.py --s3 --input-prefix input/test/ --output-prefix parsed/test/
```

## Test Data

### Sample Files Location

Unit tests use pytest fixtures that create temporary test files. For manual testing:

```
data/
├── test/                    # Manual test files
│   ├── *.csv               # Sample CSV files
│   ├── *.html              # Sample filing/legislation files
│   └── *.xml               # Sample US bills
└── README.md
```

### Creating Test Data

**CSV (Composition):**
```csv
Name;Country;Ticker;Weight
Apple Inc.;United States;AAPL;7.5
Microsoft Corp.;United States;MSFT;6.8
```

**CSV (Performance):**
```csv
Date;Price;Change
2024-01-01;100.50;2.5
2024-01-02;102.00;1.5
```

**10-K Filing:**
```html
<html>
<head><title>Apple Inc. 10-K</title></head>
<body>
    <div>CIK: 0000320193</div>
    <h2>Item 1. Business</h2>
    <p>Apple designs and manufactures...</p>
</body>
</html>
```

Save as: `2024-09-30-10k-AAPL.html`

**EU Directive:**
```html
<html>
<head><title>REGULATION (EU) 2024/1689</title></head>
<body>
    <h1>REGULATION (EU) 2024/1689 OF THE EUROPEAN PARLIAMENT</h1>
    <section>
        <h2>Article 1</h2>
        <p>This Regulation lays down rules on AI...</p>
    </section>
</body>
</html>
```

Save in: `data/test/directives/`

## Continuous Testing

### Pre-commit Tests

Run before committing:
```bash
# Quick test
python test_parsers_manual.py

# Full test suite
pytest tests/unit/ -v
```

### CI/CD Integration

For GitHub Actions (future):
```yaml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: conda-incubator/setup-miniconda@v2
      - run: conda env create -f environment-local.yml
      - run: conda activate datathon-local
      - run: pytest tests/unit/ -v --cov=src
```

## Debugging Tests

### Run with Debug Output

```bash
# Print statements
pytest tests/unit/ -v -s

# Debug on failure
pytest tests/unit/ --pdb

# Verbose logging
pytest tests/unit/ -v --log-cli-level=DEBUG
```

### Check Specific Test

```python
# Run single test interactively
python -m pytest tests/unit/test_csv_parser.py::TestCSVParser::test_parse_composition_csv -v -s
```

### Inspect Test Fixtures

```python
# In test file
def test_debug_fixture(sample_composition_csv):
    print(f"File: {sample_composition_csv}")
    print(f"Content: {sample_composition_csv.read_text()}")
    assert False  # Force stop to see output
```

## Performance Testing

### Time Individual Tests

```bash
pytest tests/unit/ -v --durations=10
```

### Profile Tests

```bash
pip install pytest-profiling
pytest tests/unit/ --profile
```

### Benchmark Parsing

```python
import time
from pathlib import Path
from src.parsers import ParserFactory

factory = ParserFactory()
file_path = Path("data/large_file.html")

start = time.time()
result = factory.parse_file(file_path)
duration = time.time() - start

print(f"Parse time: {duration:.2f}s")
```

## Troubleshooting

### Issue: pytest not found

**Solution:**
```bash
conda activate datathon-local
# If still not found:
conda install pytest pytest-cov
```

### Issue: Import errors

**Solution:**
```bash
# Run from project root
cd /home/artypuppet/datathon-2025
python -m pytest tests/unit/ -v
```

### Issue: Module not found (bs4, langdetect, etc.)

**Solution:**
```bash
# Make sure environment is activated
conda activate datathon-local

# Check installed packages
conda list | grep beautifulsoup
conda list | grep langdetect

# If missing, install
conda install beautifulsoup4 lxml langdetect
```

### Issue: Temp files not cleaned up

**Solution:**
```bash
# Manual cleanup
rm -rf test_data_manual/
rm -rf output/test/
rm -rf /tmp/pytest-*
```

### Issue: S3 tests failing

**Solution:**
```bash
# Check .env file
cat .env

# Test S3 connection
python -c "from src.utils import get_s3_client; print(get_s3_client())"

# Skip S3 tests
pytest tests/unit/ -v -k "not s3"
```

## Best Practices

### 1. Run Tests Before Committing
```bash
pytest tests/unit/ -v && git commit
```

### 2. Write Tests for New Features
- Add test when adding new parser
- Add test when fixing bug
- Follow existing test structure

### 3. Keep Tests Fast
- Use small sample files
- Mock external services (S3) when possible
- Use fixtures for setup/teardown

### 4. Test Edge Cases
- Empty files
- Malformed data
- Missing fields
- Large files
- Non-ASCII characters

### 5. Maintain Test Coverage
- Target: >80% coverage
- Check with: `pytest --cov=src --cov-report=term-missing`

## Test Checklist

Before merging code:

- [ ] All unit tests pass (`pytest tests/unit/ -v`)
- [ ] Manual tests pass (`python test_parsers_manual.py`)
- [ ] Code coverage >80% (`pytest --cov=src`)
- [ ] No linter errors
- [ ] New features have tests
- [ ] Documentation updated
- [ ] Test data cleaned up

## Next Steps

1. **Set up environment**: Follow instructions at top
2. **Run manual tests**: `python test_parsers_manual.py`
3. **Run unit tests**: `pytest tests/unit/ -v`
4. **Check coverage**: `pytest tests/unit/ --cov=src --cov-report=html`
5. **Add S3 tests**: See `S3_INTEGRATION.md`

## Related Documentation

- [Setup Guide](../04_setup_environment.md)
- [S3 Integration](../S3_INTEGRATION.md)
- [Code Style](../STYLE_GUIDE.md)
- [Testing Strategy](../.cursor/references/testing_strategy.md)

