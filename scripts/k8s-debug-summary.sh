#!/usr/bin/env bash
# k8s-debug-summary.sh — Quick K8s status for lb-automotive and gamebox-security
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
echo "=== Recent events (lb-automotive) ==="
run get events -n lb-automotive --sort-by='.lastTimestamp' --tail=10 2>/dev/null || true
