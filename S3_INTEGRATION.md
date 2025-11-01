# S3 Integration Guide

## What is S3?

Amazon S3 (Simple Storage Service) is cloud-based object storage:
- **Buckets**: Top-level containers (think of them as root folders)
- **Keys**: File paths within buckets (e.g., `input/filings/2024-10k-AAPL.html`)
- **Objects**: The actual files stored in S3
- **No real folders**: S3 simulates folders using key prefixes

## Architecture

```
S3 Bucket: datathon-2025-bucket/
├── input/                          # Raw input files
│   ├── filings/                    # 10-K/10-Q HTML files
│   │   └── 2024-09-30-10k-AAPL.html
│   ├── legislation/                # Legislation HTML/XML
│   │   └── REGULATION_EU_2024_1689_AI_ACT.html
│   └── financial/                  # CSV files
│       └── 2024-01-01-composition-MSCI.csv
│
├── parsed/                         # Parsed JSON output
│   ├── 2024-09-30-10k-AAPL.json
│   ├── REGULATION_EU_2024_1689_AI_ACT.json
│   └── 2024-01-01-composition-MSCI.json
│
└── embeddings/                     # Vector embeddings (future)
    └── embeddings_batch_001.json
```

## Setup

### 1. Environment Variables

Create `.env` file (copy from `.env.example`):
```bash
cp .env.example .env
```

Edit `.env`:
```bash
# Your AWS credentials
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
AWS_REGION=us-east-1

# Your S3 bucket name
S3_BUCKET=datathon-2025-bucket
```

### 2. Install boto3

Already included in `environment-local.yml` and `environment-aws.yml`:
```yaml
- boto3=1.34.10
```

### 3. Test S3 Connection

```python
from src.utils.s3_client import get_s3_client

s3 = get_s3_client()
if s3:
    print("S3 connected!")
    files = s3.list_files(prefix="input/")
    print(f"Found {len(files)} files")
```

## Usage

### Option 1: Parse Local Files

```bash
# Parse all files in data/ directory
python parse_batch.py --local --input data/ --output output/

# Parse specific file types
python parse_batch.py --local --input data/ --pattern "*.html"

# Parse and upload to S3
python parse_batch.py --local --input data/ --upload-to-s3
```

### Option 2: Parse Files from S3

```bash
# Parse all files in S3 prefix
python parse_batch.py --s3 --input-prefix input/filings/ --output-prefix parsed/

# Filter by file type
python parse_batch.py --s3 --input-prefix input/legislation/ --suffix .html

# Parse from S3 and save locally
python parse_batch.py --s3 --input-prefix input/ --save-local
```

### Option 3: Programmatic Usage

```python
from pathlib import Path
from src.parsers.parser_runner import ParserRunner
from src.utils.s3_client import get_s3_client

# Initialize
s3_client = get_s3_client()
runner = ParserRunner(s3_client=s3_client)

# Parse local file and upload to S3
data = runner.parse_local_file(
    Path("data/2024-10k-AAPL.html"),
    save_to_s3=True,
    s3_output_prefix="parsed/"
)

# Parse file from S3
data = runner.parse_s3_file(
    "input/filings/2024-10k-AAPL.html",
    save_to_s3=True,
    s3_output_prefix="parsed/"
)

# Batch process S3 directory
results = runner.batch_parse_s3(
    s3_input_prefix="input/filings/",
    s3_output_prefix="parsed/",
    suffix_filter=".html"
)
```

## S3 Client API

### Reading Files

```python
from src.utils.s3_client import S3Client

s3 = S3Client(bucket_name="my-bucket")

# Download to disk
s3.download_file("input/file.html", Path("local/file.html"))

# Read directly into memory (no disk IO)
content = s3.read_file_content("input/file.html")  # bytes
text = s3.read_text_file("input/file.html")        # string
```

### Writing Files

```python
# Upload from disk
s3.upload_file(Path("local/file.html"), "input/file.html")

# Write directly from memory (no disk IO)
s3.write_content(b"content", "output/file.txt")
s3.write_text("text content", "output/file.txt")

# Write JSON
s3.write_json({"key": "value"}, "output/data.json")
```

### Listing and Managing Files

```python
# List all files
files = s3.list_files()

# List with prefix
files = s3.list_files(prefix="input/filings/")

# List with suffix filter
files = s3.list_files(prefix="input/", suffix=".html")

# Check existence
exists = s3.file_exists("input/file.html")

# Get file size
size = s3.get_file_size("input/file.html")  # bytes

# Delete file
s3.delete_file("temp/old_file.html")
```

## Streamlit Integration (User Uploads)

When users upload files via Streamlit dashboard:

```python
import streamlit as st
from src.utils.s3_client import get_s3_client
from src.parsers.parser_runner import ParserRunner
import tempfile
from pathlib import Path

s3 = get_s3_client()
runner = ParserRunner(s3_client=s3)

# File upload widget
uploaded_file = st.file_uploader("Upload document", type=["html", "csv", "xml"])

if uploaded_file:
    # Save to temp file
    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(uploaded_file.name).suffix) as tmp:
        tmp.write(uploaded_file.read())
        tmp_path = Path(tmp.name)
    
    try:
        # Upload to S3
        s3_key = f"user_uploads/{uploaded_file.name}"
        s3.upload_file(tmp_path, s3_key)
        st.success(f"Uploaded to S3: {s3_key}")
        
        # Parse the file
        with st.spinner("Parsing..."):
            data = runner.parse_s3_file(
                s3_key,
                save_to_s3=True,
                s3_output_prefix="parsed/"
            )
        
        if data:
            st.success("Parsed successfully!")
            st.json(data)
        
    finally:
        tmp_path.unlink()  # Cleanup
```

## Cost Considerations

S3 pricing (as of 2024):
- **Storage**: ~$0.023/GB/month
- **PUT requests**: $0.005 per 1,000 requests
- **GET requests**: $0.0004 per 1,000 requests
- **Data transfer OUT**: $0.09/GB (first 10TB)

Example costs for our project:
- 1,000 documents (~100MB total): ~$0.002/month storage
- Daily parsing (1,000 reads + 1,000 writes): ~$0.005/day
- **Total estimate**: < $1/month for MVP

## Best Practices

### 1. Use Prefixes as Folders

```python
# Good: Organized structure
input/filings/2024-10k-AAPL.html
input/legislation/EU_AI_ACT.html
parsed/2024-10k-AAPL.json

# Bad: Everything in root
2024-10k-AAPL.html
EU_AI_ACT.html
```

### 2. Avoid Downloading When Possible

```python
# Good: Read directly to memory
content = s3.read_file_content("file.html")

# Bad: Unnecessary disk IO
s3.download_file("file.html", "/tmp/file.html")
with open("/tmp/file.html") as f:
    content = f.read()
```

### 3. Batch Operations

```python
# Good: Process multiple files
results = runner.batch_parse_s3("input/filings/")

# Bad: Individual processing
for file in files:
    runner.parse_s3_file(file)  # Too many separate calls
```

### 4. Error Handling

```python
# Always handle S3 errors
try:
    content = s3.read_file_content("file.html")
    if content is None:
        logger.error("File not found or read failed")
except Exception as e:
    logger.error(f"S3 error: {e}")
```

## Troubleshooting

### Issue: "S3 not configured"
**Solution**: Check `.env` file has correct credentials and S3_BUCKET set

### Issue: "Access Denied"
**Solution**: Verify IAM permissions for your AWS credentials:
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
        "arn:aws:s3:::datathon-2025-bucket",
        "arn:aws:s3:::datathon-2025-bucket/*"
      ]
    }
  ]
}
```

### Issue: "Bucket does not exist"
**Solution**: Create bucket in AWS Console or via CLI:
```bash
aws s3 mb s3://datathon-2025-bucket --region us-east-1
```

### Issue: Slow downloads
**Solution**: Use memory operations instead of disk:
```python
# Fast: Direct to memory
content = s3.read_file_content(key)

# Slow: Via disk
s3.download_file(key, tmp_path)
```

## Local Development (No S3)

For local-only development without S3:

```python
# ParserRunner works without S3
runner = ParserRunner()  # s3_client=None

# Only local operations
data = runner.parse_local_file(Path("data/file.html"))
results = runner.batch_parse_local(Path("data/"))
```

Set in `.env`:
```bash
LOCAL_MODE=true
```

## Next Steps

1. **Set up S3 bucket**: Create bucket in AWS Console
2. **Configure credentials**: Update `.env` file
3. **Upload test files**: Use AWS CLI or Console
4. **Test integration**: Run `examples/parse_single_file.py`
5. **Batch processing**: Use `parse_batch.py` for production

See `examples/parse_single_file.py` for complete working examples.

