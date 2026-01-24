#!/bin/bash
# Quick setup script for local development environment

set -e  # Exit on error

echo "=========================================="
echo "Risk Scorer 2025 Local Development Setup"
echo "=========================================="
echo ""

# Check if conda is installed
if ! command -v conda &> /dev/null; then
    echo "[ERROR] Conda not found. Please install Miniconda first:"
    echo "   https://docs.conda.io/en/latest/miniconda.html"
    exit 1
fi

echo "[OK] Conda found"

# Create environment
echo ""
echo "Creating local development environment..."
if conda env list | grep -q "risk-scorer-local"; then
    echo "[WARN] Environment 'risk-scorer-local' already exists."
    read -p "Remove and recreate? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        conda env remove -n risk-scorer-local -y
        conda env create -f environment-local.yml
    fi
else
    conda env create -f environment-local.yml
fi

echo ""
echo "[OK] Environment created"

# Activate and download spaCy model
echo ""
echo "Downloading spaCy model..."
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate risk-scorer-local
# Use direct pip install to avoid 404 errors with spacy download command
pip install https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.1/en_core_web_sm-3.7.1-py3-none-any.whl

echo ""
echo "[OK] spaCy model downloaded"

# Create test directories
echo ""
echo "Creating test data directories..."
mkdir -p data/test-sample/{filings,legislation,processed,cache}
mkdir -p logs
mkdir -p src/{parsers,features,scoring,dashboard,utils,pipeline}
mkdir -p tests/{unit,integration,e2e,fixtures}

echo "[OK] Directories created"

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo ""
    echo "Creating .env file..."
    cat > .env << EOF
# Environment Configuration
ENVIRONMENT=local

# Local Configuration
BATCH_SIZE=8
MAX_WORKERS=2
TEST_MODE=true

# Model Configuration
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
SPACY_MODEL=en_core_web_sm

# AWS Configuration (leave empty for local dev)
AWS_REGION=
S3_BUCKET=
OPENSEARCH_ENDPOINT=

# Polymarket API (optional)
POLYMARKET_API_KEY=
EOF
    echo "[OK] .env file created"
else
    echo "[WARN] .env file already exists, skipping..."
fi

# Create sample test files
echo ""
echo "Creating sample test data..."

# Create a sample parsed filing JSON
cat > data/test-sample/processed/SAMPLE.json << 'EOF'
{
  "ticker": "SAMPLE",
  "company": "Sample Corp",
  "source": "10-K",
  "filing_date": "2024-11-01",
  "sections": [
    {
      "title": "Business",
      "text": "Sample Corp is a technology company focused on innovation."
    },
    {
      "title": "Risk Factors",
      "text": "The Company faces regulatory risks related to international trade."
    }
  ],
  "entities": [
    {"text": "Sample Corp", "label": "ORG"},
    {"text": "technology", "label": "PRODUCT"}
  ]
}
EOF

# Create sample risk scores CSV
cat > data/test-sample/sample_risk_scores.csv << EOF
ticker,company,sector,risk_score,risk_level
AAPL,Apple Inc.,Technology,0.78,high
MSFT,Microsoft Corp.,Technology,0.65,medium
JNJ,Johnson & Johnson,Healthcare,0.45,medium
JPM,JPMorgan Chase,Financials,0.52,medium
XOM,Exxon Mobil,Energy,0.71,high
EOF

echo "[OK] Sample data created"

# Verification
echo ""
echo "Verifying installation..."
python << EOF
try:
    import torch
    print("[OK] PyTorch installed")
    import spacy
    nlp = spacy.load("en_core_web_sm")
    print("[OK] spaCy model loaded")
    from sentence_transformers import SentenceTransformer
    print("[OK] Sentence-Transformers installed")
    import streamlit
    print("[OK] Streamlit installed")
    import pandas
    print("[OK] Pandas installed")
    print("\n[SUCCESS] All core libraries installed successfully!")
except Exception as e:
    print(f"\n[ERROR] Verification failed: {e}")
    exit(1)
EOF

echo ""
echo "=========================================="
echo "[SUCCESS] Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Activate environment:  conda activate risk-scorer-local"
echo "  2. Copy sample filings:   cp data/initial-dataset/fillings/AAPL/*.html data/test-sample/filings/"
echo "  3. Start coding!          python src/parsers/filing_parser.py"
echo "  4. Run tests:             pytest tests/unit/"
echo "  5. Launch dashboard:      streamlit run src/dashboard/dashboard.py"
echo ""
echo "Documentation: .cursor/00_README.md"
echo "Local workflow: .cursor/references/local_testing_workflow.md"
echo ""

