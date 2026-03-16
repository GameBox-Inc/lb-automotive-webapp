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
3. If DB errors: ensure `DATABASE_URL` in `app-secrets` points to a valid DB (PostgreSQL/Supabase URL).

---

## 2. Backend rollout stuck (0 of 1 updated replicas are available)

**Symptoms:** Jenkins waits on `rollout status deployment/backend`; log repeats "0 of 1 updated replicas are available", "1 old replicas are pending termination".

**Cause:** The **new** backend pod never becomes Ready because the readiness probe fails. The deployment uses a readiness probe; if it fails, the new pod is not considered Ready, so the old pod is not terminated and the rollout never completes.

**Why the probe fails:** The manifest previously used `/health` for readiness. `/health` returns **503** when the database or Redis check fails. So if `DATABASE_URL` is missing/invalid, or DB/Redis is slow or down, the new pod never passes readiness.

**Diagnostic (on server):**
```bash
ssh lb-admin@178.156.223.196

# Which pod is the new one (e.g. backend-xxxxx-yyyy)
sudo k3s kubectl get pods -n lb-automotive -l app=backend -o wide

# Why the new pod isn't Ready
sudo k3s kubectl describe pod -n lb-automotive -l app=backend | grep -A 20 "Conditions:"

# Backend logs (crash or DB error at startup?)
BPOD=$(sudo k3s kubectl get pods -n lb-automotive -l app=backend --sort-by=.metadata.creationTimestamp -o jsonpath='{.items[-1].metadata.name}')
sudo k3s kubectl logs -n lb-automotive $BPOD -c backend --tail=100
```

**Fix 1 (recommended):** Use `/ready` for readiness so rollout can complete even when DB/Redis is temporarily unavailable. The repo’s `deployment/k8s/backend.yaml` is updated to use `path: /ready` for both `startupProbe` and `readinessProbe`. Redeploy (push the change and re-run Jenkins, or apply the manifest on the server).

**Fix 2 (root cause):** Ensure `app-secrets` has a valid `DATABASE_URL` (PostgreSQL/Supabase) so `/health` would pass. Run `deployment/k8s/create-secrets.sh` or re-run Jenkins "Ensure App Secrets" with the correct credentials.

**Unblock immediately (one-time):** If you need to unblock without redeploying the manifest, on the server you can patch the deployment to use `/ready`:
```bash
sudo k3s kubectl patch deployment backend -n lb-automotive --type='json' -p='[
  {"op":"replace","path":"/spec/template/spec/containers/0/readinessProbe/httpGet/path","value":"/ready"},
  {"op":"replace","path":"/spec/template/spec/containers/0/startupProbe/httpGet/path","value":"/ready"}
]'
```
Then the next rollout (or the current one if the new pod is still starting) may complete.

---

## 3. DiskPressure and pod evictions

**Symptoms:** Many pods in `Evicted` or `Pending`; `kubectl describe node` shows `DiskPressure: True`, taint `node.kubernetes.io/disk-pressure:NoSchedule`. Rollouts never settle; deleting pods doesn’t help because the control plane keeps creating new ones.

**Cause:** The node’s disk has dropped below the kubelet eviction threshold (e.g. &lt;5% free or &lt;1GB depending on install). The kubelet sets DiskPressure and evicts pods to free space. The Deployment controller immediately creates replacement pods; those get evicted again (or can’t schedule due to the taint), so you get a loop. Root cause is **disk fill** from:

- **Containerd/K3s image store** — Each deploy pulls new backend/frontend images; old layers accumulate until pruned.
- **Docker** (if Jenkins runs on the same server) — Build cache and image layers.
- **Logs** — Journal, container logs, Jenkins logs if not rotated.
- **Evicted pod debris** — Minor; the main gain is from pruning images and logs.

**Diagnostic (on server):**
```bash
# Node conditions and taints
sudo k3s kubectl describe node rocket-1 | grep -A5 "Conditions:\|Taints:"

# Disk usage
df -h /

# Where space is used (containerd is under K3s agent)
sudo du -sh /var/lib/rancher/k3s/agent/containerd 2>/dev/null
sudo du -sh /var/lib/docker 2>/dev/null
```

**Prevention (before next deploy):**
1. **Pre-deploy cleanup** — The Jenkins pipeline runs a “Ensure disk headroom” stage that prunes unused containerd and Docker images on the server *before* applying manifests and pulling new images. That keeps headroom so the deploy doesn’t tip the node over the eviction threshold.
2. **Daily cleanup** — On the server, ensure a daily cron runs (e.g. `deployment/scripts/setup_log_rotation.sh` creates `/etc/cron.daily/disk-cleanup`). Run manually if needed: `sudo /etc/cron.daily/disk-cleanup`.
3. **When already in trouble** — Scale app deployments to 0 to stop the create/evict loop, free disk (prune containerd/Docker, clean logs), then confirm `DiskPressure: False` before scaling back to 1.

**Immediate recovery (on server):**
```bash
# Stop the create/evict loop
sudo k3s kubectl scale deploy redis -n lb-automotive --replicas=0
sudo k3s kubectl scale deploy backend -n lb-automotive --replicas=0
sudo k3s kubectl scale deploy frontend -n lb-automotive --replicas=0

# Free space: prune images (K3s uses containerd, not Docker on the node)
sudo k3s crictl rmi --prune
sudo docker system prune -a -f --filter "until=168h" 2>/dev/null || true

# Remove evicted/failed pods (optional, frees little space)
sudo k3s kubectl delete pods -n lb-automotive --field-selector=status.phase=Failed --ignore-not-found

# Re-check node; wait until DiskPressure is False
sudo k3s kubectl describe node rocket-1 | grep -A2 "DiskPressure"

# Then scale back up
sudo k3s kubectl scale deploy redis -n lb-automotive --replicas=1
sudo k3s kubectl scale deploy backend -n lb-automotive --replicas=1
sudo k3s kubectl scale deploy frontend -n lb-automotive --replicas=1
```

See also: `deployment/STORAGE_OPTIMIZATION.md`, `QUICK_FIX_2GB_SERVER.md`, `deployment/scripts/setup_log_rotation.sh`.

---

## 4. Backend CrashLoopBackOff — SQLite / PostgreSQL

**Symptoms:** `sqlite3.OperationalError` or `ValueError: Valid PostgreSQL/Supabase connection string required`.

**Cause:** Deployed image is old (SQLite) or `DATABASE_URL` missing/invalid.

**Fix:**
- Run Jenkins pipeline to deploy PostgreSQL backend image
- Ensure Supabase secret in Vault: `deployment/scripts/configure-vault-supabase.sh`

---

## 5. Vault 403 — Permission Denied

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

## 6. Twilio Webhook 403 / 503

**Symptoms:** `https://twilio.kozytherocket.space/lb-automotive/api/twilio/webhook` returns 403 or 503.

**403 "Invalid Twilio Signature"** — URL used for HMAC validation doesn’t match what Twilio sent (e.g. proxy stripping `/lb-automotive` or wrong scheme).

**403 "Validation Error"** — An exception occurred during validation (e.g. bad request body, validator error). Check backend logs for the real exception: `kubectl logs deployment/backend -n lb-automotive --tail=100` and look for `Error validating Twilio request: <type>: <message>`.

**503 "Twilio webhook not configured"** — `TWILIO_AUTH_TOKEN` is not set. Backend uses optional `twilio-secrets`; if that secret is missing or has no `TWILIO_AUTH_TOKEN`, validation fails.

**Fix:**
- **503:** Create `twilio-secrets` with `TWILIO_AUTH_TOKEN` (and optionally `TWILIO_ACCOUNT_SID`, `TWILIO_PHONE_NUMBER`): run `deployment/k8s/create-secrets.sh` on the server or create the secret manually, then restart the backend.
- **403 Invalid Signature:** The backend must validate the request URL exactly as Twilio signed it (`https://twilio.kozytherocket.space/lb-automotive/api/twilio/webhook?...`). The HTTPRoute in `deployment/k8s/gamebox-security/traefik/lb-automotive-routes.yaml` must send **X-Forwarded-Proto: https** and **X-Forwarded-Prefix: /lb-automotive** (via `RequestHeaderModifier`) so the backend can reconstruct that URL. If you changed the route and removed those headers, add them back. Twilio Console webhook URL must be `https://twilio.kozytherocket.space/lb-automotive/api/twilio/webhook`.
- **403 Validation Error:** Inspect backend logs for the exception type and message; fix the underlying cause (e.g. request body format, missing headers).
- **Invalid Twilio Signature after deploy:** Ensure the new backend image is running: `kubectl get pods -n lb-automotive -l app=backend -o jsonpath='{.items[0].status.containerStatuses[0].image}'` and restart if the image tag is old: `kubectl rollout restart deployment/backend -n lb-automotive`. Ensure `TWILIO_WEBHOOK_BASE_URL` in twilio-secrets (or backend env) matches the Twilio Console webhook URL exactly (e.g. `https://twilio.kozytherocket.space/lb-automotive/api/twilio/webhook`). Check logs for `Validating URL=` to see the URL used for signature validation.

---

## 7. Traefik / Gateway configuration

**Relevant when:** Twilio webhook returns 403 Invalid Signature, or public requests to `twilio.kozytherocket.space` get 404/502.

**Flow:** Cloudflare Tunnel → cloudflared (connects to `traefik.gamebox-security.svc.cluster.local:80`) → Traefik Gateway (HTTPRoutes) → backend.

**Key files:**
- `deployment/k8s/gamebox-security/traefik/lb-automotive-routes.yaml` — HTTPRoutes for `twilio.kozytherocket.space`
- `deployment/k8s/gamebox-security/traefik/gateway.yaml` — GatewayClass + Gateway (listener port 8000; Service may expose 80)
- `deployment/k8s/gamebox-security/cloudflared.yaml` — tunnel ingress to Traefik on port **80**

**Checks:**
1. **Twilio 403:** The route for `/lb-automotive/api/twilio` must include a `RequestHeaderModifier` that adds `X-Forwarded-Proto: https` and `X-Forwarded-Prefix: /lb-automotive` so the backend can reconstruct the signed URL. See `lb-automotive-routes.yaml` rule 2.
2. **Port mismatch:** cloudflared uses `http://traefik...:80`. The Traefik Service must expose port 80 (or the port the Gateway listener uses). Helm values use `ports.web.port: 8000`; the chart usually maps Service port 80 → 8000.
3. **Route not attached:** `kubectl get httproute -n gamebox-security` and `kubectl describe httproute lb-automotive-twilio -n gamebox-security` to confirm the route is attached to the Gateway and has no status errors.
4. **Backend unreachable:** From a pod in the cluster, `curl -v http://backend.lb-automotive.svc.cluster.local:8000/health` (or similar) to confirm the backend responds.

**Apply route changes:** After editing `lb-automotive-routes.yaml`, run `kubectl apply -f deployment/k8s/gamebox-security/traefik/lb-automotive-routes.yaml` (or re-run Jenkins so manifests are synced and applied). No need to restart Traefik for HTTPRoute updates.

---

## 8. Jenkins Pipeline — pytest / DATABASE_URL

**Symptoms:** Docker build fails with `ValueError: Valid PostgreSQL/Supabase connection string required`.

**Cause:** `database.py` raises at import when `DATABASE_URL` is unset. Pytest runs during Docker build.

**Fix:** Dockerfile sets `DATABASE_URL=postgresql://localhost:5432/test` for pytest; tests may fail (no DB) but build continues with `|| true` or equivalent.

---

## 8. Vault Uninitialized / CrashLoopBackOff

**Symptoms:** `vault-0` in CrashLoopBackOff; logs: "stored unseal keys supported, but none were found".

**Cause:** Main Vault not initialized. Transit seal configured but no recovery keys.

**Fix:**
```bash
sudo k3s kubectl exec -n gamebox-security vault-0 -c vault -- \
  env VAULT_SKIP_VERIFY=true vault operator init -recovery-shares=1 -recovery-threshold=1
```
Store recovery key and root token.

---

## 10. Main Vault CrashLoopBackOff — Transit Token 403

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

## 10. Main Vault — Transit Decrypt 400 (cipher: message authentication failed)

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

## 11. OOM / 2GB Server

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
