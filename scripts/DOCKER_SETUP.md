# Docker Image Setup for SageMaker

This guide explains how to build a custom Docker image and use it in SageMaker Processing Jobs.

---

## Why Use a Custom Docker Image?

**Benefits:**
- ✅ All dependencies pre-installed (faster startup)
- ✅ Consistent environment across runs
- ✅ Can include custom libraries and system packages
- ✅ Better for production deployments
- ✅ Easier to version and manage

---

## Prerequisites

1. **Docker** installed locally ✅ Required
2. **AWS CLI** configured (recommended for automation, but optional)
3. **ECR access** (to push images)
4. **SageMaker access** (to use the image)

**Don't have AWS CLI?** See [INSTALL_AWS_CLI.md](INSTALL_AWS_CLI.md) or use the manual push method below.

---

## Quick Start

### Option 1: Automated (Requires AWS CLI)

```bash
cd /home/artypuppet/datathon-2025

# Set your AWS region
export AWS_REGION=us-east-1

# Build and push (automated script)
chmod +x scripts/build_and_push_image.sh
./scripts/build_and_push_image.sh
```

This will:
1. Create ECR repository if needed
2. Build Docker image
3. Push to ECR
4. Print the image URI to use

### Option 2: Manual Push (No AWS CLI Required)

```bash
cd /home/artypuppet/datathon-2025

# Build image locally
./scripts/build_and_push_manual.sh

# Then push via AWS Console:
# 1. Go to ECR Console
# 2. Create repository: sagemaker/batch-embedding-job
# 3. Click "View push commands"
# 4. Copy and run the commands shown
```

### Step 2: Use in SageMaker Console

1. Go to **SageMaker** → **Processing** → **Processing jobs** → **Create**
2. Under **Container image**, select **"Use a different image location"**
3. Enter your image URI: `ACCOUNT_ID.dkr.ecr.REGION.amazonaws.com/sagemaker/batch-embedding-job:latest`
4. Configure rest of job as normal

---

## Manual Build Process

### Step 1: Create ECR Repository

```bash
aws ecr create-repository \
    --repository-name sagemaker/batch-embedding-job \
    --region us-east-1 \
    --image-scanning-configuration scanOnPush=true
```

### Step 2: Login to ECR

```bash
aws ecr get-login-password --region us-east-1 | \
    docker login --username AWS --password-stdin \
    ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com
```

### Step 3: Build Image

```bash
docker build -f Dockerfile.sagemaker -t batch-embedding-job:latest .
```

### Step 4: Tag Image

```bash
docker tag batch-embedding-job:latest \
    ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/sagemaker/batch-embedding-job:latest
```

### Step 5: Push to ECR

```bash
docker push \
    ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/sagemaker/batch-embedding-job:latest
```

---

## Image Configuration

### Dockerfile Overview

The `Dockerfile.sagemaker`:
- **Base image**: `pytorch/pytorch:2.1.0-cuda11.8-cudnn8-runtime` (GPU support)
- **Python**: 3.10+ (from PyTorch image)
- **Dependencies**: Installed from `requirements.txt`
- **Code**: Copied from project
- **Entrypoint**: Script is set as default command

### Customizing the Image

**To add system packages:**
```dockerfile
RUN apt-get update && apt-get install -y \
    your-package \
    && rm -rf /var/lib/apt/lists/*
```

**To add Python packages:**
```dockerfile
RUN pip install your-package
```

**To change base image:**
```dockerfile
# For CPU-only (smaller, faster build)
FROM python:3.11-slim

# For GPU support
FROM pytorch/pytorch:2.1.0-cuda11.8-cudnn8-runtime
```

---

## Using the Image in SageMaker

### Option 1: AWS Console

1. **Processing Job Configuration**:
   - **Image location**: `Use a different image location`
   - **Image URI**: `ACCOUNT_ID.dkr.ecr.REGION.amazonaws.com/sagemaker/batch-embedding-job:latest`
   
2. **Command override** (optional):
   ```
   python3 /opt/ml/code/scripts/batch_embed_all_tickers.py
   ```
   
3. **Arguments**:
   ```
   --s3-csv-key data/2025-08-15_composition_sp500.csv
   --opensearch-endpoint ${OPENSEARCH_ENDPOINT}
   --opensearch-index company_embeddings
   --vectordb-backend opensearch
   --output-results /opt/ml/processing/output/results.json
   ```

### Option 2: Python SDK

```python
from sagemaker.processing import Processor, ProcessingInput, ProcessingOutput

# Create processor with custom image
processor = Processor(
    role='arn:aws:iam::ACCOUNT:role/SageMakerBatchEmbeddingRole',
    image_uri='ACCOUNT_ID.dkr.ecr.REGION.amazonaws.com/sagemaker/batch-embedding-job:latest',
    instance_count=1,
    instance_type='ml.g4dn.xlarge'
)

# Run processing job
processor.run(
    inputs=[
        ProcessingInput(
            source='s3://bucket/data/2025-08-15_composition_sp500.csv',
            destination='/opt/ml/processing/input/data'
        )
    ],
    outputs=[
        ProcessingOutput(
            source='/opt/ml/processing/output',
            destination='s3://bucket/results/'
        )
    ],
    arguments=[
        '--sp500-csv', '/opt/ml/processing/input/data/2025-08-15_composition_sp500.csv',
        '--opensearch-endpoint', 'https://your-endpoint.es.amazonaws.com',
        '--output-results', '/opt/ml/processing/output/results.json'
    ],
    environment={
        'OPENSEARCH_ENDPOINT': 'https://your-endpoint.es.amazonaws.com',
        'S3_BUCKET': 'your-bucket'
    }
)
```

### Option 3: AWS CLI

```bash
aws sagemaker create-processing-job \
    --processing-job-name batch-embed-$(date +%s) \
    --role-arn arn:aws:iam::ACCOUNT:role/SageMakerBatchEmbeddingRole \
    --app-specification '{
        "ImageUri": "ACCOUNT_ID.dkr.ecr.REGION.amazonaws.com/sagemaker/batch-embedding-job:latest",
        "ContainerEntrypoint": ["python3"],
        "ContainerArguments": [
            "/opt/ml/code/scripts/batch_embed_all_tickers.py",
            "--s3-csv-key", "data/2025-08-15_composition_sp500.csv",
            "--opensearch-endpoint", "https://your-endpoint.es.amazonaws.com"
        ]
    }' \
    --environment '{
        "OPENSEARCH_ENDPOINT": "https://your-endpoint.es.amazonaws.com"
    }' \
    --processing-resources '{
        "ClusterConfig": {
            "InstanceCount": 1,
            "InstanceType": "ml.g4dn.xlarge",
            "VolumeSizeInGB": 100
        }
    }' \
    --processing-output-config '{
        "Outputs": [{
            "OutputName": "results",
            "S3Output": {
                "S3Uri": "s3://bucket/results/",
                "LocalPath": "/opt/ml/processing/output"
            }
        }]
    }'
```

---

## Image Tagging Strategy

### Version Tags

```bash
# Tag with version
IMAGE_TAG=v1.0.0 ./scripts/build_and_push_image.sh

# Tag with git commit
IMAGE_TAG=$(git rev-parse --short HEAD) ./scripts/build_and_push_image.sh

# Tag with date
IMAGE_TAG=$(date +%Y%m%d) ./scripts/build_and_push_image.sh
```

### Multiple Tags

```bash
# Build once, tag multiple times
docker tag batch-embedding-job:latest \
    ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/sagemaker/batch-embedding-job:v1.0.0

docker tag batch-embedding-job:latest \
    ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/sagemaker/batch-embedding-job:latest

# Push all tags
docker push ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/sagemaker/batch-embedding-job:v1.0.0
docker push ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/sagemaker/batch-embedding-job:latest
```

---

## Local Testing

**Before pushing to ECR, test your image locally!** See **[DOCKER_TESTING.md](DOCKER_TESTING.md)** for complete testing guide.

### Quick Test

```bash
# Basic validation (no AWS needed)
./scripts/test_docker_image.sh

# Full test with real resources
./scripts/test_docker_local.sh
```

### Manual Test

```bash
# Build image
docker build -f Dockerfile.sagemaker -t batch-embedding-job:local .

# Test script help
docker run --rm batch-embedding-job:local --help

# Test with real data (small subset)
docker run -it --rm \
    -v $(pwd)/output:/opt/ml/processing/output \
    -e AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID \
    -e AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY \
    -e OPENSEARCH_ENDPOINT=$OPENSEARCH_ENDPOINT \
    batch-embedding-job:local \
    --tickers AAPL MSFT \
    --max-tickers 2 \
    --opensearch-endpoint $OPENSEARCH_ENDPOINT
```

See [DOCKER_TESTING.md](DOCKER_TESTING.md) for more testing scenarios.

---

## Image Size Optimization

### Current Size

- **Base PyTorch image**: ~4-5 GB
- **With dependencies**: ~6-7 GB
- **Total**: ~7 GB

### Optimization Tips

1. **Use smaller base image**:
   ```dockerfile
   FROM python:3.11-slim  # ~200 MB instead of 4 GB
   # Then install PyTorch CPU version
   RUN pip install torch --index-url https://download.pytorch.org/whl/cpu
   ```

2. **Multi-stage build** (for smaller final image):
   ```dockerfile
   FROM pytorch/pytorch:2.1.0-cuda11.8-cudnn8-runtime as builder
   # Install dependencies
   
   FROM pytorch/pytorch:2.1.0-cuda11.8-cudnn8-runtime
   COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
   ```

3. **Remove unnecessary packages**:
   ```dockerfile
   RUN apt-get clean && \
       rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*
   ```

---

## Troubleshooting

### Issue: "repository does not exist"

**Solution**: Create repository first:
```bash
aws ecr create-repository --repository-name sagemaker/batch-embedding-job
```

### Issue: "unauthorized: authentication required"

**Solution**: Re-login to ECR:
```bash
aws ecr get-login-password --region us-east-1 | \
    docker login --username AWS --password-stdin \
    ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com
```

### Issue: Image too large (ECR has limits)

**Solution**: 
- Use smaller base image
- Enable compression
- Use multi-stage builds

### Issue: Build fails on dependency installation

**Solution**: Check `requirements.txt` and ensure all packages are compatible

---

## Cost Considerations

**ECR Storage**:
- First 500 MB/month: Free
- Additional: ~$0.10/GB/month

**Data Transfer**:
- ECR to SageMaker: Free within same region
- Cross-region: ~$0.02/GB

**Image Pull Time**:
- ~7 GB image: ~2-5 minutes to pull
- Consider using regional ECR for faster pulls

---

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Build and Push Docker Image

on:
  push:
    branches: [ main ]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v1
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1
      
      - name: Login to Amazon ECR
        run: |
          aws ecr get-login-password | docker login --username AWS --password-stdin ${{ secrets.AWS_ACCOUNT_ID }}.dkr.ecr.us-east-1.amazonaws.com
      
      - name: Build and push
        run: |
          ./scripts/build_and_push_image.sh
```

---

## Next Steps

1. ✅ Build and push image using script
2. ✅ Test image locally
3. ✅ Use in SageMaker Processing Job
4. ✅ Monitor performance and optimize
5. ✅ Set up CI/CD for automated builds

