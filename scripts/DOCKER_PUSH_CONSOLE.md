# Push Docker Image to ECR via AWS Console (No AWS CLI Required)

This guide shows how to push your Docker image to ECR using only the AWS Console - no AWS CLI needed!

---

## Step 1: Build Image Locally

First, build the image on your local machine:

```bash
cd /home/artypuppet/datathon-2025
./scripts/build_and_push_manual.sh
```

This builds: `batch-embedding-job:latest`

---

## Step 2: Create ECR Repository in Console

1. Go to **AWS Console** → **ECR** (Elastic Container Registry)
   - Search "ECR" in AWS Console or go to: https://console.aws.amazon.com/ecr/

2. Click **Create repository**

3. Configure repository:
   - **Visibility settings**: Private
   - **Repository name**: `sagemaker/batch-embedding-job`
   - **Tag immutability**: Enable (recommended)
   - **Image scanning**: Enable scan on push (recommended)
   - **Encryption**: Default (AES-256)

4. Click **Create repository**

---

## Step 3: Get Push Commands from Console

1. In your ECR repository page, click **View push commands** button
   - This will show you exactly what to run

2. AWS will display 4 commands:
   ```
   1. aws ecr get-login-password --region us-east-1 | docker login ...
   2. docker tag batch-embedding-job:latest ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/...
   3. docker push ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/...
   4. (Optional) docker pull ...
   ```

**But wait!** You don't have AWS CLI, so command #1 won't work. Use the alternative below.

---

## Step 4: Login to ECR (Alternative Method)

Since you don't have AWS CLI, you need to get the login token another way:

### Option A: Install AWS CLI (Quick)

See [INSTALL_AWS_CLI.md](INSTALL_AWS_CLI.md) for installation instructions.

Then run:
```bash
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin ACCOUNT.dkr.ecr.us-east-1.amazonaws.com
```

### Option B: Use AWS Console to Get Login Token

1. Go to **AWS Console** → **IAM** → **Users** → Your user
2. **Security credentials** tab
3. Create access key (if you don't have one)
4. Use Python to get login token:

```bash
# Save this as get_ecr_token.py
python3 << 'EOF'
import boto3
import subprocess

# Get ECR login token
ecr = boto3.client('ecr', region_name='us-east-1')
token = ecr.get_authorization_token()

auth_data = token['authorizationData'][0]
username = 'AWS'
password = auth_data['authorizationToken']

# Decode password (base64)
import base64
password_decoded = base64.b64decode(password).decode('utf-8').split(':')[1]

# Login
import subprocess
subprocess.run([
    'docker', 'login',
    '--username', username,
    '--password-stdin',
    auth_data['proxyEndpoint']
], input=password_decoded.encode())

print("[OK] Logged in to ECR")
EOF
```

**Note**: This requires `boto3` (Python AWS SDK):
```bash
pip install boto3
```

### Option C: Use AWS SDK for JavaScript (Browser Console)

If you prefer browser-based:
1. Open browser console (F12)
2. Use AWS SDK for JavaScript (if available)
3. Get token and use in Docker login

---

## Step 5: Tag Image

Tag your local image with the ECR repository URI:

```bash
# Replace ACCOUNT and REGION with your values
# You can find these in the ECR repository page URL or settings

export AWS_ACCOUNT_ID="123456789012"  # Your account ID
export AWS_REGION="us-east-1"

docker tag batch-embedding-job:latest \
    ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/sagemaker/batch-embedding-job:latest
```

**To find your Account ID**:
- Look at ECR repository page URL: `https://console.aws.amazon.com/ecr/repositories/private/123456789012/...`
- Or go to: AWS Console → Support → Support Center (shows account ID)

---

## Step 6: Push Image

```bash
docker push \
    ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/sagemaker/batch-embedding-job:latest
```

---

## Simplified: Use Provided Python Script

We've included a Python script that handles everything:

```bash
# Install boto3 if needed
pip install boto3

# Build image first
./scripts/build_and_push_manual.sh

# Push to ECR (handles login, tag, push automatically)
python3 scripts/push_to_ecr.py
```

**With custom options**:
```bash
# Specify region and account
python3 scripts/push_to_ecr.py --region us-east-1 --account-id 123456789012

# Login only (manual push)
python3 scripts/push_to_ecr.py --login-only

# Custom repository name
python3 scripts/push_to_ecr.py --repo-name my-custom-repo/batch-embedding
```

**Note**: Requires `boto3` and AWS credentials configured (environment variables or `~/.aws/credentials`).

---

## Verify Image in Console

1. Go to ECR repository: `sagemaker/batch-embedding-job`
2. You should see your image with tag `latest`
3. Click on image to see details
4. Copy the **Image URI** for use in SageMaker

---

## Next: Use in SageMaker

Once image is in ECR:

1. Go to **SageMaker** → **Processing jobs** → **Create**
2. **Image location**: "Use a different image location"
3. **Image URI**: Paste the URI from ECR console
4. Configure rest of job as normal

---

## Troubleshooting

### "unauthorized: authentication required"

**Solution**: Re-run Docker login step (token expires after 12 hours)

### "repository does not exist"

**Solution**: Create repository in ECR console first

### "denied: Your authorization token has expired"

**Solution**: Get new login token (they expire after 12 hours)

---

## Recommendation

While you can push without AWS CLI, **installing AWS CLI is recommended** because:
- Easier to automate
- Better for CI/CD
- More reliable
- See: [INSTALL_AWS_CLI.md](INSTALL_AWS_CLI.md)

