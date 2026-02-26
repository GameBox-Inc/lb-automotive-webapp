#!/bin/bash
set -e

echo "🚀 Deploying GameBox Security Gateway (Traefik)"
echo ""

# Deploy namespace
echo "📦 Creating gamebox-security namespace..."
kubectl apply -f deployment/k8s/gamebox-security/namespace.yaml

# Label lb-automotive namespace for network policies
echo "🏷️  Labeling lb-automotive namespace..."
kubectl label namespace lb-automotive name=lb-automotive --overwrite

# Deploy network policies
echo "🔒 Configuring network policies..."
kubectl apply -f deployment/k8s/gamebox-security/network-policy.yaml

# ── Stage 1: Gateway API foundation ──────────────────────────────────────────
echo ""
echo "⚙️  Stage 1: Applying GatewayClass + Gateway..."
kubectl apply -f deployment/k8s/gamebox-security/traefik/gateway.yaml

# Wait for Traefik to be available
echo "⏳ Waiting for Traefik deployment to be ready..."
kubectl rollout status deployment/traefik -n gamebox-security --timeout=2m || echo "  (Traefik not yet deployed via Helm — skipping rollout check)"

# ── Stage 2: Middleware + cross-namespace permissions ─────────────────────────
echo ""
echo "⚙️  Stage 2: Applying Middlewares and ReferenceGrant..."
kubectl apply -f deployment/k8s/gamebox-security/traefik/middlewares.yaml
kubectl apply -f deployment/k8s/lb-automotive/reference-grant.yaml

# ── Stage 3: HTTPRoutes ───────────────────────────────────────────────────────
echo ""
echo "⚙️  Stage 3: Applying HTTPRoutes..."
kubectl apply -f deployment/k8s/gamebox-security/traefik/lb-automotive-routes.yaml

# ── Stage 4: Validate Gateway API routes accepted ─────────────────────────────
echo ""
echo "🔍 Verifying HTTPRoutes are accepted by Traefik..."
sleep 3
kubectl get httproute -n gamebox-security -o wide

# ── Stage 5: Remove legacy Ingress objects ─────────────────────────────────────
echo ""
echo "🧹 Removing legacy Ingress objects (replaced by HTTPRoutes)..."
kubectl delete ingress lb-automotive-ingress -n lb-automotive --ignore-not-found
kubectl delete ingress twilio-webhook-ingress -n lb-automotive --ignore-not-found

# ── Stage 6: Apply Cloudflare Tunnel (K8s deployment) ─────────────────────────
echo ""
echo "☁️  Stage 6: Applying Cloudflare Tunnel deployment..."
kubectl apply -f deployment/k8s/gamebox-security/cloudflared.yaml
kubectl rollout status deployment/cloudflared -n gamebox-security --timeout=2m

# Get service info
echo ""
echo "✅ GameBox Security Gateway deployed successfully!"
echo ""
echo "📊 Deployment Status:"
kubectl get pods -n gamebox-security
echo ""
kubectl get svc -n gamebox-security
echo ""
echo "📋 HTTPRoute status:"
kubectl get httproute -n gamebox-security
echo ""
echo "📝 Next steps:"
echo "1. Ensure the systemd cloudflared service is STOPPED on the host:"
echo "   sudo systemctl stop cloudflared && sudo systemctl disable cloudflared"
echo "2. Test Twilio webhook: make a call to your Twilio number"
echo "3. Monitor backend logs: kubectl logs -n lb-automotive -l app=backend -f"
echo ""
