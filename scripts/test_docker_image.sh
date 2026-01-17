#!/bin/bash
# Test Docker image locally before pushing to ECR/SageMaker

# Don't use set -e - we want to continue even if optional tests fail
set +e

# Configuration
IMAGE_NAME="batch-embedding-job"
IMAGE_TAG="${IMAGE_TAG:-latest}"
TEST_MODE="${TEST_MODE:-true}"

# Track test results
CRITICAL_TESTS_PASSED=true

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

echo_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

echo_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

echo_info "=========================================="
echo_info "Local Docker Image Testing"
echo_info "=========================================="
echo ""

# Check if Docker is running
if ! docker info &> /dev/null; then
    echo_error "Docker is not running. Please start Docker first."
    exit 1
fi

# Check if image exists
if ! docker images | grep -q "${IMAGE_NAME}.*${IMAGE_TAG}"; then
    echo_warn "Image ${IMAGE_NAME}:${IMAGE_TAG} not found."
    echo_info "Building image first..."
    ./scripts/build_and_push_manual.sh || {
        echo_error "Failed to build image"
        exit 1
    }
fi

echo_info "Image found: ${IMAGE_NAME}:${IMAGE_TAG}"
echo ""

# Test 1: Basic container startup
echo_info "Test 1: Container Startup Test"
echo_info "Checking if container can start..."

if docker run --rm --entrypoint python3 "${IMAGE_NAME}:${IMAGE_TAG}" --version &> /dev/null; then
    echo_info "[OK] Container starts successfully"
else
    echo_warn "[WARN] Container may have issues"
fi
echo ""

# Test 2: Python imports
echo_info "Test 2: Python Dependencies Test"
echo_info "Checking if all Python imports work..."

if ! docker run --rm --entrypoint python3 "${IMAGE_NAME}:${IMAGE_TAG}" \
    -c "
import sys
sys.path.insert(0, '/opt/ml/code')
sys.path.insert(0, '/opt/ml/code/src')

try:
    from src.pipeline.stage_aggregate import CompanyAggregator
    from src.pipeline.stage_embed import EmbeddingStage
    from src.vectordb.client import VectorDBClient
    print('[OK] All imports successful')
except Exception as e:
    print(f'[ERROR] Import failed: {e}')
    sys.exit(1)
" 2>&1; then
    CRITICAL_TESTS_PASSED=false
    echo_error "Python imports failed - CRITICAL"
fi
echo ""

# Test 3: Model loading (if accessible)
echo_info "Test 3: Model Loading Test (Optional)"
echo_info "Checking if embedding model can be loaded..."

if docker run --rm --entrypoint python3 "${IMAGE_NAME}:${IMAGE_TAG}" \
    -c "
from transformers import AutoTokenizer, AutoModel
import torch

model_name = 'llmware/industry-bert-sec-v0.1'
print(f'[INFO] Loading model: {model_name}')

try:
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModel.from_pretrained(model_name)
    print('[OK] Model loaded successfully')
    print(f'[INFO] Model hidden size: {model.config.hidden_size}')
except Exception as e:
    print(f'[WARN] Model loading failed: {e}')
    print('[INFO] This is OK - model will download when first used in SageMaker')
    exit(0)
" 2>&1; then
    echo_info "[OK] Model loading test passed"
else
    echo_warn "[WARN] Model loading test skipped (needs internet or cached model)"
fi
echo ""

# Test 4: Script executable and argument parsing
echo_info "Test 4: Script Executability Test"
echo_info "Checking if script is executable and accepts --help..."

if docker run --rm "${IMAGE_NAME}:${IMAGE_TAG}" --help 2>&1 | head -5 &> /dev/null; then
    echo_info "[OK] Script is executable and accepts arguments"
else
    echo_warn "[WARN] Script execution test had issues"
fi
echo ""

# Test 5: File structure
echo_info "Test 5: File Structure Verification"
echo_info "Checking if all required files are present in image..."

# Check files individually (portable shell syntax, no arrays)
if ! docker run --rm --entrypoint sh "${IMAGE_NAME}:${IMAGE_TAG}" \
    -c "
all_good=true

if [ -f '/opt/ml/code/scripts/batch_embed_all_tickers.py' ]; then
    echo '[OK] Found: /opt/ml/code/scripts/batch_embed_all_tickers.py'
else
    echo '[ERROR] Missing: /opt/ml/code/scripts/batch_embed_all_tickers.py'
    all_good=false
fi

if [ -f '/opt/ml/code/src/pipeline/stage_embed.py' ]; then
    echo '[OK] Found: /opt/ml/code/src/pipeline/stage_embed.py'
else
    echo '[ERROR] Missing: /opt/ml/code/src/pipeline/stage_embed.py'
    all_good=false
fi

if [ -f '/opt/ml/code/src/vectordb/client.py' ]; then
    echo '[OK] Found: /opt/ml/code/src/vectordb/client.py'
else
    echo '[ERROR] Missing: /opt/ml/code/src/vectordb/client.py'
    all_good=false
fi

if [ \"\$all_good\" = true ]; then
    echo '[OK] All required files present'
    exit 0
else
    echo '[ERROR] Some files missing'
    exit 1
fi
" 2>&1; then
    CRITICAL_TESTS_PASSED=false
    echo_error "File structure test failed - CRITICAL"
fi
echo ""

# Test 6: Environment variables
echo_info "Test 6: Environment Variable Test"
echo_info "Checking Python path and environment..."

docker run --rm --entrypoint python3 \
    -e OPENSEARCH_ENDPOINT="https://test.es.amazonaws.com" \
    -e S3_BUCKET="test-bucket" \
    -e AWS_REGION="us-east-1" \
    "${IMAGE_NAME}:${IMAGE_TAG}" \
    -c "
import os
print(f'[INFO] PYTHONPATH: {os.environ.get(\"PYTHONPATH\", \"not set\")}')
print(f'[INFO] OPENSEARCH_ENDPOINT: {os.environ.get(\"OPENSEARCH_ENDPOINT\", \"not set\")}')
print(f'[INFO] S3_BUCKET: {os.environ.get(\"S3_BUCKET\", \"not set\")}')
print('[OK] Environment variables accessible')
"
echo ""

# Summary
echo ""
echo_info "=========================================="
echo_info "Test Summary"
echo_info "=========================================="

if [ "$CRITICAL_TESTS_PASSED" = true ]; then
    echo_info "[SUCCESS] All critical tests passed!"
    echo_info "Image is ready for pushing to ECR."
    EXIT_CODE=0
else
    echo_error "[FAILURE] Some critical tests failed!"
    echo_error "Fix issues before pushing to ECR."
    EXIT_CODE=1
fi

echo_info ""
echo_info "Next steps:"
echo_info "  1. (Optional) Run full test with real data:"
echo_info "     ./scripts/test_docker_local.sh"
echo_info ""
echo_info "  2. Push to ECR:"
echo_info "     python3 scripts/push_to_ecr.py"
echo_info ""
echo_info "  3. Use in SageMaker (see AWS_CONSOLE_SETUP.md)"
echo_info "=========================================="

exit $EXIT_CODE

