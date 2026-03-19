---
name: disk-pressure-cleanup
description: Resolve Kubernetes node DiskPressure and Docker "Total reclaimed space: 0B" when pruning. Use when the node has DiskPressure=True, docker system prune -a -f reclaims 0B but /var/lib/docker is large, or deploy is blocked by disk.
---

# Disk Pressure & Docker Cleanup Skill

Use this skill when:
- A Kubernetes (K3s) node shows **DiskPressure=True** and deploy is blocked.
- **`docker system prune -a -f`** keeps reporting **"Total reclaimed space: 0B"** even though `/var/lib/docker` is large (e.g. 20GB+).
- You need a repeatable way to free space and clear DiskPressure without taking down the application unnecessarily.

---

## Why Docker Prune Reclaims 0B

Docker reports **0B reclaimed** when it considers all data **in use**:

1. **Build cache** — `docker system prune` does **not** remove the **build cache**. That cache can be many GB. Use **`docker builder prune -a -f`** first.
2. **Running containers** — Images used by running containers (e.g. Jenkins) are "in use", so `prune -a` won’t remove them until those containers are stopped (or you only rely on builder prune to free cache).

**Fix:** Run **`docker builder prune -a -f`** before or instead of relying only on `docker system prune -a -f`.

---

## Step 1: Diagnose (on the server)

```bash
df -h /
docker system df
sudo du -sh /var/lib/docker /var/lib/rancher/k3s 2>/dev/null
```

If **Build Cache** in `docker system df` is large, builder prune will free it.

---

## Step 2: Free Docker Space (including build cache)

On the host where Docker is used (Jenkins agent or K3s server):

```bash
# Clear build cache (this is why prune often reclaims 0B)
sudo docker builder prune -a -f

# Then remove unused images/containers/networks
sudo docker system prune -a -f

# Optional: volumes (only if you don't need old Jenkins/runner data)
# sudo docker volume prune -f

df -h /
```

---

## Step 3: If Node Has DiskPressure — Scale Down, Then Clean

On the K3s server:

```bash
# Stop the create/evict loop
sudo k3s kubectl scale deploy redis -n lb-automotive --replicas=0
sudo k3s kubectl scale deploy backend -n lb-automotive --replicas=0
sudo k3s kubectl scale deploy frontend -n lb-automotive --replicas=0

# Prune K3s/containerd
sudo k3s crictl rmi --prune
sudo k3s kubectl delete pods --all-namespaces --field-selector=status.phase=Failed --ignore-not-found
```

Then run **Step 2** (Docker builder prune + system prune) on the same host.

---

## Step 4: Recheck DiskPressure and Scale Back Up

```bash
sleep 30
sudo k3s kubectl describe node <node-name> | grep -A1 "DiskPressure"
```

When **DiskPressure** is **False**:

```bash
sudo k3s kubectl scale deploy redis -n lb-automotive --replicas=1
sudo k3s kubectl scale deploy backend -n lb-automotive --replicas=1
sudo k3s kubectl scale deploy frontend -n lb-automotive --replicas=1
```

---

## Prevention

- **Pipeline:** Ensure "Ensure disk headroom" runs before deploy. Consider adding **`docker builder prune -f --filter "until=168h"`** to that stage (or a server cron) so build cache doesn’t grow unbounded.
- **Cron:** Use `/etc/cron.daily/disk-cleanup` (from `deployment/scripts/setup_log_rotation.sh`) and optionally add builder prune with a time filter.

---

## Repo References

- **Runbook (full detail):** `docs/runbooks/disk-pressure-docker-cleanup.md`
- **Incident §3:** `docs/incidents/common-failures.md` (DiskPressure and pod evictions)
- **Storage:** `deployment/STORAGE_OPTIMIZATION.md`, `QUICK_FIX_2GB_SERVER.md`
