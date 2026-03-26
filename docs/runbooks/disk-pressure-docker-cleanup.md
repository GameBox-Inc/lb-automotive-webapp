# Disk Pressure & Docker Cleanup Runbook

**When to use:** Node shows `DiskPressure=True`, `docker system prune -a -f` reports "Total reclaimed space: 0B", or `/var/lib/docker` is large (e.g. 20GB+) on a K3s host.

---

## Why `docker system prune -a -f` Reports 0B Reclaimed

Docker reports **0B reclaimed** when it considers every image/layer **in use**. Common causes:

| Cause | What to do |
|-------|------------|
| **Build cache** | `docker system prune` does **not** remove build cache. Use `docker builder prune -a -f` first. |
| **Running containers** | Images used by running containers (e.g. Jenkins) are "in use". Stop non-essential containers, then prune; or run **builder prune** (build cache is often the biggest consumer). |
| **All images tagged** | Less common; builder prune + prune after stopping Jenkins usually frees space. |

**Recommended order:** Clear build cache first, then system prune. If Jenkins runs on the same host, optionally stop it before pruning to allow image prune to remove old app images, then start Jenkins again.

---

## 1. Diagnose What’s Using Space

On the server (e.g. `ssh lb-admin@<server>`):

```bash
df -h /
sudo du -sh /var/lib/docker 2>/dev/null
sudo du -sh /var/lib/rancher/k3s/* 2>/dev/null
docker system df
```

If `docker system df` shows large "Reclaimable" for **Build Cache**, use builder prune (step 2).

---

## 2. Free Space: Docker (Including Build Cache)

Run on the host where Docker is used (e.g. Jenkins agent or the K3s server):

```bash
# Clear build cache (often 5–20GB). This is why "prune -a" reclaimed 0B.
sudo docker builder prune -a -f

# Then remove unused images/containers/networks
sudo docker system prune -a -f

# Optional: remove unused volumes (can break old Jenkins data if you need it)
# sudo docker volume prune -f

df -h /
```

If you need to free **even more** and can afford a short Jenkins downtime:

```bash
# Stop Jenkins (or any container using images you can re-pull)
sudo docker stop <jenkins-container-name>   # or: docker compose -f ... down

# Now prune can remove images that were "in use" by that container
sudo docker builder prune -a -f
sudo docker system prune -a -f

# Start Jenkins again
sudo docker start <jenkins-container-name>   # or: docker compose up -d
```

---

## 3. Free Space: K3s / Containerd

On the K3s node:

```bash
# Scale down app workloads to stop create/evict loop
sudo k3s kubectl scale deploy redis -n lb-automotive --replicas=0
sudo k3s kubectl scale deploy backend -n lb-automotive --replicas=0
sudo k3s kubectl scale deploy frontend -n lb-automotive --replicas=0

# Prune unused containerd images
sudo k3s crictl rmi --prune

# Delete evicted/failed pods
sudo k3s kubectl delete pods --all-namespaces --field-selector=status.phase=Failed --ignore-not-found
```

---

## 4. Optional: Logs and Journal

```bash
sudo journalctl --vacuum-size=200M
sudo find /var/log -name "*.gz" -mtime +7 -delete 2>/dev/null
```

---

## 5. Recheck DiskPressure and Scale Back Up

```bash
# Wait ~30s for kubelet to re-evaluate
sleep 30
sudo k3s kubectl describe node <node-name> | grep -A1 "DiskPressure"
```

If **`df -h /` shows plenty of free space** but **`DiskPressure` stays `True`** (condition heartbeat stops updating), the kubelet may be stuck. **Restart K3s** so it republishes node conditions:

```bash
sudo systemctl restart k3s
# Brief API blip on single-node clusters; pods should reschedule.
sudo k3s kubectl describe node <node-name> | grep -A1 "DiskPressure"
```

When **DiskPressure** is **False**:

```bash
sudo k3s kubectl scale deploy redis -n lb-automotive --replicas=1
sudo k3s kubectl scale deploy backend -n lb-automotive --replicas=1
sudo k3s kubectl scale deploy frontend -n lb-automotive --replicas=1
sudo k3s kubectl get pods -n lb-automotive -o wide
```

---

## 6. Jenkins Docker-in-Docker (`jenkins-docker`)

If **`/var/lib/docker` is huge** but **`docker system df` on the host** shows modest usage, check the **inner** daemon used for pipeline builds:

```bash
sudo docker exec jenkins-docker docker system df
sudo du -sh /var/lib/docker/volumes/* 2>/dev/null | sort -h | tail -5
```

**Fix (same order as host):** prune build cache inside DinD, then unused images:

```bash
sudo docker exec jenkins-docker docker builder prune -a -f
sudo docker exec jenkins-docker docker image prune -a -f --filter "until=168h"
```

Host-level `docker builder prune` **does not** clean this; omitting this step allowed **~16GB+** build cache and dozens of stale `lb-automotive-backend:*` image tags on one production node (Mar 2026).

---

## 7. Prevent Recurrence

- **Jenkins pipeline:** `Ensure disk headroom` (see `Jenkinsfile`) prunes K3s containerd, **host** Docker (builder + 7-day system prune), **`jenkins-docker` inner** builder cache and old images, then deletes Failed pods.
- **Cron on server:** `/etc/cron.daily/disk-cleanup` from `deployment/scripts/setup_log_rotation.sh` includes host builder prune, Docker/K3s prune, and **DinD** builder/image prune (`until=168h`). Re-run the setup script on the server if your live cron predates that block.
- **Eviction threshold:** If the node uses a very strict threshold (e.g. 20% free), consider relaxing it when reinstalling K3s (see `deployment/k8s/install-k3s-minimal.sh`) or free more space before deploy.

---

## Quick Reference: “Prune Reclaimed 0B” Fix

```bash
# 1. Builder cache (main fix for 0B reclaimed)
sudo docker builder prune -a -f

# 2. Then system prune
sudo docker system prune -a -f

# 3. Check
docker system df
df -h /
```

See also: `docs/incidents/common-failures.md` §3 (DiskPressure), `deployment/STORAGE_OPTIMIZATION.md`, `QUICK_FIX_2GB_SERVER.md`.
