#!/bin/bash
# =============================================================================
# configure-vault-supabase.sh — Store Supabase/PostgreSQL URL in Vault
#
# Run after Vault is initialized and unsealed. Creates the database secret
# at gamebox/clients/lb-autorepair/database required by the backend.
#
# Usage:
#   export VAULT_TOKEN=<root-or-admin-token>
#   export DATABASE_URL="postgresql://user:pass@host:5432/dbname"
#   # Optional: read replica for read-only queries
#   export DATABASE_READ_URL="postgresql://user:pass@replica:5432/dbname"
#
#   ./configure-vault-supabase.sh
#
# Or run via kubectl exec (from a machine with cluster access):
#   VAULT_TOKEN=$(cat /path/to/token) DATABASE_URL="postgresql://..." \
#     bash -c 'kubectl exec -n gamebox-security vault-0 -c vault -i -- \
#       env VAULT_ADDR=https://127.0.0.1:8200 VAULT_SKIP_VERIFY=true VAULT_TOKEN=$VAULT_TOKEN \
#       sh -c "vault kv put gamebox/clients/lb-autorepair/database url=\"$DATABASE_URL\" \
#         \${DATABASE_READ_URL:+read_url=\"$DATABASE_READ_URL\"}"'
# =============================================================================
set -euo pipefail

NAMESPACE="${VAULT_NAMESPACE:-gamebox-security}"
VAULT_POD="${VAULT_POD:-vault-0}"
# Use "sudo k3s kubectl" when running on the K3s server
KUBECTL="${KUBECTL:-kubectl}"

if [[ -z "${VAULT_TOKEN:-}" ]]; then
  echo "ERROR: VAULT_TOKEN is required."
  echo "  export VAULT_TOKEN=<your-root-or-admin-token>"
  exit 1
fi

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "ERROR: DATABASE_URL is required (PostgreSQL/Supabase connection string)."
  echo "  export DATABASE_URL=\"postgresql://user:pass@host:5432/dbname\""
  exit 1
fi

if [[ "$DATABASE_URL" != postgres* ]]; then
  echo "ERROR: DATABASE_URL must be a PostgreSQL URL (postgresql://...)."
  exit 1
fi

echo "▶ Writing Supabase/PostgreSQL secret to gamebox/clients/lb-autorepair/database..."

if [[ -n "${DATABASE_READ_URL:-}" ]]; then
  $KUBECTL exec -n "$NAMESPACE" "$VAULT_POD" -c vault -- \
    env VAULT_ADDR=https://127.0.0.1:8200 VAULT_SKIP_VERIFY=true VAULT_TOKEN="$VAULT_TOKEN" \
    vault kv put "gamebox/clients/lb-autorepair/database" \
      url="$DATABASE_URL" \
      read_url="$DATABASE_READ_URL"
else
  $KUBECTL exec -n "$NAMESPACE" "$VAULT_POD" -c vault -- \
    env VAULT_ADDR=https://127.0.0.1:8200 VAULT_SKIP_VERIFY=true VAULT_TOKEN="$VAULT_TOKEN" \
    vault kv put "gamebox/clients/lb-autorepair/database" \
      url="$DATABASE_URL"
fi

echo "✅ Secret written. Restart backend to pick up: kubectl rollout restart deploy/backend -n lb-automotive"
