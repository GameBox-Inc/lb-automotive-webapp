#!/bin/bash
# =============================================================================
# vault-init.sh — Initialize, Unseal, and Configure Vault for GameBox OS
#
# Run ONCE after Vault is deployed via Helm and the pod is Running.
# This script:
#   1. Initializes Vault (generates 5 unseal keys, 3 required)
#   2. Unseals Vault
#   3. Enables KV v2 secrets engine
#   4. Enables Kubernetes auth method + configures it
#   5. Migrates lb-automotive secrets from K8s secrets into Vault
#   6. Registers lb-automotive as the first GameBox OS app
#
# Prerequisites:
#   - kubectl access to the cluster
#   - helm install vault already done
#   - vault CLI installed locally OR use kubectl exec
#
# ⚠️  SECURITY: The unseal keys and root token printed at the end MUST be
#     stored securely (e.g. printed and locked in a safe, or split across
#     trusted parties). Do NOT commit them anywhere.
# =============================================================================
set -euo pipefail

NAMESPACE="gamebox-security"
VAULT_POD="vault-0"
VAULT_ADDR="https://vault.${NAMESPACE}.svc.cluster.local:8200"

# Use kubectl exec to run vault commands inside the pod
VAULT_EXEC="kubectl exec -n $NAMESPACE $VAULT_POD -- vault"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo "================================================"
echo " GameBox OS — Vault Initialization"
echo " Pod:  $VAULT_POD  |  Namespace: $NAMESPACE"
echo "================================================"
echo ""

# ─── Wait for Vault pod to be ready ──────────────────────────────────────────
echo "▶ Waiting for Vault pod to be Running..."
kubectl wait pod/$VAULT_POD \
  --namespace=$NAMESPACE \
  --for=condition=Ready \
  --timeout=120s
echo -e "${GREEN}  ✅ Vault pod is Ready${NC}"

# ─── 1. Initialize Vault ─────────────────────────────────────────────────────
echo ""
echo "▶ Initializing Vault (5 keys, threshold 3)..."

INIT_OUTPUT=$(kubectl exec -n $NAMESPACE $VAULT_POD -- \
  vault operator init \
    -key-shares=5 \
    -key-threshold=3 \
    -format=json 2>&1)

if echo "$INIT_OUTPUT" | grep -q "already initialized"; then
  echo -e "${YELLOW}  ⚠️  Vault already initialized — skipping init step${NC}"
  echo "     Provide unseal keys and root token manually:"
  read -sp "     Root Token: " VAULT_TOKEN; echo ""
  export VAULT_TOKEN
else
  # Save init output
  echo "$INIT_OUTPUT" > /tmp/vault-init-output.json
  chmod 600 /tmp/vault-init-output.json

  UNSEAL_KEY_1=$(echo "$INIT_OUTPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['unseal_keys_b64'][0])")
  UNSEAL_KEY_2=$(echo "$INIT_OUTPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['unseal_keys_b64'][1])")
  UNSEAL_KEY_3=$(echo "$INIT_OUTPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['unseal_keys_b64'][2])")
  ROOT_TOKEN=$(echo   "$INIT_OUTPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['root_token'])")

  echo -e "${GREEN}  ✅ Vault initialized!${NC}"
  echo -e "${RED}"
  echo "  ╔══════════════════════════════════════════════════════════════╗"
  echo "  ║  SECURITY: STORE THESE OFFLINE — DO NOT COMMIT              ║"
  echo "  ╠══════════════════════════════════════════════════════════════╣"
  echo "  ║  Unseal Key 1: $UNSEAL_KEY_1"
  echo "  ║  Unseal Key 2: $UNSEAL_KEY_2"
  echo "  ║  Unseal Key 3: $UNSEAL_KEY_3"
  echo "  ║  Root Token:   $ROOT_TOKEN"
  echo "  ╚══════════════════════════════════════════════════════════════╝"
  echo -e "${NC}"
  echo "  Full output saved to: /tmp/vault-init-output.json (delete after storing keys)"

  export VAULT_TOKEN="$ROOT_TOKEN"
fi

# ─── 2. Unseal Vault ─────────────────────────────────────────────────────────
echo ""
echo "▶ Unsealing Vault (3 of 5 keys required)..."

for KEY_VAR in UNSEAL_KEY_1 UNSEAL_KEY_2 UNSEAL_KEY_3; do
  # If running after a restart, prompt for keys
  KEY_VALUE="${!KEY_VAR:-}"
  if [[ -z "$KEY_VALUE" ]]; then
    read -sp "  Enter unseal key ($KEY_VAR): " KEY_VALUE; echo ""
  fi
  kubectl exec -n $NAMESPACE $VAULT_POD -- \
    vault operator unseal "$KEY_VALUE" > /dev/null
done

echo -e "${GREEN}  ✅ Vault unsealed${NC}"

# ─── Set Vault CLI env (for remaining commands via kubectl exec) ───────────────
VAULT_CMD="kubectl exec -n $NAMESPACE $VAULT_POD -- env VAULT_TOKEN=$VAULT_TOKEN VAULT_ADDR=https://127.0.0.1:8200 VAULT_SKIP_VERIFY=true vault"

# ─── 3. Enable KV v2 Secrets Engine ─────────────────────────────────────────
echo ""
echo "▶ Enabling KV v2 secrets engine at 'secret/'..."
$VAULT_CMD secrets enable -path=secret kv-v2 2>/dev/null || echo "  (already enabled)"
echo -e "${GREEN}  ✅ KV v2 enabled at secret/${NC}"

# ─── 4. Enable and Configure Kubernetes Auth ─────────────────────────────────
echo ""
echo "▶ Enabling Kubernetes auth method..."
$VAULT_CMD auth enable kubernetes 2>/dev/null || echo "  (already enabled)"

echo "▶ Configuring Kubernetes auth (using in-cluster API server)..."
K8S_HOST="https://kubernetes.default.svc"
K8S_CA=$(kubectl config view --raw --minify --flatten -o jsonpath='{.clusters[0].cluster.certificate-authority-data}' | base64 -d)

# Use the Vault SA token for the auth backend configuration
VAULT_SA_SECRET=$(kubectl get secret -n $NAMESPACE \
  -l app=vault -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")

if [[ -n "$VAULT_SA_SECRET" ]]; then
  VAULT_SA_JWT=$(kubectl get secret -n $NAMESPACE "$VAULT_SA_SECRET" \
    -o jsonpath='{.data.token}' | base64 -d)
else
  # K8s 1.24+ — generate token directly
  VAULT_SA_JWT=$(kubectl create token vault -n $NAMESPACE --duration=8760h)
fi

$VAULT_CMD write auth/kubernetes/config \
  kubernetes_host="$K8S_HOST" \
  kubernetes_ca_cert="$K8S_CA" \
  token_reviewer_jwt="$VAULT_SA_JWT" \
  disable_local_ca_jwt=false

echo -e "${GREEN}  ✅ Kubernetes auth configured${NC}"

# ─── 5. Load lb-automotive Secrets ───────────────────────────────────────────
echo ""
echo "▶ Migrating lb-automotive secrets into Vault..."
echo "  (Reading from existing K8s secrets in lb-automotive namespace)"

# Read each K8s secret and load into Vault  
read_k8s_secret() {
  local SECRET_NAME=$1
  local FIELD=$2
  kubectl get secret -n lb-automotive "$SECRET_NAME" \
    -o jsonpath="{.data.$FIELD}" 2>/dev/null | base64 -d || echo ""
}

# App secrets
SECRET_KEY=$(read_k8s_secret app-secrets SECRET_KEY)
ALLOWED_ORIGINS=$(read_k8s_secret app-secrets ALLOWED_ORIGINS)
DATABASE_URL=$(read_k8s_secret app-secrets DATABASE_URL)
REDIS_URL=$(read_k8s_secret app-secrets REDIS_URL)
CSP_POLICY=$(read_k8s_secret app-secrets CSP_POLICY)
LLM_PROVIDER=$(read_k8s_secret app-secrets LLM_PROVIDER)

# Prompt for any missing values
[[ -z "$SECRET_KEY" ]] && { read -sp "  SECRET_KEY: " SECRET_KEY; echo ""; }

$VAULT_CMD kv put secret/lb-automotive/app \
  SECRET_KEY="$SECRET_KEY" \
  ALLOWED_ORIGINS="${ALLOWED_ORIGINS:-https://kozytherocket.space}" \
  DATABASE_URL="${DATABASE_URL:-sqlite:////app/data/lb_automotive.db}" \
  REDIS_URL="${REDIS_URL:-redis://redis:6379/0}" \
  CSP_POLICY="${CSP_POLICY:-strict}" \
  LLM_PROVIDER="${LLM_PROVIDER:-anthropic}" \
  ENVIRONMENT="production" \
  CAPTCHA_REQUIRED="true" \
  RATE_LIMIT_PER_MINUTE="120"

echo -e "${GREEN}  ✅ secret/lb-automotive/app written${NC}"

# Twilio secrets (optional)
TWILIO_SID=$(read_k8s_secret twilio-secrets TWILIO_ACCOUNT_SID)
TWILIO_TOKEN=$(read_k8s_secret twilio-secrets TWILIO_AUTH_TOKEN)
TWILIO_PHONE=$(read_k8s_secret twilio-secrets TWILIO_PHONE_NUMBER)

if [[ -n "$TWILIO_SID" ]]; then
  $VAULT_CMD kv put secret/lb-automotive/twilio \
    TWILIO_ACCOUNT_SID="$TWILIO_SID" \
    TWILIO_AUTH_TOKEN="$TWILIO_TOKEN" \
    TWILIO_PHONE_NUMBER="$TWILIO_PHONE" \
    TWILIO_WEBHOOK_BASE_URL="https://twilio.kozytherocket.space/lb-automotive/api/twilio/webhook"
  echo -e "${GREEN}  ✅ secret/lb-automotive/twilio written${NC}"
fi

# Anthropic secrets (optional)
ANTHROPIC_KEY=$(read_k8s_secret anthropic-secrets ANTHROPIC_API_KEY)
ANTHROPIC_MODEL=$(read_k8s_secret anthropic-secrets ANTHROPIC_MODEL)

if [[ -n "$ANTHROPIC_KEY" ]]; then
  $VAULT_CMD kv put secret/lb-automotive/anthropic \
    ANTHROPIC_API_KEY="$ANTHROPIC_KEY" \
    ANTHROPIC_MODEL="${ANTHROPIC_MODEL:-claude-3-5-sonnet-20241022}"
  echo -e "${GREEN}  ✅ secret/lb-automotive/anthropic written${NC}"
fi

# ─── 6. Register lb-automotive with Vault ────────────────────────────────────
echo ""
echo "▶ Registering lb-automotive as first GameBox OS application..."

# Write the policy
$VAULT_CMD policy write lb-automotive-policy - <<'POLICY'
path "secret/data/lb-automotive/*" {
  capabilities = ["read", "list"]
}
path "auth/token/renew-self" {
  capabilities = ["update"]
}
path "auth/token/lookup-self" {
  capabilities = ["read"]
}
POLICY

# Create the auth role
$VAULT_CMD write auth/kubernetes/role/lb-automotive-role \
  bound_service_account_names="lb-automotive-backend" \
  bound_service_account_namespaces="lb-automotive" \
  policies="lb-automotive-policy" \
  ttl="1h" \
  max_ttl="24h"

echo -e "${GREEN}  ✅ Vault role 'lb-automotive-role' created${NC}"

# Label namespace for injector webhook
kubectl label namespace lb-automotive vault-injection=enabled --overwrite
echo -e "${GREEN}  ✅ lb-automotive namespace labeled for injector${NC}"

# ─── Summary ─────────────────────────────────────────────────────────────────
echo ""
echo "================================================"
echo -e "${GREEN}✅ Vault is initialized and configured!${NC}"
echo ""
echo "Vault status:"
$VAULT_CMD status
echo ""
echo "Next steps:"
echo "  1. Store unseal keys and root token securely (offline)"
echo "  2. Delete /tmp/vault-init-output.json from the server"
echo "  3. Restart the backend pod: kubectl rollout restart deploy/backend -n lb-automotive"
echo "  4. To register a new app: bash register-app.sh --namespace <ns> --app <app> --sa <sa>"
echo "================================================"
