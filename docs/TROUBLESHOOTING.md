# Troubleshooting Guide

Common issues and solutions for the PolyFinances Datathon 2025 project.

## Environment Setup Issues

### Issue: "conda: command not found"

**Problem**: Conda is not installed or not in PATH.

**Solution**:
```bash
# Install Miniconda
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh
# Follow prompts and restart shell
```

### Issue: "Environment already exists"

**Problem**: Trying to create environment that already exists.

**Solution**:
```bash
# Remove old environment
conda env remove -n datathon-local

# Recreate
conda env create -f environment-local.yml
```

### Issue: Environment activation doesn't persist

**Problem**: Need to activate environment in each new shell.

**Solution**:
```bash
# Add to ~/.bashrc for automatic activation
echo "conda activate datathon-local" >> ~/.bashrc

# Or activate manually each time
conda activate datathon-local
```

## spaCy Issues

### Issue: HTTP 404 Error When Downloading spaCy Model

**Problem**: `python -m spacy download en_core_web_sm` returns 404 error.

**Error Message**:
```
ERROR: HTTP error 404 while getting https://github.com/explosion/spacy-models/releases/download/-en_core_web_sm/-en_core_web_sm.tar.gz
```

**Root Cause**: Bug in spaCy's download command that malforms the URL.

**Solution**: Use direct pip install instead:
```bash
conda activate datathon-local

pip install https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.1/en_core_web_sm-3.7.1-py3-none-any.whl
```

**Verify Installation**:
```bash
python -c "import spacy; nlp = spacy.load('en_core_web_sm'); print('OK')"
```

### Issue: "Can't find model 'en_core_web_sm'"

**Problem**: Model not installed or not found.

**Solution**:
```bash
conda activate datathon-local

# Install model
pip install https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.1/en_core_web_sm-3.7.1-py3-none-any.whl

# Verify
python -c "import spacy; spacy.load('en_core_web_sm')"
```

## PyTorch Issues

### Issue: "No module named 'torch'"

**Problem**: PyTorch not installed (needs separate install step).

**Solution**:
```bash
conda activate datathon-local

# For CUDA 12.1
pip install torch==2.1.2 --index-url https://download.pytorch.org/whl/cu121

# For CUDA 11.8
pip install torch==2.1.2 --index-url https://download.pytorch.org/whl/cu118

# For CPU only
pip install torch==2.1.2 --index-url https://download.pytorch.org/whl/cpu
```

### Issue: "CUDA out of memory"

**Problem**: GPU doesn't have enough memory for model.

**Solution**:
```bash
# Uninstall GPU version
pip uninstall torch

# Install CPU version
pip install torch==2.1.2 --index-url https://download.pytorch.org/whl/cpu
```

### Issue: "RuntimeError: CUDA error: no kernel image is available"

**Problem**: PyTorch CUDA version doesn't match your GPU's CUDA version.

**Solution**:
```bash
# Check your CUDA version
nvidia-smi

# Install matching PyTorch version
# For CUDA 12.x
pip install torch==2.1.2 --index-url https://download.pytorch.org/whl/cu121

# For CUDA 11.x
pip install torch==2.1.2 --index-url https://download.pytorch.org/whl/cu118
```

## Import Errors

### Issue: "No module named 'bs4'"

**Problem**: BeautifulSoup4 not installed.

**Solution**:
```bash
conda activate datathon-local
conda install beautifulsoup4 lxml
```

### Issue: "No module named 'boto3'"

**Problem**: AWS SDK not installed.

**Solution**:
```bash
conda activate datathon-local
conda install boto3
```

### Issue: "No module named 'src'"

**Problem**: Python can't find the src module.

**Solution**:
```bash
# Run from project root
cd /home/artypuppet/datathon-2025

# Or add to PYTHONPATH
export PYTHONPATH=/home/artypuppet/datathon-2025:$PYTHONPATH
```

## Testing Issues

### Issue: "pytest: command not found"

**Problem**: pytest not installed or environment not activated.

**Solution**:
```bash
conda activate datathon-local

# Check if installed
conda list pytest

# If not, install
conda install pytest pytest-cov
```

### Issue: Tests fail with import errors

**Problem**: Running tests from wrong directory or environment not activated.

**Solution**:
```bash
# Activate environment
conda activate datathon-local

# Run from project root
cd /home/artypuppet/datathon-2025

# Run tests
pytest tests/unit/ -v
```

### Issue: "No tests found"

**Problem**: Test discovery failed or wrong directory.

**Solution**:
```bash
# Make sure you're in project root
cd /home/artypuppet/datathon-2025

# Check test files exist
ls tests/unit/test_*.py

# Run with verbose discovery
pytest tests/unit/ -v --collect-only
```

## S3 Issues

### Issue: "S3 not configured"

**Problem**: Missing `.env` file or AWS credentials.

**Solution**:
```bash
# Copy template
cp .env.example .env

# Edit with your credentials
nano .env

# Add:
# AWS_ACCESS_KEY_ID=your_key
# AWS_SECRET_ACCESS_KEY=your_secret
# S3_BUCKET=your-bucket
```

### Issue: "Access Denied" on S3 operations

**Problem**: IAM permissions insufficient.

**Solution**: Ensure your IAM user has these permissions:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::your-bucket",
        "arn:aws:s3:::your-bucket/*"
      ]
    }
  ]
}
```

### Issue: "Bucket does not exist"

**Problem**: S3 bucket not created yet.

**Solution**:
```bash
# Create bucket
aws s3 mb s3://your-bucket-name --region us-east-1

# Verify
aws s3 ls
```

### Issue: S3 operations are slow

**Problem**: Downloading large files to disk.

**Solution**: Use memory operations instead:
```python
# Bad: disk IO
s3.download_file(key, temp_path)
with open(temp_path) as f:
    content = f.read()

# Good: memory only
content = s3.read_file_content(key)
```

## Parser Issues

### Issue: "No parser found for file"

**Problem**: File doesn't match any parser's `can_parse()` criteria.

**Solution**:
```bash
# Check filename format
# CSV: YYYY-MM-DD-type-name.csv
# Filing: YYYY-MM-DD-10k-TICKER.html
# Legislation: Must be in directives/ folder or have keywords

# Rename file to match pattern
mv document.html 2024-01-01-10k-AAPL.html
```

### Issue: "Parse failed" with valid file

**Problem**: File encoding or format issues.

**Solution**:
```bash
# Check file encoding
file -i your-file.html

# Convert to UTF-8 if needed
iconv -f ISO-8859-1 -t UTF-8 your-file.html > your-file-utf8.html

# Check for BOM
dos2unix your-file.html
```

### Issue: Parser extracts no sections

**Problem**: HTML structure doesn't match expected patterns.

**Solution**: The parser uses fallback extraction for unknown structures. Check logs:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
# Run parser again to see detailed logs
```

## Performance Issues

### Issue: Tests run very slowly

**Problem**: Loading large models or downloading data.

**Solution**:
```bash
# Run manual tests (faster)
python test_parsers_manual.py

# Skip slow tests
pytest tests/unit/ -v -m "not slow"

# Run in parallel
pytest tests/unit/ -v -n auto
```

### Issue: Parsing is very slow

**Problem**: Processing large files or complex HTML.

**Solution**:
- Parsers limit text extraction to prevent memory issues
- For large batches, use batch processing with parallelization (future feature)
- Consider using S3 for distributed processing

## WSL2-Specific Issues

### Issue: GPU not detected in WSL2

**Problem**: WSL2 can't access GPU.

**Solution**:
```bash
# Check CUDA availability
nvidia-smi

# If not available, install WSL2 CUDA drivers
# Follow: https://docs.nvidia.com/cuda/wsl-user-guide/index.html

# Or use CPU mode
pip install torch==2.1.2 --index-url https://download.pytorch.org/whl/cpu
```

### Issue: File permissions in WSL2

**Problem**: Scripts not executable.

**Solution**:
```bash
chmod +x setup_local.sh
chmod +x install_pytorch_gpu.sh
chmod +x run_tests.sh
```

## General Debugging

### Enable Verbose Logging

```python
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
```

### Check Environment

```bash
# Python version
python --version

# Conda environment
conda info --envs

# Installed packages
conda list

# CUDA version
nvidia-smi

# Disk space
df -h
```

### Get Help

1. Check documentation in `docs/` folder
2. Review examples in `examples/` folder
3. Check error logs carefully
4. Search for error message in GitHub issues
5. Verify environment is activated

## Quick Fixes Checklist

When something goes wrong:

- [ ] Is conda environment activated? (`conda activate datathon-local`)
- [ ] Are you in project root? (`cd /home/artypuppet/datathon-2025`)
- [ ] Is spaCy model installed? (`python -c "import spacy; spacy.load('en_core_web_sm')"`)
- [ ] Is PyTorch installed? (`python -c "import torch; print(torch.__version__)"`)
- [ ] Are dependencies up to date? (`conda env update -f environment-local.yml --prune`)
- [ ] Check logs for detailed error messages
- [ ] Try the quick test: `python test_quick.py`

## Still Having Issues?

1. Check this troubleshooting guide thoroughly
2. Review relevant documentation (see `docs/README.md`)
3. Check error messages and stack traces
4. Verify all dependencies installed
5. Try fresh environment: `conda env remove -n datathon-local && conda env create -f environment-local.yml`

---

**Last Updated**: 2024-11-01  
**For detailed setup instructions**: See `docs/QUICK_START.md`

