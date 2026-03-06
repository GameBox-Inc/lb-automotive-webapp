#!/bin/bash
# Jenkins Kubernetes Deployment Script
# Deploys to K8s cluster on the same server

set -e

DEPLOY_DIR="$1"
BRANCH="$2"
SECRET_KEY="$3"
ALLOWED_ORIGINS="$4"
LLM_PROVIDER="$5"
ANTHROPIC_API_KEY="$6"
TWILIO_ACCOUNT_SID="$7"
TWILIO_AUTH_TOKEN="$8"
TWILIO_PHONE_NUMBER="$9"
IMAGE_TAG="${10}"

echo "========================================="
echo "🚀 Kubernetes Deployment Script"
echo "========================================="
echo "Deploy directory: $DEPLOY_DIR"
echo "Branch: $BRANCH"
echo "Image Tag: $IMAGE_TAG"
echo "========================================="

# Navigate to deployment directory
cd "$DEPLOY_DIR"

# Pull latest code
echo "📥 Pulling latest code from $BRANCH..."
git fetch origin
git reset --hard origin/"$BRANCH"

# Update Image Tags in Manifests
if [ -n "$IMAGE_TAG" ]; then
    echo "🏷️ Updating image tags to: $IMAGE_TAG"
    sed -i "s|image: ghcr.io/gamebox-inc/lb-automotive-backend:.*|image: ghcr.io/gamebox-inc/lb-automotive-backend:$IMAGE_TAG|g" deployment/k8s/backend.yaml
    sed -i "s|image: ghcr.io/gamebox-inc/lb-automotive-frontend:.*|image: ghcr.io/gamebox-inc/lb-automotive-frontend:$IMAGE_TAG|g" deployment/k8s/frontend.yaml
fi

# Update Kubernetes secrets
echo "🔐 Updating Kubernetes secrets..."

# Anthropic secrets
if [ -n "$ANTHROPIC_API_KEY" ]; then
    kubectl create secret generic anthropic-secrets -n lb-automotive \
        --from-literal=ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
        --from-literal=ANTHROPIC_MODEL="claude-3-5-sonnet-20241022" \
        --dry-run=client -o yaml | kubectl apply -f -
    echo "✓ Anthropic secrets updated"
fi

# App secrets
kubectl create secret generic app-secrets -n lb-automotive \
    --from-literal=SECRET_KEY="$SECRET_KEY" \
    --from-literal=ALLOWED_ORIGINS="$ALLOWED_ORIGINS" \
    --from-literal=DATABASE_URL="sqlite:////app/data/lb_automotive.db" \
    --from-literal=REDIS_URL="redis://redis:6379/0" \
    --from-literal=LLM_PROVIDER="$LLM_PROVIDER" \
    --from-literal=CSP_POLICY="strict" \
    --dry-run=client -o yaml | kubectl apply -f -
echo "✓ App secrets updated"

# Twilio secrets
if [ -n "$TWILIO_ACCOUNT_SID" ]; then
    kubectl create secret generic twilio-secrets -n lb-automotive \
        --from-literal=TWILIO_ACCOUNT_SID="$TWILIO_ACCOUNT_SID" \
        --from-literal=TWILIO_AUTH_TOKEN="$TWILIO_AUTH_TOKEN" \
        --from-literal=TWILIO_PHONE_NUMBER="$TWILIO_PHONE_NUMBER" \
        --dry-run=client -o yaml | kubectl apply -f -
    echo "✓ Twilio secrets updated"
fi

# Apply Kubernetes configurations
echo "📦 Applying Kubernetes configurations..."
kubectl apply -f deployment/k8s/namespace.yaml
kubectl apply -f deployment/k8s/pvc.yaml
kubectl apply -f deployment/k8s/redis.yaml
kubectl apply -f deployment/k8s/backend.yaml
kubectl apply -f deployment/k8s/frontend.yaml
kubectl apply -f deployment/k8s/ingress.yaml
kubectl apply -f deployment/k8s/disk-monitor-cronjob.yaml || true

echo "✓ Configurations applied"

# Restart deployments to pick up new images and configs
echo "🔄 Restarting deployments..."
kubectl rollout restart deployment backend -n lb-automotive
kubectl rollout restart deployment frontend -n lb-automotive
kubectl rollout restart deployment redis -n lb-automotive

# Wait for deployments to complete
echo "⏳ Waiting for deployments to complete..."
kubectl rollout status deployment backend -n lb-automotive --timeout=5m
kubectl rollout status deployment frontend -n lb-automotive --timeout=5m
kubectl rollout status deployment redis -n lb-automotive --timeout=5m

# Check pod status
echo "📊 Checking pod status..."
kubectl get pods -n lb-automotive -o wide

# Get memory and disk usage
echo ""
echo "💾 Resource usage:"
free -h | grep -E "Mem:|Swap:"
df -h / | tail -1

echo ""
echo "========================================="
echo "✅ Deployment complete!"
echo "========================================="
echo "Frontend URL: http://178.156.223.196"
echo "Backend URL: http://178.156.223.196:8000"
echo "========================================="
