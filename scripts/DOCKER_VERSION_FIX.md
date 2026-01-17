# Docker Image Version Compatibility Fix

## Problem

The Docker image was failing with compatibility errors:
1. `AttributeError: module 'torch.utils._pytree' has no attribute 'register_pytree_node'`
2. NumPy initialization warnings

## Root Cause

The base image `pytorch/pytorch:2.1.0-cuda11.8-cudnn8-runtime` comes with:
- PyTorch 2.1.0 pre-installed
- A specific NumPy version

Installing:
- `torch>=2.0.0` would reinstall/upgrade PyTorch causing conflicts
- `transformers>=4.30.0` would install the latest (possibly 4.36+), which requires PyTorch 2.1.1+ and uses newer pytree APIs

## Solution

### Updated `requirements.txt`

1. **Removed torch** - already in base image, don't reinstall
2. **Pinned transformers to 4.34.1** - compatible with PyTorch 2.1.0
3. **Constrained NumPy** - `>=1.24.0,<2.0.0` to avoid NumPy 2.0 compatibility issues

### Version Compatibility Matrix

| PyTorch Version | Compatible transformers | Notes |
|----------------|------------------------|-------|
| 2.1.0 | 4.30.0 - 4.34.1 | Use 4.34.1 (recommended) |
| 2.1.1+ | 4.35.0+ | Can use newer versions |

## Testing

After rebuilding the image:

```bash
# Rebuild image
./scripts/build_and_push_manual.sh

# Test imports
docker run --rm batch-embedding-job:latest python3 -c "
import torch
import transformers
from transformers import AutoTokenizer, AutoModel
print(f'PyTorch: {torch.__version__}')
print(f'transformers: {transformers.__version__}')
print('[OK] Imports successful')
"

# Test model loading
docker run --rm batch-embedding-job:latest python3 -c "
from transformers import AutoTokenizer, AutoModel
tokenizer = AutoTokenizer.from_pretrained('llmware/industry-bert-sec-v0.1')
model = AutoModel.from_pretrained('llmware/industry-bert-sec-v0.1')
print('[OK] Model loaded')
"
```

## Alternative: Upgrade Base Image

If you need newer transformers features, consider upgrading the base image:

```dockerfile
# Option 1: PyTorch 2.1.2 (compatible with transformers 4.35+)
FROM pytorch/pytorch:2.1.2-cuda11.8-cudnn8-runtime

# Option 2: Latest stable (may have breaking changes)
FROM pytorch/pytorch:2.2.0-cuda11.8-cudnn8-runtime
```

Then update `requirements.txt`:
```txt
transformers==4.35.2  # or newer
```

## Verifying Versions

Check what's installed in the image:

```bash
docker run --rm batch-embedding-job:latest pip list | grep -E "(torch|transformers|numpy)"
```

Expected output:
```
numpy              1.24.x
torch              2.1.0+cu118
transformers       4.34.1
```

## Troubleshooting

### Still getting pytree errors?

Try even older transformers:
```txt
transformers==4.33.3
```

### NumPy errors?

Check NumPy version in base image:
```bash
docker run --rm pytorch/pytorch:2.1.0-cuda11.8-cudnn8-runtime python -c "import numpy; print(numpy.__version__)"
```

Then pin to compatible version in `requirements.txt`:
```txt
numpy==1.24.3  # Match base image version
```

### Want to use latest everything?

Upgrade base image and remove version pins:
```dockerfile
FROM pytorch/pytorch:2.2.0-cuda11.8-cudnn8-runtime
```

```txt
# Use latest compatible versions
transformers>=4.35.0
```

