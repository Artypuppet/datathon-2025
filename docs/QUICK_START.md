# Quick Start Guide

Get up and running with the parser system in 5 minutes.

## Prerequisites

- Linux/WSL2/macOS
- Python 3.11
- Conda/Miniconda installed
- (Optional) NVIDIA GPU with CUDA for faster embeddings

## Setup (First Time)

### Step 1: Clone and Navigate

```bash
cd /home/artypuppet/datathon-2025
```

### Step 2: Create Environment

```bash
# Create conda environment (takes ~5 minutes)
conda env create -f environment-local.yml

# Activate environment
conda activate datathon-local
```

### Step 3: Install PyTorch (GPU Support)

```bash
# Check your CUDA version
nvidia-smi

# Run automated installer
./install_pytorch_gpu.sh
# Choose option based on your CUDA version:
# 1) CUDA 12.1
# 2) CUDA 11.8
# 3) CPU only
```

Or manually:
```bash
# For CUDA 12.1
pip install torch==2.1.2 --index-url https://download.pytorch.org/whl/cu121

# For CUDA 11.8
pip install torch==2.1.2 --index-url https://download.pytorch.org/whl/cu118

# For CPU only
pip install torch==2.1.2 --index-url https://download.pytorch.org/whl/cpu
```

### Step 4: Download spaCy Model

```bash
# Method 1 (Recommended - Direct pip install)
pip install https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.1/en_core_web_sm-3.7.1-py3-none-any.whl

# Method 2 (Alternative - may have issues)
# python -m spacy download en_core_web_sm
```

### Step 5: Verify Setup

```bash
# Test GPU (if applicable)
python check_gpu.py

# Test parsers
python test_parsers_manual.py
```

## Usage

### Parse Local Files

```bash
# Single file
python -c "
from pathlib import Path
from src.parsers import ParserFactory

factory = ParserFactory()
result = factory.parse_file(Path('data/your-file.html'))
print('Success!' if result.success else 'Failed')
"

# Batch processing
python parse_batch.py --local --input data/ --output output/
```

### Run Tests

```bash
# Quick manual test (no pytest needed)
python test_parsers_manual.py

# Full unit tests
pytest tests/unit/ -v

# With coverage
pytest tests/unit/ --cov=src --cov-report=html
```

## S3 Integration (Optional)

### Step 1: Configure AWS

```bash
# Copy template
cp .env.example .env

# Edit .env with your credentials
nano .env
```

Add:
```bash
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_REGION=us-east-1
S3_BUCKET=your-bucket-name
```

### Step 2: Create S3 Bucket

```bash
aws s3 mb s3://your-bucket-name --region us-east-1
```

### Step 3: Test S3

```bash
# Run examples
python examples/parse_single_file.py

# Parse from S3
python parse_batch.py --s3 --input-prefix input/ --output-prefix parsed/
```

## Common Commands

### Environment Management

```bash
# Activate environment
conda activate datathon-local

# Deactivate
conda deactivate

# Update environment
conda env update -f environment-local.yml --prune

# Remove environment
conda env remove -n datathon-local
```

### Testing

```bash
# Quick test (no setup needed)
python test_parsers_manual.py

# All unit tests
pytest tests/unit/ -v

# Specific test
pytest tests/unit/test_csv_parser.py -v

# With coverage
pytest tests/unit/ --cov=src/parsers --cov-report=html
```

### Parsing

```bash
# Local files
python parse_batch.py --local --input data/ --output output/

# From S3
python parse_batch.py --s3 --input-prefix input/filings/

# Local to S3
python parse_batch.py --local --input data/ --upload-to-s3
```

## Project Structure

```
datathon-2025/
├── src/
│   ├── parsers/          # Parser implementations
│   │   ├── base.py       # Abstract base class
│   │   ├── csv_parser.py
│   │   ├── html_filing_parser.py
│   │   ├── html_legislation_parser.py
│   │   ├── factory.py
│   │   └── parser_runner.py
│   └── utils/
│       └── s3_client.py  # S3 operations
├── tests/
│   └── unit/             # Unit tests (40+ tests)
├── data/                 # Input data
├── output/               # Parsed JSON output
├── examples/             # Usage examples
└── docs/                 # Documentation
```

## Next Steps

1. **Verify Setup**: `python test_parsers_manual.py`
2. **Parse Test Data**: `python parse_batch.py --local --input data/`
3. **Read Documentation**: 
   - [Testing Guide](TESTING.md)
   - [S3 Integration](../S3_INTEGRATION.md)
   - [Parser Implementation](../PARSERS_IMPLEMENTED.md)
4. **Configure S3**: Follow S3 section above
5. **Next Module**: Feature extraction and embeddings

## Troubleshooting

### "conda: command not found"
Install Miniconda: https://docs.conda.io/en/latest/miniconda.html

### "pytest not found"
```bash
conda activate datathon-local
conda list pytest
```

### "No module named 'bs4'"
```bash
conda activate datathon-local
conda install beautifulsoup4 lxml
```

### "CUDA out of memory"
Your GPU doesn't have enough memory. Use CPU mode:
```bash
pip uninstall torch
pip install torch==2.1.2 --index-url https://download.pytorch.org/whl/cpu
```

### "S3 not configured"
Either:
- Create `.env` file with AWS credentials
- Or use local-only mode (skip S3 setup)

## Getting Help

- Check documentation in `docs/` folder
- Review examples in `examples/` folder
- Check `.cursor/` folder for detailed specs
- Read error messages carefully

## Key Files

- `environment-local.yml` - Dependencies
- `.env.example` - Configuration template
- `parse_batch.py` - Batch processing tool
- `test_parsers_manual.py` - Quick test script
- `docs/TESTING.md` - Testing guide
- `S3_INTEGRATION.md` - S3 setup guide

## Support Matrix

| Feature | Status | Notes |
|---------|--------|-------|
| CSV Parsing | [OK] | Composition & performance |
| HTML Filing Parsing | [OK] | 10-K, 10-Q |
| Legislation Parsing | [OK] | EU, US, CN |
| Local Files | [OK] | Full support |
| S3 Integration | [OK] | Optional |
| GPU Support | [OK] | Optional, CUDA 11.8/12.1 |
| Unit Tests | [OK] | 40+ tests |
| Batch Processing | [OK] | CLI tool |

## MVP Checklist

- [x] Parser implementations (CSV, HTML filing, HTML legislation)
- [x] Unit tests (40+ tests)
- [x] S3 integration
- [x] Batch processing tool
- [x] Manual test scripts
- [x] Documentation
- [ ] Feature extraction module (next)
- [ ] Risk scoring module (next)
- [ ] Streamlit dashboard (next)

You are here: **Parsing Module Complete** → Next: **Feature Extraction**

