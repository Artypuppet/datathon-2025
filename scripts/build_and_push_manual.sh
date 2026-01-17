#!/bin/bash
# Manual Docker build script (doesn't require AWS CLI)
# Use this if AWS CLI is not installed - you'll push manually via console

set -e

# Configuration
IMAGE_NAME="batch-embedding-job"
IMAGE_TAG="${IMAGE_TAG:-latest}"
AWS_REGION="${AWS_REGION:-us-east-1}"

echo "[INFO] =========================================="
echo "[INFO] Docker Image Builder (Manual Push)"
echo "[INFO] =========================================="
echo "[INFO] This script builds the image locally."
echo "[INFO] You'll need to push it manually using:"
echo "[INFO]   1. AWS Console ECR 'View push commands'"
echo "[INFO]   2. Or install AWS CLI and use build_and_push_image.sh"
echo "[INFO] =========================================="
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "[ERROR] Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Dockerfile exists
if [ ! -f "Dockerfile.sagemaker" ]; then
    echo "[ERROR] Dockerfile.sagemaker not found in current directory"
    exit 1
fi

# Check if requirements.txt exists
if [ ! -f "requirements.txt" ]; then
    echo "[ERROR] requirements.txt not found in current directory"
    exit 1
fi

echo "[INFO] Building Docker image..."
echo "[INFO] This may take 10-15 minutes (downloading base image and dependencies)..."
echo ""

docker build \
    -f Dockerfile.sagemaker \
    -t "${IMAGE_NAME}:${IMAGE_TAG}" \
    . || {
    echo "[ERROR] Docker build failed"
    exit 1
}

echo ""
echo "[OK] Image built successfully: ${IMAGE_NAME}:${IMAGE_TAG}"
echo ""
echo "[INFO] =========================================="
echo "[INFO] Next Steps: Push to ECR"
echo "[INFO] =========================================="
echo ""
echo "Option 1: Use AWS Console (No CLI needed)"
echo "  1. Go to: AWS Console -> ECR -> Repositories"
echo "  2. Create repository: sagemaker/batch-embedding-job"
echo "  3. Click 'View push commands'"
echo "  4. Follow the commands shown (login, tag, push)"
echo ""
echo "Option 2: Install AWS CLI and use automated script"
echo "  1. Install AWS CLI (see INSTALL_AWS_CLI.md)"
echo "  2. Run: ./scripts/build_and_push_image.sh"
echo ""
echo "[INFO] =========================================="

