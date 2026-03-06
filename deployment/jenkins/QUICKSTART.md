# Jenkins CI/CD Quick Start Guide

This guide will get you up and running with Jenkins in under 30 minutes.

---

## Prerequisites Checklist

Before starting, ensure you have:

- ✅ SSH access to server: `lb-admin@178.156.223.196`
- ✅ Docker and Docker Compose installed on server
- ✅ Git repository cloned at: `/opt/lb-automotive-dashboard`
- ✅ Port 8080 accessible (or configure firewall for your IP)

---

## Quick Setup (5 Steps)

### Step 1: Deploy Jenkins Server (2 minutes)

SSH into your server and run the setup script:

```bash
ssh lb-admin@178.156.223.196

# Navigate to the repository
cd /opt/lb-automotive-dashboard

# Make script executable
chmod +x deployment/jenkins/setup-jenkins.sh

# Run setup script
bash deployment/jenkins/setup-jenkins.sh
```

This will:
- Create Jenkins directory at `/opt/jenkins`
- Start Jenkins container
- Generate SSH keys for deployment
- Display initial admin password

**Save the initial admin password shown at the end!**

---

### Step 2: Complete Jenkins Initial Setup (5 minutes)

1. Open Jenkins in your browser:
   ```
   http://178.156.223.196:8080
   ```

2. Enter the **initial admin password** from Step 1

3. Click **Install suggested plugins** (wait for installation to complete)

4. Create admin user:
   - Username: `admin` (or your choice)
   - Password: (choose a strong password)
   - Email: your email

5. Jenkins URL: `http://178.156.223.196:8080` (keep default)

6. Click **Start using Jenkins**

---

### Step 3: Configure SSH for Deployment (2 minutes)

Back in your SSH terminal, run:

```bash
cd /opt/lb-automotive-dashboard

# Add SSH public key to authorized_keys (if not already done)
cat ~/.ssh/jenkins_deploy_key.pub >> ~/.ssh/authorized_keys

# Configure SSH in Jenkins container
chmod +x deployment/jenkins/configure-ssh.sh
bash deployment/jenkins/configure-ssh.sh
```

Verify you see: `✅ SSH connection works!`

---

### Step 4: Install Required Jenkins Plugins (5 minutes)

In Jenkins UI:

1. Go to: **Manage Jenkins** → **Manage Plugins**

2. Click **Available** tab

3. Search and select these plugins:
   - Docker Pipeline
   - SSH Agent
   - Credentials Binding
   - Blue Ocean (optional, but recommended)

4. Click **Install without restart**

5. Wait for installation, then click **Go back to the top page**

---

### Step 5: Add Credentials & Create Pipeline (10 minutes)

#### A. Add Secrets to Jenkins

Go to: **Manage Jenkins** → **Manage Credentials** → **System** → **Global credentials** → **Add Credentials**

Add these credentials one by one (Kind: **Secret text**):

| ID | Value | How to Get |
|----|-------|-----------|
| `secret-key` | Generate with: `openssl rand -hex 32` | Run in terminal |
| `allowed-origins` | `http://178.156.223.196,http://localhost:5173` | Copy this value |
| `llm-provider` | `ollama` | Type "ollama" |
| `anthropic-api-key` | Your Anthropic key (optional) | From Anthropic console |
| `twilio-account-sid` | Your Twilio SID (optional) | From Twilio console |
| `twilio-auth-token` | Your Twilio token (optional) | From Twilio console |
| `twilio-phone-number` | Your Twilio phone (optional) | From Twilio console |

For each:
- Click **Add Credentials**
- Kind: **Secret text**
- Scope: **Global**
- Secret: (paste the value)
- ID: (enter the ID from table above)
- Click **OK**

#### B. Create Pipeline Job

1. Click **New Item** (top left)

2. Enter name: `LB-Automotive-Dashboard`

3. Select: **Pipeline**

4. Click **OK**

5. Configure:
   - **Description:** CI/CD pipeline for LB Automotive Dashboard

   - **Build Triggers:**
     - ☑ Check **Poll SCM**
     - Schedule: `H/5 * * * *` (checks every 5 minutes)

   - **Pipeline section:**
     - Definition: **Pipeline script from SCM**
     - SCM: **Git**
     - Repository URL: `https://github.com/GameBox-Inc/lb-automotive-webapp.git`
       (or your Git URL)
     - Credentials: (add if private repo)
     - Branch Specifier: `*/release/v0.1` (or your branch)
     - Script Path: `Jenkinsfile`

6. Click **Save**

---

## Test Your Setup

### Run First Build

1. Click **Build Now** on your pipeline job

2. Click on the build number (e.g., `#1`)

3. Click **Console Output** to watch progress

### Expected Output

You should see:
```
✓ Checkout code
✓ Setup Python
✓ Backend tests
✓ Setup Node
✓ Frontend tests
✓ Build Docker images
✓ Deploy to server
✓ Verify deployment
✅ Pipeline completed successfully
```

### Verify Deployment

After successful build, test the application:

```bash
# Backend health check
curl http://178.156.223.196:8000/health

# Frontend
curl http://178.156.223.196/

# Check containers
docker compose -f /opt/lb-automotive-dashboard/deployment/docker/docker-compose.yml ps
```

---

## Common Issues & Quick Fixes

### Issue: "Permission denied" during SSH

**Fix:**
```bash
# Ensure SSH key is in authorized_keys
cat ~/.ssh/jenkins_deploy_key.pub >> ~/.ssh/authorized_keys

# Run configure script again
bash deployment/jenkins/configure-ssh.sh
```

### Issue: Can't access Jenkins UI

**Fix:**
```bash
# Check if Jenkins is running
docker ps | grep lb-jenkins

# If not running, start it
cd /opt/jenkins
docker compose up -d

# Check logs
docker logs lb-jenkins
```

### Issue: Build fails with "credentials not found"

**Fix:**
- Go to **Manage Jenkins** → **Manage Credentials**
- Verify all credential IDs match exactly:
  - `secret-key`
  - `allowed-origins`
  - `llm-provider`
  - etc.
- Credentials must be in **Global** scope

### Issue: Deployment fails

**Fix:**
```bash
# Check deployment script
cat /opt/lb-automotive-dashboard/deployment/scripts/jenkins-deploy.sh

# Test SSH manually
ssh lb-admin@178.156.223.196 "echo 'SSH works'"

# Check disk space
df -h

# Check Docker
docker ps
```

---

## Next Steps

✅ Jenkins is now set up and running!

### Recommended Actions:

1. **Test the pipeline** - Push a change to trigger automatic build

2. **Configure webhook** (optional) - For instant builds on git push:
   - GitHub: Repository → Settings → Webhooks
   - Webhook URL: `http://178.156.223.196:8080/github-webhook/`

3. **Restrict Jenkins access** - Limit to your IP:
   ```bash
   sudo ufw allow from YOUR_IP to any port 8080 proto tcp
   sudo ufw deny 8080
   ```

4. **Set up backups** - Backup Jenkins config regularly:
   ```bash
   docker exec lb-jenkins tar -czf /tmp/jenkins_backup.tar.gz /var/jenkins_home
   docker cp lb-jenkins:/tmp/jenkins_backup.tar.gz ./jenkins_backup_$(date +%Y%m%d).tar.gz
   ```

5. **Disable GitHub Actions** (if migrating):
   ```bash
   # Stop self-hosted runner
   cd /opt/actions-runner
   ./svc.sh stop
   ./svc.sh uninstall

   # Or delete workflow file
   git rm .github/workflows/gamebox-engine.yaml
   git commit -m "Migrate to Jenkins CI/CD"
   ```

---

## Monitoring

### View Logs

```bash
# Jenkins logs
docker logs lb-jenkins -f

# Application logs
docker logs lb-auto-backend -f
docker logs lb-auto-frontend -f
```

### Jenkins Status

```bash
# Check Jenkins container
docker ps | grep lb-jenkins

# Check resources
docker stats lb-jenkins
```

### Build History

- View in Jenkins UI: Job → **Build History**
- Or from terminal:
  ```bash
  docker exec lb-jenkins ls -lh /var/jenkins_home/jobs/LB-Automotive-Dashboard/builds/
  ```

---

## Useful Commands

```bash
# Start Jenkins
cd /opt/jenkins && docker compose up -d

# Stop Jenkins
cd /opt/jenkins && docker compose down

# Restart Jenkins
docker compose restart lb-jenkins

# View logs
docker logs lb-jenkins -f

# Get admin password
docker exec lb-jenkins cat /var/jenkins_home/secrets/initialAdminPassword

# Backup Jenkins
docker exec lb-jenkins tar -czf /tmp/jenkins_backup.tar.gz /var/jenkins_home

# Update Jenkins
cd /opt/jenkins
docker compose pull
docker compose up -d
```

---

## Support

Having issues? Check:

1. **Console output** in Jenkins UI for error details
2. **Docker logs**: `docker logs lb-jenkins`
3. **Full documentation**: `deployment/jenkins/README.md`
4. **SSH connectivity**: `ssh lb-admin@178.156.223.196`
5. **Application logs**: `docker logs lb-auto-backend`

---

## Architecture Overview

```
Your Local Machine
        │
        │ git push
        ▼
    Git Repository
        │
        │ webhook/poll
        ▼
Jenkins (178.156.223.196:8080)
        │
        │ 1. Tests
        │ 2. Build
        │ 3. Deploy via SSH
        ▼
Production Server (same host)
  - Frontend (port 80)
  - Backend (port 8000)
  - Redis
  - Ollama
```

---

**Estimated Setup Time:** 20-30 minutes
**Difficulty:** Easy

Once completed, every git push will automatically trigger tests, build, and deployment! 🚀

---

For detailed information, see: `deployment/jenkins/README.md`
