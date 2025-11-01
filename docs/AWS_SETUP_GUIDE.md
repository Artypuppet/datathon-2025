# AWS S3 Setup Guide

Complete guide to setting up AWS credentials and S3 for the project.

## AWS vs GCP Comparison

If you're coming from GCP, here's the mapping:

| GCP | AWS | Purpose |
|-----|-----|---------|
| Service Account | IAM User | Identity for programmatic access |
| Service Account Key (JSON) | Access Key ID + Secret Access Key | Credentials for API calls |
| Cloud Storage | S3 | Object storage |
| GCS Bucket | S3 Bucket | Container for objects |
| IAM Roles | IAM Policies | Permissions |

## Quick Setup (5 Steps)

### Step 1: Create AWS Account

If you don't have one:
1. Go to https://aws.amazon.com/
2. Click "Create an AWS Account"
3. Follow the signup process
4. You'll get 12 months of Free Tier access

**Free Tier Includes:**
- 5GB S3 storage
- 20,000 GET requests
- 2,000 PUT requests per month
- More than enough for this project!

### Step 2: Create IAM User (Similar to GCP Service Account)

1. **Log into AWS Console**: https://console.aws.amazon.com/

2. **Navigate to IAM**:
   - Search for "IAM" in the top search bar
   - Click "IAM" service

3. **Create User**:
   - Click "Users" in left sidebar
   - Click "Create user" button
   - Enter username: `datathon-2025-dev` (or any name you prefer)
   - Click "Next"

4. **Set Permissions**:
   - Select "Attach policies directly"
   - Search for and check: **`AmazonS3FullAccess`**
   - This gives full S3 access (like GCP Storage Admin role)
   - Click "Next"

5. **Review and Create**:
   - Review settings
   - Click "Create user"

### Step 3: Generate Access Keys (Like GCP Service Account Key)

1. **Click on your new user** in the users list

2. **Go to Security Credentials tab**

3. **Create Access Key**:
   - Scroll to "Access keys" section
   - Click "Create access key"
   - Select use case: **"Command Line Interface (CLI)"**
   - Check "I understand the above recommendation"
   - Click "Next"
   - (Optional) Add description: "Datathon 2025 local dev"
   - Click "Create access key"

4. **IMPORTANT - Save Your Credentials**:
   ```
   Access Key ID: AKIAIOSFODNN7EXAMPLE
   Secret Access Key: wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
   ```
   
   **WARNING**: The secret key is shown ONLY ONCE!
   - Download the CSV file (recommended)
   - Or copy both values to a secure location
   - Never commit these to git!

### Step 4: Create S3 Bucket

**Option A: Via AWS Console (Easier)**

1. **Navigate to S3**:
   - Search for "S3" in top search bar
   - Click "S3" service

2. **Create Bucket**:
   - Click "Create bucket" button
   - **Bucket name**: `datathon-2025-your-name` (must be globally unique)
   - **AWS Region**: Choose closest to you (e.g., `us-east-1`, `us-west-2`)
   - **Block Public Access**: Leave all checked (recommended)
   - Leave other settings as default
   - Click "Create bucket"

**Option B: Via AWS CLI (If you have it installed)**

```bash
# Install AWS CLI first if needed
pip install awscli

# Configure credentials (interactive)
aws configure
# Enter your Access Key ID
# Enter your Secret Access Key
# Default region: us-east-1
# Default output format: json

# Create bucket
aws s3 mb s3://datathon-2025-your-name --region us-east-1
```

### Step 5: Configure Your Project

1. **Copy environment template**:
   ```bash
   cd /home/artypuppet/datathon-2025
   cp .env.example .env
   ```

2. **Edit `.env` file**:
   ```bash
   nano .env
   ```

3. **Add your credentials**:
   ```bash
   # AWS Configuration
   AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
   AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
   AWS_REGION=us-east-1
   
   # S3 Bucket
   S3_BUCKET=datathon-2025-your-name
   
   # S3 Path Structure (optional)
   S3_INPUT_PREFIX=input/
   S3_PARSED_PREFIX=parsed/
   S3_EMBEDDINGS_PREFIX=embeddings/
   
   # Local Development
   LOCAL_MODE=false
   ```

4. **Save and close** (Ctrl+X, Y, Enter in nano)

5. **Verify `.gitignore` protects `.env`**:
   ```bash
   grep "^\.env$" .gitignore
   # Should show: .env
   ```

## Testing Your Setup

### Test 1: Verify Credentials

```bash
conda activate datathon-local

python -c "
from src.utils import get_s3_client

s3 = get_s3_client()
if s3:
    print('[OK] S3 client initialized')
    print(f'[OK] Bucket: {s3.bucket_name}')
    print(f'[OK] Region: {s3.region}')
else:
    print('[ERROR] Failed to initialize S3 client')
"
```

**Expected Output:**
```
[OK] S3 client initialized
[OK] Bucket: datathon-2025-your-name
[OK] Region: us-east-1
```

### Test 2: List Bucket Contents

```bash
python -c "
from src.utils import get_s3_client

s3 = get_s3_client()
files = s3.list_files()
print(f'[OK] Bucket accessible')
print(f'[INFO] Files in bucket: {len(files)}')
"
```

### Test 3: Upload a Test File

```bash
python -c "
from pathlib import Path
from src.utils import get_s3_client

s3 = get_s3_client()

# Create test file
test_file = Path('test_upload.txt')
test_file.write_text('Hello from datathon-2025!')

# Upload
success = s3.upload_file(test_file, 'test/hello.txt')
print(f'[OK] Upload: {success}')

# List to verify
files = s3.list_files(prefix='test/')
print(f'[OK] Files in test/: {files}')

# Cleanup
test_file.unlink()
"
```

### Test 4: Upload Real Dataset to S3

```bash
# Navigate to project
cd /home/artypuppet/datathon-2025

# Upload data directory to S3
python -c "
from pathlib import Path
from src.utils import get_s3_client

s3 = get_s3_client()
data_dir = Path('data/initial-dataset')

print('[INFO] Uploading dataset to S3...')

# Upload composition file
comp_file = data_dir / '2025-08-15_composition_sp500.csv'
if comp_file.exists():
    s3.upload_file(comp_file, 'input/financial/2025-08-15_composition_sp500.csv')
    print(f'[OK] Uploaded: {comp_file.name}')

# Upload performance file
perf_file = data_dir / '2025-09-26_stocks-performance.csv'
if perf_file.exists():
    s3.upload_file(perf_file, 'input/financial/2025-09-26_stocks-performance.csv')
    print(f'[OK] Uploaded: {perf_file.name}')

print('[OK] Upload complete!')
"
```

### Test 5: Parse Files from S3

```bash
# Parse a file from S3 and save result back to S3
python examples/parse_single_file.py
```

## Troubleshooting

### Error: "InvalidAccessKeyId"
**Problem**: Access Key ID is incorrect
**Solution**: 
- Double-check the key in `.env`
- Generate new access key in IAM console
- Make sure no extra spaces in `.env`

### Error: "SignatureDoesNotMatch"
**Problem**: Secret Access Key is incorrect
**Solution**:
- Regenerate access key (delete old one first)
- Update `.env` with new credentials

### Error: "NoSuchBucket"
**Problem**: Bucket doesn't exist or wrong name
**Solution**:
```bash
# List your buckets
aws s3 ls

# Verify bucket name in .env matches exactly
```

### Error: "Access Denied"
**Problem**: IAM user doesn't have S3 permissions
**Solution**:
1. Go to IAM Console
2. Click your user
3. Click "Add permissions" → "Attach policies directly"
4. Add `AmazonS3FullAccess`

### Error: "BucketAlreadyExists"
**Problem**: Bucket name is taken (must be globally unique)
**Solution**: Choose a different bucket name with your unique identifier

## Security Best Practices

### 1. Never Commit Credentials

```bash
# Verify .env is gitignored
cat .gitignore | grep ".env"

# If you accidentally committed .env:
git rm --cached .env
git commit -m "Remove .env from git"
```

### 2. Use Least Privilege

For production, create more restrictive policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::datathon-2025-your-name",
        "arn:aws:s3:::datathon-2025-your-name/*"
      ]
    }
  ]
}
```

### 3. Rotate Keys Regularly

- Rotate access keys every 90 days
- Delete unused access keys
- Use AWS IAM Access Analyzer

### 4. Enable MFA (Multi-Factor Authentication)

- Add MFA to your AWS root account
- Add MFA to IAM users with console access

## Cost Monitoring

### Check Current Usage

```bash
# Via AWS CLI
aws s3 ls s3://datathon-2025-your-name --recursive --summarize

# Via Python
python -c "
from src.utils import get_s3_client

s3 = get_s3_client()
files = s3.list_files()

total_size = 0
for file_key in files:
    size = s3.get_file_size(file_key)
    if size:
        total_size += size

print(f'Total files: {len(files)}')
print(f'Total size: {total_size / (1024**2):.2f} MB')
print(f'Estimated cost: ${(total_size / (1024**3)) * 0.023:.4f}/month')
"
```

### Set Up Billing Alerts

1. Go to AWS Billing Console
2. Click "Budgets"
3. Create budget with $5 threshold
4. Set email alert

### Free Tier Limits

- **Storage**: 5 GB (you're using ~100MB = safe)
- **Requests**: 20,000 GET, 2,000 PUT per month
- **Data Transfer**: 100 GB out per month

## Next Steps

Once setup is complete:

1. **Upload dataset to S3**:
   ```bash
   python parse_batch.py --local --input data/initial-dataset/ --upload-to-s3
   ```

2. **Parse from S3**:
   ```bash
   python parse_batch.py --s3 --input-prefix input/financial/ --output-prefix parsed/
   ```

3. **Verify results**:
   ```bash
   python -c "
   from src.utils import get_s3_client
   s3 = get_s3_client()
   parsed = s3.list_files(prefix='parsed/')
   print(f'Parsed files: {len(parsed)}')
   for f in parsed:
       print(f'  - {f}')
   "
   ```

## Quick Reference Commands

```bash
# Test S3 connection
python -c "from src.utils import get_s3_client; print('[OK]' if get_s3_client() else '[FAIL]')"

# List bucket contents
aws s3 ls s3://your-bucket-name/

# Upload file
aws s3 cp local-file.txt s3://your-bucket-name/remote-file.txt

# Download file
aws s3 cp s3://your-bucket-name/remote-file.txt local-file.txt

# Delete file
aws s3 rm s3://your-bucket-name/file.txt

# Sync directory (like rsync)
aws s3 sync data/ s3://your-bucket-name/data/
```

## Alternative: LocalStack (For Local Testing)

If you want to test S3 locally without AWS:

```bash
# Install LocalStack
pip install localstack

# Start LocalStack
localstack start

# Use with local endpoint
export AWS_ENDPOINT_URL=http://localhost:4566
```

## Support

- **AWS Documentation**: https://docs.aws.amazon.com/s3/
- **AWS Free Tier**: https://aws.amazon.com/free/
- **IAM Best Practices**: https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html
- **S3 Pricing**: https://aws.amazon.com/s3/pricing/

---

**Created**: 2024-11-01  
**For project**: PolyFinances Datathon 2025  
**See also**: [S3 Integration Guide](../S3_INTEGRATION.md)

