#!/bin/bash
# Build and push Docker image to Amazon ECR for SageMaker

set -e

# Configuration
AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-}"
IMAGE_NAME="batch-embedding-job"
IMAGE_TAG="${IMAGE_TAG:-latest}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

echo_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

echo_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo_error "AWS CLI is not installed."
    echo_error ""
    echo_error "To install AWS CLI:"
    echo_error "  See: scripts/INSTALL_AWS_CLI.md"
    echo_error ""
    echo_error "Alternative (no CLI needed):"
    echo_error "  1. Build image: ./scripts/build_and_push_manual.sh"
    echo_error "  2. Push via AWS Console ECR 'View push commands'"
    echo_error ""
    exit 1
fi

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo_error "Docker is not installed. Please install it first."
    exit 1
fi

# Get AWS account ID if not provided
if [ -z "$AWS_ACCOUNT_ID" ]; then
    echo_info "Getting AWS account ID..."
    AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    if [ -z "$AWS_ACCOUNT_ID" ]; then
        echo_error "Failed to get AWS account ID. Please set AWS_ACCOUNT_ID or configure AWS CLI."
        exit 1
    fi
    echo_info "Using AWS account ID: $AWS_ACCOUNT_ID"
fi

# ECR repository name
ECR_REPO_NAME="sagemaker/${IMAGE_NAME}"
ECR_REPOSITORY_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_NAME}"

echo_info "=========================================="
echo_info "SageMaker Docker Image Builder"
echo_info "=========================================="
echo_info "Region: $AWS_REGION"
echo_info "Account ID: $AWS_ACCOUNT_ID"
echo_info "Repository: $ECR_REPO_NAME"
echo_info "Image URI: $ECR_REPOSITORY_URI:$IMAGE_TAG"
echo_info "=========================================="
echo ""

# Step 1: Create ECR repository if it doesn't exist
echo_info "Step 1: Checking ECR repository..."
if aws ecr describe-repositories --repository-names "$ECR_REPO_NAME" --region "$AWS_REGION" &> /dev/null; then
    echo_info "Repository $ECR_REPO_NAME already exists"
else
    echo_info "Creating ECR repository: $ECR_REPO_NAME"
    aws ecr create-repository \
        --repository-name "$ECR_REPO_NAME" \
        --region "$AWS_REGION" \
        --image-scanning-configuration scanOnPush=true \
        --encryption-configuration encryptionType=AES256 || {
        echo_error "Failed to create ECR repository"
        exit 1
    }
    echo_info "Repository created successfully"
fi

# Step 2: Login to ECR
echo_info "Step 2: Logging in to Amazon ECR..."
aws ecr get-login-password --region "$AWS_REGION" | \
    docker login --username AWS --password-stdin "$ECR_REPOSITORY_URI" || {
    echo_error "Failed to login to ECR"
    exit 1
}
echo_info "Logged in successfully"

# Step 3: Build Docker image
echo_info "Step 3: Building Docker image..."
echo_info "This may take several minutes (downloading base image and dependencies)..."
docker build \
    -f Dockerfile.sagemaker \
    -t "${IMAGE_NAME}:${IMAGE_TAG}" \
    -t "${ECR_REPOSITORY_URI}:${IMAGE_TAG}" \
    . || {
    echo_error "Docker build failed"
    exit 1
}
echo_info "Image built successfully"

# Step 4: Push image to ECR
echo_info "Step 4: Pushing image to ECR..."
docker push "${ECR_REPOSITORY_URI}:${IMAGE_TAG}" || {
    echo_error "Failed to push image to ECR"
    exit 1
}
echo_info "Image pushed successfully"

# Step 5: Print summary
echo ""
echo_info "=========================================="
echo_info "Build Complete!"
echo_info "=========================================="
echo_info "Image URI: ${ECR_REPOSITORY_URI}:${IMAGE_TAG}"
echo_info ""
echo_info "To use this image in SageMaker:"
echo_info "1. Go to SageMaker Console -> Processing jobs"
echo_info "2. Create processing job"
echo_info "3. Select 'Use a different image location'"
echo_info "4. Enter: ${ECR_REPOSITORY_URI}:${IMAGE_TAG}"
echo_info ""
echo_info "Or use in Python SDK:"
echo_info "  image_uri = '${ECR_REPOSITORY_URI}:${IMAGE_TAG}'"
echo_info "=========================================="

