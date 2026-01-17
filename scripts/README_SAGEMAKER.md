# SageMaker Batch Embedding Generation

This directory contains scripts for running batch embedding generation on AWS SageMaker.

## Overview

The `batch_embed_all_tickers.py` script processes all S&P 500 companies:
1. Aggregates filings per company
2. Generates embeddings using transformer models
3. Stores embeddings in OpenSearch vector database

## Setup

### Prerequisites

1. **SageMaker Execution Role**: IAM role with permissions for:
   - S3 read/write access
   - OpenSearch access
   - SageMaker execution

2. **S3 Bucket**: Contains:
   - Parsed filings: `s3://bucket/parsed/`
   - S&P 500 CSV: `s3://bucket/data/2025-08-15_composition_sp500.csv`

3. **OpenSearch Domain**: Configured and accessible from SageMaker

### Installation

```bash
# Copy scripts to SageMaker-compatible location
cp scripts/* /opt/ml/code/

# Install dependencies (in SageMaker environment)
pip install -r requirements.txt
```

## Running Locally (Testing)

```bash
# Test with a few tickers
python scripts/batch_embed_all_tickers.py \
    --tickers AAPL MSFT NVDA \
    --max-tickers 3 \
    --opensearch-endpoint https://your-endpoint.es.amazonaws.com

# Test with S&P 500 CSV
python scripts/batch_embed_all_tickers.py \
    --sp500-csv data/initial-dataset/2025-08-15_composition_sp500.csv \
    --max-tickers 10 \
    --opensearch-endpoint https://your-endpoint.es.amazonaws.com
```

## Running on SageMaker

### Quick Start: AWS Console Setup

**For step-by-step AWS Console instructions**, see **[AWS_CONSOLE_SETUP.md](AWS_CONSOLE_SETUP.md)**.

This guide covers:
- Creating deployment packages
- Setting up IAM roles
- Creating Processing Jobs in the console
- Configuring inputs/outputs/environment variables
- Monitoring and troubleshooting

### Alternative: Python SDK or CLI

If you prefer using Python SDK or AWS CLI, see methods below.

### Method 1: Using SageMaker Python SDK

```python
from sagemaker.processing import ScriptProcessor, ProcessingInput, ProcessingOutput
import boto3

sagemaker_session = boto3.Session().region_name

processor = ScriptProcessor(
    role='arn:aws:iam::ACCOUNT:role/SageMakerExecutionRole',
    image_uri='your-custom-image',  # Or use default SageMaker image
    instance_type='ml.g4dn.xlarge',
    instance_count=1,
    command=['python3'],
    base_job_name='batch-embed-tickers'
)

processor.run(
    code='scripts/batch_embed_all_tickers.py',
    inputs=[
        ProcessingInput(
            source='s3://bucket/data/2025-08-15_composition_sp500.csv',
            destination='/opt/ml/processing/input'
        )
    ],
    outputs=[
        ProcessingOutput(
            source='/opt/ml/processing/output',
            destination='s3://bucket/results/embeddings/'
        )
    ],
    arguments=[
        '--sp500-csv', '/opt/ml/processing/input/2025-08-15_composition_sp500.csv',
        '--opensearch-endpoint', 'https://your-endpoint.es.amazonaws.com',
        '--output-results', '/opt/ml/processing/output/results.json',
        '--checkpoint-path', '/opt/ml/checkpoints/checkpoint.json'
    ],
    environment={
        'OPENSEARCH_ENDPOINT': 'https://your-endpoint.es.amazonaws.com',
        'S3_BUCKET': 'your-bucket'
    }
)
```

### Method 2: Using SageMaker Training Job

Create a training job configuration:

```python
from sagemaker.estimator import Estimator

estimator = Estimator(
    image_uri='your-custom-image',
    role='arn:aws:iam::ACCOUNT:role/SageMakerExecutionRole',
    instance_type='ml.g4dn.xlarge',
    instance_count=1,
    base_job_name='batch-embed-tickers',
    hyperparameters={
        'model-name': 'llmware/industry-bert-sec-v0.1',
        'max-tickers': '500'
    },
    environment={
        'OPENSEARCH_ENDPOINT': 'https://your-endpoint.es.amazonaws.com'
    }
)

estimator.fit({
    'training': 's3://bucket/data/'
})
```

### Method 3: Using AWS CLI

```bash
aws sagemaker create-training-job \
    --training-job-name batch-embed-tickers-$(date +%s) \
    --role-arn arn:aws:iam::ACCOUNT:role/SageMakerExecutionRole \
    --algorithm-specification '{
        "TrainingInputMode": "File",
        "TrainingImage": "your-custom-image"
    }' \
    --input-data-config '[{
        "ChannelName": "data",
        "DataSource": {
            "S3DataSource": {
                "S3DataType": "S3Prefix",
                "S3Uri": "s3://bucket/data/"
            }
        }
    }]' \
    --output-data-config '{
        "S3OutputPath": "s3://bucket/results/"
    }' \
    --resource-config '{
        "InstanceType": "ml.g4dn.xlarge",
        "InstanceCount": 1,
        "VolumeSizeInGB": 100
    }' \
    --hyper-parameters '{
        "model-name": "llmware/industry-bert-sec-v0.1",
        "opensearch-endpoint": "https://your-endpoint.es.amazonaws.com"
    }'
```

## Configuration

### Environment Variables

Set in SageMaker job environment or `.env` file:

```bash
OPENSEARCH_ENDPOINT=https://your-endpoint.es.amazonaws.com
AWS_DEFAULT_REGION=us-east-1
S3_BUCKET=your-datathon-bucket
OPENSEARCH_USERNAME=opensearch
OPENSEARCH_PASSWORD=your-password
```

### Command Line Arguments

```bash
# Data source
--sp500-csv PATH              # Local path to S&P 500 CSV
--s3-csv-key S3_KEY          # S3 key to S&P 500 CSV
--tickers TICKER1 TICKER2    # Direct ticker list

# Model configuration
--model-name MODEL            # Transformer model (default: llmware/industry-bert-sec-v0.1)
--use-contextual-enrichment   # Enable knowledge database enrichment
--sentence-level-chunking     # Use sentence-level chunking

# VectorDB configuration
--opensearch-endpoint URL     # OpenSearch endpoint
--opensearch-index NAME       # Index name (default: company_embeddings)
--vectordb-backend BACKEND   # opensearch|chroma|auto

# Processing options
--max-tickers N               # Limit number of tickers (for testing)
--no-resume                   # Disable checkpoint/resume
--checkpoint-path PATH        # Checkpoint file path

# Output
--output-results PATH         # Save results JSON locally
--s3-results-key S3_KEY      # Save results JSON to S3
```

## Checkpointing and Resume

The script supports checkpoint/resume:

1. **Checkpoint file**: Saved to `/tmp/embedding_checkpoint.json` (or custom path)
2. **Resume capability**: Automatically resumes from last checkpoint
3. **Skip processed**: Already processed tickers are skipped

To start fresh:
```bash
--no-resume
```

## Monitoring

### CloudWatch Logs

SageMaker automatically sends logs to CloudWatch:
- Log group: `/aws/sagemaker/ProcessingJobs`
- Stream: Job name

### Progress Tracking

The script logs progress every 10 tickers:
```
[INFO] Progress: 50/500 (48 success, 2 failed)
```

### Results JSON

Final results saved to JSON:
```json
{
  "total": 500,
  "successful": 485,
  "failed": 10,
  "skipped": 5,
  "results": [
    {
      "ticker": "AAPL",
      "status": "success",
      "chunks_count": 1250,
      "embeddings_stored": 1250,
      "timestamp": "2025-11-02T10:30:00"
    }
  ]
}
```

## Error Handling

### Retry Logic

The script handles:
- Network failures (retries with exponential backoff)
- S3 access errors (logs and continues)
- OpenSearch connection errors (logs and continues)
- Invalid data (skips and logs)

### Failed Tickers

Failed tickers are:
1. Logged with error message
2. Saved to checkpoint
3. Included in results JSON
4. Can be reprocessed later

## Performance

### Estimated Runtime

- **Per ticker**: ~2-5 minutes (depends on filing size)
- **500 tickers**: ~17-42 hours on single GPU instance
- **Parallelization**: Can use multiple instances for faster processing

### Resource Recommendations

- **CPU instance**: `ml.m5.xlarge` (cheaper, slower)
- **GPU instance**: `ml.g4dn.xlarge` (faster embeddings)
- **Memory**: Minimum 16GB RAM
- **Storage**: 100GB+ for temporary files

## Troubleshooting

### "S3 client not configured"
- Check AWS credentials
- Verify `S3_BUCKET` environment variable

### "OpenSearch connection failed"
- Verify `OPENSEARCH_ENDPOINT` is correct
- Check security groups allow SageMaker access
- Verify credentials/authentication

### "No tickers found"
- Check CSV file format
- Verify S3 prefix for parsed files
- Use `--tickers` to provide direct list

### "Out of memory"
- Use larger instance type
- Process in smaller batches (`--max-tickers`)
- Reduce chunking size in embedding stage

## Next Steps

1. **Monitor job**: Check CloudWatch logs
2. **Verify embeddings**: Query OpenSearch to confirm storage
3. **Process failed**: Re-run with failed tickers only
4. **Scale up**: Use multiple instances for faster processing

