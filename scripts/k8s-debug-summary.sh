#!/usr/bin/env bash
# k8s-debug-summary.sh — Quick K8s status for 502 / backend-down diagnostics
# Usage: ./scripts/k8s-debug-summary.sh [user@host]
# Set DEPLOY_HOST or pass as first arg. Uses ssh if host given.

set -e
HOST="${1:-${DEPLOY_HOST:-lb-admin@178.156.223.196}}"
KUBECTL="sudo k3s kubectl"

run() {
  if [[ "$HOST" == *"@"* ]]; then
    ssh -o StrictHostKeyChecking=no "$HOST" "$KUBECTL $*"
  else
    $KUBECTL "$@"
  fi
}

echo "=== Pods (lb-automotive) ==="
run get pods -n lb-automotive -o wide 2>/dev/null || true

echo ""
echo "=== Pods (gamebox-security) ==="
run get pods -n gamebox-security -o wide 2>/dev/null || true

echo ""
echo "=== Pods (vault-unseal) ==="
run get pods -n vault-unseal -o wide 2>/dev/null || true

echo ""
echo "=== Unseal Vault status (unseal-vault-0) ==="
run exec -n vault-unseal unseal-vault-0 -c vault -- env VAULT_ADDR=http://127.0.0.1:8200 vault status 2>/dev/null || echo "(pod not Running or exec failed)"

echo ""
echo "=== Main Vault status (vault-0) ==="
run exec -n gamebox-security vault-0 -c vault -- env VAULT_SKIP_VERIFY=true vault status 2>/dev/null || echo "(pod not Running or exec failed)"

echo ""
echo "=== Backend pod / app-secrets (backend uses K8s Secrets, no Vault) ==="
run get secret app-secrets -n lb-automotive -o name 2>/dev/null || echo "(app-secrets missing — run create-secrets.sh or Jenkins Ensure App Secrets)"
BPOD=$(run get pods -n lb-automotive -l app=backend -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)

echo ""
echo "=== Backend container logs — if not Ready or CrashLoopBackOff ==="
if [[ -n "$BPOD" ]]; then
  run logs -n lb-automotive "$BPOD" -c backend --tail=30 2>/dev/null || \
  run logs -n lb-automotive "$BPOD" -c backend --previous --tail=30 2>/dev/null || echo "(no backend logs)"
fi

echo ""
echo "=== Recent events (lb-automotive) ==="
run get events -n lb-automotive --sort-by='.lastTimestamp' --tail=10 2>/dev/null || true

echo ""
echo "--- 502 fix: Ensure app-secrets exist (create-secrets.sh or Jenkins) → Restart backend ---"
