#!/bin/bash
# Create Kubernetes secrets for LB Automotive application
# Run on server: bash deployment/k8s/create-secrets.sh

set -e

echo "=========================================="
echo "Creating Kubernetes Secrets"
echo "=========================================="
echo ""

# Create namespace if it doesn't exist
if ! kubectl get namespace lb-automotive &>/dev/null; then
    echo "Creating namespace lb-automotive..."
    kubectl create namespace lb-automotive
    echo "✅ Namespace created"
else
    echo "✅ Namespace lb-automotive exists"
fi
echo ""

# 1. GitHub Container Registry secret (for pulling images)
echo "1. GitHub Container Registry Secret"
read -p "   Enter GitHub username [gamebox-inc]: " GITHUB_USER
GITHUB_USER=${GITHUB_USER:-gamebox-inc}

read -sp "   Enter GitHub token (for GHCR): " GITHUB_TOKEN
echo ""

kubectl create secret docker-registry ghcr-secret \
  --docker-server=ghcr.io \
  --docker-username=$GITHUB_USER \
  --docker-password=$GITHUB_TOKEN \
  --namespace=lb-automotive \
  --dry-run=client -o yaml | kubectl apply -f -

echo "   ✅ GHCR secret created"
echo ""

# 2. Application secrets
echo "2. Application Secrets"

# Generate SECRET_KEY if not provided
read -sp "   Enter SECRET_KEY (or press Enter to generate): " SECRET_KEY
echo ""
if [ -z "$SECRET_KEY" ]; then
    SECRET_KEY=$(openssl rand -hex 32)
    echo "   Generated SECRET_KEY: $SECRET_KEY"
fi

read -p "   Enter ALLOWED_ORIGINS [https://kozytherocket.space]: " ALLOWED_ORIGINS
ALLOWED_ORIGINS=${ALLOWED_ORIGINS:-https://kozytherocket.space}

# Twilio (optional)
read -p "   Enter TWILIO_ACCOUNT_SID (or press Enter to skip): " TWILIO_ACCOUNT_SID
read -sp "   Enter TWILIO_AUTH_TOKEN (or press Enter to skip): " TWILIO_AUTH_TOKEN
echo ""
read -p "   Enter TWILIO_PHONE_NUMBER (or press Enter to skip): " TWILIO_PHONE_NUMBER

# LLM Configuration
read -p "   Enter LLM_PROVIDER [anthropic]: " LLM_PROVIDER
LLM_PROVIDER=${LLM_PROVIDER:-anthropic}

if [ "$LLM_PROVIDER" = "anthropic" ]; then
    read -sp "   Enter ANTHROPIC_API_KEY: " ANTHROPIC_API_KEY
    echo ""
    read -p "   Enter ANTHROPIC_MODEL [claude-3-5-sonnet-20241022]: " ANTHROPIC_MODEL
    ANTHROPIC_MODEL=${ANTHROPIC_MODEL:-claude-3-5-sonnet-20241022}
fi

# Create application secret
kubectl create secret generic app-secrets \
  --from-literal=SECRET_KEY="$SECRET_KEY" \
  --from-literal=ALLOWED_ORIGINS="$ALLOWED_ORIGINS" \
  --from-literal=LLM_PROVIDER="$LLM_PROVIDER" \
  --from-literal=DATABASE_URL="sqlite:////app/data/lb_automotive.db" \
  --from-literal=REDIS_URL="redis://redis:6379/0" \
  --from-literal=CSP_POLICY="strict" \
  --namespace=lb-automotive \
  --dry-run=client -o yaml | kubectl apply -f -

echo "   ✅ Application secrets created"
echo ""

# Create Twilio secret if provided
if [ -n "$TWILIO_ACCOUNT_SID" ]; then
    kubectl create secret generic twilio-secrets \
      --from-literal=TWILIO_ACCOUNT_SID="$TWILIO_ACCOUNT_SID" \
      --from-literal=TWILIO_AUTH_TOKEN="$TWILIO_AUTH_TOKEN" \
      --from-literal=TWILIO_PHONE_NUMBER="$TWILIO_PHONE_NUMBER" \
      --namespace=lb-automotive \
      --dry-run=client -o yaml | kubectl apply -f -
    echo "   ✅ Twilio secrets created"
fi

# Create Anthropic secret if using Anthropic
if [ "$LLM_PROVIDER" = "anthropic" ] && [ -n "$ANTHROPIC_API_KEY" ]; then
    kubectl create secret generic anthropic-secrets \
      --from-literal=ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
      --from-literal=ANTHROPIC_MODEL="$ANTHROPIC_MODEL" \
      --namespace=lb-automotive \
      --dry-run=client -o yaml | kubectl apply -f -
    echo "   ✅ Anthropic secrets created"
fi

echo ""
echo "=========================================="
echo "Secrets Created Successfully"
echo "=========================================="
echo ""
echo "Verify secrets:"
echo "   kubectl get secrets -n lb-automotive"
echo ""
echo "Next steps:"
echo "   1. Deploy application via ArgoCD"
echo "   2. Test Jenkins pipeline"
