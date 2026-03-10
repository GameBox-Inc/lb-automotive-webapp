#!/usr/bin/env bash
set -euo pipefail

# Rekey Unseal Vault Shamir shares (interactive).
# This rotates the unseal key shares without reinitializing storage.
#
# IMPORTANT: This cluster's Unseal Vault is HTTP (tls_disable=1).
# Do NOT use https://127.0.0.1:8200 here.

NS="vault-unseal"
POD="unseal-vault-0"
CONTAINER="vault"
VAULT_ADDR="http://127.0.0.1:8200"

echo "== Unseal Vault Shamir Rekey =="
echo "Namespace : $NS"
echo "Pod       : $POD"
echo "VAULT_ADDR: $VAULT_ADDR"
echo ""

exec_vault() {
  sudo k3s kubectl exec -n "$NS" "$POD" -c "$CONTAINER" -- env VAULT_ADDR="$VAULT_ADDR" vault "$@"
}

if ! sudo k3s kubectl get pod -n "$NS" "$POD" >/dev/null 2>&1; then
  echo "ERROR: $NS/$POD not found"
  exit 1
fi

STATUS="$(exec_vault status 2>/dev/null || true)"
echo "$STATUS" | egrep 'Seal Type|Initialized|Sealed|Total Shares|Threshold' || true
echo ""

if echo "$STATUS" | grep -q 'Sealed[[:space:]]*true'; then
  echo "ERROR: Unseal Vault is sealed. Unseal it first, then re-run rekey."
  exit 1
fi

read -r -p "Proceed with rekey (rotate unseal shares)? Type 'rekey' to continue: " CONFIRM
if [[ "$CONFIRM" != "rekey" ]]; then
  echo "Aborted."
  exit 0
fi

read -r -p "New total shares (default 5): " NEW_SHARES
NEW_SHARES="${NEW_SHARES:-5}"

read -r -p "New threshold (default 3): " NEW_THRESHOLD
NEW_THRESHOLD="${NEW_THRESHOLD:-3}"

echo ""
echo "Starting rekey (shares=$NEW_SHARES threshold=$NEW_THRESHOLD)..."
echo ""

# We run inside the pod but need a VAULT_TOKEN.
# Ask the operator to paste the Unseal Vault root token into this shell.
read -r -s -p "Paste Unseal Vault root token (input hidden): " VAULT_TOKEN
echo ""
export VAULT_TOKEN

REKEY_INIT_JSON="$(sudo k3s kubectl exec -n "$NS" "$POD" -c "$CONTAINER" -- env VAULT_ADDR="$VAULT_ADDR" VAULT_TOKEN="$VAULT_TOKEN" vault operator rekey -init -format=json -key-shares="$NEW_SHARES" -key-threshold="$NEW_THRESHOLD")"
NONCE="$(python3 - <<'PY'
import json,sys
print(json.loads(sys.stdin.read())["nonce"])
PY
<<<"$REKEY_INIT_JSON")"

echo "Nonce: $NONCE"
echo ""

echo "Enter existing key shares to authorize rekey."
echo "You must provide the CURRENT threshold number of shares."
echo "Each share will be submitted immediately."
echo ""

for i in $(seq 1 10); do
  # Stop once rekey completes (vault returns complete=true).
  read -r -s -p "Current key share #$i (hidden, press Enter when pasted): " SHARE
  echo ""
  OUT="$(sudo k3s kubectl exec -n "$NS" "$POD" -c "$CONTAINER" -- env VAULT_ADDR="$VAULT_ADDR" VAULT_TOKEN="$VAULT_TOKEN" vault operator rekey -nonce="$NONCE" -format=json "$SHARE")" || true

  COMPLETE="$(python3 - <<'PY'
import json,sys
try:
  print(str(json.loads(sys.stdin.read()).get("complete","false")).lower())
except Exception:
  print("false")
PY
<<<"$OUT")"

  if [[ "$COMPLETE" == "true" ]]; then
    echo ""
    echo "✅ Rekey complete. NEW key shares below — store offline immediately:"
    echo ""
    python3 - <<'PY'
import json,sys
d=json.loads(sys.stdin.read())
keys=d.get("keys") or []
for idx,k in enumerate(keys, start=1):
  print(f"{idx}. {k}")
PY
<<<"$OUT"
    echo ""
    echo "IMPORTANT: Update Jenkins credentials (vault-unseal-key-1/2/3) to the new shares if Jenkins auto-unseals."
    exit 0
  fi

  echo "Share accepted. Rekey not complete yet."
done

echo "ERROR: Rekey did not complete after 10 shares; investigate output above."
exit 1

