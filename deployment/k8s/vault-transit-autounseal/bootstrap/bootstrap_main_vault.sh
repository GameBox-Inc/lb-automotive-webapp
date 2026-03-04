#!/bin/bash
# =============================================================================
# bootstrap_main_vault.sh — Deploy and initialize Main Vault in K3s
#
# Run AFTER:
#   1. bootstrap_unseal_vault.sh completed
#   2. K8s secret vault-transit-token created in gamebox-security
#   3. K8s secret unseal-vault-ca created in gamebox-security
#   4. K8s secret vault-server-tls exists in gamebox-security (pre-existing)
#
# Usage:
#   bash bootstrap_main_vault.sh
# =============================================================================
set -euo pipefail

NAMESPACE="gamebox-security"
VAULT_POD="vault-0"
HELM_RELEASE="vault"
VALUES_FILE="${VALUES_FILE:-../main-vault/vault-helm-values-ha.yaml}"
OUTPUT_DIR="${OUTPUT_DIR:-.}"
K8S_AUTH_PATH="${K8S_AUTH_PATH:-kubernetes/}"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

vault_exec() {
  kubectl exec -n "$NAMESPACE" "$VAULT_POD" -c vault -- \
    env VAULT_SKIP_VERIFY=true VAULT_ADDR=https://127.0.0.1:8200 "$@"
}

# ── Step 1: Check prerequisites ───────────────────────────────────────────────
info "Checking prerequisites..."
kubectl get secret vault-transit-token -n "$NAMESPACE" > /dev/null || \
  error "Secret vault-transit-token not found in $NAMESPACE. Run bootstrap_unseal_vault.sh first."
kubectl get secret unseal-vault-ca -n "$NAMESPACE" > /dev/null || \
  error "Secret unseal-vault-ca not found in $NAMESPACE. Create it from the CA cert."
kubectl get secret vault-server-tls -n "$NAMESPACE" > /dev/null || \
  error "Secret vault-server-tls not found. Run deployment/k8s/gamebox-security/vault/vault-tls-secret.sh"
info "✅ All secrets present"

# ── Step 2: Helm upgrade (install or upgrade) ─────────────────────────────────
info "Adding hashicorp helm repo..."
helm repo add hashicorp https://helm.releases.hashicorp.com 2>/dev/null || true
helm repo update

info "Deploying/upgrading Main Vault via Helm..."
helm upgrade --install "$HELM_RELEASE" hashicorp/vault \
  --namespace "$NAMESPACE" \
  --values "$VALUES_FILE" \
  --wait --timeout 5m
info "✅ Helm release applied"

# ── Step 3: Wait for pod ─────────────────────────────────────────────────────
info "Waiting for $VAULT_POD to be running..."
kubectl wait pod "$VAULT_POD" -n "$NAMESPACE" \
  --for=condition=Initialized --timeout=120s
sleep 5

# ── Step 4: Check if already initialized ─────────────────────────────────────
INIT_STATUS=$(vault_exec vault status -format=json 2>/dev/null | \
  grep -o '"initialized":[^,}]*' | grep -o 'true\|false' || echo "unknown")

if [ "$INIT_STATUS" = "true" ]; then
  warn "Main Vault already initialized. Checking seal status..."
else
  # ── Step 5: Initialize Main Vault ────────────────────────────────────────
  info "Initializing Main Vault with transit auto-unseal..."
  info "With transit auto-unseal, you only need 1 recovery key (not unseal keys)."

  vault_exec vault operator init \
    -recovery-shares=5 \
    -recovery-threshold=3 \
    -format=json > "$OUTPUT_DIR/main_vault_init.json"

  chmod 600 "$OUTPUT_DIR/main_vault_init.json"
  info "✅ Main Vault initialized"
  warn "⚠️  Recovery keys saved to $OUTPUT_DIR/main_vault_init.json — BACK UP OFFLINE"
  warn "    Recovery keys are for disaster recovery only — NOT for routine unsealing"
fi

# ── Step 6: Verify auto-unseal worked ────────────────────────────────────────
SEALED=$(vault_exec vault status -format=json 2>/dev/null | \
  grep -o '"sealed":[^,}]*' | grep -o 'true\|false' || echo "unknown")

if [ "$SEALED" = "false" ]; then
  info "✅ Main Vault is unsealed (auto-unseal via transit is working!)"
else
  error "Main Vault is still sealed. Check that Unseal Vault is reachable and transit token is valid."
fi

# ── Step 7: Login and enable Kubernetes auth ──────────────────────────────────
ROOT_TOKEN=$(jq -r '.root_token' "$OUTPUT_DIR/main_vault_init.json" 2>/dev/null || \
  { echo "Enter Main Vault root token:"; read -rs T; echo "$T"; })

vault_exec vault login "$ROOT_TOKEN" > /dev/null
info "✅ Logged in with root token"

# Enable audit log
if ! vault_exec vault audit list | grep -q "file/"; then
  vault_exec vault audit enable file file_path=stdout
  info "✅ Audit log enabled"
fi

# Enable Kubernetes auth
if ! vault_exec vault auth list | grep -q "^${K8S_AUTH_PATH}"; then
  vault_exec vault auth enable -path="${K8S_AUTH_PATH}" kubernetes
  info "✅ Kubernetes auth enabled at $K8S_AUTH_PATH"

  # Configure K8s auth
  vault_exec vault write auth/${K8S_AUTH_PATH}config \
    kubernetes_host="https://kubernetes.default.svc:443" \
    issuer="https://kubernetes.default.svc.cluster.local"
  info "✅ Kubernetes auth configured"
else
  warn "Kubernetes auth already enabled"
fi

echo ""
echo "══════════════════════════════════════════════════════════════"
echo " ✅ Main Vault bootstrap complete!"
echo "══════════════════════════════════════════════════════════════"
echo ""
echo " Seal type   : transit (auto-unseal via Unseal Vault)"
echo " Sealed      : false"
echo " Root token  : saved in $OUTPUT_DIR/main_vault_init.json"
echo " Recovery keys: same file — STORE OFFLINE"
echo ""
echo " Run ops/verify.sh to validate the full setup."
echo "══════════════════════════════════════════════════════════════"
