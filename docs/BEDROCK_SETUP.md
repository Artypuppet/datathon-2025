# AWS Bedrock Setup Guide

Complete guide for setting up AWS Bedrock to use Claude models for LLM-based risk analysis.

---

## Prerequisites

1. **AWS Account** (free tier eligible)
2. **IAM User or Role** with Bedrock permissions
3. **Model Access** - Request access to Claude models in Bedrock console

---

## Step 1: AWS Credentials

You need AWS credentials configured. Choose one of these methods:

### Option A: AWS CLI Configuration (Recommended for Local Development)

```bash
# Install AWS CLI if not already installed
pip install awscli

# Configure credentials (interactive)
aws configure
```

Enter when prompted:
- **AWS Access Key ID**: Your IAM user's access key
- **AWS Secret Access Key**: Your IAM user's secret key
- **Default region**: `us-east-1` (or your preferred region)
- **Default output format**: `json`

This creates `~/.aws/credentials` and `~/.aws/config` files.

### Option B: Environment Variables

```bash
export AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
export AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
export AWS_DEFAULT_REGION=us-east-1
```

### Option C: .env File

Add to your `.env` file:
```bash
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
AWS_REGION=us-east-1
```

Then load in Python:
```python
from dotenv import load_dotenv
load_dotenv()
```

### Option D: IAM Role (For EC2/Lambda/SageMaker)

If running on AWS infrastructure:
1. Attach IAM role to your EC2 instance/Lambda/SageMaker job
2. No explicit credentials needed - uses role automatically

---

## Step 2: Create IAM User with Bedrock Permissions

### 2.1 Create IAM User

1. Go to **AWS Console** → **IAM**
2. Click **Users** → **Create user**
3. Username: `bedrock-user` (or any name)
4. Click **Next**

### 2.2 Attach Bedrock Permissions

**Option A: Use Managed Policy (Easiest)**

1. Select **"Attach policies directly"**
2. Search for: `AmazonBedrockFullAccess`
3. Check the policy
4. Click **Next** → **Create user**

**Option B: Custom Policy (More Secure - Recommended)**

Create a custom policy with minimal permissions:

1. Go to **IAM** → **Policies** → **Create policy**
2. Click **JSON** tab
3. Paste this policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream",
        "bedrock:ListFoundationModels"
      ],
      "Resource": [
        "arn:aws:bedrock:*::foundation-model/anthropic.claude-3-5-sonnet-20241022-v2:0",
        "arn:aws:bedrock:*::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0",
        "arn:aws:bedrock:*::foundation-model/anthropic.claude-3-haiku-20240307-v1:0"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:ListFoundationModels"
      ],
      "Resource": "*"
    }
  ]
}
```

4. Name: `BedrockClaudeAccess`
5. Description: "Access to invoke Claude models on Bedrock"
6. Click **Create policy**

7. **Attach to User**:
   - Go back to your user
   - Click **Add permissions** → **Attach policies directly**
   - Search for `BedrockClaudeAccess`
   - Select and attach

### 2.3 Generate Access Keys

1. Click on your user → **Security credentials** tab
2. Scroll to **Access keys**
3. Click **Create access key**
4. Select use case: **Command Line Interface (CLI)**
5. Click **Next** → **Create access key**
6. **IMPORTANT**: Save both:
   - **Access Key ID**
   - **Secret Access Key** (shown only once!)

7. Add to your `.env` or AWS CLI config:
   ```bash
   AWS_ACCESS_KEY_ID=AKIA...
   AWS_SECRET_ACCESS_KEY=wJalr...
   AWS_REGION=us-east-1
   ```

---

## Step 3: Request Model Access (CRITICAL)

**You MUST enable Claude models in Bedrock console before using them!**

### 3.1 Navigate to Bedrock Console

1. Go to **AWS Console**
2. Search for **"Bedrock"** in top search bar
3. Click **Amazon Bedrock** service

### 3.2 Enable Model Access

1. In left sidebar, click **Model access**
2. Click **Request model access** button
3. **Filter by Provider**: Select **Anthropic**
4. **Select Models** (check boxes):
   - ☑ **Claude 3.5 Sonnet** (recommended - most capable)
   - ☑ **Claude 3 Sonnet** (fallback option)
   - ☑ **Claude 3 Haiku** (faster, cheaper option)

5. Click **Next**
6. Review and click **Submit request**

### 3.3 Wait for Approval

- **Free Tier**: Usually approved instantly (up to 30 seconds)
- **Pay-as-you-go**: May take a few minutes
- You'll see status change from "Access pending" → "Access granted"

**Note**: If you don't see the models you need, you may need to:
- Complete AWS account verification
- Accept Bedrock terms of service
- Have a valid payment method on file (even for free tier)

---

## Step 4: Verify Setup

### 4.1 Test AWS Credentials

```bash
# Test with AWS CLI
aws sts get-caller-identity

# Should return your account ID and user ARN
```

### 4.2 Test Bedrock Access

```python
import boto3
from botocore.exceptions import ClientError

# Initialize Bedrock client
bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')

# Try to list available models
try:
    bedrock_control = boto3.client('bedrock', region_name='us-east-1')
    models = bedrock_control.list_foundation_models()
    claude_models = [
        m for m in models['modelSummaries'] 
        if 'claude' in m['modelId'].lower()
    ]
    print(f"Found {len(claude_models)} Claude models:")
    for model in claude_models:
        print(f"  - {model['modelId']}: {model.get('modelName', 'N/A')}")
except ClientError as e:
    print(f"Error: {e}")
    print("Check that:")
    print("  1. IAM user has Bedrock permissions")
    print("  2. Model access has been granted in Bedrock console")
```

### 4.3 Test LLM Analyzer

```python
from src.vectordb import LLMAnalyzer

# Initialize analyzer
analyzer = LLMAnalyzer(
    model_id="anthropic.claude-3-5-sonnet-20241022-v2:0",
    region_name="us-east-1",
    use_bedrock=True  # Set to False for testing without AWS
)

# Test legislation summarization
test_text = "The United States imposes a 50% tariff on smartphones assembled outside the US."
summary = analyzer.summarize_legislation(test_text, "TEST_LEG")
print(f"Summary: {summary}")
```

---

## Step 5: Configuration Options

### Model Selection

The `LLMAnalyzer` supports different Claude models:

```python
# Claude 3.5 Sonnet (default - best balance of speed and capability)
analyzer = LLMAnalyzer(model_id=LLMAnalyzer.CLAUDE_3_5_SONNET)

# Claude 3 Sonnet (slightly older, still very capable)
analyzer = LLMAnalyzer(model_id=LLMAnalyzer.CLAUDE_3_SONNET)

# Claude 3 Haiku (fastest, cheapest, good for simple tasks)
analyzer = LLMAnalyzer(model_id=LLMAnalyzer.CLAUDE_3_HAIKU)

# Custom model ID
analyzer = LLMAnalyzer(model_id="anthropic.claude-3-5-sonnet-20241022-v2:0")
```

### Region Configuration

Bedrock is available in multiple regions. Choose the closest one:

```python
analyzer = LLMAnalyzer(region_name="us-east-1")   # N. Virginia (default)
analyzer = LLMAnalyzer(region_name="us-west-2")   # Oregon
analyzer = LLMAnalyzer(region_name="eu-west-1")   # Ireland
analyzer = LLMAnalyzer(region_name="ap-southeast-1")  # Singapore
```

**Important**: Model IDs may differ by region. Check Bedrock console for region-specific IDs.

---

## Troubleshooting

### Error: "AccessDeniedException: The API key provided does not have access"

**Problem**: IAM user doesn't have Bedrock permissions

**Solution**:
1. Check IAM user has `AmazonBedrockFullAccess` or custom Bedrock policy
2. Verify policy allows `bedrock:InvokeModel` action
3. Wait a few minutes after attaching policy (IAM propagation delay)

### Error: "ModelNotFoundException: Could not find model"

**Problem**: Model access not granted in Bedrock console

**Solution**:
1. Go to Bedrock console → **Model access**
2. Request access to the specific Claude model you're using
3. Wait for approval (usually instant for free tier)

### Error: "ValidationException: Model access denied"

**Problem**: Model access granted but account restrictions

**Solution**:
1. Check Bedrock console → **Model access** - verify status is "Access granted"
2. Ensure AWS account is verified
3. Accept Bedrock terms of service if prompted
4. For pay-as-you-go: ensure payment method is on file

### Error: "botocore.exceptions.ClientError: An error occurred (403)"

**Problem**: Region mismatch or permissions issue

**Solution**:
1. Verify region matches where Bedrock is available
2. Check IAM policy allows access in that region
3. Try different region if model not available

### Error: "NoCredentialsError: Unable to locate credentials"

**Problem**: AWS credentials not configured

**Solution**:
1. Run `aws configure` to set up credentials
2. Or set `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` environment variables
3. Or ensure IAM role is attached (for EC2/Lambda/SageMaker)

---

## Cost Considerations

### Claude Model Pricing (as of 2024)

| Model | Input (per 1M tokens) | Output (per 1M tokens) |
|-------|---------------------|----------------------|
| Claude 3.5 Sonnet | $3.00 | $15.00 |
| Claude 3 Sonnet | $3.00 | $15.00 |
| Claude 3 Haiku | $0.25 | $1.25 |

### Free Tier

- **New AWS accounts**: $1 credit for Claude models (first 30 days)
- **Free tier**: 5,000 input tokens + 2,500 output tokens per month (Claude 3 Haiku)

### Usage Estimate for This Project

For risk analysis:
- **Legislation summarization**: ~500-1000 tokens input, ~100-200 tokens output
- **Impact analysis**: ~2000-4000 tokens input, ~500-1000 tokens output

**Per company analysis**: ~$0.01-0.03 (using Claude 3.5 Sonnet)
**500 companies**: ~$5-15 total

---

## Security Best Practices

1. **Never commit credentials**: Use `.env` file (gitignored) or AWS IAM roles
2. **Least privilege**: Create custom IAM policy with only needed permissions
3. **Rotate keys**: Rotate access keys every 90 days
4. **Monitor usage**: Set up CloudWatch alarms for unexpected costs
5. **Use IAM roles**: For AWS infrastructure, prefer IAM roles over access keys

---

## Next Steps

Once Bedrock is configured:

1. **Test LLM Analyzer**:
   ```python
   from src.vectordb import LLMAnalyzer
   analyzer = LLMAnalyzer()
   ```

2. **Integrate with Pipeline**:
   ```python
   from src.vectordb import LegislationImpactAnalyzer
   
   analyzer = LegislationImpactAnalyzer(
       legislation_text=legislation_text,
       use_llm_analysis=True  # Enabled by default
   )
   ```

3. **Run end-to-end test**:
   ```bash
   python test_vectordb_opensearch.py --ticker AAPL
   ```

The LLM analysis will automatically run and include structured recommendations in the results!

---

## Quick Reference

**Required Credentials**:
- `AWS_ACCESS_KEY_ID` - IAM user access key
- `AWS_SECRET_ACCESS_KEY` - IAM user secret key
- `AWS_REGION` (or `AWS_DEFAULT_REGION`) - Region (e.g., `us-east-1`)

**Required Permissions**:
- `bedrock:InvokeModel`
- `bedrock:InvokeModelWithResponseStream`
- `bedrock:ListFoundationModels` (optional, for testing)

**Required Setup**:
- Model access granted in Bedrock console for Claude models

**Default Configuration**:
- Model: `anthropic.claude-3-5-sonnet-20241022-v2:0`
- Region: `us-east-1`
- Temperature: `0.2` (deterministic)
- Max tokens: `1000`

