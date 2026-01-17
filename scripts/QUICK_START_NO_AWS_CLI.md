# Quick Start: Docker Image Setup (No AWS CLI Required)

If you don't have AWS CLI installed, here are your options:

---

## Option 1: Use Python Script (Easiest) ⭐ Recommended

**Prerequisites**: Docker + Python + boto3

```bash
# Step 1: Install boto3 if needed
pip install boto3

# Step 2: Build Docker image
./scripts/build_and_push_manual.sh

# Step 3: Push to ECR (handles everything automatically)
python3 scripts/push_to_ecr.py
```

**That's it!** The script will:
- Auto-detect your AWS account ID
- Login to ECR
- Tag the image
- Push to ECR
- Print the image URI

**Configure AWS credentials** (if not already):
```bash
export AWS_ACCESS_KEY_ID=your-key
export AWS_SECRET_ACCESS_KEY=your-secret
export AWS_REGION=us-east-1
```

Or create `~/.aws/credentials`:
```ini
[default]
aws_access_key_id = your-key
aws_secret_access_key = your-secret
region = us-east-1
```

---

## Option 2: Build Locally, Push via Console

**Prerequisites**: Docker only

```bash
# Step 1: Build image
./scripts/build_and_push_manual.sh

# Step 2: Create ECR repository via AWS Console
#   - Go to: AWS Console -> ECR
#   - Create repository: sagemaker/batch-embedding-job

# Step 3: Get push commands from Console
#   - In repository page, click "View push commands"
#   - BUT: Skip command #1 (requires AWS CLI)
#   - Use Python script for login instead:
python3 scripts/push_to_ecr.py --login-only

# Step 4: Run commands #2 and #3 from Console
docker tag batch-embedding-job:latest ACCOUNT.dkr.ecr.REGION.amazonaws.com/sagemaker/batch-embedding-job:latest
docker push ACCOUNT.dkr.ecr.REGION.amazonaws.com/sagemaker/batch-embedding-job:latest
```

See [DOCKER_PUSH_CONSOLE.md](DOCKER_PUSH_CONSOLE.md) for detailed steps.

---

## Option 3: Install AWS CLI (Most Flexible)

If you want full automation, install AWS CLI:

**Linux/WSL**:
```bash
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install
aws configure
```

**macOS**:
```bash
brew install awscli
aws configure
```

See [INSTALL_AWS_CLI.md](INSTALL_AWS_CLI.md) for full instructions.

Then use:
```bash
./scripts/build_and_push_image.sh
```

---

## Quick Comparison

| Method | Requirements | Difficulty | Automation |
|--------|-------------|------------|------------|
| **Python Script** | Docker + boto3 | Easy | Full |
| **Console Push** | Docker | Medium | Manual |
| **AWS CLI** | Docker + AWS CLI | Easy | Full |

---

## Recommended Workflow

**If you have Python/boto3**:
1. ✅ Use `push_to_ecr.py` (Option 1) - Simplest!

**If you only have Docker**:
1. Build with `build_and_push_manual.sh`
2. Use ECR Console "View push commands" for manual steps
3. Or install boto3: `pip install boto3` and use Option 1

**For production**:
1. Install AWS CLI (better for CI/CD)
2. Use automated scripts

---

## Need Help?

- **Docker build issues**: See [DOCKER_SETUP.md](DOCKER_SETUP.md)
- **Console push guide**: See [DOCKER_PUSH_CONSOLE.md](DOCKER_PUSH_CONSOLE.md)
- **AWS CLI install**: See [INSTALL_AWS_CLI.md](INSTALL_AWS_CLI.md)
- **Console job setup**: See [AWS_CONSOLE_SETUP.md](AWS_CONSOLE_SETUP.md)

