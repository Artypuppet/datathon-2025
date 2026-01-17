# Environment Variables Setup (.env file)

This project uses `.env` files to manage AWS credentials and other sensitive configuration.

---

## Creating .env File

Create a `.env` file in the project root (`/home/artypuppet/datathon-2025/.env`) with your AWS credentials:

```bash
# AWS Credentials
AWS_ACCESS_KEY_ID=your-access-key-id
AWS_SECRET_ACCESS_KEY=your-secret-access-key
AWS_REGION=us-east-1

# Optional: AWS Default Region (alternative to AWS_REGION)
AWS_DEFAULT_REGION=us-east-1

# S3 Configuration
S3_BUCKET=your-s3-bucket-name

# OpenSearch Configuration
OPENSEARCH_ENDPOINT=https://your-opensearch-endpoint.es.amazonaws.com

# Option 1: Basic Auth (Username/Password) - Recommended for development
OPENSEARCH_USE_IAM_AUTH=false
OPENSEARCH_USERNAME=your-username
OPENSEARCH_PASSWORD=your-password

# Option 2: IAM Auth (for production) - Uncomment and set OPENSEARCH_USE_IAM_AUTH=true
# OPENSEARCH_USE_IAM_AUTH=true
# (AWS credentials will be used automatically via AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY)

# Optional: If using AWS credentials file instead
# Leave blank and configure ~/.aws/credentials instead
```

---

## Security: .gitignore

**IMPORTANT**: Make sure `.env` is in `.gitignore` to prevent committing secrets:

```bash
echo ".env" >> .gitignore
```

Check if it's already there:
```bash
grep -q "^\.env$" .gitignore && echo ".env already in .gitignore" || echo ".env not in .gitignore - ADD IT!"
```

---

## Usage in Scripts

Scripts automatically load `.env` file using `python-dotenv`:

### Python Scripts

```python
from dotenv import load_dotenv
load_dotenv()

# Now environment variables are available
import os
aws_key = os.getenv('AWS_ACCESS_KEY_ID')
```

### Shell Scripts

For shell scripts, you'll need to manually source or export:

```bash
# Option 1: Export manually
export AWS_ACCESS_KEY_ID=$(grep AWS_ACCESS_KEY_ID .env | cut -d '=' -f2)
export AWS_SECRET_ACCESS_KEY=$(grep AWS_SECRET_ACCESS_KEY .env | cut -d '=' -f2)

# Option 2: Use a script (BE CAREFUL with quoting!)
source <(grep -v '^#' .env | sed 's/^/export /')
```

---

## Credential Priority Order

When scripts look for credentials, they check in this order:

1. **Command-line arguments** (highest priority)
2. **Environment variables** (exported in shell)
3. **`.env` file** (project root or script directory)
4. **AWS credentials file** (`~/.aws/credentials`) - via boto3
5. **IAM role** (if running on EC2/Lambda/ECS)

---

## Example: Using push_to_ecr.py

The `push_to_ecr.py` script automatically loads `.env`:

```bash
# Create .env file with credentials
cat > .env << EOF
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=wJalr...
AWS_REGION=us-east-1
EOF

# Run script (no need to export manually)
python3 scripts/push_to_ecr.py
```

Or override with environment variables:

```bash
export AWS_ACCESS_KEY_ID=different-key
python3 scripts/push_to_ecr.py  # Uses exported value, not .env
```

---

## Testing Credentials

Test if credentials are loaded correctly:

```python
import os
from dotenv import load_dotenv

load_dotenv()

print(f"AWS_ACCESS_KEY_ID: {os.getenv('AWS_ACCESS_KEY_ID', 'NOT SET')[:10]}...")
print(f"AWS_REGION: {os.getenv('AWS_REGION', 'NOT SET')}")
```

---

## Alternative: AWS Credentials File

If you prefer not to use `.env`, you can use AWS credentials file:

```bash
# Configure AWS CLI (if installed)
aws configure

# Or manually create ~/.aws/credentials:
[default]
aws_access_key_id = your-key
aws_secret_access_key = your-secret

# And ~/.aws/config:
[default]
region = us-east-1
```

boto3 will automatically use these credentials if environment variables are not set.

---

## Docker Containers

For Docker containers, pass credentials via environment variables (don't copy `.env` into image):

```bash
docker run -it --rm \
    -e AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID" \
    -e AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY" \
    -e AWS_REGION="$AWS_REGION" \
    your-image:tag
```

---

## Troubleshooting

### "Credentials not found"

1. Check `.env` file exists: `ls -la .env`
2. Check file format (no spaces around `=`): `cat .env`
3. Verify variables are loaded: `python3 -c "from dotenv import load_dotenv; load_dotenv(); import os; print(os.getenv('AWS_ACCESS_KEY_ID'))"`
4. Check for typos in variable names

### "Permission denied"

Make sure `.env` file permissions are secure:
```bash
chmod 600 .env  # Only owner can read/write
```

### Script not finding .env

The script looks for `.env` in:
1. Project root (parent of `scripts/`)
2. Script directory (`scripts/`)
3. Current working directory

Make sure you're running from the project root or adjust paths accordingly.

---

## Best Practices

1. **Never commit `.env`** - Always in `.gitignore`
2. **Use different credentials for dev/prod** - Different `.env` files per environment
3. **Rotate credentials regularly** - Update `.env` when rotating AWS keys
4. **Restrict permissions** - `chmod 600 .env` to prevent others from reading
5. **Document required variables** - List all required env vars in README or this file

