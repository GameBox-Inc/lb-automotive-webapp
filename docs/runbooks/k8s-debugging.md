# Kubernetes Debugging Runbook

**Last Updated:** March 2026  
**Cluster:** K3s on Hetzner (178.156.223.196)

---

## Server Access

```bash
ssh lb-admin@178.156.223.196
# Use sudo k3s kubectl (not plain kubectl)
```

---

## Namespaces

| Namespace | Purpose |
|-----------|---------|
| `lb-automotive` | Backend, frontend, Redis |
| `gamebox-security` | Vault, Traefik, Cloudflared |
| `vault-unseal` | Unseal Vault (transit seal) |
| `kube-system` | CoreDNS, metrics-server |

---

## Common Commands

### Pod status

```bash
sudo k3s kubectl get pods -A
sudo k3s kubectl get pods -n lb-automotive -o wide
```

### Logs

```bash
# Backend
sudo k3s kubectl logs -n lb-automotive -l app=backend -c backend --tail=100

# Frontend
sudo k3s kubectl logs -n lb-automotive -l app=frontend -c frontend --tail=100

# Vault
sudo k3s kubectl logs -n gamebox-security vault-0 -c vault --tail=100

# Previous (crashed) container
sudo k3s kubectl logs -n lb-automotive <pod> --previous --tail=100
```

### Describe / events

```bash
sudo k3s kubectl describe pod -n lb-automotive <pod-name>
sudo k3s kubectl get events -n lb-automotive --sort-by='.lastTimestamp'
```

### Restart deployments

```bash
sudo k3s kubectl rollout restart deploy/backend -n lb-automotive
sudo k3s kubectl rollout restart deploy/frontend -n lb-automotive
```

---

## Rollout timeout (backend / frontend)

When Jenkins reports **"Backend rollout timed out"** or **"Frontend rollout timed out"**, the new pod is not becoming Ready within the timeout (default 5m). Run these on the server:

```bash
# 1. Pod status and why they're not Ready
sudo k3s kubectl get pods -n lb-automotive -o wide
sudo k3s kubectl describe pod -n lb-automotive -l app=backend
sudo k3s kubectl describe pod -n lb-automotive -l app=frontend

# 2. Backend logs (startup / probe failures)
sudo k3s kubectl logs -n lb-automotive -l app=backend -c backend --tail=200
sudo k3s kubectl logs -n lb-automotive -l app=backend -c backend --previous --tail=100

# 3. Frontend logs
sudo k3s kubectl logs -n lb-automotive -l app=frontend -c frontend --tail=200

# 4. Recent events
sudo k3s kubectl get events -n lb-automotive --sort-by='.lastTimestamp' | tail -30
```

**Common causes**

| Symptom | Likely cause | Fix |
|--------|----------------|-----|
| Backend pod `CrashLoopBackOff` or never Ready | Missing/invalid `DATABASE_URL` or `SECRET_KEY` in `app-secrets` | Check secret exists: `sudo k3s kubectl get secret app-secrets -n lb-automotive -o jsonpath='{.data}'`. Ensure Jenkins "Ensure App Secrets" stage ran and `supabase-db-url` (or equivalent) is set. |
| Backend probe fails | App starts but `/health` returned 503 (DB/Redis down) | Readiness uses `/ready` (process up only). If still failing, check backend logs for DB connection errors; fix Supabase/Postgres URL and connectivity. |
| Frontend pod not Ready | Image pull failure, OOM, or Nginx not listening on 80 | Check `describe pod` for `Failed`/`PullBackOff`; check logs for OOM or startup errors. |
| "1 old replicas are pending termination" | New replica never becomes Ready, so old one is kept | Fix the new pod (secrets, DB, image); once new pod is Ready, rollout completes. |
| Backend/frontend pod `ImagePullBackOff` or `ErrImagePull` | Cannot pull image from GHCR; events show **403 Forbidden** on `ghcr.io/token` | See [ImagePullBackOff (403 from GHCR)](#imagepullbackoff-403-from-ghcr) below. |

**Quick recovery (if rollback is acceptable)**

```bash
sudo k3s kubectl rollout undo deployment/backend -n lb-automotive
sudo k3s kubectl rollout undo deployment/frontend -n lb-automotive
```

**Recovery when image pull fails (use last known good tag)**

```bash
# List backend images already on the node (one of these can be used)
sudo k3s crictl images | grep lb-automotive-backend

# Point deployment at a tag that already exists on the node (e.g. 231-7495406)
sudo k3s kubectl set image deployment/backend backend=ghcr.io/gamebox-inc/lb-automotive-backend:231-7495406 -n lb-automotive
sudo k3s kubectl rollout status deployment/backend -n lb-automotive --timeout=3m
```

---

## ImagePullBackOff (403 from GHCR)

When events show **`failed to authorize: ... 403 Forbidden`** for `ghcr.io/token`, the node cannot pull the image because registry auth failed.

**Diagnose**

```bash
sudo k3s kubectl get pods -n lb-automotive -l app=backend -o wide
sudo k3s kubectl describe pod -n lb-automotive -l app=backend | grep -A2 "Events:"
```

Look for: `Failed to pull image ... 403 Forbidden` or `ErrImagePull` / `ImagePullBackOff`.

**Causes**

1. **Token expired or revoked** — `ghcr-secret` was created with a GitHub PAT that no longer works. Recreate the secret (see below).
2. **Token lacks permission** — PAT must have `read:packages`. For org packages, use a PAT or GitHub App token that has access to the org.
3. **Image tag not pushed or package private** — Jenkins may have set the deployment to a tag that was never pushed, or the package is private and the token cannot see it.

**Fix: recreate GHCR pull secret**

On your **local machine** (with a valid GitHub PAT that has `read:packages`):

```bash
kubectl create secret docker-registry ghcr-secret \
  --docker-server=ghcr.io \
  --docker-username=YOUR_GITHUB_USERNAME_OR_ORG \
  --docker-password=YOUR_GITHUB_PAT \
  --namespace=lb-automotive \
  --dry-run=client -o yaml | kubectl apply -f -
```

Or on the server using `deployment/k8s/create-secrets.sh` (run the script and enter a new token when prompted for GHCR).

Then retry the rollout or re-run the pipeline. To unblock immediately using an image already on the node, use the “Recovery when image pull fails” command in the previous section.

---

## Backend Init / CrashLoopBackOff

Backend uses Vault Agent init to inject secrets. If init fails:

1. **Check Vault status** — `vault-0` must be unsealed.
2. **Check Vault policy** — `lb-automotive-role` needs `secret/data/lb-automotive/*` and `gamebox/data/clients/lb-autorepair/database`.
3. **Init container logs** — `kubectl logs <pod> -c vault-agent-init` for 403/permission errors.

---

## 502 Bad Gateway

- Frontend Nginx proxies `/api/*` to backend. If backend is down or not ready → 502.
- **VPN:** `10.100.0.1:30080` → frontend → backend.
- **Public:** Cloudflare → Traefik → backend (Twilio only).

**Quick diagnostic:** Run `./scripts/k8s-debug-summary.sh lb-admin@178.156.223.196` from repo root. See [Common Failures § 502](../incidents/common-failures.md#1-502-bad-gateway-frontend--api).

---

## Vault Unseal

Main Vault uses **Transit Auto-Unseal**. No manual unseal keys. If Main Vault is uninitialized:

```bash
sudo k3s kubectl exec -n gamebox-security vault-0 -c vault -- \
  env VAULT_SKIP_VERIFY=true vault operator init -recovery-shares=1 -recovery-threshold=1
```

Store the recovery key and root token securely.

---

## Resource Limits

- 2GB server; memory is tight.
- Backend: 256Mi limit
- Frontend: 128Mi limit
- Redis: 64Mi limit

---

## Disk Space

- CronJob `disk-monitor` runs periodically.
- Log rotation: 7-day retention.
- See `deployment/scripts/remove_memory_hogs.sh` and `QUICK_FIX_2GB_SERVER.md` for emergencies.

---

## Related

- [Common Failures](../incidents/common-failures.md)
- [CLAUDE.md](../../CLAUDE.md) — Notes 17–19 for routing
