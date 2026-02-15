#!/bin/bash
set -e

echo "🚀 Deploying GameBox Security Gateway"
echo ""

# Deploy namespace
echo "📦 Creating gamebox-security namespace..."
kubectl apply -f deployment/k8s/gamebox-security/namespace.yaml

# Label lb-automotive namespace for network policies
echo "🏷️  Labeling lb-automotive namespace..."
kubectl label namespace lb-automotive name=lb-automotive --overwrite

# Deploy nginx gateway
echo "🌐 Deploying nginx gateway..."
kubectl apply -f deployment/k8s/gamebox-security/nginx-config.yaml
kubectl apply -f deployment/k8s/gamebox-security/nginx-gateway.yaml

# Deploy network policies
echo "🔒 Configuring network policies..."
kubectl apply -f deployment/k8s/gamebox-security/network-policy.yaml

# Wait for deployment
echo "⏳ Waiting for nginx-gateway to be ready..."
kubectl rollout status deployment/nginx-gateway -n gamebox-security --timeout=2m

# Get service info
echo ""
echo "✅ GameBox Security Gateway deployed successfully!"
echo ""
echo "📊 Deployment Status:"
kubectl get pods -n gamebox-security
echo ""
kubectl get svc -n gamebox-security
echo ""
echo "🔗 Nginx Gateway is exposed on NodePort 30880"
echo ""
echo "📝 Next steps:"
echo "1. Set up Cloudflare Tunnel (run deployment/scripts/setup-cloudflare-tunnel.sh)"
echo "2. Test cross-namespace communication"
echo "3. Update Twilio webhook URL"
echo ""
