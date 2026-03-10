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
