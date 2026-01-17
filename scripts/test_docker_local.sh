#!/bin/bash
# Test Docker image locally with real AWS resources (if available)

set -e

# Configuration
IMAGE_NAME="batch-embedding-job"
IMAGE_TAG="${IMAGE_TAG:-latest}"

# Function to load .env file
load_env_file() {
    local env_file="$1"
    if [ -f "$env_file" ]; then
        echo "[INFO] Loading environment variables from: $env_file"
        # Read .env file, skip comments and empty lines, export variables
        while IFS= read -r line || [ -n "$line" ]; do
            # Skip comments and empty lines
            [[ "$line" =~ ^[[:space:]]*# ]] && continue
            [[ -z "$line" ]] && continue
            
            # Remove whitespace around =
            line=$(echo "$line" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
            
            # Export variable if it contains =
            if [[ "$line" == *"="* ]]; then
                export "$line"
            fi
        done < "$env_file"
        return 0
    fi
    return 1
}

# Try to load .env file from project root or script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Try project root first, then script directory
if ! load_env_file "$PROJECT_ROOT/.env"; then
    load_env_file "$SCRIPT_DIR/.env" || true
fi

echo "[INFO] =========================================="
echo "[INFO] Local Docker Test with Real Resources"
echo "[INFO] =========================================="
echo ""

# Check environment variables
if [ -z "$OPENSEARCH_ENDPOINT" ]; then
    echo "[WARN] OPENSEARCH_ENDPOINT not set"
    echo "[INFO] Set it in .env file or: export OPENSEARCH_ENDPOINT=https://your-endpoint.es.amazonaws.com"
fi

# Check OpenSearch authentication
OPENSEARCH_USE_IAM_AUTH="${OPENSEARCH_USE_IAM_AUTH:-false}"
if [ "$OPENSEARCH_USE_IAM_AUTH" != "true" ]; then
    # Using basic auth - need username and password
    if [ -z "$OPENSEARCH_USERNAME" ] || [ -z "$OPENSEARCH_PASSWORD" ]; then
        echo "[WARN] OPENSEARCH_USERNAME and OPENSEARCH_PASSWORD not set"
        echo "[INFO] Set them in .env file for basic auth, or set OPENSEARCH_USE_IAM_AUTH=true for IAM auth"
    fi
else
    echo "[INFO] Using IAM authentication for OpenSearch"
fi

if [ -z "$S3_BUCKET" ]; then
    echo "[WARN] S3_BUCKET not set"
    echo "[INFO] Set it in .env file or: export S3_BUCKET=your-bucket"
fi

# Check AWS credentials
if [ -z "$AWS_ACCESS_KEY_ID" ] || [ -z "$AWS_SECRET_ACCESS_KEY" ]; then
    echo "[WARN] AWS credentials not set"
    echo "[INFO] Set them in .env file or export AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY"
fi

# Create output directory
mkdir -p output/docker_test

echo "[INFO] Running Docker container with test configuration..."
echo "[INFO] Processing 2 test tickers (AAPL, MSFT)..."
echo ""

# Run container with real AWS credentials
# Variables are loaded from .env file or environment
docker run -it --rm \
    -v "$(pwd)/output:/opt/ml/processing/output" \
    -v "$(pwd)/data:/opt/ml/processing/input/data:ro" \
    -e AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID}" \
    -e AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY}" \
    -e AWS_DEFAULT_REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-us-east-1}}" \
    -e OPENSEARCH_ENDPOINT="${OPENSEARCH_ENDPOINT}" \
    -e OPENSEARCH_USERNAME="${OPENSEARCH_USERNAME}" \
    -e OPENSEARCH_PASSWORD="${OPENSEARCH_PASSWORD}" \
    -e OPENSEARCH_USE_IAM_AUTH="${OPENSEARCH_USE_IAM_AUTH:-false}" \
    -e S3_BUCKET="${S3_BUCKET}" \
    "${IMAGE_NAME}:${IMAGE_TAG}" \
    --tickers AAPL MSFT \
    --max-tickers 2 \
    --opensearch-endpoint "${OPENSEARCH_ENDPOINT}" \
    --opensearch-index company_embeddings \
    --vectordb-backend opensearch \
    --checkpoint-path "/tmp/test_checkpoint.json" \
    --output-results "/opt/ml/processing/output/test_results.json"

echo ""
echo "[OK] Test completed! Check output/docker_test/ for results"

