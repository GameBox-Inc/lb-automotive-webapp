# Jenkins CI/CD Setup for LB Automotive Dashboard

This guide covers setting up Jenkins for continuous integration and deployment of the LB Automotive Dashboard application.

## Overview

**Jenkins Server:** Self-hosted on your Hetzner server (178.156.223.196)
**Access:** Behind firewall, accessed via IP address
**Pipeline:** Automated testing, building, and deployment

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Git Repository                      │
│              (GitHub/GitLab/etc.)                    │
└────────────────┬────────────────────────────────────┘
                 │ Push/Webhook
                 ▼
┌─────────────────────────────────────────────────────┐
│              Jenkins Server                          │
│        (178.156.223.196:8080)                       │
│                                                      │
│  ┌──────────────────────────────────────┐          │
│  │  Pipeline Stages:                     │          │
│  │  1. Checkout Code                     │          │
│  │  2. Run Tests (Backend + Frontend)    │          │
│  │  3. Build Docker Images               │          │
│  │  4. Push to Registry (optional)       │          │
│  │  5. Deploy to Server                  │          │
│  │  6. Run Migrations                    │          │
│  │  7. Verify Deployment                 │          │
│  └──────────────────────────────────────┘          │
└────────────────┬────────────────────────────────────┘
                 │ SSH Deploy
                 ▼
┌─────────────────────────────────────────────────────┐
│           Production Environment                     │
│         /opt/lb-automotive-dashboard                │
│                                                      │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐   │
│  │  Frontend  │  │  Backend   │  │   Redis    │   │
│  │  (Nginx)   │  │  (FastAPI) │  │            │   │
│  └────────────┘  └────────────┘  └────────────┘   │
└─────────────────────────────────────────────────────┘
```

---

## Prerequisites

### On Server (178.156.223.196)

1. **Docker & Docker Compose installed**
2. **Port 8080 accessible** (for Jenkins UI - can be firewalled to your IP only)
3. **SSH access configured** for Jenkins to deploy
4. **Git repository cloned** at `/opt/lb-automotive-dashboard`

---

## Installation Steps

### Step 1: Deploy Jenkins Server

SSH into your server:

```bash
ssh lb-admin@178.156.223.196
```

Create Jenkins directory and deploy:

```bash
cd /opt
sudo mkdir -p jenkins
sudo chown lb-admin:lb-admin jenkins
cd jenkins

# Copy the docker-compose.yml from this directory
# Or create it directly (see docker-compose.yml in this folder)

# Start Jenkins
docker compose up -d
```

### Step 2: Initial Jenkins Setup

1. **Access Jenkins UI:**
   ```
   http://178.156.223.196:8080
   ```

2. **Get initial admin password:**
   ```bash
   docker exec lb-jenkins cat /var/jenkins_home/secrets/initialAdminPassword
   ```

3. **Complete setup wizard:**
   - Install suggested plugins
   - Create admin user
   - Set Jenkins URL: `http://178.156.223.196:8080`

### Step 3: Install Required Plugins

Navigate to: **Manage Jenkins → Manage Plugins → Available**

Install these plugins:
- ✅ **Git plugin** (usually pre-installed)
- ✅ **Docker plugin**
- ✅ **Docker Pipeline**
- ✅ **SSH Agent**
- ✅ **Credentials Binding**
- ✅ **Pipeline**
- ✅ **Blue Ocean** (optional, better UI)

Restart Jenkins after installing plugins.

### Step 4: Configure Credentials

Navigate to: **Manage Jenkins → Manage Credentials → System → Global credentials**

Add the following credentials:

#### 4.1 SSH Private Key (for server deployment)

- **Kind:** SSH Username with private key
- **ID:** `server-ssh-key`
- **Username:** `lb-admin`
- **Private Key:** Enter directly or from file
  - Generate if needed:
    ```bash
    ssh-keygen -t rsa -b 4096 -f ~/.ssh/jenkins_deploy_key
    # Add public key to server's authorized_keys
    ssh-copy-id -i ~/.ssh/jenkins_deploy_key.pub lb-admin@178.156.223.196
    ```

#### 4.2 Docker Registry Credentials (if using private registry)

- **Kind:** Username with password
- **ID:** `dockerhub-credentials`
- **Username:** Your Docker Hub username
- **Password:** Your Docker Hub password or access token

#### 4.3 Application Secrets

Add these as **Secret text** credentials:

| Credential ID | Description | Example Value |
|--------------|-------------|---------------|
| `secret-key` | JWT signing key | Generate with: `openssl rand -hex 32` |
| `allowed-origins` | CORS origins | `http://178.156.223.196,http://localhost:5173` |
| `llm-provider` | LLM provider | `ollama` or `anthropic` |
| `anthropic-api-key` | Anthropic API key | `sk-ant-...` (optional) |
| `twilio-account-sid` | Twilio Account SID | (optional) |
| `twilio-auth-token` | Twilio Auth Token | (optional) |
| `twilio-phone-number` | Twilio Phone Number | (optional) |

### Step 5: Configure SSH Access in Jenkins

1. Navigate to: **Manage Jenkins → Configure System**
2. Scroll to **SSH remote hosts**
3. Add server:
   - **Hostname:** `178.156.223.196`
   - **Port:** `22`
   - **Credentials:** Select `server-ssh-key`
   - **Test Connection** to verify

### Step 6: Create Jenkins Pipeline Job

1. **New Item**
   - Name: `LB-Automotive-Dashboard`
   - Type: **Pipeline**
   - Click OK

2. **Configure Pipeline:**
   - **Description:** CI/CD pipeline for LB Automotive Dashboard

   - **Build Triggers:**
     - ☑ Poll SCM (if not using webhooks)
       - Schedule: `H/5 * * * *` (check every 5 minutes)
     - Or configure webhook from your Git provider

   - **Pipeline:**
     - **Definition:** Pipeline script from SCM
     - **SCM:** Git
     - **Repository URL:** Your Git repository URL
       - Example: `https://github.com/GameBox-Inc/lb-automotive-webapp.git`
     - **Credentials:** Add if private repo
     - **Branches to build:** `*/main`, `*/master`, `*/release/*`
     - **Script Path:** `Jenkinsfile`

3. **Save**

### Step 7: Configure Git Webhook (Optional, for instant builds)

#### For GitHub:

1. Go to your repository → **Settings → Webhooks**
2. Click **Add webhook**
3. **Payload URL:** `http://178.156.223.196:8080/github-webhook/`
4. **Content type:** `application/json`
5. **Which events:** Just the push event
6. **Active:** ☑ Checked
7. Save

#### For GitLab:

1. Go to your repository → **Settings → Webhooks**
2. **URL:** `http://178.156.223.196:8080/project/LB-Automotive-Dashboard`
3. **Trigger:** Push events
4. **Enable SSL verification:** Uncheck (if using HTTP)
5. Add webhook

### Step 8: Prepare Deployment Directory on Server

Make sure deployment script is executable:

```bash
cd /opt/lb-automotive-dashboard
chmod +x deployment/scripts/jenkins-deploy.sh

# Verify SSH key-based authentication works
ssh-add ~/.ssh/jenkins_deploy_key  # if not default key
ssh lb-admin@localhost "echo 'SSH works!'"
```

### Step 9: Configure Jenkins for SSH

Add SSH configuration to the Jenkins container so it can deploy (SSH to server) and clone the repo (SSH to GitHub). Either run the script or use the manual steps below.

**Note:** The container runs as the default `jenkins` user (not root). If you previously ran with `user: root`, after changing to the default user you may need to fix volume ownership once on the server: `docker run --rm -v jenkins_jenkins-data:/data alpine chown -R 1000:1000 /data` (then restart Jenkins).

**Option A: Run the setup script** (recommended; adds deploy server, localhost, and GitHub to `known_hosts`):

```bash
# From the repo root on the server
bash deployment/jenkins/configure-ssh.sh
```

**Option B: Manual steps**

```bash
# Copy SSH keys into Jenkins container
docker cp ~/.ssh/jenkins_deploy_key lb-jenkins:/var/jenkins_home/.ssh/id_rsa
docker cp ~/.ssh/jenkins_deploy_key.pub lb-jenkins:/var/jenkins_home/.ssh/id_rsa.pub

# Set permissions
docker exec lb-jenkins chown jenkins:jenkins /var/jenkins_home/.ssh/id_rsa
docker exec lb-jenkins chmod 600 /var/jenkins_home/.ssh/id_rsa

# Add server and GitHub to known_hosts (container runs as jenkins user; Git and deploy both use /var/jenkins_home/.ssh)
docker exec lb-jenkins mkdir -p /var/jenkins_home/.ssh
docker exec lb-jenkins sh -c 'ssh-keyscan -H 178.156.223.196 >> /var/jenkins_home/.ssh/known_hosts'
docker exec lb-jenkins sh -c 'ssh-keyscan -H localhost >> /var/jenkins_home/.ssh/known_hosts'
docker exec lb-jenkins sh -c 'ssh-keyscan -H github.com >> /var/jenkins_home/.ssh/known_hosts'
docker exec lb-jenkins chown -R jenkins:jenkins /var/jenkins_home/.ssh
```

---

## Testing the Pipeline

### Manual Build Test

1. Go to Jenkins Dashboard
2. Click on **LB-Automotive-Dashboard** job
3. Click **Build Now**
4. Watch the build progress (click on build number → Console Output)

### Expected Pipeline Flow

```
✓ Checkout          (Pull latest code)
✓ Setup Python      (Install backend dependencies)
✓ Backend Tests     (Run pytest)
✓ Setup Node        (Install frontend dependencies)
✓ Frontend Tests    (Run npm test)
✓ Build Images      (Build Docker images)
✓ Push Images       (Push to registry - optional)
✓ Deploy            (Deploy to production)
✓ Verify            (Health checks)
```

### Verify Deployment

After successful build:

```bash
# Check container status
docker compose -f /opt/lb-automotive-dashboard/deployment/docker/docker-compose.yml ps

# Test backend
curl http://178.156.223.196:8000/health

# Test frontend
curl http://178.156.223.196/
```

---

## Pipeline Configuration

### Jenkinsfile Location

The pipeline is defined in: `Jenkinsfile` (root of repository)

### Customizing the Pipeline

Edit `Jenkinsfile` to:
- Add/remove test stages
- Configure different build arguments
- Change deployment targets
- Add notifications (Slack, email, etc.)

### Branch-Specific Builds

Current configuration:
- **Tests:** Run on all branches
- **Build & Deploy:** Only on `main`, `master`, and `release/*` branches

To change:
```groovy
when {
    branch pattern: "main|master|release/.*|develop", comparator: "REGEXP"
}
```

---

## Deployment Script

Location: `deployment/scripts/jenkins-deploy.sh`

This script:
1. Creates `.env` file with secrets
2. Pulls latest code from git
3. Stops existing containers
4. Builds and starts new containers
5. Runs database migrations
6. Verifies deployment

### Manual Deployment

You can also run deployments manually:

```bash
cd /opt/lb-automotive-dashboard
bash deployment/scripts/jenkins-deploy.sh \
    "/opt/lb-automotive-dashboard" \
    "release/v0.1" \
    "$SECRET_KEY" \
    "$ALLOWED_ORIGINS" \
    "$LLM_PROVIDER" \
    "$ANTHROPIC_API_KEY" \
    "$TWILIO_ACCOUNT_SID" \
    "$TWILIO_AUTH_TOKEN" \
    "$TWILIO_PHONE_NUMBER"
```

---

## Firewall Configuration

### Restrict Jenkins Access

To limit Jenkins UI access to your IP only:

```bash
# Using UFW (Ubuntu Firewall)
sudo ufw allow from YOUR_IP_ADDRESS to any port 8080 proto tcp
sudo ufw deny 8080

# Using iptables
sudo iptables -A INPUT -p tcp --dport 8080 -s YOUR_IP_ADDRESS -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 8080 -j DROP
```

### Required Ports

| Port | Service | Access |
|------|---------|--------|
| 22 | SSH | Firewall/VPN only |
| 80 | HTTP Frontend | Behind firewall |
| 443 | HTTPS Frontend | Behind firewall |
| 8000 | Backend API | Behind firewall |
| 8080 | Jenkins UI | Restricted IP |
| 50000 | Jenkins Agent | Internal only |

---

## Monitoring & Logs

### Jenkins Logs

```bash
# Jenkins container logs
docker logs lb-jenkins -f

# View specific build logs
# Go to Jenkins UI → Build #X → Console Output
```

### Application Logs

```bash
# Backend logs
docker logs lb-auto-backend --tail 100 -f

# Frontend logs
docker logs lb-auto-frontend --tail 100 -f

# All containers
docker compose -f /opt/lb-automotive-dashboard/deployment/docker/docker-compose.yml logs -f
```

### Build History

Jenkins keeps build history at:
```
/var/jenkins_home/jobs/LB-Automotive-Dashboard/builds/
```

Access via:
```bash
docker exec lb-jenkins ls -lh /var/jenkins_home/jobs/LB-Automotive-Dashboard/builds/
```

---

## Troubleshooting

### Issue: Checkout fails with "No ED25519 host key is known for github.com" / "Host key verification failed"

The pipeline uses an SSH repo URL (`git@github.com:...`). The Jenkins container must have GitHub's host key in `known_hosts`.

**Quick fix (on the server):** Run the redirect inside the container so the file is created there (container runs as jenkins user, so Git uses `/var/jenkins_home/.ssh/known_hosts`):

```bash
docker exec lb-jenkins mkdir -p /var/jenkins_home/.ssh
docker exec lb-jenkins sh -c 'ssh-keyscan -H github.com >> /var/jenkins_home/.ssh/known_hosts'
docker exec lb-jenkins chown -R jenkins:jenkins /var/jenkins_home/.ssh
```

Then re-run the pipeline (Build Now). Then re-run the pipeline (Build Now).

### Issue: "Permission denied" during SSH deployment

**Solution:**
```bash
# Verify SSH key permissions
docker exec lb-jenkins ls -lh /var/jenkins_home/.ssh/
docker exec lb-jenkins chmod 600 /var/jenkins_home/.ssh/id_rsa

# Test SSH from Jenkins container
docker exec -it lb-jenkins ssh lb-admin@178.156.223.196 "echo 'SSH test'"
```

### Issue: "Docker command not found" in pipeline

**Solution:**
```bash
# Ensure Docker is accessible in Jenkins container
docker exec lb-jenkins which docker

# If missing, install Docker CLI in Jenkins:
docker exec -u root lb-jenkins apt-get update
docker exec -u root lb-jenkins apt-get install -y docker.io
```

### Issue: Tests failing in pipeline

**Solution:**
```bash
# Check test logs in build console output
# Verify environment variables are set correctly
# Run tests manually:
cd /opt/lb-automotive-dashboard/python-backend
python -m pytest --verbose
```

### Issue: Deployment fails with "unable to connect to server"

**Solution:**
```bash
# Verify network connectivity
docker exec lb-jenkins ping -c 3 178.156.223.196

# Check SSH configuration
docker exec lb-jenkins cat /var/jenkins_home/.ssh/config

# Verify server is accessible
ssh lb-admin@178.156.223.196 "echo 'Connection works'"
```

### Issue: "Credentials not found"

**Solution:**
1. Go to **Manage Jenkins → Manage Credentials**
2. Verify all credential IDs match those in Jenkinsfile:
   - `server-ssh-key`
   - `secret-key`
   - `allowed-origins`
   - etc.
3. Credentials must be in **Global** scope

---

## Backups

### Jenkins Configuration Backup

```bash
# Backup Jenkins home directory
docker exec lb-jenkins tar -czf /tmp/jenkins_backup.tar.gz /var/jenkins_home
docker cp lb-jenkins:/tmp/jenkins_backup.tar.gz ./jenkins_backup_$(date +%Y%m%d).tar.gz

# Or use volume backup
docker run --rm -v jenkins_jenkins-data:/data -v $(pwd):/backup \
    alpine tar czf /backup/jenkins_backup_$(date +%Y%m%d).tar.gz /data
```

### Restore Jenkins

```bash
# Stop Jenkins
docker compose down

# Restore backup
docker run --rm -v jenkins_jenkins-data:/data -v $(pwd):/backup \
    alpine tar xzf /backup/jenkins_backup_YYYYMMDD.tar.gz -C /

# Start Jenkins
docker compose up -d
```

---

## Maintenance

### Update Jenkins

```bash
cd /opt/jenkins
docker compose pull
docker compose up -d
```

### Clean Old Builds

Configure in Jenkins:
- **Job → Configure → Discard old builds**
- Keep last 10 builds
- Or keep builds from last 30 days

### Disk Space Management

```bash
# Check disk usage
df -h

# Clean Docker images
docker system prune -a

# Clean Jenkins workspace
docker exec lb-jenkins du -sh /var/jenkins_home/workspace/*
docker exec lb-jenkins rm -rf /var/jenkins_home/workspace/*/
```

---

## Migration from GitHub Actions

### Differences from GitHub Actions:

| Aspect | GitHub Actions | Jenkins |
|--------|----------------|---------|
| **Hosting** | GitHub cloud | Self-hosted |
| **Secrets** | GitHub Secrets | Jenkins Credentials |
| **Triggers** | GitHub webhooks | Polling or webhooks |
| **Execution** | GitHub runners | Jenkins agents |
| **Configuration** | `.github/workflows/*.yml` | `Jenkinsfile` |

### Disabling GitHub Actions

To disable the old GitHub Actions workflow:

1. Option 1: Delete workflow file:
   ```bash
   git rm .github/workflows/gamebox-engine.yaml
   git commit -m "Migrate to Jenkins CI/CD"
   git push
   ```

2. Option 2: Disable in GitHub UI:
   - Go to repository → **Actions**
   - Click on workflow → **Disable workflow**

3. Option 3: Stop self-hosted runner:
   ```bash
   # On server
   cd /opt/actions-runner
   ./svc.sh stop
   ./svc.sh uninstall
   ```

---

## Security Best Practices

1. **Restrict Jenkins UI access** to your IP only
2. **Use SSH key authentication**, not passwords
3. **Store secrets in Jenkins Credentials**, never in code
4. **Enable CSRF protection** (enabled by default)
5. **Keep Jenkins updated** regularly
6. **Use HTTPS** for Jenkins UI (configure reverse proxy)
7. **Regular backups** of Jenkins configuration
8. **Audit logs** - review build history and access logs

---

## Next Steps

1. ✅ Set up Jenkins server
2. ✅ Configure pipeline
3. ✅ Test deployment
4. 🔲 Configure HTTPS for Jenkins UI (optional)
5. 🔲 Set up build notifications (Slack/Email)
6. 🔲 Add production monitoring
7. 🔲 Configure backup automation

---

## Additional Resources

- **Jenkins Documentation:** https://www.jenkins.io/doc/
- **Pipeline Syntax:** https://www.jenkins.io/doc/book/pipeline/syntax/
- **Docker Plugin:** https://plugins.jenkins.io/docker-plugin/
- **SSH Plugin:** https://plugins.jenkins.io/ssh-agent/

---

## Support

For issues or questions:
1. Check Jenkins console output for errors
2. Review application logs: `docker logs lb-auto-backend`
3. Check deployment script: `deployment/scripts/jenkins-deploy.sh`
4. Verify credentials in Jenkins
5. Test SSH connectivity manually

---

**Last Updated:** February 2026
**Maintainer:** LB Automotive Team
