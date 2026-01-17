# AWS Console Setup Guide - SageMaker Batch Embedding Job

Complete step-by-step guide for setting up the batch embedding job in AWS SageMaker using the AWS Console.

---

## Prerequisites

Before starting, ensure you have:

1. **AWS Account** with SageMaker access
2. **S3 Bucket** created with your data:
   - Parsed filings: `s3://your-bucket/parsed/`
   - S&P 500 CSV: `s3://your-bucket/data/2025-08-15_composition_sp500.csv`
3. **OpenSearch Domain** created and accessible
4. **IAM Role** with SageMaker execution permissions (or we'll create one)

---

## Step 0: Choose Your Approach

**Option 1: Custom Docker Image** ⭐ **Recommended**
- All dependencies pre-installed
- Faster job startup
- More reliable
- See: [DOCKER_SETUP.md](DOCKER_SETUP.md)

**Option 2: Code Package (ZIP)**
- Simpler initial setup
- Dependencies installed at runtime
- Slower startup

---

## Step 1: Prepare Deployment Package

### If Using Docker Image (Recommended)

See [DOCKER_SETUP.md](DOCKER_SETUP.md) for building and pushing the image.

Quick start:
```bash
./scripts/build_and_push_image.sh
```

### If Using Code Package (ZIP)

### 1.1 Create Deployment Package

On your local machine, create a package with the required files:

```bash
cd /home/artypuppet/datathon-2025

# Create deployment directory
mkdir -p sagemaker_deploy/scripts
mkdir -p sagemaker_deploy/src

# Copy required files
cp scripts/batch_embed_all_tickers.py sagemaker_deploy/scripts/
cp scripts/sagemaker_entrypoint.py sagemaker_deploy/scripts/
cp -r src/ sagemaker_deploy/

# Create requirements.txt if not exists
cat > sagemaker_deploy/requirements.txt << EOF
torch>=2.0.0
transformers>=4.30.0
numpy>=1.24.0
pandas>=2.0.0
opensearch-py>=2.0.0
boto3>=1.28.0
python-dotenv>=1.0.0
spacy>=3.7.0
EOF

# Create .zip file
cd sagemaker_deploy
zip -r ../sagemaker_code.zip .
cd ..
```

### 1.2 Upload to S3

```bash
# Upload code package to S3
aws s3 cp sagemaker_code.zip s3://your-datathon-bucket/sagemaker-code/batch-embedding.zip

# Verify upload
aws s3 ls s3://your-datathon-bucket/sagemaker-code/
```

---

## Step 2: Create IAM Role (If Needed)

### 2.1 Navigate to IAM Console

1. Go to **AWS Console** → **IAM**
2. Click **Roles** in left sidebar
3. Click **Create role**

### 2.2 Configure Trust Relationship

1. **Trusted entity type**: AWS service
2. **Use case**: SageMaker
3. Click **Next**

### 2.3 Attach Policies

Attach these policies:
- `AmazonSageMakerFullAccess`
- `AmazonS3FullAccess` (or create custom policy with specific bucket access)
- `AmazonOpenSearchServiceFullAccess` (or specific domain access)

**Or create custom policy**:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::your-datathon-bucket/*",
        "arn:aws:s3:::your-datathon-bucket"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "es:ESHttpPost",
        "es:ESHttpPut",
        "es:DescribeElasticsearchDomain"
      ],
      "Resource": "arn:aws:es:region:account-id:domain/your-opensearch-domain/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "*"
    }
  ]
}
```

### 2.4 Name Role

- **Role name**: `SageMakerBatchEmbeddingRole`
- Click **Create role**

**Note the Role ARN** - you'll need it later!

---

## Step 3: Create SageMaker Processing Job (Console)

### 3.1 Navigate to SageMaker

1. Go to **AWS Console** → **SageMaker**
2. In left sidebar, click **Processing** → **Processing jobs**
3. Click **Create processing job**

### 3.2 Configure Job Settings

#### Basic Information
- **Processing job name**: `batch-embed-tickers-YYYYMMDD-HHMMSS` (or auto-generated)
- **Description**: `Batch embedding generation for S&P 500 companies`

#### Container Image
You have two options:

**Option A: Use Custom Docker Image** ⭐ **Recommended**
- **Image location**: Select **"Use a different image location"**
- **Image URI**: `ACCOUNT_ID.dkr.ecr.REGION.amazonaws.com/sagemaker/batch-embedding-job:latest`
- **Benefits**: All dependencies pre-installed, faster startup, more reliable
- **Setup**: See [DOCKER_SETUP.md](DOCKER_SETUP.md) for building and pushing image
- **Quick build**: Run `./scripts/build_and_push_image.sh`

**Option B: Use SageMaker Built-in Python Image** (Simpler setup, slower startup)
- **Image**: Select `Python 3 (Data Science)` or `PyTorch`
- Requires installing dependencies at runtime
- More prone to dependency issues

**We recommend Option A (Custom Docker Image)** for production.

#### IAM Role
- Select the role you created: `SageMakerBatchEmbeddingRole`

### 3.3 Configure Processing Job (Script Mode)

Since we're using custom code, we need to configure it properly:

#### Input Configuration

**Input 1: Code Location**
- **Channel name**: `code`
- **S3 location type**: S3
- **S3 URI**: `s3://your-datathon-bucket/sagemaker-code/batch-embedding.zip`
- **Local path**: `/opt/ml/processing/input/code`

**Input 2: CSV Data** (Optional if using S3 key)
- **Channel name**: `data`
- **S3 location type**: S3
- **S3 URI**: `s3://your-datathon-bucket/data/2025-08-15_composition_sp500.csv`
- **Local path**: `/opt/ml/processing/input/data`

**Input 3: Checkpoints** (Optional - for resume)
- **Channel name**: `checkpoints`
- **S3 location type**: S3
- **S3 URI**: `s3://your-datathon-bucket/checkpoints/`
- **Local path**: `/opt/ml/checkpoints`

#### Output Configuration

**Output 1: Results**
- **Output name**: `results`
- **S3 output path**: `s3://your-datathon-bucket/results/embeddings/`
- **Local path**: `/opt/ml/processing/output`

**Output 2: Checkpoints**
- **Output name**: `checkpoints`
- **S3 output path**: `s3://your-datathon-bucket/checkpoints/`
- **Local path**: `/opt/ml/checkpoints`

### 3.4 Environment Variables

Click **Add environment variable** and add:

| Key | Value |
|-----|-------|
| `OPENSEARCH_ENDPOINT` | `https://your-opensearch-domain.region.es.amazonaws.com` |
| `AWS_DEFAULT_REGION` | `us-east-1` (your region) |
| `S3_BUCKET` | `your-datathon-bucket` |
| `PYTHONPATH` | `/opt/ml/processing/input/code:/opt/ml/processing/input/code/src` |

### 3.5 Command and Arguments

Since we're using a SageMaker Python image, we need to:

**Command**:
```bash
python3
```

**Arguments**:
```
/opt/ml/processing/input/code/scripts/batch_embed_all_tickers.py
--s3-csv-key data/2025-08-15_composition_sp500.csv
--opensearch-endpoint ${OPENSEARCH_ENDPOINT}
--opensearch-index company_embeddings
--vectordb-backend opensearch
--model-name llmware/industry-bert-sec-v0.1
--checkpoint-path /opt/ml/checkpoints/checkpoint.json
--output-results /opt/ml/processing/output/results.json
--s3-results-key results/batch_embedding_results.json
```

**OR** if CSV is in input channel:
```
/opt/ml/processing/input/code/scripts/batch_embed_all_tickers.py
--sp500-csv /opt/ml/processing/input/data/2025-08-15_composition_sp500.csv
--opensearch-endpoint ${OPENSEARCH_ENDPOINT}
--opensearch-index company_embeddings
--vectordb-backend opensearch
--model-name llmware/industry-bert-sec-v0.1
--checkpoint-path /opt/ml/checkpoints/checkpoint.json
--output-results /opt/ml/processing/output/results.json
--s3-results-key results/batch_embedding_results.json
```

### 3.6 Resource Configuration

- **Instance type**: 
  - `ml.m5.xlarge` (CPU, cheaper, ~$0.23/hr)
  - `ml.g4dn.xlarge` (GPU, faster embeddings, ~$0.75/hr) - **Recommended**
- **Instance count**: `1`
- **Volume size**: `100 GB` (for model downloads and temporary files)

### 3.7 Network Configuration (Optional)

- **VPC**: Select if OpenSearch is in VPC
- **Subnets**: Select subnets that can access OpenSearch
- **Security groups**: Allow outbound HTTPS (443) for OpenSearch

### 3.8 Tags (Optional)

Add tags for cost tracking:
- `Project`: `datathon-2025`
- `Component`: `batch-embedding`

### 3.9 Review and Create

1. Review all settings
2. Click **Create processing job**

---

## Step 4: Monitor Job Execution

### 4.1 View Job Status

1. Go to **SageMaker** → **Processing** → **Processing jobs**
2. Click on your job name
3. View status: **InProgress**, **Completed**, or **Failed**

### 4.2 View Logs

1. In job details, click **View logs** (or **CloudWatch logs**)
2. This opens CloudWatch Logs
3. Filter by log stream to see progress

**Look for**:
- `[INFO] Processing ticker: AAPL`
- `[OK] Stored N embeddings`
- `[OK] Batch processing complete`

### 4.3 Monitor Progress

The script logs progress every 10 tickers:
```
[INFO] Progress: 50/500 (48 success, 2 failed)
```

### 4.4 Check Results

After completion, check S3:
```bash
aws s3 ls s3://your-datathon-bucket/results/embeddings/
aws s3 cp s3://your-datathon-bucket/results/embeddings/results.json .
```

---

## Step 5: Troubleshooting

### Issue: Job Fails Immediately

**Check**:
1. IAM role permissions
2. S3 bucket access
3. Code zip file is correct format
4. Entry point script path is correct

**Solution**: Check CloudWatch logs for specific error

### Issue: "Module not found" Errors

**Problem**: Dependencies not installed

**Solution**: 
1. Add `requirements.txt` to code package
2. Modify entry point to install dependencies:
```python
import subprocess
subprocess.check_call(['pip', 'install', '-r', 'requirements.txt'])
```

### Issue: OpenSearch Connection Failed

**Problem**: Network/VPC configuration

**Solution**:
1. Verify OpenSearch endpoint is correct
2. Check security groups allow outbound HTTPS
3. If OpenSearch in VPC, ensure SageMaker job is in same VPC

### Issue: Out of Memory

**Problem**: Model too large or batch size too high

**Solution**:
1. Use larger instance (`ml.g4dn.2xlarge`)
2. Reduce batch size in code
3. Process fewer tickers at once (`--max-tickers 50`)

### Issue: Job Takes Too Long

**Problem**: Processing 500 companies sequentially

**Solution**:
1. Use GPU instance (`ml.g4dn.xlarge`)
2. Process in smaller batches
3. Increase instance count (but need to handle parallelization)

---

## Step 6: Resume Failed Job

If job fails partway through:

1. **Check checkpoint file**:
```bash
aws s3 cp s3://your-datathon-bucket/checkpoints/checkpoint.json .
cat checkpoint.json
```

2. **Create new job** with same settings but:
   - **Checkpoint path**: Point to existing checkpoint
   - **Remove `--no-resume`** flag (or don't add it)
   - Job will skip already processed tickers

---

## Step 7: Verify Results

### 7.1 Check Embeddings in OpenSearch

```python
from opensearchpy import OpenSearch

client = OpenSearch(
    hosts=[{'host': 'your-endpoint.es.amazonaws.com', 'port': 443}],
    http_auth=('username', 'password'),
    use_ssl=True,
    verify_certs=True
)

# Check index
response = client.search(
    index='company_embeddings',
    body={
        'query': {'match': {'ticker': 'AAPL'}},
        'size': 10
    }
)
print(f"Found {response['hits']['total']['value']} embeddings for AAPL")
```

### 7.2 Check Results JSON

```bash
aws s3 cp s3://your-bucket/results/batch_embedding_results.json .
python3 -m json.tool batch_embedding_results.json | head -50
```

Expected structure:
```json
{
  "total": 500,
  "successful": 485,
  "failed": 10,
  "skipped": 5,
  "results": [...]
}
```

---

## Alternative: Using SageMaker Notebook

If console setup is complex, use a SageMaker Notebook:

1. **Create Notebook Instance**:
   - SageMaker → Notebook → Notebook instances → Create
   - Instance type: `ml.t3.medium`
   - IAM role: Same as processing job

2. **Upload and Run Script**:
   ```python
   # In notebook cell
   import subprocess
   import sys
   
   !pip install opensearch-py transformers torch
   
   # Run script
   !python scripts/batch_embed_all_tickers.py \
       --s3-csv-key data/2025-08-15_composition_sp500.csv \
       --opensearch-endpoint https://your-endpoint.es.amazonaws.com
   ```

3. **Monitor**: Use notebook output cells to see progress

---

## Cost Estimation

**Processing Job Costs** (us-east-1):
- `ml.m5.xlarge`: ~$0.23/hr × 24 hours = **$5.52** (CPU, slower)
- `ml.g4dn.xlarge`: ~$0.75/hr × 8 hours = **$6.00** (GPU, faster)

**Data Transfer**: Minimal if everything in same region

**S3 Storage**: ~$0.023/GB/month for results

**Total**: ~$10-15 for processing 500 companies (one-time)

---

## Quick Reference: Console Checklist

- [ ] Code package created and uploaded to S3
- [ ] IAM role created with necessary permissions
- [ ] OpenSearch domain accessible
- [ ] S3 bucket has parsed filings data
- [ ] Processing job created with correct:
  - [ ] Input channels configured
  - [ ] Output paths set
  - [ ] Environment variables added
  - [ ] Command and arguments correct
  - [ ] Instance type selected
- [ ] Job started and monitored
- [ ] Results verified in S3 and OpenSearch

---

## Next Steps After Setup

1. **Schedule Recurring Jobs**: Use EventBridge to run periodically
2. **Add Notifications**: SNS alerts on job completion/failure
3. **Optimize**: Monitor and adjust instance types/batch sizes
4. **Scale**: Process subsets in parallel if needed

