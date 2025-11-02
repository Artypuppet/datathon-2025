# Running the Dashboard

## Quick Start

```bash
# Activate environment
conda activate datathon-local

# Run dashboard
streamlit run dashboard.py
```

Dashboard will open in browser at `http://localhost:8501`

## Features

### File Upload
- Upload CSV, HTML, or XML files
- Max file size: 100 MB
- Files saved to: `s3://bucket/input/user_uploads/{timestamp}_{filename}`

### Processing Options
- **Test Mode (Dry Run)**: Process without updating embeddings
- **Auto-process**: Automatically trigger pipeline after upload

### Results Display
- Upload status
- Parsing results
- Output file location
- Stage-by-stage status

## Usage

### Step 1: Upload File

1. Click "Choose a file to upload"
2. Select a CSV, HTML, or XML file
3. File info displayed automatically

### Step 2: Configure Options

- **Test Mode**: Check to run without making changes
- **Auto-process**: Check to trigger pipeline automatically

### Step 3: Upload and Process

1. Click "Upload to S3" button
2. Wait for upload to complete
3. If auto-process enabled, pipeline triggers
4. View results in UI

## Example Workflow

### Upload CSV File

```
1. Select: 2025-08-15_composition_sp500.csv
2. Check "Auto-process after upload"
3. Click "Upload to S3"
4. View results:
   ✓ File uploaded: input/user_uploads/20241101_120000_2025-08-15_composition_sp500.csv
   ✓ Processing complete!
   ✓ Output: parsed/2025-08-15_composition_sp500.json
```

### Upload with Test Mode

```
1. Select: regulation-eu-2024-1689.html
2. Check "Test Mode (Dry Run)"
3. Check "Auto-process after upload"
4. Click "Upload to S3"
5. View results:
   ✓ Dry run complete (no changes made)
   ⊘ Would process embeddings and update database
```

## Troubleshooting

### "S3 not configured"
**Solution**: Set up `.env` file with AWS credentials
```bash
cp .env.example .env
nano .env
# Add AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, S3_BUCKET
```

### "Upload failed"
**Causes**:
- Invalid credentials
- Bucket doesn't exist
- IAM permissions insufficient
- Network issues

**Solution**: Run `python test_s3_connection.py`

### "Processing failed"
**Causes**:
- Invalid file format
- Parser error
- S3 write permissions

**Solution**: Check file format, verify parsers work with local files first

### Dashboard won't start
**Solution**:
```bash
conda activate datathon-local
pip install streamlit
streamlit run dashboard.py
```

## Integration with Pipeline

Dashboard directly uses pipeline:
1. Uploads file to S3
2. Creates `PipelineOrchestrator` instance
3. Executes with `orchestrator.execute(event)`
4. Displays results inline

No Lambda needed for local development!

## Next Steps

1. Deploy Lambda function to AWS
2. Configure S3 trigger
3. Remove auto-process from UI (let Lambda handle it)
4. Add real-time status updates (WebSocket polling)

## Commands

```bash
# Run dashboard
streamlit run dashboard.py

# Test pipeline separately
python test_pipeline.py

# Test S3 connection
python test_s3_connection.py
```

## See Also

- [Pipeline Overview](PIPELINE_OVERVIEW.md)
- [AWS Setup Guide](AWS_SETUP_GUIDE.md)
- [S3 Integration](../S3_INTEGRATION.md)

