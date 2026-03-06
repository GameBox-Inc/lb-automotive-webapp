#!/bin/bash
# =============================================================================
# create-cloudflare-secret.sh — Load tunnel credentials into K8s
#
# Run on the server BEFORE applying cloudflared.yaml.
# The credentials JSON was created when you ran:
#   cloudflared tunnel create gamebox-gateway
# and lives at /etc/cloudflared/credentials.json
# =============================================================================
set -euo pipefail

NAMESPACE="gamebox-security"
CREDENTIALS_FILE="${1:-/etc/cloudflared/credentials.json}"

if [[ ! -f "$CREDENTIALS_FILE" ]]; then
  echo "❌ Credentials file not found: $CREDENTIALS_FILE"
  echo "   Run: cloudflared tunnel create gamebox-gateway"
  echo "   Then copy the credentials to /etc/cloudflared/credentials.json"
  exit 1
fi

echo "▶ Creating cloudflare-tunnel-credentials secret in $NAMESPACE..."

kubectl create secret generic cloudflare-tunnel-credentials \
  --namespace="$NAMESPACE" \
  --from-file=credentials.json="$CREDENTIALS_FILE" \
  --dry-run=client -o yaml | kubectl apply -f -

echo "✅ Secret created: cloudflare-tunnel-credentials"
echo ""
echo "Next: kubectl apply -f deployment/k8s/gamebox-security/cloudflared.yaml"
