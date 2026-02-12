# QUICK FIX: 2GB Server Out of Memory

## Emergency Steps (Run Now!)

### 1. SSH into Server
```bash
ssh lb-admin@178.156.223.196
cd /opt/lb-automotive-dashboard
```

### 2. Pull Latest Optimizations
```bash
git fetch origin
git checkout release/v0.1
git pull origin release/v0.1
chmod +x deployment/scripts/*.sh
```

### 3. Remove Memory Hogs (Frees ~2GB)
```bash
./deployment/scripts/remove_memory_hogs.sh
```

### 4. Setup Log Rotation (Saves Disk Space)
```bash
sudo ./deployment/scripts/setup_log_rotation.sh
```

### 5. Apply Optimized Configs
```bash
kubectl apply -f deployment/k8s/redis.yaml
kubectl apply -f deployment/k8s/backend.yaml
kubectl apply -f deployment/k8s/frontend.yaml
kubectl apply -f deployment/k8s/disk-monitor-cronjob.yaml
```

### 6. Restart Frontend (Fix Your Current Issue)
```bash
kubectl rollout restart deployment frontend -n lb-automotive
kubectl rollout restart deployment backend -n lb-automotive
```

### 7. Verify It's Working
```bash
# Check pods are running
kubectl get pods -n lb-automotive

# Check memory usage
kubectl top nodes
kubectl top pods -n lb-automotive

# Should see:
# - backend: ~200-300MB
# - frontend: ~50-80MB  
# - redis: ~50-70MB
# - Total: ~500-700MB (leaving 1GB+ free)
```

### 8. Add Swap (If Still Having Issues)
```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
free -h  # Verify swap is active
```

## What Changed?

**REMOVED:**
- ❌ Ollama (was using 1-2GB RAM)
- ❌ ArgoCD (was using 500MB-1GB RAM)

**OPTIMIZED:**
- ✅ Redis: Limited to 64MB with LRU eviction
- ✅ Backend: 256MB request / 384MB limit
- ✅ Frontend: 64MB request / 128MB limit
- ✅ Logs: Auto-rotate, compress, cleanup
- ✅ Database: Monthly archiving

**CONFIGURED:**
- Backend now uses Anthropic Claude API (not local Ollama)
- Ensure `ANTHROPIC_API_KEY` is set in secrets

## Expected Results

After these changes:
- **Free memory**: 1-1.3GB (out of 2GB)
- **Pods stable**: No more OOM crashes
- **Logs managed**: Won't fill 40GB disk
- **Database**: Old data archived monthly

## If Frontend Still Won't Start

```bash
# Check pod status
kubectl describe pod -n lb-automotive <frontend-pod-name>

# Check events (look for OOM or ImagePullBackOff)
kubectl get events -n lb-automotive --sort-by='.lastTimestamp' | tail -20

# Force delete and recreate
kubectl delete pod -n lb-automotive <frontend-pod-name>

# Check logs
kubectl logs -n lb-automotive <new-frontend-pod-name>
```

## Monitor Going Forward

```bash
# Daily check
watch -n 5 'kubectl top pods -n lb-automotive'

# Weekly check
df -h  # Disk usage
free -h  # Memory usage
```

## When to Upgrade

Upgrade to **4GB RAM** ($9-12/mo) if:
- Still seeing OOM after optimization
- Need high availability (2+ replicas)
- Want to run Ollama locally
- Have > 50 concurrent users

Upgrade to **8GB RAM** ($18-24/mo) if:
- Need production HA setup
- Want ArgoCD back
- Have > 100 concurrent users
- Need full observability stack

## Full Documentation

See `DEPLOYMENT_2GB_SERVER.md` for complete details.
