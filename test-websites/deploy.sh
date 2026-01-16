#!/bin/bash
# Deploy test websites using CDK with CloudFront signed cookies
# 
# This script:
# 1. Generates RSA key pair for CloudFront signed cookies (if not exists)
# 2. Deploys CDK stack with private S3 + CloudFront + OAC
# 3. Outputs environment variables needed for the agent
#
# Usage: ./deploy.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
INFRA_DIR="$PROJECT_ROOT/infra"

KEY_DIR="$HOME/.cloudfront"
KEY_NAME="airline-demo-key"
PRIVATE_KEY="$KEY_DIR/$KEY_NAME.pem"
PUBLIC_KEY="$KEY_DIR/$KEY_NAME.pub"

generate_keys() {
    echo "Generating RSA key pair for CloudFront signed cookies..."
    mkdir -p "$KEY_DIR"
    chmod 700 "$KEY_DIR"
    
    openssl genrsa -out "$PRIVATE_KEY" 2048 2>/dev/null
    chmod 600 "$PRIVATE_KEY"
    
    openssl rsa -in "$PRIVATE_KEY" -pubout -out "$PUBLIC_KEY" 2>/dev/null
    chmod 644 "$PUBLIC_KEY"
    
    echo "Keys generated:"
    echo "  Private: $PRIVATE_KEY"
    echo "  Public:  $PUBLIC_KEY"
}

check_keys() {
    if [[ ! -f "$PRIVATE_KEY" ]] || [[ ! -f "$PUBLIC_KEY" ]]; then
        echo "CloudFront signing keys not found."
        generate_keys
    else
        echo "Using existing keys:"
        echo "  Private: $PRIVATE_KEY"
        echo "  Public:  $PUBLIC_KEY"
    fi
}

deploy_cdk() {
    echo ""
    echo "Deploying CDK stack..."
    cd "$INFRA_DIR"
    
    if [[ ! -d "$INFRA_DIR/.venv" ]]; then
        echo "Creating Python virtual environment..."
        python3 -m venv "$INFRA_DIR/.venv"
    fi
    
    echo "Activating virtual environment and installing dependencies..."
    source "$INFRA_DIR/.venv/bin/activate"
    pip install -q -r requirements.txt
    
    cdk deploy AirlineTestWebsitesStack \
        -c cloudfront_public_key_path="$PUBLIC_KEY" \
        --outputs-file cdk-outputs.json \
        --require-approval never
    
    echo ""
    echo "CDK deployment complete."
}

extract_outputs() {
    local outputs_file="$INFRA_DIR/cdk-outputs.json"
    
    if [[ ! -f "$outputs_file" ]]; then
        echo "Error: CDK outputs file not found: $outputs_file"
        exit 1
    fi
    
    KEY_PAIR_ID=$(jq -r '.AirlineTestWebsitesStack.CloudFrontKeyPairId // empty' "$outputs_file")
    DISTRIBUTION_DOMAIN=$(jq -r '.AirlineTestWebsitesStack | to_entries | map(select(.key | startswith("Website1"))) | .[0].value // empty' "$outputs_file")
    
    if [[ -z "$KEY_PAIR_ID" ]]; then
        echo "Warning: Could not extract CloudFrontKeyPairId from CDK outputs"
        echo "Check $outputs_file manually"
    fi
}

print_env_instructions() {
    echo ""
    echo "============================================================"
    echo "DEPLOYMENT COMPLETE"
    echo "============================================================"
    echo ""
    echo "CloudFront Key Pair ID: $KEY_PAIR_ID"
    echo "Private Key Location:   $PRIVATE_KEY"
    echo ""
    echo "Website URLs (from CDK outputs):"
    
    local outputs_file="$INFRA_DIR/cdk-outputs.json"
    if [[ -f "$outputs_file" ]]; then
        jq -r '.AirlineTestWebsitesStack | to_entries | map(select(.key | contains("Url"))) | .[] | "  \(.key): \(.value)"' "$outputs_file" 2>/dev/null || true
    fi
    
    echo ""
    echo "============================================================"
    echo "ADD TO YOUR .env FILES"
    echo "============================================================"
    echo ""
    echo "# CloudFront signed cookie credentials"
    echo "CLOUDFRONT_KEY_PAIR_ID=$KEY_PAIR_ID"
    echo "CLOUDFRONT_PRIVATE_KEY=$PRIVATE_KEY"
    echo ""
    echo "Example .env.website1:"
    echo "  AIRLINE_URL=https://<distribution>.cloudfront.net"
    echo "  CHECK_IN_LOGIN=SMITH"
    echo "  CHECK_IN_CODE=ABC123"
    echo "  SEAT_PREFERENCE=window"
    echo "  CLOUDFRONT_KEY_PAIR_ID=$KEY_PAIR_ID"
    echo "  CLOUDFRONT_PRIVATE_KEY=$PRIVATE_KEY"
    echo ""
}

check_dependencies() {
    local missing=()
    
    command -v openssl >/dev/null 2>&1 || missing+=("openssl")
    command -v cdk >/dev/null 2>&1 || missing+=("cdk (npm install -g aws-cdk)")
    command -v jq >/dev/null 2>&1 || missing+=("jq")
    
    if [[ ${#missing[@]} -gt 0 ]]; then
        echo "Error: Missing required tools:"
        for tool in "${missing[@]}"; do
            echo "  - $tool"
        done
        exit 1
    fi
}

main() {
    echo "============================================================"
    echo "Airline Test Websites CDK Deployment"
    echo "============================================================"
    echo ""
    
    check_dependencies
    check_keys
    deploy_cdk
    extract_outputs
    print_env_instructions
}

main "$@"
