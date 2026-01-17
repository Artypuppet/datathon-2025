# Testing Docker Image Locally

Before pushing your Docker image to ECR and running on SageMaker, test it locally to catch issues early.

---

## Quick Test (No AWS Resources Required)

### Basic Validation Test

```bash
./scripts/test_docker_image.sh
```

This script tests:
- ✅ Container can start
- ✅ Python imports work
- ✅ Required files are present
- ✅ Environment variables work
- ✅ Script accepts arguments

**No AWS credentials needed** - just validates the image is built correctly.

---

## Full Test with Real AWS Resources

### Test with Small Dataset

```bash
# Set environment variables
export AWS_ACCESS_KEY_ID=your-key
export AWS_SECRET_ACCESS_KEY=your-secret
export AWS_REGION=us-east-1
export OPENSEARCH_ENDPOINT=https://your-endpoint.es.amazonaws.com
export S3_BUCKET=your-bucket

# Run test with 2 tickers
./scripts/test_docker_local.sh
```

Or manually:

```bash
docker run -it --rm \
    -v "$(pwd)/output:/opt/ml/processing/output" \
    -e AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID" \
    -e AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY" \
    -e OPENSEARCH_ENDPOINT="$OPENSEARCH_ENDPOINT" \
    batch-embedding-job:latest \
    --tickers AAPL MSFT \
    --max-tickers 2 \
    --opensearch-endpoint "$OPENSEARCH_ENDPOINT" \
    --output-results /opt/ml/processing/output/test_results.json
```

---

## Test Scenarios

### Scenario 1: Import Validation

Test if all Python modules can be imported:

```bash
docker run --rm batch-embedding-job:latest \
    python3 -c "
import sys
sys.path.insert(0, '/opt/ml/code/src')

from src.pipeline.stage_embed import EmbeddingStage
from src.vectordb.client import VectorDBClient
print('[OK] All imports successful')
"
```

### Scenario 2: Model Loading Test

Test if the embedding model can be loaded (requires internet or cached model):

```bash
docker run --rm batch-embedding-job:latest \
    python3 -c "
from transformers import AutoTokenizer, AutoModel
tokenizer = AutoTokenizer.from_pretrained('llmware/industry-bert-sec-v0.1')
model = AutoModel.from_pretrained('llmware/industry-bert-sec-v0.1')
print('[OK] Model loaded')
print(f'Embedding dimension: {model.config.hidden_size}')
"
```

**Note**: First run will download model (~400 MB), subsequent runs use cache.

### Scenario 3: Script Help

Test if script shows help (validates argument parsing):

```bash
docker run --rm batch-embedding-job:latest --help
```

### Scenario 4: Dry Run Test

Test script with invalid/missing resources (should fail gracefully):

```bash
docker run --rm \
    -e OPENSEARCH_ENDPOINT="https://invalid-endpoint.es.amazonaws.com" \
    batch-embedding-job:latest \
    --tickers TEST \
    --max-tickers 1 \
    --opensearch-endpoint "https://invalid-endpoint.es.amazonaws.com"
```

**Expected**: Script should fail with clear error message (not crash).

### Scenario 5: Small Real Test

Test with 1-2 real tickers if you have AWS access:

```bash
docker run -it --rm \
    -v "$(pwd)/output:/opt/ml/processing/output" \
    -e AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID" \
    -e AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY" \
    -e OPENSEARCH_ENDPOINT="$OPENSEARCH_ENDPOINT" \
    batch-embedding-job:latest \
    --tickers AAPL \
    --max-tickers 1 \
    --opensearch-endpoint "$OPENSEARCH_ENDPOINT" \
    --output-results /opt/ml/processing/output/test_results.json
```

Check results:
```bash
cat output/test_results.json
```

---

## Common Issues and Fixes

### Issue: "Module not found"

**Problem**: Missing dependencies in image

**Check**:
```bash
docker run --rm batch-embedding-job:latest pip list | grep transformers
```

**Fix**: Rebuild image, check `requirements.txt` includes all dependencies

### Issue: "Cannot connect to OpenSearch"

**Problem**: Network/authentication issue

**Test**:
```bash
# Test from host
curl -X GET "$OPENSEARCH_ENDPOINT" -u "username:password"

# Test from container
docker run --rm batch-embedding-job:latest \
    python3 -c "
from opensearchpy import OpenSearch
client = OpenSearch(
    hosts=[{'host': 'your-endpoint.es.amazonaws.com', 'port': 443}],
    http_auth=('user', 'pass'),
    use_ssl=True
)
print(client.info())
"
```

### Issue: "S3 access denied"

**Problem**: IAM permissions

**Test**:
```bash
# Test from container with credentials
docker run --rm \
    -e AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID" \
    -e AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY" \
    batch-embedding-job:latest \
    python3 -c "
import boto3
s3 = boto3.client('s3')
print(s3.list_buckets())
"
```

### Issue: "Out of memory"

**Problem**: Container needs more memory

**Test with more memory**:
```bash
docker run -it --rm --memory="8g" batch-embedding-job:latest ...
```

### Issue: Model download fails

**Problem**: No internet access or HuggingFace blocked

**Solution**: 
- Pre-download model and mount as volume
- Use cached model if available
- Or test without model loading (skip embedding test)

---

## Interactive Testing

### Shell into Container

Explore the container interactively:

```bash
docker run -it --rm \
    -v "$(pwd)/output:/opt/ml/processing/output" \
    -e OPENSEARCH_ENDPOINT="$OPENSEARCH_ENDPOINT" \
    batch-embedding-job:latest \
    /bin/bash
```

Inside container:
```bash
# Check Python path
echo $PYTHONPATH

# Test imports
python3 -c "from src.pipeline.stage_embed import EmbeddingStage; print('OK')"

# Check files
ls -la /opt/ml/code/scripts/
ls -la /opt/ml/code/src/

# Run script manually
python3 /opt/ml/code/scripts/batch_embed_all_tickers.py --help
```

---

## Simulating SageMaker Environment

SageMaker Processing Jobs mount data to specific paths. Simulate this:

```bash
docker run -it --rm \
    -v "$(pwd)/data/initial-dataset:/opt/ml/processing/input/data:ro" \
    -v "$(pwd)/output:/opt/ml/processing/output" \
    -v "$(pwd)/output:/opt/ml/checkpoints" \
    -e OPENSEARCH_ENDPOINT="$OPENSEARCH_ENDPOINT" \
    batch-embedding-job:latest \
    --sp500-csv /opt/ml/processing/input/data/2025-08-15_composition_sp500.csv \
    --opensearch-endpoint "$OPENSEARCH_ENDPOINT" \
    --checkpoint-path /opt/ml/checkpoints/checkpoint.json \
    --output-results /opt/ml/processing/output/results.json \
    --max-tickers 3
```

---

## Performance Testing

### Benchmark Embedding Generation

```bash
docker run --rm \
    batch-embedding-job:latest \
    python3 -c "
from transformers import AutoTokenizer, AutoModel
import torch
import time

model_name = 'llmware/industry-bert-sec-v0.1'
print(f'Loading model: {model_name}')

start = time.time()
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModel.from_pretrained(model_name)
load_time = time.time() - start

print(f'Model load time: {load_time:.2f}s')

# Test inference speed
text = 'This is a test sentence for embedding generation.'
inputs = tokenizer(text, return_tensors='pt', padding=True, truncation=True)

start = time.time()
with torch.no_grad():
    outputs = model(**inputs)
    embedding = outputs.last_hidden_state.mean(dim=1)
inference_time = time.time() - start

print(f'Inference time: {inference_time*1000:.2f}ms')
print(f'Embedding shape: {embedding.shape}')
"
```

---

## Validation Checklist

Before pushing to ECR, verify:

- [ ] Container builds successfully
- [ ] All Python imports work
- [ ] Required files are present in image
- [ ] Script shows help when run with `--help`
- [ ] Environment variables are accessible
- [ ] Model can be loaded (if internet available)
- [ ] Script accepts all expected arguments
- [ ] Error handling works (test with invalid inputs)
- [ ] Output directory is writable
- [ ] (Optional) Small real test succeeds

---

## Pre-Push Checklist

Before pushing to ECR and using in SageMaker:

1. ✅ All tests pass locally
2. ✅ Image size is reasonable (~7 GB is expected)
3. ✅ No sensitive data in image (check for hardcoded secrets)
4. ✅ Image tag is correct (e.g., `latest` or version tag)
5. ✅ Documentation is updated with image URI

---

## Next Steps After Testing

Once local tests pass:

1. **Push to ECR**:
   ```bash
   python3 scripts/push_to_ecr.py
   ```

2. **Verify in ECR Console**:
   - Check image appears in repository
   - Verify image size and tags

3. **Test in SageMaker**:
   - Create processing job with small dataset
   - Monitor logs
   - Verify results

---

## Troubleshooting

### "Cannot connect to Docker daemon"

**Solution**: Start Docker Desktop or Docker service

### "Image not found"

**Solution**: Build image first: `./scripts/build_and_push_manual.sh`

### "Permission denied"

**Solution**: 
```bash
chmod +x scripts/test_docker_image.sh
sudo usermod -aG docker $USER  # Linux, then logout/login
```

### Tests pass locally but fail in SageMaker

**Common causes**:
- Different Python version in SageMaker
- Missing environment variables
- Network/VPC configuration
- IAM permissions

**Solution**: Compare local environment with SageMaker logs

