# S3 Integration - Complete Summary

## Overview

We've implemented full S3 integration for the parser system, supporting:
1. Reading input files from S3
2. Writing parsed JSON output to S3
3. Batch processing for both local and S3 storage
4. Flexible workflows for local development and cloud deployment

## What Was Implemented

### 1. S3 Client (`src/utils/s3_client.py`)

A robust S3 client with comprehensive operations:

**Reading:**
- `download_file()` - Download to disk
- `read_file_content()` - Read directly to memory (bytes)
- `read_text_file()` - Read as text/string

**Writing:**
- `upload_file()` - Upload from disk
- `write_content()` - Write bytes directly to S3
- `write_text()` - Write string to S3
- `write_json()` - Serialize and write JSON

**Management:**
- `list_files()` - List with prefix/suffix filters
- `file_exists()` - Check existence
- `get_file_size()` - Get file size
- `delete_file()` - Delete files

### 2. Parser Runner (`src/parsers/parser_runner.py`)

Orchestrates parsing with S3 support:

**Methods:**
- `parse_local_file()` - Parse local, optionally upload to S3
- `parse_s3_file()` - Parse from S3, save back to S3
- `batch_parse_local()` - Batch process local directory
- `batch_parse_s3()` - Batch process S3 prefix (folder)

### 3. Command-Line Tool (`parse_batch.py`)

Production-ready batch processing script:

```bash
# Parse local files
python parse_batch.py --local --input data/ --output output/

# Parse from S3
python parse_batch.py --s3 --input-prefix input/filings/ --output-prefix parsed/

# Parse local and upload to S3
python parse_batch.py --local --input data/ --upload-to-s3

# Parse S3 and save locally
python parse_batch.py --s3 --input-prefix input/ --save-local
```

### 4. Examples (`examples/parse_single_file.py`)

Working code examples showing:
- Parse local file
- Parse local and upload to S3
- Parse file from S3
- Direct S3 operations

### 5. Configuration Files

**`.env.example`** - Template for AWS configuration:
```bash
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_REGION=us-east-1
S3_BUCKET=datathon-2025-bucket
```

**`.gitignore`** - Protect sensitive files:
- Excludes `.env` from git
- Ignores temp files, outputs, etc.

### 6. Documentation

**`S3_INTEGRATION.md`** - Comprehensive guide covering:
- S3 basics and concepts
- Setup instructions
- Usage examples
- API reference
- Troubleshooting
- Best practices
- Cost analysis

## S3 Bucket Structure

```
s3://datathon-2025-bucket/
├── input/                    # Raw input files uploaded by users
│   ├── filings/             # 10-K/10-Q HTML files
│   ├── legislation/         # Legislation HTML/XML
│   └── financial/           # CSV files
│
├── parsed/                  # Parsed JSON output (intermediate representation)
│   ├── 2024-09-30-10k-AAPL.json
│   ├── EU_AI_ACT.json
│   └── 2024-01-01-composition-MSCI.json
│
├── embeddings/              # Vector embeddings (future module)
│   └── embeddings_batch_001.json
│
└── user_uploads/            # Files uploaded via Streamlit dashboard
    └── ...
```

## Complete Workflows

### Workflow 1: Local Development

```python
from pathlib import Path
from src.parsers import ParserRunner

# Initialize without S3
runner = ParserRunner()

# Parse local file
data = runner.parse_local_file(Path("data/2024-10k-AAPL.html"))

# Batch process
results = runner.batch_parse_local(
    input_dir=Path("data/"),
    file_pattern="*.html"
)

# Output saved to: output/*.json
```

### Workflow 2: Upload to S3 After Parsing

```python
from pathlib import Path
from src.parsers import ParserRunner
from src.utils import get_s3_client

# Initialize with S3
s3_client = get_s3_client()
runner = ParserRunner(s3_client=s3_client)

# Parse local and upload results
data = runner.parse_local_file(
    Path("data/2024-10k-AAPL.html"),
    save_to_s3=True,
    s3_output_prefix="parsed/"
)

# Result saved locally AND uploaded to S3
```

### Workflow 3: Parse Files from S3

```python
from src.parsers import ParserRunner
from src.utils import get_s3_client

# Initialize with S3
s3_client = get_s3_client()
runner = ParserRunner(s3_client=s3_client)

# Parse file from S3
data = runner.parse_s3_file(
    "input/filings/2024-09-30-10k-AAPL.html",
    save_to_s3=True,
    s3_output_prefix="parsed/"
)

# Input downloaded from S3, parsed, output uploaded to S3
```

### Workflow 4: User Upload via Streamlit

```python
import streamlit as st
from src.utils import get_s3_client
from src.parsers import ParserRunner
import tempfile
from pathlib import Path

# Initialize
s3 = get_s3_client()
runner = ParserRunner(s3_client=s3)

# File upload widget
uploaded_file = st.file_uploader("Upload document", type=["html", "csv", "xml"])

if uploaded_file:
    # Save to temp location
    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(uploaded_file.name).suffix) as tmp:
        tmp.write(uploaded_file.read())
        tmp_path = Path(tmp.name)
    
    try:
        # Upload to S3
        s3_key = f"user_uploads/{uploaded_file.name}"
        s3.upload_file(tmp_path, s3_key)
        
        # Parse the uploaded file
        with st.spinner("Processing document..."):
            data = runner.parse_s3_file(
                s3_key,
                save_to_s3=True,
                s3_output_prefix="parsed/"
            )
        
        if data:
            st.success("Document processed successfully!")
            
            # Trigger embedding update (future module)
            # update_embeddings(data)
            
    finally:
        tmp_path.unlink()
```

### Workflow 5: Batch Processing from S3

```bash
# Process all filings in S3
python parse_batch.py \
    --s3 \
    --input-prefix input/filings/ \
    --output-prefix parsed/ \
    --suffix .html

# Output: Parsed JSON files in s3://bucket/parsed/
```

## How S3 Works (Simplified)

### 1. Buckets and Keys

- **Bucket**: Top-level container (like `datathon-2025-bucket`)
- **Key**: Full path to file (like `input/filings/2024-10k-AAPL.html`)
- **No real folders**: S3 uses key prefixes to simulate folders

### 2. Common Operations

```python
# Upload file
s3.upload_file(local_path, "input/file.html")

# Download file
s3.download_file("input/file.html", local_path)

# Read directly to memory (faster, no disk IO)
content = s3.read_file_content("input/file.html")

# Write JSON directly
s3.write_json({"data": "..."}, "parsed/file.json")

# List files in "folder"
files = s3.list_files(prefix="input/filings/")
```

### 3. Memory vs Disk Operations

**Good (Memory):**
```python
# Read directly to memory - FAST
content = s3.read_file_content("file.html")
data = parse(content)
s3.write_json(data, "output.json")
```

**Bad (Disk):**
```python
# Unnecessary disk IO - SLOW
s3.download_file("file.html", "/tmp/file.html")
with open("/tmp/file.html") as f:
    content = f.read()
data = parse(content)
with open("/tmp/output.json", "w") as f:
    json.dump(data, f)
s3.upload_file("/tmp/output.json", "output.json")
```

For large files or files needed by parsers that require file paths, we use temporary files that are cleaned up automatically.

## Setup Instructions

### 1. Install Dependencies

Already included in environment files:
```yaml
# environment-local.yml and environment-aws.yml
- boto3=1.34.10
```

### 2. Configure AWS Credentials

Create `.env` file:
```bash
cp .env.example .env
```

Edit `.env`:
```bash
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
AWS_REGION=us-east-1
S3_BUCKET=datathon-2025-bucket
```

### 3. Create S3 Bucket

Via AWS Console or CLI:
```bash
aws s3 mb s3://datathon-2025-bucket --region us-east-1
```

### 4. Test Connection

```python
from src.utils import get_s3_client

s3 = get_s3_client()
if s3:
    print("Connected!")
    files = s3.list_files()
    print(f"Files in bucket: {len(files)}")
```

### 5. Upload Test Files

```bash
# Via CLI
aws s3 cp data/2024-10k-AAPL.html s3://datathon-2025-bucket/input/filings/

# Via Python
from pathlib import Path
from src.utils import get_s3_client

s3 = get_s3_client()
s3.upload_file(Path("data/2024-10k-AAPL.html"), "input/filings/2024-10k-AAPL.html")
```

## Cost Estimate

For MVP (1,000 documents, ~100MB total):
- **Storage**: ~$0.002/month
- **Operations**: ~$0.15/month (reads + writes)
- **Data transfer**: Minimal for < 1GB
- **Total**: < $1/month

S3 is extremely cost-effective for document storage.

## Next Steps

1. **Set up environment** (if not done):
   ```bash
   conda env create -f environment-local.yml
   conda activate datathon-local
   pip install torch==2.1.2 --index-url https://download.pytorch.org/whl/cu121
   python -m spacy download en_core_web_sm
   ```

2. **Configure S3**:
   - Copy `.env.example` to `.env`
   - Fill in AWS credentials
   - Create S3 bucket

3. **Test locally**:
   ```bash
   # Test parsers without S3
   python test_parsers_manual.py
   
   # Test with local files
   python parse_batch.py --local --input data/ --output output/
   ```

4. **Test S3 integration**:
   ```bash
   # Run examples
   python examples/parse_single_file.py
   
   # Parse from S3
   python parse_batch.py --s3 --input-prefix input/ --output-prefix parsed/
   ```

5. **Deploy to production**:
   - Use Lambda for serverless parsing
   - Use Step Functions for workflow orchestration
   - Use S3 events to trigger parsing automatically

## Files Created

```
src/
├── utils/
│   ├── __init__.py          # Updated: exports S3Client
│   └── s3_client.py         # NEW: S3 operations
└── parsers/
    ├── __init__.py          # Updated: exports ParserRunner
    └── parser_runner.py     # NEW: Orchestrates parsing with S3

examples/
└── parse_single_file.py     # NEW: Usage examples

parse_batch.py               # NEW: CLI tool for batch processing
.env.example                 # NEW: Configuration template
.gitignore                   # NEW: Protect sensitive files
S3_INTEGRATION.md           # NEW: Complete S3 guide
S3_WORKFLOW_SUMMARY.md      # NEW: This file

environment-local.yml        # Updated: Added boto3
environment-aws.yml          # Already had boto3
```

## Key Benefits

1. **Flexible**: Works locally or with S3
2. **Efficient**: Memory operations avoid disk IO
3. **Scalable**: Batch processing for any number of files
4. **User-friendly**: Streamlit integration for uploads
5. **Production-ready**: Error handling, logging, cleanup
6. **Cost-effective**: Minimal S3 costs
7. **Well-documented**: Comprehensive guides and examples

## Troubleshooting

### "S3 not configured"
- Check `.env` file exists and has correct values
- Verify `S3_BUCKET` is set

### "Access Denied"
- Check AWS credentials are correct
- Verify IAM permissions for S3 bucket

### "Bucket does not exist"
- Create bucket: `aws s3 mb s3://your-bucket`

### Slow performance
- Use memory operations instead of disk
- Enable parallel processing for batch operations

See `S3_INTEGRATION.md` for detailed troubleshooting.

## Summary

You now have a complete parsing system that:
- Parses CSV, HTML filings, and legislation
- Works with local files and S3
- Supports batch processing
- Integrates with Streamlit for user uploads
- Outputs standardized JSON for downstream processing
- Is production-ready with comprehensive error handling

The parsed JSON files in S3 will be fed to the embedding module (next step) for vector generation and storage in the vector database.

