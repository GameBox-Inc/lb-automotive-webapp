#!/bin/bash
# =============================================================================
# verify.sh — Validate the full Vault Transit Auto-Unseal setup
#
# Usage: bash ops/verify.sh
# =============================================================================
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
pass() { echo -e "${GREEN}[PASS]${NC} $*"; }
fail() { echo -e "${RED}[FAIL]${NC} $*"; FAILED=$((FAILED+1)); }
info() { echo -e "${BLUE}[INFO]${NC} $*"; }
FAILED=0

unseal_exec() { kubectl exec -n vault-unseal vault-0 -c vault -- env VAULT_SKIP_VERIFY=true VAULT_ADDR=https://127.0.0.1:8200 "$@" 2>/dev/null; }
main_exec()   { kubectl exec -n gamebox-security vault-0 -c vault -- env VAULT_SKIP_VERIFY=true VAULT_ADDR=https://127.0.0.1:8200 "$@" 2>/dev/null; }

echo ""
echo "══════════════════════════════════════════════════════"
echo " Vault Transit Auto-Unseal Verification"
echo "══════════════════════════════════════════════════════"

# ── 1. Unseal Vault health ────────────────────────────────────────────────────
echo ""
info "1/5 — Unseal Vault status"
if kubectl get pod vault-0 -n vault-unseal -o jsonpath='{.status.phase}' 2>/dev/null | grep -q Running; then
  SEALED=$(unseal_exec vault status -format=json | grep -o '"sealed":[^,}]*' | grep -o 'true\|false' || echo unknown)
  INIT=$(unseal_exec vault status -format=json | grep -o '"initialized":[^,}]*' | grep -o 'true\|false' || echo unknown)
  [ "$INIT" = "true" ]  && pass "Unseal Vault initialized" || fail "Unseal Vault NOT initialized"
  [ "$SEALED" = "false" ] && pass "Unseal Vault unsealed"  || fail "Unseal Vault is SEALED"
else
  fail "Unseal Vault pod not running"
fi

# ── 2. Main Vault health ──────────────────────────────────────────────────────
echo ""
info "2/5 — Main Vault status"
if kubectl get pod vault-0 -n gamebox-security -o jsonpath='{.status.phase}' 2>/dev/null | grep -q Running; then
  MAIN_STATUS=$(main_exec vault status -format=json 2>/dev/null || echo '{}')
  MAIN_SEALED=$(echo "$MAIN_STATUS" | grep -o '"sealed":[^,}]*' | grep -o 'true\|false' || echo unknown)
  MAIN_INIT=$(echo "$MAIN_STATUS" | grep -o '"initialized":[^,}]*' | grep -o 'true\|false' || echo unknown)
  SEAL_TYPE=$(echo "$MAIN_STATUS" | grep -o '"type":"[^"]*"' | head -1 | grep -o '"[^"]*"$' | tr -d '"' || echo unknown)

  [ "$MAIN_INIT" = "true" ]   && pass "Main Vault initialized"            || fail "Main Vault NOT initialized"
  [ "$MAIN_SEALED" = "false" ] && pass "Main Vault unsealed"              || fail "Main Vault is SEALED"
  [ "$SEAL_TYPE" = "transit" ] && pass "Seal type: transit (auto-unseal)" || fail "Seal type is '$SEAL_TYPE' (expected transit)"
else
  fail "Main Vault pod not running"
fi

# ── 3. Auto-unseal on pod restart ─────────────────────────────────────────────
echo ""
info "3/5 — Auto-unseal test: killing Main Vault pod..."
kubectl delete pod vault-0 -n gamebox-security --grace-period=0 2>/dev/null || true
info "Waiting 45s for pod to restart and auto-unseal..."
sleep 45

if kubectl wait pod vault-0 -n gamebox-security --for=condition=Ready --timeout=60s 2>/dev/null; then
  SEALED_AFTER=$(main_exec vault status -format=json | grep -o '"sealed":[^,}]*' | grep -o 'true\|false' || echo unknown)
  [ "$SEALED_AFTER" = "false" ] && pass "Auto-unseal after restart works!" || fail "Vault still sealed after restart"
else
  fail "Main Vault pod did not become Ready within 60s"
fi

# ── 4. Transit encrypt/decrypt round-trip ─────────────────────────────────────
echo ""
info "4/5 — Transit encrypt/decrypt test (using Unseal Vault token)"
UNSEAL_TOKEN="${UNSEAL_VAULT_TOKEN:-}"
if [ -z "$UNSEAL_TOKEN" ] && [ -f "./main_vault_unseal_token.txt" ]; then
  UNSEAL_TOKEN=$(cat ./main_vault_unseal_token.txt)
fi

if [ -n "$UNSEAL_TOKEN" ]; then
  PLAINTEXT_B64=$(echo -n "test-autounceal-verification" | base64)
  CIPHERTEXT=$(kubectl exec -n vault-unseal vault-0 -c vault -- \
    env VAULT_SKIP_VERIFY=true VAULT_ADDR=https://127.0.0.1:8200 VAULT_TOKEN="$UNSEAL_TOKEN" \
    vault write -field=ciphertext transit/encrypt/autounseal \
    plaintext="$PLAINTEXT_B64" 2>/dev/null || echo "")

  if [ -n "$CIPHERTEXT" ]; then
    pass "Transit encrypt succeeded: ${CIPHERTEXT:0:30}..."
    DECRYPTED=$(kubectl exec -n vault-unseal vault-0 -c vault -- \
      env VAULT_SKIP_VERIFY=true VAULT_ADDR=https://127.0.0.1:8200 VAULT_TOKEN="$UNSEAL_TOKEN" \
      vault write -field=plaintext transit/decrypt/autounseal \
      ciphertext="$CIPHERTEXT" 2>/dev/null | base64 -d || echo "")
    [ "$DECRYPTED" = "test-autounceal-verification" ] && \
      pass "Transit decrypt succeeded: round-trip verified" || \
      fail "Transit decrypt failed or wrong value: '$DECRYPTED'"
  else
    fail "Transit encrypt failed (check token permissions)"
  fi
else
  info "Skipping encrypt/decrypt test (set UNSEAL_VAULT_TOKEN env var or place token in ./main_vault_unseal_token.txt)"
fi

# ── 5. Backend sidecar ────────────────────────────────────────────────────────
echo ""
info "5/5 — Backend sidecar injection"
CONTAINERS=$(kubectl get pod -l app=backend -n lb-automotive \
  -o jsonpath='{.items[0].spec.containers[*].name}' 2>/dev/null || echo "")
if echo "$CONTAINERS" | grep -q "vault-agent"; then
  pass "Vault agent sidecar present in backend pod"
else
  fail "Vault agent sidecar NOT found. Containers: $CONTAINERS"
fi

if kubectl exec deployment/backend -n lb-automotive -c backend -- \
   env 2>/dev/null | grep -q "TWILIO_AUTH_TOKEN"; then
  pass "TWILIO_AUTH_TOKEN injected by sidecar"
else
  fail "TWILIO_AUTH_TOKEN not found in backend env"
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════════════"
if [ "$FAILED" -eq 0 ]; then
  echo -e "${GREEN} ✅ All checks passed!${NC}"
else
  echo -e "${RED} ❌ $FAILED check(s) failed${NC}"
fi
echo "══════════════════════════════════════════════════════"
exit "$FAILED"
