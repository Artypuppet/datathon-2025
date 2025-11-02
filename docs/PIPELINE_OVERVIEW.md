# Pipeline Overview - MVP Implementation

## Architecture

```
User uploads via Streamlit
         ↓
Upload to S3: input/user_uploads/{timestamp}_{filename}
         ↓
PipelineOrchestrator.execute()
         ↓
Stage 1: ParseStage
  ├─ Detect file type (CSV/HTML/XML)
  ├─ Run appropriate parser
  └─ Save to S3: parsed/{filename}.json
         ↓
Stage 2: EmbeddingsStage (SKIPPED in MVP)
         ↓
Stage 3: DatabaseUpdateStage (SKIPPED in MVP)
         ↓
Return success/failure status
```

## Components

### 1. Pipeline Configuration (`src/pipeline/config.py`)

Configurable settings:
- S3 paths (input, parsed, embeddings)
- Processing flags (dry_run, skip_embeddings)
- Error handling (retries, continue_on_error)

Load from environment or event:
```python
config = PipelineConfig.from_env()
config = PipelineConfig.from_event(event)
```

### 2. Parse Stage (`src/pipeline/stage_parse.py`)

Parses uploaded files:
- Auto-detects file type
- Uses existing parser infrastructure
- Saves structured JSON to S3
- Returns context with parse results

**Output**: `parsed/{filename}.json`

### 3. Orchestrator (`src/pipeline/orchestrator.py`)

Coordinates all stages:
- Manages execution flow
- Handles errors
- Reports status
- Supports dry run mode

**Returns**: Result dictionary with status

### 4. Streamlit Widget (`src/dashboard/upload_widget.py`)

File upload interface:
- Upload to S3
- Trigger pipeline
- Display results
- Test mode option

### 5. Lambda Handler (`src/lambda/handler.py`)

AWS Lambda entry point:
- Handles S3 events
- Triggers pipeline
- Returns HTTP response

## Usage

### Local Testing

```python
from src.pipeline import PipelineOrchestrator, PipelineConfig

# Create config
config = PipelineConfig(dry_run=False, skip_embeddings=True)

# Create orchestrator
orchestrator = PipelineOrchestrator(config=config)

# Execute
event = {
    'file_key': 'input/financial/file.csv',
    'timestamp': '2024-11-01T12:00:00Z',
    'dry_run': False
}

result = orchestrator.execute(event)
print(result)
```

**Result**:
```json
{
  "status": "success",
  "file_key": "input/financial/file.csv",
  "parsed_key": "parsed/file.json",
  "document_type": "csv_financial",
  "stages": {
    "parse": "success",
    "embeddings": "skipped",
    "db_update": "skipped"
  }
}
```

### Test Mode (Dry Run)

```python
config = PipelineConfig(dry_run=True)
orchestrator = PipelineOrchestrator(config=config)

result = orchestrator.execute(event)
# Returns: {"status": "dry_run", ...}
```

### Streamlit Dashboard

```bash
# Run dashboard
streamlit run dashboard.py

# Upload file via UI
# Pipeline triggers automatically
# View results inline
```

### AWS Lambda (Future)

```python
# Lambda triggered by S3 event
# Event structure:
{
  "Records": [{
    "s3": {
      "bucket": {"name": "bucket-name"},
      "object": {"key": "path/to/file.html"}
    }
  }]
}

# Lambda handler processes event
# Returns status
```

## Testing

### Run Tests

```bash
# Test pipeline
python test_pipeline.py

# Expected output:
# ============================================================
# PIPELINE TEST SUITE
# ============================================================
# [OK] Dry run test passed
# [OK] Actual processing test passed
# [SUCCESS] All tests passed!
```

### Manual Testing

```bash
# Test with actual S3 file
python -c "
from src.pipeline import PipelineOrchestrator, PipelineConfig

config = PipelineConfig()
orch = PipelineOrchestrator(config=config)

event = {'file_key': 'input/financial/file.csv'}
result = orch.execute(event)
print(result)
"
```

## Error Handling

Pipeline handles errors gracefully:

```python
# If parse fails
{
  "status": "failed",
  "error": "Parse failed: Invalid file format",
  "stages": {
    "parse": "failed",
    "embeddings": "not_reached",
    "db_update": "not_reached"
  }
}

# Partial failure (future)
# If embeddings fail but parse succeeded
{
  "status": "partial_failure",
  "parse_status": "success",
  "embedding_error": "...",
  "parsed_key": "parsed/file.json"
}
```

## Deployment

### Local Development

```bash
# Run dashboard
streamlit run dashboard.py

# Files uploaded trigger pipeline immediately
# Results shown in UI
```

### AWS Lambda (Future)

**Setup**:
1. Package Lambda deployment
2. Create Lambda function
3. Configure S3 trigger
4. Set environment variables

**Trigger**:
- S3: `s3:ObjectCreated:*` in `input/user_uploads/`
- Invokes Lambda
- Lambda runs pipeline
- Status logged to CloudWatch

## Current Limitations (MVP)

1. **No embeddings**: Stage 2 skipped
2. **No database**: Stage 3 skipped
3. **Synchronous**: No async processing
4. **No retries**: Single attempt only
5. **No notifications**: Silent failures

These will be addressed in Phase 2.

## Next Steps

### Phase 2 Features

1. **Embeddings Stage**
   - Load sentence-transformers model
   - Extract text sections
   - Generate embeddings
   - Save to S3

2. **Database Update**
   - Connect to OpenSearch
   - Batch insert vectors
   - Handle duplicates
   - Return update status

3. **Lambda Integration**
   - Deploy Lambda function
   - Configure S3 trigger
   - Test event handling
   - Monitor CloudWatch logs

4. **Monitoring**
   - CloudWatch metrics
   - Error notifications (SNS)
   - Success/failure tracking
   - Processing time metrics

## File Structure

```
src/
├── pipeline/
│   ├── __init__.py           # Module exports
│   ├── config.py             # Configuration
│   ├── orchestrator.py       # Main pipeline
│   └── stage_parse.py        # Parse stage
│
├── dashboard/
│   ├── __init__.py           # Module exports
│   └── upload_widget.py      # Streamlit widget
│
└── lambda/
    └── handler.py            # Lambda entry point

Root:
├── dashboard.py              # Streamlit app
└── test_pipeline.py          # Pipeline tests
```

## Configuration

### Environment Variables

```bash
# .env
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1
S3_BUCKET=datathon-2025-bucket

# Pipeline paths
S3_INPUT_PREFIX=input/
S3_PARSED_PREFIX=parsed/
S3_EMBEDDINGS_PREFIX=embeddings/

# Pipeline flags
PIPELINE_DRY_RUN=false
SKIP_EMBEDDINGS=true  # MVP: skip embeddings
```

## See Also

- [Pipeline Implementation](../src/pipeline/)
- [Dashboard](../dashboard.py)
- [Lambda Handler](../src/lambda/handler.py)
- [S3 Integration](../S3_INTEGRATION.md)

