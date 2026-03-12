#!/usr/bin/env bash
# =============================================================================
# vault-health-check.sh — Fail if Vault sealed or backend stuck in Init
#
# Used by a CronJob to surface alerts when the seal chain is broken.
# Exit 0 = healthy; exit 1 = unhealthy (CronJob shows as failed).
#
# Run inside cluster (as CronJob) or with KUBECONFIG / kubectl context set.
# =============================================================================
set -euo pipefail

KUBECTL="${KUBECTL:-kubectl}"
FAILED=0

# Unseal Vault must be unsealed
if $KUBECTL get pod -n vault-unseal unseal-vault-0 -o jsonpath='{.status.phase}' 2>/dev/null | grep -q Running; then
  SEALED=$($KUBECTL exec -n vault-unseal unseal-vault-0 -c vault -- \
    env VAULT_ADDR=http://127.0.0.1:8200 vault status -format=json 2>/dev/null | grep -o '"sealed":[^,}]*' | grep -o 'true\|false' || echo "unknown")
  if [[ "$SEALED" == "true" ]]; then
    echo "❌ Unseal Vault (vault-unseal) is SEALED"
    FAILED=1
  fi
else
  echo "⚠️ Unseal Vault pod not Running"
  FAILED=1
fi

# Main Vault must be unsealed
if $KUBECTL get pod -n gamebox-security vault-0 -o jsonpath='{.status.phase}' 2>/dev/null | grep -q Running; then
  SEALED=$($KUBECTL exec -n gamebox-security vault-0 -c vault -- \
    env VAULT_SKIP_VERIFY=true vault status -format=json 2>/dev/null | grep -o '"sealed":[^,}]*' | grep -o 'true\|false' || echo "unknown")
  if [[ "$SEALED" == "true" ]]; then
    echo "❌ Main Vault (gamebox-security/vault-0) is SEALED"
    FAILED=1
  fi
else
  echo "⚠️ Main Vault pod not Running"
  FAILED=1
fi

# Backend pods should not be stuck in Init
INIT_COUNT=$($KUBECTL get pods -n lb-automotive -l app=backend -o json 2>/dev/null | \
  grep -c '"phase":"Pending"' || true)
BACKEND_INIT=$($KUBECTL get pods -n lb-automotive -l app=backend -o jsonpath='{.items[*].status.containerStatuses[*].ready}' 2>/dev/null || true)
# If any backend pod has init container not completed, status shows Init:0/1
BACKEND_STATUS=$($KUBECTL get pods -n lb-automotive -l app=backend -o jsonpath='{range .items[*]}{.metadata.name}: {.status.phase} {.status.containerStatuses[*].ready}{"\n"}{end}' 2>/dev/null || echo "no-backend")
if echo "$BACKEND_STATUS" | grep -q "Init"; then
  echo "❌ Backend pods stuck in Init (Vault Agent not ready)"
  FAILED=1
fi

if [[ $FAILED -eq 1 ]]; then
  echo "▶ Vault health check FAILED — see docs/incidents/common-failures.md"
  exit 1
fi

echo "✅ Vault health check OK"
exit 0
