# AWS OpenSearch Setup Guide

This guide walks you through setting up AWS OpenSearch (formerly Elasticsearch) for vector similarity search with our pipeline.

## Prerequisites

- AWS Account with appropriate permissions
- AWS CLI configured (or AWS Console access)
- IAM permissions for OpenSearch Service

## Step 1: Create OpenSearch Domain

### Via AWS Console:

1. **Navigate to Amazon OpenSearch Service**
   - Go to AWS Console → Services → Amazon OpenSearch Service
   - Click "Create domain"

2. **Configure Domain Settings**

   **Domain configuration:**
   - **Domain name**: `datathon-vectordb` (or your preferred name)
   - **Deployment type**: Choose based on needs:
     - **Production**: Single-Domain (recommended for production)
     - **Development**: Development (single node, cheaper)
   - **Version**: OpenSearch 2.11+ (recommended for k-NN features)

   **Instance configuration:**
   - **Instance type**: 
     - Development: `t3.small.search` (minimum)
     - Production: `r6g.large.search` or larger (for better performance)
   - **Number of instances**: 
     - Development: 1
     - Production: 2+ (for HA)
   - **Number of AZs**: 
     - Development: 1
     - Production: 2-3 (for multi-AZ)

   **Storage:**
   - **EBS volume type**: gp3 (recommended) or gp2
   - **EBS volume size**: Start with 20GB (can scale later)
   - **Encryption**: Enable at rest encryption (recommended)

3. **Network Configuration**

   **Network type:**
   - **VPC**: Recommended for production (select your VPC, subnets, security groups)
   - **Public**: Simpler for development/testing (requires fine-grained access control)

   **Fine-grained access control:**
   - **Enable**: Yes (required for authentication)
   - **Master user**: Choose one:
     - **Option 1 (Simplest)**: Master username and password
       - **Master user**: Create master user
       - **Master user name**: `admin` (or your choice)
       - **Master user password**: Create a strong password
       - **Master user ARN**: Leave blank
     - **Option 2**: IAM-based (for production)
       - **Master user**: IAM ARN
       - **Master user ARN**: `arn:aws:iam::ACCOUNT_ID:user/USERNAME`
       - **Master user name**: Leave blank

4. **Access Policy**

   **RECOMMENDED: Use Fine-Grained Access Control Only**
   
   If you enabled fine-grained access control with master username/password, you can use a simple access policy that allows HTTPS access, and authentication is handled by fine-grained access control.
   
   **Simplest Option (Master Username/Password):**
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Principal": {
           "AWS": "*"
         },
         "Action": "es:*",
         "Resource": "arn:aws:es:REGION:ACCOUNT_ID:domain/DOMAIN_NAME/*"
       }
     ]
   }
   ```
   This works because fine-grained access control (master username/password) handles authentication. The access policy just allows HTTPS connections.
   
   **For VPC Access:**
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Principal": {
           "AWS": "*"
         },
         "Action": "es:*",
         "Resource": "arn:aws:es:REGION:ACCOUNT_ID:domain/DOMAIN_NAME/*",
         "Condition": {
           "IpAddress": {
             "aws:SourceIp": ["YOUR_IP/32"]
           }
         }
       }
     ]
   }
   ```
   Restrict by IP address for additional security.
   
   **Alternative: IAM-based Access (If using IAM ARN as master user):**
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Principal": {
           "AWS": "arn:aws:iam::ACCOUNT_ID:user/USERNAME"
         },
         "Action": "es:*",
         "Resource": "arn:aws:es:REGION:ACCOUNT_ID:domain/DOMAIN_NAME/*"
       }
     ]
   }
   ```
   
   **IMPORTANT**: The `Principal.AWS` field must be a **string** for single principal, **array** for multiple.

5. **Advanced Options**

   **k-NN settings** (Important for vector search):
   - **k-NN**: Enable
   - **k-NN algorithm**: `hnsw` (Hierarchical Navigable Small World)
   - **k-NN space type**: `cosinesimil` (for cosine similarity)

6. **Review and Create**
   - Review all settings
   - Click "Create"
   - Wait 15-30 minutes for domain to initialize

## Step 2: Get Domain Endpoint

After the domain is created:

1. Go to your domain in OpenSearch Service console
2. Find the **Domain endpoint** (e.g., `https://search-datathon-vectordb-xxxxx.us-east-1.es.amazonaws.com`)
3. Copy this endpoint - you'll need it for configuration

## Step 3: Configure Access

### Option A: Master Username/Password (Simplest - Recommended for Development)

If you enabled fine-grained access control with master username and password during domain creation:

1. **You're all set!** The master credentials handle authentication
2. **Access policy**: Use the simple policy that allows `"Principal": {"AWS": "*"}` - fine-grained access control will handle auth
3. **No IAM setup needed** - just use the username and password

### Option B: IAM-based Access (For Production)

If you want to use IAM authentication instead:

1. **Create IAM Policy**:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": [
           "es:ESHttpPost",
           "es:ESHttpPut",
           "es:ESHttpGet",
           "es:ESHttpDelete",
           "es:DescribeElasticsearchDomain",
           "es:ListDomainNames"
         ],
         "Resource": "arn:aws:es:REGION:ACCOUNT_ID:domain/DOMAIN_NAME/*"
       }
     ]
   }
   ```

2. **Attach Policy to IAM User/Role**

3. **Set IAM ARN as Master User** during domain creation

4. **Update Domain Access Policy** to allow your IAM user/role

## Step 4: Environment Configuration

Set environment variables in your `.env` file or export them:

### Option A: Master Username/Password (Simplest)

```bash
# OpenSearch Configuration
export OPENSEARCH_ENDPOINT=https://search-datathon-vectordb-xxxxx.us-east-1.es.amazonaws.com

# Basic auth (master username/password)
export OPENSEARCH_USE_IAM_AUTH=false
export OPENSEARCH_USERNAME=admin  # Your master username
export OPENSEARCH_PASSWORD=your_strong_password  # Your master password
export AWS_REGION=us-east-1
```

### Option B: IAM Authentication (Production)

```bash
# OpenSearch Configuration
export OPENSEARCH_ENDPOINT=https://search-datathon-vectordb-xxxxx.us-east-1.es.amazonaws.com

# IAM authentication
export OPENSEARCH_USE_IAM_AUTH=true
export AWS_REGION=us-east-1
# AWS credentials should be configured via AWS CLI or environment variables
```

## Step 5: Test Connection

Test your OpenSearch connection:

```python
from src.vectordb import get_vectordb_client

# This will auto-detect OpenSearch if OPENSEARCH_ENDPOINT is set
vectordb = get_vectordb_client(backend='auto')

# Try a simple operation
# (Index will be created automatically on first use)
```

## Step 6: Create Security Group (For VPC Access)

If using VPC:

1. Go to EC2 → Security Groups
2. Create new security group or edit existing
3. Add inbound rules:
   - **Type**: HTTPS
   - **Port**: 443
   - **Source**: 
     - Your application subnet CIDR, or
     - Specific IPs for development

4. Attach this security group to your OpenSearch domain during/after creation

## Step 7: Network Configuration (VPC)

If using VPC:

1. **Subnets**: Select at least 2 subnets in different AZs
2. **Security Groups**: Select the security group created above
3. **VPC Endpoint** (optional): For private access without internet gateway

## Step 8: Cost Optimization

### Development Environment:
- Use **Development** deployment type (single node)
- Use smaller instance: `t3.small.search`
- Use minimal storage: 10-20GB
- Consider using **UltraWarm** for older data (optional)

### Production Environment:
- Use **Production** deployment type
- Use dedicated master nodes (optional, for large clusters)
- Enable **Auto-Tune** for performance optimization
- Set up **CloudWatch alarms** for monitoring
- Consider **Reserved Instances** for cost savings

## Step 9: Monitoring

1. **CloudWatch Metrics**:
   - Go to CloudWatch → Metrics → OpenSearch
   - Monitor: SearchLatency, IndexingLatency, ClusterStatus, etc.

2. **OpenSearch Dashboards**:
   - Access: `https://YOUR_DOMAIN_ENDPOINT/_dashboards`
   - Login with master user or IAM
   - View cluster health, indices, etc.

## Step 10: Index Configuration

Our VectorDB client automatically creates indices with k-NN configuration, but you can also pre-create:

```python
from opensearchpy import OpenSearch

client = OpenSearch(
    hosts=[{'host': 'your-endpoint', 'port': 443}],
    http_auth=None,  # Or use IAM/basic auth
    use_ssl=True,
    verify_certs=True
)

index_body = {
    "settings": {
        "index": {
            "knn": True,
            "knn.algo_param.ef_search": 100
        }
    },
    "mappings": {
        "properties": {
            "embedding": {
                "type": "knn_vector",
                "dimension": 768,
                "method": {
                    "name": "hnsw",
                    "space_type": "cosinesimil",
                    "engine": "nmslib"
                }
            }
        }
    }
}

client.indices.create(index="company_legislation_embeddings", body=index_body)
```

## Troubleshooting

### Connection Issues:

1. **"Connection refused"**:
   - Check security group allows HTTPS (443) from your IP/subnet
   - Verify domain endpoint is correct
   - Check if domain status is "Active"

2. **"Forbidden" or 403 errors**:
   - Verify IAM permissions or access policy
   - Check if fine-grained access control is configured correctly
   - Verify master user credentials (if using basic auth)

3. **"Timeout" errors**:
   - Domain might still be initializing (wait 15-30 min)
   - Check network connectivity
   - Verify endpoint URL format

### Performance Issues:

1. **Slow queries**:
   - Increase instance size
   - Tune `ef_search` parameter (balance accuracy vs speed)
   - Monitor CloudWatch metrics

2. **Indexing slow**:
   - Increase instance size
   - Increase number of instances
   - Batch your indexing operations

## Cost Estimate (Example)

**Development Environment:**
- Instance: `t3.small.search` (~$0.036/hour)
- Storage: 20GB gp3 (~$1.60/month)
- **Monthly**: ~$27 + storage

**Production Environment:**
- Instances: 2x `r6g.large.search` (~$0.30/hour each)
- Storage: 100GB gp3 (~$8/month)
- **Monthly**: ~$432 + storage

*Note: Actual costs vary by region and usage*

## Next Steps

After setup:
1. Run pipeline with `skip_embeddings=False`
2. VectorDB stage will automatically create index and store embeddings
3. Test inference with `test_inference.py`
4. Monitor CloudWatch for performance metrics

## References

- [AWS OpenSearch Service Documentation](https://docs.aws.amazon.com/opensearch-service/)
- [OpenSearch k-NN Documentation](https://opensearch.org/docs/latest/search-plugins/knn/)
- [IAM Policies for OpenSearch](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/ac.html)

