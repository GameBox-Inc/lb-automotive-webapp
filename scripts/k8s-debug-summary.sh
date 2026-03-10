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
echo "=== Backend init logs (vault-agent-init) — if Init:0/1 ==="
BPOD=$(run get pods -n lb-automotive -l app=backend -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
if [[ -n "$BPOD" ]]; then
  run logs -n lb-automotive "$BPOD" -c vault-agent-init --tail=30 2>/dev/null || echo "(no init logs)"
fi

echo ""
echo "=== Backend container logs — if CrashLoopBackOff ==="
if [[ -n "$BPOD" ]]; then
  run logs -n lb-automotive "$BPOD" -c backend --tail=30 2>/dev/null || \
  run logs -n lb-automotive "$BPOD" -c backend --previous --tail=30 2>/dev/null || echo "(no backend logs)"
fi

echo ""
echo "=== Recent events (lb-automotive) ==="
run get events -n lb-automotive --sort-by='.lastTimestamp' --tail=10 2>/dev/null || true

echo ""
echo "--- 502 fix order: Unseal Vault (unsealed) → Main Vault (auto-unseals) → Backend (starts) ---"
