#!/bin/bash
# Install PyTorch with GPU support after conda environment is created

set -e

echo "=============================================="
echo "PyTorch GPU Installation"
echo "=============================================="
echo ""

# Check if conda environment is activated
if [ -z "$CONDA_DEFAULT_ENV" ] || [ "$CONDA_DEFAULT_ENV" = "base" ]; then
    echo "[ERROR] Please activate the datathon-local environment first:"
    echo "        conda activate datathon-local"
    exit 1
fi

echo "[INFO] Active environment: $CONDA_DEFAULT_ENV"
echo ""

# Check for NVIDIA GPU
if command -v nvidia-smi &> /dev/null; then
    echo "[INFO] Detecting CUDA version..."
    nvidia-smi
    echo ""
    
    # Try to extract CUDA version
    CUDA_VERSION=$(nvidia-smi | grep -oP "CUDA Version: \K[0-9.]+")
    echo "[INFO] Detected CUDA Version: $CUDA_VERSION"
    echo ""
    
    # Recommend PyTorch version based on CUDA
    if [[ "$CUDA_VERSION" == 12.* ]]; then
        RECOMMENDED="cu121"
        echo "[RECOMMEND] For CUDA 12.x, use: cu121"
    elif [[ "$CUDA_VERSION" == 11.8* ]]; then
        RECOMMENDED="cu118"
        echo "[RECOMMEND] For CUDA 11.8, use: cu118"
    else
        RECOMMENDED="cu118"
        echo "[WARN] Unrecognized CUDA version, defaulting to cu118"
    fi
else
    echo "[WARN] nvidia-smi not found. GPU may not be available."
    RECOMMENDED="cpu"
    echo "[RECOMMEND] Installing CPU-only version"
fi

echo ""
echo "Choose PyTorch variant:"
echo "  1) CUDA 12.1 (cu121)"
echo "  2) CUDA 11.8 (cu118)"
echo "  3) CUDA 13.0 (cu130)"
echo "  4) CPU only"
echo ""
read -p "Enter choice [1-4] (default: 3): " choice
choice=${choice:-2}

case $choice in
    1)
        echo "[INFO] Installing PyTorch with CUDA 12.1 support..."
        pip install torch==2.1.2 --index-url https://download.pytorch.org/whl/cu121
        ;;
    2)
        echo "[INFO] Installing PyTorch with CUDA 11.8 support..."
        pip install torch==2.1.2 --index-url https://download.pytorch.org/whl/cu118
        ;;
    3)
        echo "[INFO] Installing PyTorch with CUDA 13.0 support..."
        pip install torch==2.1.2 --index-url https://download.pytorch.org/whl/cu130
        ;;
    4)
        echo "[INFO] Installing PyTorch CPU-only..."
        pip install torch==2.1.2 --index-url https://download.pytorch.org/whl/cpu
        ;;
    *)
        echo "[ERROR] Invalid choice"
        exit 1
        ;;
esac

echo ""
echo "[INFO] Verifying installation..."
python -c "import torch; print(f'PyTorch version: {torch.__version__}'); print(f'CUDA available: {torch.cuda.is_available()}')"

echo ""
echo "=============================================="
echo "[SUCCESS] PyTorch installation complete!"
echo "=============================================="
echo ""
echo "Next steps:"
echo "  1. Run: python check_gpu.py"
echo "  2. Test with: python -c \"import torch; print(torch.cuda.is_available())\""

