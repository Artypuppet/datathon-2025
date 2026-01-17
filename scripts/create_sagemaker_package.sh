#!/bin/bash
# Script to create SageMaker deployment package

set -e

echo "[INFO] Creating SageMaker deployment package..."

# Configuration
DEPLOY_DIR="sagemaker_deploy"
ZIP_FILE="sagemaker_code.zip"
BUCKET="${S3_BUCKET:-your-datathon-bucket}"
S3_PATH="sagemaker-code/batch-embedding.zip"

# Clean previous deployment
if [ -d "$DEPLOY_DIR" ]; then
    echo "[INFO] Cleaning previous deployment directory..."
    rm -rf "$DEPLOY_DIR"
fi

if [ -f "$ZIP_FILE" ]; then
    echo "[INFO] Removing previous zip file..."
    rm -f "$ZIP_FILE"
fi

# Create directories
mkdir -p "$DEPLOY_DIR/scripts"
mkdir -p "$DEPLOY_DIR/src"

echo "[INFO] Copying scripts..."
cp scripts/batch_embed_all_tickers.py "$DEPLOY_DIR/scripts/"
cp scripts/sagemaker_entrypoint.py "$DEPLOY_DIR/scripts/"

echo "[INFO] Copying source code..."
cp -r src/ "$DEPLOY_DIR/"

echo "[INFO] Creating requirements.txt..."
cat > "$DEPLOY_DIR/requirements.txt" << 'EOF'
torch>=2.0.0
transformers>=4.30.0
numpy>=1.24.0
pandas>=2.0.0
opensearch-py>=2.0.0
boto3>=1.28.0
python-dotenv>=1.0.0
spacy>=3.7.0
EOF

echo "[INFO] Creating startup script..."
cat > "$DEPLOY_DIR/run.sh" << 'EOF'
#!/bin/bash
# SageMaker startup script

echo "[INFO] Installing dependencies..."
pip install -r requirements.txt -q

echo "[INFO] Setting Python path..."
export PYTHONPATH="${PYTHONPATH}:/opt/ml/processing/input/code:/opt/ml/processing/input/code/src"

echo "[INFO] Running batch embedding script..."
python3 scripts/batch_embed_all_tickers.py "$@"
EOF

chmod +x "$DEPLOY_DIR/run.sh"

echo "[INFO] Creating zip archive..."
cd "$DEPLOY_DIR"
zip -r "../$ZIP_FILE" . > /dev/null
cd ..

echo "[OK] Package created: $ZIP_FILE"
echo "[INFO] Package size: $(du -h $ZIP_FILE | cut -f1)"

# Upload to S3 if bucket specified
if [ "$BUCKET" != "your-datathon-bucket" ]; then
    echo "[INFO] Uploading to S3..."
    aws s3 cp "$ZIP_FILE" "s3://$BUCKET/$S3_PATH" || {
        echo "[WARN] Failed to upload to S3. Upload manually:"
        echo "  aws s3 cp $ZIP_FILE s3://$BUCKET/$S3_PATH"
    }
    echo "[OK] Uploaded to s3://$BUCKET/$S3_PATH"
else
    echo "[INFO] To upload manually:"
    echo "  aws s3 cp $ZIP_FILE s3://$BUCKET/$S3_PATH"
fi

echo ""
echo "[SUCCESS] Deployment package ready!"
echo ""
echo "Next steps:"
echo "1. Go to AWS Console -> SageMaker -> Processing jobs"
echo "2. Create processing job with these settings:"
echo "   - Input: s3://$BUCKET/$S3_PATH"
echo "   - Entry point: scripts/batch_embed_all_tickers.py"
echo "   - See AWS_CONSOLE_SETUP.md for full instructions"

