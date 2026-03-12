# Common Failures

**Last Updated:** March 2026

---

## 1. 502 Bad Gateway (Frontend → API)

**Symptoms:** Browser console shows `GET /api/auth/me 502`, `GET /api/auth/captcha 502`, `POST /api/auth/login 502`. You may also see `Manifest: Line: 1, column: 1, Syntax error` — that is the browser parsing a 502 HTML response as JSON for the PWA manifest; fixing the 502 resolves it.

**Cause:** Backend not reachable. Frontend Nginx proxies `/api/*` to backend; if backend is down → 502.

**Backend uses K8s Secrets (no Vault).** Typical causes:
1. **Missing app-secrets** — backend needs `app-secrets` (SECRET_KEY, ALLOWED_ORIGINS, DATABASE_URL, etc.). Create via `deployment/k8s/create-secrets.sh` or run Jenkins pipeline (stage "Ensure App Secrets" uses credentials `secret-key`, `allowed-origins`).
2. **Backend pod not Running** — image pull, OOM, or bad env.

**Diagnostic:**

```bash
# From repo root (SSH to server)
./scripts/k8s-debug-summary.sh lb-admin@178.156.223.196
```

Or manually:

```bash
ssh lb-admin@178.156.223.196

# Pod status
sudo k3s kubectl get pods -n lb-automotive -o wide

# Backend logs (if CrashLoopBackOff or not Ready)
BPOD=$(sudo k3s kubectl get pods -n lb-automotive -l app=backend -o jsonpath='{.items[0].metadata.name}')
sudo k3s kubectl logs -n lb-automotive $BPOD -c backend --tail=50
sudo k3s kubectl logs -n lb-automotive $BPOD -c backend --previous --tail=50  # if restarted

# Check app-secrets exist
sudo k3s kubectl get secret app-secrets -n lb-automotive
```

**Fix order:**
1. **Ensure app-secrets exist** — run `deployment/k8s/create-secrets.sh` on the server, or add Jenkins credentials `secret-key` and `allowed-origins` and re-run the pipeline.
2. **Restart backend** — `sudo k3s kubectl rollout restart deploy/backend -n lb-automotive`
3. If DB errors: ensure `DATABASE_URL` in `app-secrets` points to a valid DB (e.g. `sqlite:////app/data/lb_automotive.db`).

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

## 4. Twilio Webhook 403 / 503

**Symptoms:** `https://twilio.kozytherocket.space/lb-automotive/api/twilio/webhook` returns 403 or 503.

**403 "Invalid Twilio Signature"** — URL used for HMAC validation doesn’t match what Twilio sent (e.g. proxy stripping `/lb-automotive` or wrong scheme).

**403 "Validation Error"** — An exception occurred during validation (e.g. bad request body, validator error). Check backend logs for the real exception: `kubectl logs deployment/backend -n lb-automotive --tail=100` and look for `Error validating Twilio request: <type>: <message>`.

**503 "Twilio webhook not configured"** — `TWILIO_AUTH_TOKEN` is not set. Backend uses optional `twilio-secrets`; if that secret is missing or has no `TWILIO_AUTH_TOKEN`, validation fails.

**Fix:**
- **503:** Create `twilio-secrets` with `TWILIO_AUTH_TOKEN` (and optionally `TWILIO_ACCOUNT_SID`, `TWILIO_PHONE_NUMBER`): run `deployment/k8s/create-secrets.sh` on the server or create the secret manually, then restart the backend.
- **403 Invalid Signature:** Ensure `x-forwarded-proto`, `x-original-uri` (or `x-forwarded-prefix`) are passed; backend fallback injects `/lb-automotive` when host is `twilio.kozytherocket.space`. Twilio Console webhook URL must be `https://twilio.kozytherocket.space/lb-automotive/api/twilio/webhook`.
- **403 Validation Error:** Inspect backend logs for the exception type and message; fix the underlying cause (e.g. request body format, missing headers).

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

## 8. Main Vault — Transit Decrypt 400 (cipher: message authentication failed)

**Symptoms:** `vault-0` fails to start; logs:
```
fetching stored unseal keys failed: invalid key: failed to decrypt keys from storage
error decrypting using seal transit: Error making API request.
URL: PUT .../v1/transit/decrypt/autounseal
Code: 400. Errors: * cipher: message authentication failed
```

**Cause:** Main Vault’s stored data was encrypted with a **different** transit key than the one that currently exists as `autounseal` on Unseal Vault. Common causes:
- Unseal Vault was **re-initialized** (or PVC wiped) and the `autounseal` key was recreated
- The transit key was **rotated** or recreated
- Main Vault was never re-initialized after Unseal Vault was reset

**You do not need to “add” a key** — the key that encrypted Main Vault’s data is gone or changed. **Removing autounseal** does not fix this; Main Vault must decrypt its storage to unseal, and that decrypt is failing.

**Recovery (destructive to Main Vault data — re-init and re-seed secrets):**

1. **Wipe Main Vault storage** so it can re-initialize with the *current* Unseal Vault transit key:
   ```bash
   # Delete the pod and its PVC so Vault starts with empty storage
   sudo k3s kubectl delete pod vault-0 -n gamebox-security --force --grace-period=0
   sudo k3s kubectl delete pvc -n gamebox-security data-vault-0
   ```
   (If the PVC name differs, check `kubectl get pvc -n gamebox-security`.)

2. **Wait for vault-0 to be recreated** (StatefulSet) and become Ready. It will auto-initialize and auto-unseal using the current transit key and token.

3. **Re-seed all app secrets** in Main Vault (previous secrets are gone). Use the canonical script:
   ```bash
   export VAULT_ADDR="https://vault.gamebox-security.svc.cluster.local:8200"
   export VAULT_TOKEN="<root-or-admin-token>"
   export VAULT_SKIP_VERIFY=true
   export SECRET_KEY="..." ALLOWED_ORIGINS="..." DATABASE_URL="..."
   export TWILIO_ACCOUNT_SID="..." TWILIO_AUTH_TOKEN="..." TWILIO_PHONE_NUMBER="..."
   export ANTHROPIC_API_KEY="..."
   bash deployment/scripts/seed-vault-secrets.sh
   ```
   (Or port-forward and run locally; see script header.)

4. **Restart backend** so Vault Agent can inject the new secrets:
   ```bash
   sudo k3s kubectl rollout restart deploy/backend -n lb-automotive
   ```

5. **Update Jenkins** credential `vault-transit-token` if you generated a new token; the existing one may still be valid.

---

## 9. OOM / 2GB Server

**Symptoms:** Pods evicted, OOMKilled.

**Fix:** See `QUICK_FIX_2GB_SERVER.md` — remove memory hogs, add swap, apply resource limits.

---

**Note:** The transit *token* in the ConfigMap is still valid; the problem is the transit *key* on Unseal Vault changed (e.g. after re-init). No need to patch the token again unless you re-ran bootstrap and created a new token.

---

## Related

- [Vault Transit Token Management](../howto/vault-transit-token-management.md) — full how-to for credential management
- [K8s Debugging Runbook](../runbooks/k8s-debugging.md)
- [Twilio Debugging Runbook](../runbooks/twilio-debugging.md)
- [CLAUDE.md](../../CLAUDE.md)
