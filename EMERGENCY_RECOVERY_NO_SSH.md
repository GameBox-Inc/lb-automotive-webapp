# Emergency Recovery - Server Unresponsive (No SSH Access)

## Current Situation
- ✅ Changes pushed to GitHub (release/v0.1 branch)
- ❌ Cannot SSH into server (likely OOM killed SSH daemon)
- ❌ GitHub Actions self-hosted runner likely also dead
- 🚨 Server needs hard reboot via Hetzner console

## Why GitHub Actions Won't Help Right Now

Your GitHub Actions workflow runs on a **self-hosted runner** on the server itself:
- If SSH is dead, the runner is also likely dead (killed by OOM)
- The runner needs the server to be responsive to execute jobs
- **You must reboot the server first**

## Solution: Reboot via Hetzner Console

### Option 1: Hetzner Cloud Console (Web Interface)

**Step-by-Step:**

1. **Go to Hetzner Cloud Console**
   - URL: https://console.hetzner.cloud/
   - Log in with your Hetzner account

2. **Find Your Server**
   - Click on your project
   - Find server with IP: `178.156.223.196`
   - Click on the server name

3. **Hard Reboot**
   - Click **"Power"** in the top right
   - Select **"Reset"** or **"Power Cycle"**
   - Confirm the action
   
   **Note:** "Reset" = hard reboot (like pressing physical power button)

4. **Wait 2-3 Minutes**
   - Server will restart
   - K3s will auto-start on boot
   - SSH daemon will restart

5. **Try SSH Again**
   ```powershell
   ssh lb-admin@178.156.223.196
   ```

6. **If SSH Works, Apply Fixes Immediately:**
   ```bash
   cd /opt/lb-automotive-dashboard
   git pull origin release/v0.1
   chmod +x deployment/scripts/*.sh
   
   # CRITICAL: Remove memory hogs first
   ./deployment/scripts/remove_memory_hogs.sh
   
   # Setup log rotation
   sudo ./deployment/scripts/setup_log_rotation.sh
   
   # Apply optimized K8s configs
   kubectl apply -f deployment/k8s/redis.yaml
   kubectl apply -f deployment/k8s/backend.yaml
   kubectl apply -f deployment/k8s/frontend.yaml
   kubectl apply -f deployment/k8s/disk-monitor-cronjob.yaml
   
   # Restart services
   kubectl rollout restart deployment -n lb-automotive frontend
   kubectl rollout restart deployment -n lb-automotive backend
   
   # Verify
   kubectl get pods -n lb-automotive
   kubectl top pods -n lb-automotive
   free -h
   ```

### Option 2: Hetzner Robot Console (For Dedicated Servers)

If you have a dedicated server (not cloud), use Hetzner Robot:

1. Go to https://robot.hetzner.com/
2. Log in
3. Find your server
4. Click **"Reset"** tab
5. Execute hardware reset
6. Wait 3-5 minutes
7. Try SSH

### Option 3: Emergency Console Access (VNC)

Some Hetzner plans have console access:

1. In Hetzner Cloud Console, click your server
2. Look for **"Console"** tab or button
3. This gives you VNC-like access to the server
4. You can run commands directly without SSH

## After Server Recovers

### 1. GitHub Actions Will Resume Automatically

Once the server is responsive:
- The self-hosted runner will restart automatically
- Future pushes to `release/v0.1` will trigger deployments
- **BUT**: The old workflow uses Docker Compose, not K8s

### 2. Enable New K8s Workflow

I've created a new workflow for Kubernetes deployment:
- File: `.github/workflows/k8s-deploy.yaml`
- Commit and push this file
- It will deploy to K8s instead of Docker Compose

**To switch workflows:**

```bash
# On Windows
git add .github/workflows/k8s-deploy.yaml
git commit -m "Add Kubernetes deployment workflow"
git push origin release/v0.1
```

**Optional: Disable old workflow:**
```bash
# Rename old workflow to disable it
git mv .github/workflows/gamebox-engine.yaml .github/workflows/gamebox-engine.yaml.disabled
git commit -m "Disable Docker Compose workflow"
git push origin release/v0.1
```

### 3. Configure GitHub Secrets

Ensure these secrets are set in GitHub:
- Go to: https://github.com/GameBox-Inc/lb-automotive-webapp/settings/secrets/actions
- Required secrets:
  - `SECRET_KEY` - Your app secret key
  - `ALLOWED_ORIGINS` - CORS origins (e.g., https://kozytherocket.space)
  - `ANTHROPIC_API_KEY` - **CRITICAL** (since Ollama is removed)
  - `ANTHROPIC_MODEL` - `claude-3-5-sonnet-20241022`
  - `TWILIO_ACCOUNT_SID` - (if using Twilio)
  - `TWILIO_AUTH_TOKEN` - (if using Twilio)
  - `TWILIO_PHONE_NUMBER` - (if using Twilio)

## Alternative: If You Can't Access Hetzner Console

### Contact Hetzner Support

If you can't access the console:
1. Email: support@hetzner.com
2. Ticket system: https://accounts.hetzner.com/
3. Request: "Please reboot my server at 178.156.223.196 - it's unresponsive"
4. Response time: Usually within 30 minutes

### Wait and Retry

Sometimes the OOM killer kills non-critical processes and SSH recovers:
- Wait 5-10 minutes
- Try SSH again: `ssh lb-admin@178.156.223.196`
- If it connects, apply fixes immediately (see step 6 above)

## Prevention: After Recovery

Once the server is fixed, prevent this from happening again:

### 1. Add Swap Space
```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### 2. Setup Monitoring Alerts

Create a simple monitoring script that alerts you:
```bash
# Add to crontab: */5 * * * *
#!/bin/bash
FREE_MEM=$(free -m | awk 'NR==2{printf "%.0f", $4}')
if [ $FREE_MEM -lt 300 ]; then
  echo "WARNING: Low memory: ${FREE_MEM}MB free" | mail -s "Server Alert" your@email.com
fi
```

### 3. Enable Kubernetes Metrics

```bash
# Install metrics-server if not already installed
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

# Then you can use:
kubectl top nodes
kubectl top pods -n lb-automotive
```

## Quick Reference

### Check if Server is Responding
```powershell
# From Windows
ping 178.156.223.196

# Try SSH
ssh -o ConnectTimeout=10 lb-admin@178.156.223.196
```

### Hetzner Console URLs
- **Cloud**: https://console.hetzner.cloud/
- **Dedicated**: https://robot.hetzner.com/
- **Support**: https://accounts.hetzner.com/

### After Recovery Checklist
- [ ] Server boots successfully
- [ ] SSH access works
- [ ] Pull latest code: `git pull origin release/v0.1`
- [ ] Remove Ollama/ArgoCD: `./deployment/scripts/remove_memory_hogs.sh`
- [ ] Setup log rotation: `sudo ./deployment/scripts/setup_log_rotation.sh`
- [ ] Apply K8s configs: `kubectl apply -f deployment/k8s/*.yaml`
- [ ] Restart deployments: `kubectl rollout restart deployment -n lb-automotive`
- [ ] Add swap space (optional but recommended)
- [ ] Configure Anthropic API key in K8s secrets
- [ ] Verify: `kubectl get pods -n lb-automotive`
- [ ] Check memory: `free -h`
- [ ] Test application: `curl http://localhost`

## Expected Timeline

- **Reboot server**: 2-3 minutes
- **SSH available**: +1 minute after boot
- **Apply fixes**: 5-10 minutes
- **Services stable**: +5 minutes
- **Total**: ~15-20 minutes from reboot to working system

## Questions?

1. **"Can I deploy without rebooting?"**
   - No. If SSH is dead, the server needs a hard reboot.

2. **"Will I lose data?"**
   - No. K3s auto-starts on boot. Persistent volumes are preserved.

3. **"Can GitHub Actions deploy automatically after?"**
   - Yes, once the runner restarts. Use the new `k8s-deploy.yaml` workflow.

4. **"Should I upgrade the server?"**
   - After fixes, 2GB should work for 10-50 users. Upgrade to 4GB if issues persist.

5. **"What if reboot doesn't fix it?"**
   - Contact Hetzner support. The server may have hardware issues.
