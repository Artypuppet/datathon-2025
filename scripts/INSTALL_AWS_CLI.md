# Installing AWS CLI

AWS CLI is needed for:
- Building and pushing Docker images to ECR
- Managing S3 uploads
- Creating/managing AWS resources

---

## Installation Options

### Option 1: Install AWS CLI v2 (Recommended)

#### Linux/WSL:

```bash
# Download installer
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"

# Unzip
unzip awscliv2.zip

# Install
sudo ./aws/install

# Verify installation
aws --version
```

#### macOS:

```bash
# Using Homebrew (easiest)
brew install awscli

# Or download installer
curl "https://awscli.amazonaws.com/AWSCLIV2.pkg" -o "AWSCLIV2.pkg"
sudo installer -pkg AWSCLIV2.pkg -target /
```

#### Windows:

1. Download MSI installer: https://awscli.amazonaws.com/AWSCLIV2.msi
2. Run installer
3. Open new terminal and verify: `aws --version`

### Option 2: Using Python pip (Simpler but older version)

```bash
pip install awscli

# Or with conda
conda install -c conda-forge awscli
```

**Note**: pip installs v1, which works but v2 is recommended.

---

## Configure AWS CLI

After installation, configure credentials:

```bash
aws configure
```

You'll be prompted for:
- **AWS Access Key ID**: Get from IAM console → Users → Security credentials
- **AWS Secret Access Key**: Get from same place (only shown once)
- **Default region**: `us-east-1` (or your preferred region)
- **Default output format**: `json`

**To get credentials**:
1. Go to AWS Console → IAM → Users
2. Click your username
3. Security credentials tab
4. Create access key
5. Download or copy key ID and secret

---

## Verify Installation

```bash
# Check version
aws --version

# Test configuration
aws sts get-caller-identity

# Should return your account ID and user info
```

---

## Alternative: Use AWS Console for ECR Operations

If you prefer not to install AWS CLI, you can:
1. Build Docker image locally
2. Use AWS Console to create ECR repository
3. Use AWS Console to push image (via "View push commands")
4. Or use the browser-based approach below

---

## Manual ECR Setup (Without AWS CLI)

### Step 1: Create ECR Repository via Console

1. Go to **AWS Console** → **ECR** (Elastic Container Registry)
2. Click **Create repository**
3. **Visibility settings**: Private
4. **Repository name**: `sagemaker/batch-embedding-job`
5. **Tag immutability**: Enable (optional, recommended)
6. **Scan on push**: Enable (for security)
7. Click **Create repository**

### Step 2: Get Push Commands from Console

1. In your ECR repository, click **View push commands**
2. AWS Console will show you the exact commands to run
3. These commands will include the Docker login step

### Step 3: Build and Push (Using Console Commands)

1. Copy the login command from ECR console
2. Run it in your terminal (requires Docker)
3. Build your image
4. Tag image
5. Push image

---

## Troubleshooting

### "aws: command not found"

**Linux/WSL**: Make sure `/usr/local/bin` is in your PATH:
```bash
export PATH=/usr/local/bin:$PATH
echo 'export PATH=/usr/local/bin:$PATH' >> ~/.bashrc
```

**macOS**: If installed via Homebrew, it should work automatically.

### "Unable to locate credentials"

**Solution**: Run `aws configure` and enter your credentials.

### "Access Denied"

**Solution**: Check IAM permissions:
- ECR: `ecr:GetAuthorizationToken`, `ecr:BatchCheckLayerAvailability`, `ecr:GetDownloadUrlForLayer`, `ecr:BatchGetImage`, `ecr:PutImage`
- S3: `s3:GetObject`, `s3:PutObject`, `s3:ListBucket`

---

## Quick Test

```bash
# Test AWS access
aws s3 ls

# Test ECR access
aws ecr describe-repositories --region us-east-1

# Test IAM
aws sts get-caller-identity
```

If these work, you're ready to build and push Docker images!

