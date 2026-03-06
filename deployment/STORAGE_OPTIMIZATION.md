# Storage Optimization Guide

**Server Constraint:** 10GB total disk space  
**Goal:** Run Jenkins + K3s + ArgoCD + Application efficiently

---

## Current Storage Breakdown (Typical)

| Component | Estimated Size | Optimization Strategy |
|-----------|---------------|----------------------|
| OS & System | ~2GB | Cannot reduce |
| Docker Images | 2-4GB | Aggressive cleanup |
| Jenkins Data | 1-2GB | Keep only recent builds |
| K3s System | 1GB | Minimal installation |
| Application Data | 500MB | SQLite database |
| **Available** | **2-4GB** | **Safety buffer** |

---

## Optimization Strategies Implemented

### 1. **K3s Minimal Installation**

Disabled unnecessary components:
- ❌ Traefik (we have our own ingress)
- ❌ ServiceLB (single node)
- ❌ Local-Storage (use hostPath)
- ❌ Metrics-Server (not needed initially)

**Savings:** ~500MB

### 2. **Aggressive Image Cleanup**

K3s kubelet configured to:
- Garbage collect images at **70% disk usage**
- Trigger pod eviction at **<1GB free**
- Remove unused images automatically

### 3. **Jenkins Build Retention**

- Keep only **last 3 builds** (vs default 10)
- Clean workspaces after build
- No build artifacts stored

**Savings:** ~500MB

### 4. **Docker Image Management**

- Use `imagePullPolicy: IfNotPresent` (don't pull if exists)
- Single replica deployments (not 3)
- Share base images between services

**Savings:** ~1GB

### 5. **Automated Cleanup Cron**

Daily cleanup script to remove:
- Stopped containers
- Dangling images
- Unused volumes
- Old Jenkins builds

---

## Manual Cleanup Commands

### Immediate Space Recovery

```bash
# Clean everything Docker (keeps running containers)
docker system prune -a --volumes -f

# Clean Jenkins old builds
docker exec lb-jenkins find /var/jenkins_home/jobs/*/builds \
  -maxdepth 1 -type d -name '[0-9]*' | \
  sort -t/ -k7 -n | head -n -3 | xargs rm -rf 2>/dev/null || true

# Clean K3s unused images (after K3s is installed)
sudo k3s crictl rmi --prune

# Check space
df -h
```

### Emergency Space Recovery (if system is failing)

```bash
# Stop non-essential services
docker compose -f /opt/lb-automotive-dashboard/deployment/jenkins/docker-compose.yml down

# Clean everything
docker system prune -a --volumes -f
sudo rm -rf /var/lib/rancher/k3s/agent/containerd/io.containerd.content.v1.content/*
sudo systemctl restart k3s

# Restart services
docker compose -f /opt/lb-automotive-dashboard/deployment/jenkins/docker-compose.yml up -d
```

---

## Automated Cleanup Cron Job

Create a daily cleanup job:

```bash
# Create cleanup script
sudo tee /usr/local/bin/cleanup-docker-k3s.sh > /dev/null <<'EOF'
#!/bin/bash
# Daily cleanup script

echo "$(date): Starting cleanup..."

# Docker cleanup
docker system prune -f --volumes

# K3s image cleanup
k3s crictl rmi --prune 2>/dev/null || true

# Jenkins old builds (keep last 3)
docker exec lb-jenkins find /var/jenkins_home/jobs/*/builds \
  -maxdepth 1 -type d -name '[0-9]*' | \
  sort -t/ -k7 -n | head -n -3 | \
  xargs rm -rf 2>/dev/null || true

echo "$(date): Cleanup complete"
df -h / | tail -1
EOF

# Make executable
sudo chmod +x /usr/local/bin/cleanup-docker-k3s.sh

# Add to crontab (runs daily at 2 AM)
(crontab -l 2>/dev/null; echo "0 2 * * * /usr/local/bin/cleanup-docker-k3s.sh >> /var/log/cleanup.log 2>&1") | crontab -
```

---

## Monitoring Disk Space

### Quick Check

```bash
# Overall usage
df -h /

# Docker breakdown
docker system df

# K3s images
sudo k3s crictl images | wc -l
sudo k3s crictl images
```

### Set Up Alerts (Optional)

```bash
# Add to crontab - alert if <1GB free
(crontab -l 2>/dev/null; echo "*/15 * * * * [ \$(df / | awk 'NR==2 {print \$4}') -lt 1048576 ] && echo 'WARNING: Less than 1GB free' | mail -s 'Disk Space Alert' admin@example.com") | crontab -
```

---

## Storage-Optimized K8s Manifests

### Image Pull Policy

Always use `IfNotPresent` for images you build:

```yaml
spec:
  containers:
  - name: backend
    image: ghcr.io/gamebox-inc/lb-automotive-backend:latest
    imagePullPolicy: IfNotPresent  # Don't re-pull if exists
```

### Single Replicas

Use 1 replica for services (not 3):

```yaml
spec:
  replicas: 1  # Single node, single replica
```

### Resource Limits

Set resource limits to prevent OOM:

```yaml
spec:
  containers:
  - name: backend
    resources:
      limits:
        memory: "512Mi"
        cpu: "500m"
      requests:
        memory: "256Mi"
        cpu: "250m"
```

---

## What NOT to Do (Space Wasters)

❌ **Don't:**
- Install full Kubernetes (use K3s)
- Keep default metrics-server (not needed initially)
- Run 3 replicas per service (1 is fine for single node)
- Store large files in Docker volumes
- Keep old Docker images
- Enable debug logging in production

✅ **Do:**
- Use K3s (not K8s)
- Aggressive image cleanup
- Single replica deployments
- Use external storage for large files
- Regular cleanup cron jobs
- Monitor disk usage

---

## Expected Final Layout

```
Total: 10GB
├── OS & System: 2GB
├── Docker Images: 1.5GB (active only)
├── Jenkins: 1GB (3 recent builds)
├── K3s: 1GB (minimal)
├── Application: 500MB
├── Logs: 500MB
└── Available: 3.5GB (safety buffer)
```

---

## Troubleshooting

### "No space left on device"

```bash
# Find what's using space
du -sh /var/lib/docker/* | sort -h
du -sh /var/lib/rancher/k3s/* | sort -h

# Emergency cleanup
docker system prune -a --volumes -f
sudo k3s crictl rmi --prune
```

### Pods stuck in "ImagePullBackOff"

Likely due to low disk space preventing image pulls.

```bash
# Clean space
docker system prune -a -f

# Check if image is already local
sudo k3s crictl images | grep your-image
```

### Jenkins builds failing

Workspace may be full.

```bash
# Clean Jenkins workspace
docker exec lb-jenkins find /var/jenkins_home/workspace -type f -name "*.log" -delete
```

---

## Regular Maintenance Schedule

| Frequency | Task | Command |
|-----------|------|---------|
| **Daily** | Auto cleanup | Cron job |
| **Weekly** | Manual check | `df -h` |
| **Monthly** | Deep clean | Stop services, prune all |

---

## Summary

With 10GB, you can successfully run:
- ✅ Jenkins CI (minimal)
- ✅ K3s Kubernetes (minimal)
- ✅ ArgoCD (lightweight)
- ✅ Your application

**Key:** Aggressive cleanup + Minimal installs + Monitoring
