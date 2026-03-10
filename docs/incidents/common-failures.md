# Common Failures

**Last Updated:** March 2026

---

## 1. 502 Bad Gateway (Frontend → API)

**Symptoms:** Browser console shows `GET /api/auth/me 502`, `GET /api/auth/captcha 502`, `POST /api/auth/login 502`. You may also see `Manifest: Line: 1, column: 1, Syntax error` — that is the browser parsing a 502 HTML response as JSON for the PWA manifest; fixing the 502 resolves it.

**Cause:** Backend not reachable. Frontend Nginx proxies `/api/*` to backend; if backend is down → 502.

**Typical chain:**
1. **Unseal Vault** sealed → Main Vault cannot auto-unseal
2. **Main Vault** (vault-0) sealed/crashlooping → Vault Agent cannot inject secrets
3. **Backend** stuck in `Init:0/1` (waiting for secrets) or `CrashLoopBackOff`

**Diagnostic (run on server or via script):**

```bash
# One-liner from repo root (SSH to server)
./scripts/k8s-debug-summary.sh lb-admin@178.156.223.196
```

Or manually:

```bash
ssh lb-admin@178.156.223.196

# 1. Pod status
sudo k3s kubectl get pods -n lb-automotive -o wide
sudo k3s kubectl get pods -n gamebox-security -o wide
sudo k3s kubectl get pods -n vault-unseal -o wide

# 2. Unseal Vault (must be unsealed first)
sudo k3s kubectl exec -n vault-unseal unseal-vault-0 -c vault -- \
  env VAULT_ADDR=http://127.0.0.1:8200 vault status

# 3. Main Vault (auto-unseals when Unseal Vault is reachable)
sudo k3s kubectl exec -n gamebox-security vault-0 -c vault -- vault status

# 4. Backend init logs (if Init:0/1)
BPOD=$(sudo k3s kubectl get pods -n lb-automotive -l app=backend -o jsonpath='{.items[0].metadata.name}')
sudo k3s kubectl logs -n lb-automotive $BPOD -c vault-agent-init --tail=50

# 5. Backend crash logs (if CrashLoopBackOff)
sudo k3s kubectl logs -n lb-automotive $BPOD -c backend --previous --tail=50
```

**Fix order:**
1. **Unseal Unseal Vault** — if sealed, unseal with Shamir keys (Jenkins credentials `vault-unseal-key-1/2/3`). See [Vault Unseal Order](../runbooks/vault-unseal-order.md).
2. **Main Vault** — should auto-unseal once Unseal Vault is reachable. If vault-0 is CrashLoopBackOff with "invalid token" / 403 on transit: see [§7 Transit Token 403](#7-main-vault-crashloopbackoff--transit-token-403).
3. **Restart backend** — after Vault is unsealed: `sudo k3s kubectl rollout restart deploy/backend -n lb-automotive`
4. If Vault 403: fix policy (e.g. `secret/data/lb-automotive/*`), restart backend.
5. If DB: ensure `DATABASE_URL` in Vault at `secret/lb-automotive/app`.

---

## 2. Backend CrashLoopBackOff — SQLite / PostgreSQL

**Symptoms:** `sqlite3.OperationalError` or `ValueError: Valid PostgreSQL/Supabase connection string required`.

**Cause:** Deployed image is old (SQLite) or `DATABASE_URL` missing/invalid.

**Fix:**
- Run Jenkins pipeline to deploy PostgreSQL backend image
- Ensure Supabase secret in Vault: `deployment/scripts/configure-vault-supabase.sh`

---

## 3. Vault 403 — Permission Denied

**Symptoms:** `vault.read(gamebox/data/clients/lb-autorepair/database): permission denied`

**Cause:** Policy path mismatch. `+` matches one segment. Nested path needs explicit rule.

**Fix:** Policy must include:
```hcl
path "gamebox/data/clients/lb-autorepair/database" {
  capabilities = ["read", "list"]
}
path "gamebox/metadata/clients/lb-autorepair/database" {
  capabilities = ["read", "list"]
}
```

Apply: `vault policy write lb-automotive-policy - < lb-automotive-policy.hcl`

---

## 4. Twilio Webhook 403 — Invalid Signature

**Symptoms:** Twilio calls fail; backend returns 403.

**Cause:** URL used for HMAC validation doesn’t match what Twilio sent. Often due to proxy stripping `/lb-automotive` or incorrect scheme.

**Fix:**
- Ensure `x-forwarded-proto`, `x-original-uri` (or `x-forwarded-prefix`) are passed
- Backend fallback: if `twilio.kozytherocket.space` in URL and `/lb-automotive` missing, inject it
- Twilio Console: webhook URL must be `https://twilio.kozytherocket.space/lb-automotive/api/twilio/webhook`

---

## 5. Jenkins Pipeline — pytest / DATABASE_URL

**Symptoms:** Docker build fails with `ValueError: Valid PostgreSQL/Supabase connection string required`.

**Cause:** `database.py` raises at import when `DATABASE_URL` is unset. Pytest runs during Docker build.

**Fix:** Dockerfile sets `DATABASE_URL=postgresql://localhost:5432/test` for pytest; tests may fail (no DB) but build continues with `|| true` or equivalent.

---

## 6. Vault Uninitialized / CrashLoopBackOff

**Symptoms:** `vault-0` in CrashLoopBackOff; logs: "stored unseal keys supported, but none were found".

**Cause:** Main Vault not initialized. Transit seal configured but no recovery keys.

**Fix:**
```bash
sudo k3s kubectl exec -n gamebox-security vault-0 -c vault -- \
  env VAULT_SKIP_VERIFY=true vault operator init -recovery-shares=1 -recovery-threshold=1
```
Store recovery key and root token.

---

## 7. Main Vault CrashLoopBackOff — Transit Token 403

**Symptoms:** `vault-0` in CrashLoopBackOff; logs:
```
error parsing Seal configuration: Error making API request.
URL: PUT http://unseal-vault.../v1/transit/encrypt/autounseal
Code: 403. Errors: permission denied / invalid token
```

**Cause:** The transit token Main Vault uses to authenticate to Unseal Vault is invalid or lacks permission. Common causes:
- Jenkins credential `vault-transit-token` was never set or has wrong value
- Unseal Vault was re-initialized; old token is invalid
- Token was revoked or expired

**Fix — create new transit token and patch Main Vault:**

**Prerequisite:** Unseal Vault root token (from `unseal_init.json` or `UNSEAL_VAULT_ROOT_TOKEN` env).

1. **Create new token on Unseal Vault** (SSH to server):

```bash
# Set your Unseal Vault root token
ROOT_TOKEN="hvs.xxxx"   # from unseal_init.json or credentials store

# Create token (policy main-vault-autounseal must exist from bootstrap)
NEW_TOKEN=$(sudo k3s kubectl exec -n vault-unseal unseal-vault-0 -c vault -- \
  env VAULT_ADDR=http://127.0.0.1:8200 VAULT_TOKEN="$ROOT_TOKEN" vault token create \
  -policy=main-vault-autounseal \
  -display-name="main-vault-autounseal" \
  -ttl=8760h -period=8760h -orphan=true -renewable=true -format=json 2>/dev/null | \
  jq -r '.auth.client_token')

echo "New token (save this): $NEW_TOKEN"
```

If policy is missing, run `bootstrap_unseal_vault.sh` or create it manually (see that script).

2. **Patch ConfigMap and restart vault-0**:

```bash
# ConfigMap name (HashiCorp Helm chart creates vault-config)
CM="vault-config"

# Step 2b: Get current config (key may be extraconfig-from-values.hcl or server-config.hcl)
CURRENT=$(sudo k3s kubectl get configmap "$CM" -n gamebox-security \
  -o jsonpath='{.data.extraconfig-from-values\.hcl}' 2>/dev/null)
CONFIG_KEY="extraconfig-from-values.hcl"

if [ -z "$CURRENT" ]; then
  CURRENT=$(sudo k3s kubectl get configmap "$CM" -n gamebox-security \
    -o jsonpath='{.data.server-config\.hcl}' 2>/dev/null)
  CONFIG_KEY="server-config.hcl"
fi

if [ -z "$CURRENT" ]; then
  echo "ERROR: ConfigMap $CM has no seal config. Check keys: sudo k3s kubectl get configmap $CM -n gamebox-security -o jsonpath='{.data}' | jq keys"
  exit 1
fi

# Replace token in seal stanza
NEW=$(echo "$CURRENT" | sed "s|token *= *\"[^\"]*\"|token = \"$NEW_TOKEN\"|")

# Patch
sudo k3s kubectl patch configmap "$CM" -n gamebox-security --type merge \
  -p "$(echo "{\"data\":{\"$CONFIG_KEY\":$(echo "$NEW" | jq -Rs .)}}")"

# Restart vault-0
sudo k3s kubectl delete pod vault-0 -n gamebox-security
sudo k3s kubectl wait pod vault-0 -n gamebox-security --for=condition=Ready --timeout=120s
```

3. **Update Jenkins credential** `vault-transit-token` with the new token so future pipelines don't overwrite it.

4. **Restart backend** after Main Vault is Ready:
```bash
sudo k3s kubectl rollout restart deploy/backend -n lb-automotive
```

**Full how-to:** [Vault Transit Token Management](../howto/vault-transit-token-management.md) — credential management, Jenkins steps, and prevention.

---

## 8. OOM / 2GB Server

**Symptoms:** Pods evicted, OOMKilled.

**Fix:** See `QUICK_FIX_2GB_SERVER.md` — remove memory hogs, add swap, apply resource limits.

---

## Related

- [Vault Transit Token Management](../howto/vault-transit-token-management.md) — full how-to for credential management
- [K8s Debugging Runbook](../runbooks/k8s-debugging.md)
- [Twilio Debugging Runbook](../runbooks/twilio-debugging.md)
- [CLAUDE.md](../../CLAUDE.md)
