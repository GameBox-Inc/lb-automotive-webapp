# Deployment Guide for 2GB RAM Server

## Server Specs
- **RAM**: 2 GB
- **CPU**: 2 vCPU
- **Disk**: 40 GB SSD
- **Provider**: Hetzner
- **IP**: 178.156.223.196

## Critical Configuration Changes

### Memory Optimization Summary
Your 2GB server requires aggressive optimization. Here's what's been changed:

**REMOVED** (saves ~2.5GB):
- ❌ **Ollama** - Local LLM (uses 1-2GB RAM)
- ❌ **ArgoCD** - GitOps tool (uses 500MB-1GB RAM)

**OPTIMIZED**:
- ✅ **Redis**: Limited to 64MB, LRU eviction policy
- ✅ **Backend**: 256MB request / 384MB limit
- ✅ **Frontend**: 64MB request / 128MB limit
- ✅ **Log Rotation**: Automatic cleanup, 7-day retention
- ✅ **Database Archiving**: Monthly archiving of old data

### New Memory Budget (2GB Total)
```
K3s System:        ~600 MB  (30%)
Backend (FastAPI): ~256 MB  (13%)
Frontend (Nginx):  ~64 MB   (3%)
Redis:             ~64 MB   (3%)
System Overhead:   ~400 MB  (20%)
Available Buffer:  ~600 MB  (30%)
```

## Deployment Steps

### 1. Emergency Cleanup (Run First!)

SSH into your server and remove memory hogs:

```bash
ssh lb-admin@178.156.223.196

# Navigate to repo
cd /opt/lb-automotive-dashboard

# Pull latest changes
git fetch origin
git checkout release/v0.1
git pull origin release/v0.1

# Make scripts executable
chmod +x deployment/scripts/*.sh

# Remove Ollama and ArgoCD immediately
./deployment/scripts/remove_memory_hogs.sh
```

This will free up ~2GB of RAM immediately.

### 2. Setup Log Rotation

Prevent logs from filling your 40GB disk:

```bash
# Setup automatic log rotation and compression
sudo ./deployment/scripts/setup_log_rotation.sh

# Verify configuration
sudo logrotate -d /etc/logrotate.d/k3s-containers
```

**What this does:**
- Rotates logs daily if > 50MB
- Keeps 7 days of compressed logs
- Limits journald to 500MB max
- Daily cleanup of old Docker images and containers
- Automatic cleanup of logs older than 14 days

### 3. Update Environment Configuration

Ensure your backend uses Anthropic Claude API (not Ollama):

```bash
# Check current secrets
kubectl get secret app-secrets -n lb-automotive -o yaml

# Update LLM_PROVIDER to use Anthropic
kubectl create secret generic app-secrets -n lb-automotive \
  --from-literal=LLM_PROVIDER=anthropic \
  --from-literal=SECRET_KEY="your-secret-key" \
  --from-literal=ALLOWED_ORIGINS="https://kozytherocket.space" \
  --from-literal=DATABASE_URL="sqlite:////app/data/lb_automotive.db" \
  --from-literal=REDIS_URL="redis://redis:6379/0" \
  --from-literal=CSP_POLICY="strict" \
  --dry-run=client -o yaml | kubectl apply -f -

# Ensure Anthropic API key is set
kubectl create secret generic anthropic-secrets -n lb-automotive \
  --from-literal=ANTHROPIC_API_KEY="your-anthropic-key" \
  --from-literal=ANTHROPIC_MODEL="claude-3-5-sonnet-20241022" \
  --dry-run=client -o yaml | kubectl apply -f -
```

### 4. Apply Optimized Kubernetes Configurations

```bash
cd /opt/lb-automotive-dashboard

# Apply updated configurations with memory limits
kubectl apply -f deployment/k8s/redis.yaml
kubectl apply -f deployment/k8s/backend.yaml
kubectl apply -f deployment/k8s/frontend.yaml

# Apply monitoring and archiving cron jobs
kubectl apply -f deployment/k8s/disk-monitor-cronjob.yaml

# Verify all pods are running
kubectl get pods -n lb-automotive -o wide

# Check memory usage
kubectl top nodes
kubectl top pods -n lb-automotive
```

### 5. Verify System Health

```bash
# Check pod status
kubectl get pods -n lb-automotive

# Check logs
kubectl logs -n lb-automotive deployment/backend --tail=50
kubectl logs -n lb-automotive deployment/frontend --tail=50

# Check memory usage
free -h
kubectl top nodes
kubectl top pods -n lb-automotive --sort-by=memory

# Check disk usage
df -h
```

### 6. Setup Database Archiving (Optional but Recommended)

Manually run database archiving to test:

```bash
# Get backend pod name
POD=$(kubectl get pods -n lb-automotive -l app=backend -o jsonpath='{.items[0].metadata.name}')

# Run archiving script
kubectl exec -n lb-automotive $POD -- python3 /app/database_archiving.py

# Check archives
kubectl exec -n lb-automotive $POD -- ls -lh /app/data/archives/
```

The cron job will run this automatically on the 1st of each month at 2 AM.

## Monitoring

### Memory Monitoring
```bash
# Real-time memory usage
watch -n 5 'kubectl top pods -n lb-automotive'

# Node memory
kubectl top nodes

# Detailed pod info
kubectl describe pod -n lb-automotive <pod-name>
```

### Disk Monitoring
```bash
# Disk usage
df -h

# Largest directories
du -sh /var/log/* | sort -rh | head -10
du -sh /var/lib/rancher/k3s/* | sort -rh | head -10

# Check log files
find /var/log/containers/ -name "*.log" -size +50M -ls
```

### Application Monitoring
```bash
# Check backend logs
kubectl logs -n lb-automotive deployment/backend --tail=100 -f

# Check frontend logs
kubectl logs -n lb-automotive deployment/frontend --tail=100 -f

# Check Redis
kubectl exec -n lb-automotive deployment/redis -- redis-cli info memory
```

## Troubleshooting

### Pod in CrashLoopBackOff
```bash
# Check pod events
kubectl describe pod -n lb-automotive <pod-name>

# Check logs (current)
kubectl logs -n lb-automotive <pod-name>

# Check logs (previous crash)
kubectl logs -n lb-automotive <pod-name> --previous

# Check memory limits
kubectl get pod -n lb-automotive <pod-name> -o yaml | grep -A 10 resources
```

### Out of Memory (OOM) Errors
If you still see OOM errors:

1. **Check which pod is OOM:**
```bash
dmesg | grep -i "killed process"
kubectl get events -n lb-automotive --sort-by='.lastTimestamp'
```

2. **Increase memory limits slightly** (but not too much for 2GB server):
```bash
# Edit deployment
kubectl edit deployment <deployment-name> -n lb-automotive

# Increase memory limit by 50-100MB max
```

3. **Add swap space** (last resort):
```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### Disk Full Issues
```bash
# Clean up immediately
sudo docker system prune -af --volumes
sudo journalctl --vacuum-size=100M

# Clean old logs
sudo find /var/log/containers/ -name "*.log.*" -delete
sudo find /var/log/pods/ -name "*.log.*" -delete

# Run manual cleanup
sudo /etc/cron.daily/disk-cleanup
```

### Redis Memory Issues
```bash
# Check Redis memory usage
kubectl exec -n lb-automotive deployment/redis -- redis-cli info memory

# If Redis is using too much memory
kubectl exec -n lb-automotive deployment/redis -- redis-cli FLUSHALL
```

## Performance Expectations

### What Works on 2GB Server:
✅ **10-50 concurrent users** - OK performance  
✅ **Basic appointment booking** - Works well  
✅ **Customer management** - Works well  
✅ **IVR integration** - Works (using Anthropic API)  
✅ **Admin dashboard** - Works well  

### What Doesn't Work:
❌ **Local LLM (Ollama)** - Removed, use Anthropic API  
❌ **High traffic (100+ concurrent users)** - Need 4GB+ RAM  
❌ **Heavy analytics/reporting** - May be slow  
❌ **Multiple replicas** - Not enough RAM for HA  

## Upgrade Recommendations

### When to Upgrade RAM:

**Upgrade to 4GB RAM if:**
- You see frequent OOM errors after optimization
- Response times > 2 seconds consistently
- You need high availability (2+ replicas)
- You want to run Ollama locally
- You have > 50 concurrent users regularly

**Upgrade to 8GB RAM if:**
- You need production-grade HA setup
- You want ArgoCD for GitOps
- You need multiple replicas (frontend + backend)
- You have > 100 concurrent users
- You want local LLM + full observability stack

### When to Upgrade Disk:

**Upgrade to 80GB+ if:**
- Database grows > 5GB
- You store many archived records
- You want > 30 days of logs
- You run frequent backups

## Cost Analysis

**Current Setup (2GB)**: $4.99/mo  
**Upgrade to 4GB**: ~$9-12/mo (estimate)  
**Upgrade to 8GB**: ~$18-24/mo (estimate)

**Anthropic Claude API Costs** (replacing Ollama):
- $3 per 1M input tokens
- $15 per 1M output tokens
- Typical IVR call: ~1,000 tokens (~$0.02/call)
- 500 calls/month: ~$10/mo
- Still cheaper than upgrading to 8GB server for Ollama

## Automation

All the following are now automated:

✅ **Log rotation**: Daily (logrotate)  
✅ **Log compression**: Automatic (gzip)  
✅ **Old log deletion**: Weekly (cron)  
✅ **Database archiving**: Monthly (K8s CronJob)  
✅ **Disk space monitoring**: Daily (K8s CronJob)  
✅ **Image cleanup**: Daily (cron)  

## Backup Strategy

Even with 40GB disk, maintain backups:

```bash
# Daily database backup (lightweight)
kubectl exec -n lb-automotive deployment/backend -- \
  sqlite3 /app/data/lb_automotive.db ".backup '/app/data/backup-$(date +%Y%m%d).db'"

# Copy to local machine
kubectl cp lb-automotive/<pod-name>:/app/data/backup-YYYYMMDD.db ./backups/

# Keep only last 7 days on server
find /app/data/backup-*.db -mtime +7 -delete
```

## Summary

Your 2GB server **can work** for small-to-medium traffic with these optimizations:

1. ✅ Ollama removed (use Anthropic API)
2. ✅ ArgoCD removed (use GitHub Actions)
3. ✅ Strict memory limits on all pods
4. ✅ Redis configured for low memory (64MB max)
5. ✅ Log rotation and compression enabled
6. ✅ Database archiving automated
7. ✅ Monitoring and alerting in place

**Expected to support**:
- 10-50 concurrent users
- 1,000-5,000 appointments/month
- 500-1,000 IVR calls/month
- 30 days of active data
- 7 days of logs

If you exceed these limits, upgrade to 4GB or 8GB RAM.

## Questions?

If something doesn't work:
1. Check memory: `free -h`
2. Check disk: `df -h`
3. Check pods: `kubectl get pods -n lb-automotive`
4. Check logs: `kubectl logs -n lb-automotive deployment/<name>`
5. Check events: `kubectl get events -n lb-automotive --sort-by='.lastTimestamp'`
