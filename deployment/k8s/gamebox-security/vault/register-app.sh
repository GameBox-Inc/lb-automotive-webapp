#!/bin/bash
# =============================================================================
# register-app.sh — Register a new GameBox OS application with Vault
#
# Usage:
#   bash register-app.sh \
#     --namespace  lb-automotive \
#     --app        backend \
#     --sa         lb-automotive-backend \
#     --ttl        1h
#
# This script:
#   1. Creates a Vault policy (read-only access to secret/<namespace>/*)
#   2. Creates a Vault Kubernetes auth role binding the SA → policy
#   3. Labels the namespace so the injector webhook activates
#
# Prerequisites:
#   - Vault is initialized and unsealed
#   - VAULT_TOKEN is set (root token or admin token)
#   - VAULT_ADDR is set (e.g. https://vault.gamebox-security.svc:8200)
#   - VAULT_CACERT is set (path to ca.crt or set VAULT_SKIP_VERIFY=true for dev)
# =============================================================================
set -euo pipefail

# ─── Parse arguments ─────────────────────────────────────────────────────────
NAMESPACE=""
APP=""
SERVICE_ACCOUNT=""
TOKEN_TTL="1h"
TOKEN_MAX_TTL="24h"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --namespace) NAMESPACE="$2"; shift 2 ;;
    --app)       APP="$2";       shift 2 ;;
    --sa)        SERVICE_ACCOUNT="$2"; shift 2 ;;
    --ttl)       TOKEN_TTL="$2"; shift 2 ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

if [[ -z "$NAMESPACE" || -z "$APP" || -z "$SERVICE_ACCOUNT" ]]; then
  echo "Usage: $0 --namespace <ns> --app <app> --sa <service-account> [--ttl 1h]"
  exit 1
fi

VAULT_ADDR="${VAULT_ADDR:-https://vault.gamebox-security.svc.cluster.local:8200}"
POLICY_NAME="${NAMESPACE}-policy"
ROLE_NAME="${NAMESPACE}-role"

echo "================================================"
echo " Registering GameBox App with Vault"
echo " Namespace:       $NAMESPACE"
echo " Application:     $APP"
echo " Service Account: $SERVICE_ACCOUNT"
echo " Policy:          $POLICY_NAME"
echo " Auth Role:       $ROLE_NAME"
echo "================================================"

# ─── 1. Create Vault Policy ───────────────────────────────────────────────────
echo ""
echo "▶ Creating Vault policy: $POLICY_NAME"
vault policy write "$POLICY_NAME" - <<EOF
# GameBox OS — Auto-generated policy for namespace: $NAMESPACE
# Application read-only access to its own secrets

path "secret/data/${NAMESPACE}/*" {
  capabilities = ["read", "list"]
}

# Token self-management (required by Vault Agent)
path "auth/token/renew-self" {
  capabilities = ["update"]
}

path "auth/token/lookup-self" {
  capabilities = ["read"]
}
EOF

echo "  ✅ Policy created: $POLICY_NAME"

# ─── 2. Create Kubernetes Auth Role ───────────────────────────────────────────
echo ""
echo "▶ Creating Vault auth role: $ROLE_NAME"
vault write auth/kubernetes/role/"$ROLE_NAME" \
  bound_service_account_names="$SERVICE_ACCOUNT" \
  bound_service_account_namespaces="$NAMESPACE" \
  policies="$POLICY_NAME" \
  ttl="$TOKEN_TTL" \
  max_ttl="$TOKEN_MAX_TTL"

echo "  ✅ Auth role created: $ROLE_NAME"
echo "     Bound SA: $SERVICE_ACCOUNT in $NAMESPACE"
echo "     Token TTL: $TOKEN_TTL / Max: $TOKEN_MAX_TTL"

# ─── 3. Label namespace for injector webhook ────────────────────────────────
echo ""
echo "▶ Labeling namespace '$NAMESPACE' for Vault Agent Injector..."
kubectl label namespace "$NAMESPACE" vault-injection=enabled --overwrite

echo "  ✅ Namespace labeled"

echo ""
echo "================================================"
echo "✅ App registered with Vault!"
echo ""
echo "Add these annotations to the pod template in your Deployment:"
echo ""
echo "  annotations:"
echo "    vault.hashicorp.com/agent-inject: \"true\""
echo "    vault.hashicorp.com/role: \"$ROLE_NAME\""
echo "    vault.hashicorp.com/agent-inject-secret-app.env: \"secret/data/$NAMESPACE/$APP\""
echo "    vault.hashicorp.com/agent-inject-template-app.env: |"
echo "      {{- with secret \"secret/data/$NAMESPACE/$APP\" -}}"
echo "      {{ range \$k, \$v := .Data.data -}}"
echo "      export {{ \$k }}={{ \$v }}"
echo "      {{ end }}"
echo "      {{- end }}"
echo ""
echo "  And add to pod spec:"
echo "    serviceAccountName: $SERVICE_ACCOUNT"
echo "    command: [\"/bin/sh\", \"-c\", \"source /vault/secrets/app.env && exec <your-start-command>\"]"
echo "================================================"
