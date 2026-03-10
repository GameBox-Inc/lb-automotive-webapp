# Common Failures

**Last Updated:** March 2026

---

## 1. 502 Bad Gateway (Frontend → API)

**Symptoms:** Browser console shows `GET /api/auth/me 502`, `GET /api/auth/captcha 502`.

**Cause:** Backend not reachable. Usually:
- Backend pods in `Init:0/1` or `CrashLoopBackOff`
- Vault Agent init failing (403 on secrets)
- Backend container crashing on startup

**Fix:**
1. `kubectl get pods -n lb-automotive` — check backend status
2. `kubectl logs -n lb-automotive <backend-pod> -c vault-agent-init` — Vault 403
3. `kubectl logs -n lb-automotive <backend-pod> -c backend --previous` — crash reason
4. If Vault: fix policy (e.g. `gamebox/data/clients/lb-autorepair/database`), restart backend
5. If DB: ensure `DATABASE_URL` in Vault at `gamebox/data/clients/lb-autorepair/database`

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

## 7. OOM / 2GB Server

**Symptoms:** Pods evicted, OOMKilled.

**Fix:** See `QUICK_FIX_2GB_SERVER.md` — remove memory hogs, add swap, apply resource limits.

---

## Related

- [K8s Debugging Runbook](../runbooks/k8s-debugging.md)
- [Twilio Debugging Runbook](../runbooks/twilio-debugging.md)
- [CLAUDE.md](../../CLAUDE.md)
