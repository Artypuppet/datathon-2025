#!/bin/bash
# Quick script to verify .env variables are loaded

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Load .env function (same as test_docker_local.sh)
load_env_file() {
    local env_file="$1"
    if [ -f "$env_file" ]; then
        echo "[INFO] Loading from: $env_file"
        while IFS= read -r line || [ -n "$line" ]; do
            [[ "$line" =~ ^[[:space:]]*# ]] && continue
            [[ -z "$line" ]] && continue
            line=$(echo "$line" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
            if [[ "$line" == *"="* ]]; then
                export "$line"
            fi
        done < "$env_file"
        return 0
    fi
    return 1
}

# Load .env
if ! load_env_file "$PROJECT_ROOT/.env"; then
    load_env_file "$SCRIPT_DIR/.env" || true
fi

echo ""
echo "[INFO] Environment Variables Check"
echo "=================================="

# Check each variable
check_var() {
    local var=$1
    local value="${!var}"
    if [ -z "$value" ]; then
        echo "[WARN] $var: NOT SET"
    else
        if [[ "$var" == *"PASSWORD"* ]] || [[ "$var" == *"SECRET"* ]]; then
            echo "[OK] $var: SET (hidden)"
        else
            echo "[OK] $var: $value"
        fi
    fi
}

check_var "OPENSEARCH_ENDPOINT"
check_var "OPENSEARCH_USERNAME"
check_var "OPENSEARCH_PASSWORD"
check_var "OPENSEARCH_USE_IAM_AUTH"
check_var "AWS_ACCESS_KEY_ID"
check_var "AWS_SECRET_ACCESS_KEY"
check_var "AWS_REGION"
check_var "S3_BUCKET"

echo ""
echo "[INFO] To use these in Docker, run:"
echo "  docker run -it --rm \\"
echo "    -e OPENSEARCH_ENDPOINT=\"\$OPENSEARCH_ENDPOINT\" \\"
echo "    -e OPENSEARCH_USERNAME=\"\$OPENSEARCH_USERNAME\" \\"
echo "    -e OPENSEARCH_PASSWORD=\"\$OPENSEARCH_PASSWORD\" \\"
echo "    -e OPENSEARCH_USE_IAM_AUTH=\"\$OPENSEARCH_USE_IAM_AUTH\" \\"
echo "    batch-embedding-job:latest \\"
echo "    python3 /opt/ml/code/scripts/check_opensearch_auth.py"

