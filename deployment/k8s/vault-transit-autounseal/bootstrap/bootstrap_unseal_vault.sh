#!/bin/bash
# =============================================================================
# bootstrap_unseal_vault.sh — Initialize and configure the Unseal Vault
#
# Run ONCE after helm install of unseal-vault into the vault-unseal namespace.
# Creates the Transit key + least-privilege token for Main Vault auto-unseal.
#
# Prerequisites:
#   - unseal-vault pod is Running in vault-unseal namespace
#   - kubectl context points to your K3s cluster
#   - TLS certs created (tls/generate-tls.sh) and K8s secret created
#
# Usage:
#   bash bootstrap_unseal_vault.sh
#
# Outputs:
#   unseal_init.json            — root token + unseal keys (0600, keep offline)
#   main_vault_unseal_token.txt — transit token for Main Vault (0600)
# =============================================================================
set -euo pipefail

NAMESPACE="vault-unseal"
POD="unseal-vault-0"
TRANSIT_KEY_NAME="${TRANSIT_KEY_NAME:-autounseal}"
TRANSIT_MOUNT_PATH="${TRANSIT_MOUNT_PATH:-transit}"
OUTPUT_DIR="${OUTPUT_DIR:-.}"

# Colors
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# Helper: run vault command inside pod
vault_exec() {
  kubectl exec -n "$NAMESPACE" "$POD" -c vault -- \
    env VAULT_ADDR=http://127.0.0.1:8200 "$@"
}

# ── Step 1: Wait for pod ──────────────────────────────────────────────────────
info "Waiting for $POD to be running..."
kubectl wait pod "$POD" -n "$NAMESPACE" \
  --for=condition=Ready --timeout=120s || true

# ── Step 2: Check initialization status ──────────────────────────────────────
INIT_STATUS=$(vault_exec vault status -format=json 2>/dev/null | \
  grep -o '"initialized":[^,}]*' | grep -o 'true\|false' || echo "unknown")

if [ "$INIT_STATUS" = "true" ]; then
  warn "Unseal Vault is already initialized. Skipping init step."
  warn "If you need the token, find it in $OUTPUT_DIR/main_vault_unseal_token.txt"
else
  # ── Step 3: Initialize ─────────────────────────────────────────────────────
  info "Initializing Unseal Vault (5 key shares, threshold 3)..."
  vault_exec vault operator init \
    -key-shares=5 \
    -key-threshold=3 \
    -format=json > "$OUTPUT_DIR/unseal_init.json"

  chmod 600 "$OUTPUT_DIR/unseal_init.json"
  info "✅ Init data saved to $OUTPUT_DIR/unseal_init.json (chmod 600)"
  warn "⚠️  BACK THIS FILE UP OFFLINE. This is the only copy of your root token + unseal keys."

  # ── Step 4: Unseal (manual — one-time for bootstrap) ─────────────────────
  info "Unsealing Unseal Vault..."
  KEY1=$(jq -r '.unseal_keys_b64[0]' "$OUTPUT_DIR/unseal_init.json")
  KEY2=$(jq -r '.unseal_keys_b64[1]' "$OUTPUT_DIR/unseal_init.json")
  KEY3=$(jq -r '.unseal_keys_b64[2]' "$OUTPUT_DIR/unseal_init.json")
  vault_exec vault operator unseal "$KEY1"
  vault_exec vault operator unseal "$KEY2"
  vault_exec vault operator unseal "$KEY3"
  info "✅ Unseal Vault is unsealed"
fi

# ── Step 5: Login with root token ─────────────────────────────────────────────
ROOT_TOKEN=$(jq -r '.root_token' "$OUTPUT_DIR/unseal_init.json" 2>/dev/null || \
  { echo "Enter Unseal Vault root token:"; read -rs TOKEN; echo "$TOKEN"; })
vault_exec vault login "$ROOT_TOKEN" > /dev/null
info "✅ Logged in with root token"

# ── Step 6: Enable audit log ──────────────────────────────────────────────────
if ! vault_exec vault audit list | grep -q "file/"; then
  vault_exec vault audit enable file file_path=stdout
  info "✅ Audit log enabled (stdout)"
fi

# ── Step 7: Enable Transit secrets engine ────────────────────────────────────
if ! vault_exec vault secrets list | grep -q "^${TRANSIT_MOUNT_PATH}/"; then
  vault_exec vault secrets enable -path="$TRANSIT_MOUNT_PATH" transit
  info "✅ Transit engine enabled at $TRANSIT_MOUNT_PATH/"
else
  warn "Transit engine already enabled"
fi

# ── Step 8: Create Transit key ───────────────────────────────────────────────
if ! vault_exec vault read "${TRANSIT_MOUNT_PATH}/keys/${TRANSIT_KEY_NAME}" \
     -format=json > /dev/null 2>&1; then
  vault_exec vault write -f \
    "${TRANSIT_MOUNT_PATH}/keys/${TRANSIT_KEY_NAME}" \
    type=aes256-gcm96 \
    exportable=false \
    allow_plaintext_backup=false
  info "✅ Transit key '$TRANSIT_KEY_NAME' created"
else
  warn "Transit key '$TRANSIT_KEY_NAME' already exists"
fi

# ── Step 9: Create least-privilege policy ────────────────────────────────────
vault_exec vault policy write main-vault-autounseal - <<EOF
# Minimum required for Vault Transit auto-unseal
# encrypt: used during Main Vault initialization/first seal
# decrypt: used on every Main Vault startup to unseal
path "${TRANSIT_MOUNT_PATH}/encrypt/${TRANSIT_KEY_NAME}" {
  capabilities = ["update"]
}
path "${TRANSIT_MOUNT_PATH}/decrypt/${TRANSIT_KEY_NAME}" {
  capabilities = ["update"]
}
EOF
info "✅ Policy 'main-vault-autounseal' created"

# ── Step 10: Create periodic token with short TTL + auto-renew ───────────────
TOKEN_JSON=$(vault_exec vault token create \
  -policy=main-vault-autounseal \
  -display-name="main-vault-autounseal" \
  -ttl=8760h \
  -period=8760h \
  -orphan=true \
  -renewable=true \
  -format=json)

UNSEAL_TOKEN=$(echo "$TOKEN_JSON" | jq -r '.auth.client_token')
echo "$UNSEAL_TOKEN" > "$OUTPUT_DIR/main_vault_unseal_token.txt"
chmod 600 "$OUTPUT_DIR/main_vault_unseal_token.txt"

info "✅ Unseal token created"
info "✅ Token saved to $OUTPUT_DIR/main_vault_unseal_token.txt (chmod 600)"

echo ""
echo "══════════════════════════════════════════════════════════════"
echo " NEXT STEP: Create K8s secret with the unseal token"
echo "══════════════════════════════════════════════════════════════"
echo ""
echo "    kubectl create secret generic vault-transit-token \\"
echo "      --from-literal=token=\$(cat $OUTPUT_DIR/main_vault_unseal_token.txt) \\"
echo "      --namespace=gamebox-security"
echo ""
echo " Then run: bootstrap_main_vault.sh"
echo "══════════════════════════════════════════════════════════════"
