#!/usr/bin/env bash
# =============================================================================
# seed-vault-secrets.sh — Canonical re-seed of Main Vault after re-init
#
# Run this after Main Vault has been re-initialized (e.g. after cipher recovery).
# Requires: VAULT_ADDR, VAULT_TOKEN (root or admin), and env vars for secrets.
#
# Usage:
#   export VAULT_ADDR="https://vault.gamebox-security.svc.cluster.local:8200"
#   export VAULT_TOKEN="hvs.xxx"
#   export VAULT_SKIP_VERIFY=true   # if using self-signed
#   export SECRET_KEY="..."
#   export ALLOWED_ORIGINS="https://app.example.com"
#   export DATABASE_URL="sqlite:///./lb_automotive.db"
#   export REDIS_URL="redis://redis:6379/0"
#   export TWILIO_ACCOUNT_SID="..." TWILIO_AUTH_TOKEN="..." TWILIO_PHONE_NUMBER="..."
#   export ANTHROPIC_API_KEY="..." ANTHROPIC_MODEL="claude-3-5-sonnet-20241022"
#   bash deployment/scripts/seed-vault-secrets.sh
#
# Or from cluster (port-forward first):
#   kubectl port-forward -n gamebox-security svc/vault 8200:8200
#   export VAULT_ADDR=http://127.0.0.1:8200 VAULT_TOKEN=$(cat /path/to/root-token)
#   bash deployment/scripts/seed-vault-secrets.sh
#
# See: docs/architecture/vault-stability-and-improvements.md
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
POLICY_HCL="${REPO_ROOT}/deployment/k8s/gamebox-security/vault/lb-automotive-policy.hcl"

check_var() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    echo "ERROR: $name is not set. Export it or pass via env." >&2
    return 1
  fi
}

# Required for Vault
check_var VAULT_ADDR || exit 1
check_var VAULT_TOKEN || exit 1

# Required for app secrets
check_var SECRET_KEY || exit 1
check_var ALLOWED_ORIGINS || exit 1
check_var DATABASE_URL || exit 1

# Optional with defaults
REDIS_URL="${REDIS_URL:-redis://redis.lb-automotive.svc.cluster.local:6379/0}"
LLM_PROVIDER="${LLM_PROVIDER:-anthropic}"
CSP_POLICY="${CSP_POLICY:-strict}"

# Twilio (required for IVR)
TWILIO_ACCOUNT_SID="${TWILIO_ACCOUNT_SID:-}"
TWILIO_AUTH_TOKEN="${TWILIO_AUTH_TOKEN:-}"
TWILIO_PHONE_NUMBER="${TWILIO_PHONE_NUMBER:-}"

# Anthropic (required if LLM_PROVIDER=anthropic)
ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}"
ANTHROPIC_MODEL="${ANTHROPIC_MODEL:-claude-3-5-sonnet-20241022}"

echo "▶ Enabling KV v2 secrets engines..."
vault secrets enable -path=secret kv-v2 2>/dev/null || vault secrets enable -path=secret kv 2>/dev/null || true
vault secrets enable -path=gamebox kv-v2 2>/dev/null || vault secrets enable -path=gamebox kv 2>/dev/null || true

echo "▶ Writing secret/lb-automotive/app..."
vault kv put secret/lb-automotive/app \
  SECRET_KEY="$SECRET_KEY" \
  ALLOWED_ORIGINS="$ALLOWED_ORIGINS" \
  DATABASE_URL="$DATABASE_URL" \
  REDIS_URL="$REDIS_URL" \
  LLM_PROVIDER="$LLM_PROVIDER" \
  CSP_POLICY="$CSP_POLICY"

echo "▶ Writing secret/lb-automotive/twilio..."
vault kv put secret/lb-automotive/twilio \
  TWILIO_ACCOUNT_SID="${TWILIO_ACCOUNT_SID}" \
  TWILIO_AUTH_TOKEN="${TWILIO_AUTH_TOKEN}" \
  TWILIO_PHONE_NUMBER="${TWILIO_PHONE_NUMBER}"

echo "▶ Writing secret/lb-automotive/anthropic..."
vault kv put secret/lb-automotive/anthropic \
  ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY}" \
  ANTHROPIC_MODEL="${ANTHROPIC_MODEL}"

echo "▶ Writing gamebox/clients/lb-autorepair/database (backend DATABASE_URL)..."
vault kv put gamebox/clients/lb-autorepair/database url="$DATABASE_URL"

echo "▶ Writing policy lb-automotive-policy..."
if [[ -f "$POLICY_HCL" ]]; then
  vault policy write lb-automotive-policy - < "$POLICY_HCL"
else
  echo "WARN: $POLICY_HCL not found; using inline policy."
  vault policy write lb-automotive-policy - <<'EOF'
path "secret/data/lb-automotive/*" { capabilities = ["read", "list"] }
path "gamebox/data/clients/lb-autorepair/database" { capabilities = ["read", "list"] }
path "gamebox/metadata/clients/lb-autorepair/database" { capabilities = ["read", "list"] }
path "auth/token/renew-self" { capabilities = ["update"] }
path "auth/token/lookup-self" { capabilities = ["read"] }
EOF
fi

echo "▶ Configuring Kubernetes auth role lb-automotive-role..."
vault write auth/kubernetes/role/lb-automotive-role \
  bound_service_account_names=lb-automotive-backend \
  bound_service_account_namespaces=lb-automotive \
  policies=lb-automotive-policy \
  ttl=1h \
  max_ttl=24h

echo "▶ Labeling namespace lb-automotive for Vault injector..."
kubectl label namespace lb-automotive vault-injection=enabled --overwrite 2>/dev/null || echo "  (kubectl not available or namespace missing — label manually)"

echo ""
echo "✅ Vault secrets and policy re-seeded. Restart backend:"
echo "   kubectl rollout restart deploy/backend -n lb-automotive"
echo ""
