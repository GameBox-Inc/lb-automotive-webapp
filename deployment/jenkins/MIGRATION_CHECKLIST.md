# GitHub Actions → Jenkins Migration Checklist

Complete migration guide from GitHub Actions to Jenkins CI/CD.

---

## Phase 1: Preparation (Before Migration)

### 1.1 Verify Current Setup

- [ ] Confirm GitHub Actions is working
- [ ] Document current deployment process
- [ ] List all secrets used in GitHub Actions
- [ ] Note any custom workflows or integrations
- [ ] Backup current deployment configuration

### 1.2 Server Prerequisites

- [ ] SSH access to server (lb-admin@178.156.223.196)
- [ ] Docker installed and running
- [ ] Docker Compose installed
- [ ] Sufficient disk space (check with `df -h`)
- [ ] Port 8080 available for Jenkins

### 1.3 Collect Secrets

Gather these values from GitHub Secrets or your secure storage:

- [ ] `SECRET_KEY` (JWT signing key)
- [ ] `ALLOWED_ORIGINS` (CORS origins)
- [ ] `LLM_PROVIDER` (ollama or anthropic)
- [ ] `ANTHROPIC_API_KEY` (if using Anthropic)
- [ ] `TWILIO_ACCOUNT_SID` (if using Twilio)
- [ ] `TWILIO_AUTH_TOKEN` (if using Twilio)
- [ ] `TWILIO_PHONE_NUMBER` (if using Twilio)

---

## Phase 2: Jenkins Setup

### 2.1 Install Jenkins

- [ ] SSH into server: `ssh lb-admin@178.156.223.196`
- [ ] Navigate to repo: `cd /opt/lb-automotive-dashboard`
- [ ] Make setup script executable: `chmod +x deployment/jenkins/setup-jenkins.sh`
- [ ] Run setup: `bash deployment/jenkins/setup-jenkins.sh`
- [ ] Save initial admin password shown in output
- [ ] Verify Jenkins is running: `docker ps | grep lb-jenkins`

### 2.2 Initial Jenkins Configuration

- [ ] Open Jenkins UI: `http://178.156.223.196:8080`
- [ ] Enter initial admin password
- [ ] Install suggested plugins
- [ ] Create admin user account
- [ ] Set Jenkins URL to: `http://178.156.223.196:8080`
- [ ] Complete setup wizard

### 2.3 Install Required Plugins

Navigate to: **Manage Jenkins** → **Manage Plugins** → **Available**

- [ ] Docker Pipeline
- [ ] SSH Agent
- [ ] Credentials Binding
- [ ] Pipeline (usually pre-installed)
- [ ] Git (usually pre-installed)
- [ ] Blue Ocean (optional, for better UI)

After installation:
- [ ] Restart Jenkins if required
- [ ] Verify plugins are active: **Manage Jenkins** → **Manage Plugins** → **Installed**

### 2.4 Configure SSH Access

- [ ] Add SSH public key to authorized_keys:
  ```bash
  cat ~/.ssh/jenkins_deploy_key.pub >> ~/.ssh/authorized_keys
  ```
- [ ] Run SSH configuration script:
  ```bash
  chmod +x deployment/jenkins/configure-ssh.sh
  bash deployment/jenkins/configure-ssh.sh
  ```
- [ ] Verify SSH connection works (script will confirm)
- [ ] Test manual SSH: `ssh -i ~/.ssh/jenkins_deploy_key lb-admin@178.156.223.196 "echo test"`

---

## Phase 3: Jenkins Configuration

### 3.1 Add Credentials

Go to: **Manage Jenkins** → **Manage Credentials** → **System** → **Global credentials**

Add each credential as **Secret text**:

- [ ] ID: `secret-key`, Value: (your SECRET_KEY)
- [ ] ID: `allowed-origins`, Value: `http://178.156.223.196,http://localhost:5173`
- [ ] ID: `llm-provider`, Value: `ollama`
- [ ] ID: `anthropic-api-key`, Value: (your key or leave blank)
- [ ] ID: `twilio-account-sid`, Value: (your SID or leave blank)
- [ ] ID: `twilio-auth-token`, Value: (your token or leave blank)
- [ ] ID: `twilio-phone-number`, Value: (your number or leave blank)

Verify:
- [ ] All credentials are added
- [ ] All IDs match exactly (case-sensitive)
- [ ] Scope is set to **Global** for all

### 3.2 Create Pipeline Job

- [ ] Click **New Item**
- [ ] Name: `LB-Automotive-Dashboard`
- [ ] Type: **Pipeline**
- [ ] Click **OK**

Configure the job:

- [ ] Set description: "CI/CD pipeline for LB Automotive Dashboard"
- [ ] **Build Triggers** → ☑ Poll SCM
- [ ] Schedule: `H/5 * * * *` (checks every 5 minutes)
- [ ] **Pipeline** → Definition: **Pipeline script from SCM**
- [ ] SCM: **Git**
- [ ] Repository URL: (your Git repository URL)
- [ ] Credentials: (add if private repository)
- [ ] Branch Specifier: `*/release/v0.1` (or your branch)
- [ ] Script Path: `Jenkinsfile`
- [ ] Click **Save**

### 3.3 Configure Git Integration

#### Option A: Webhook (Recommended for instant builds)

**For GitHub:**
- [ ] Go to repository → **Settings** → **Webhooks**
- [ ] Click **Add webhook**
- [ ] Payload URL: `http://178.156.223.196:8080/github-webhook/`
- [ ] Content type: `application/json`
- [ ] Select: **Just the push event**
- [ ] ☑ Active
- [ ] Click **Add webhook**
- [ ] Test webhook (should see green checkmark)

**For GitLab:**
- [ ] Go to repository → **Settings** → **Webhooks**
- [ ] URL: `http://178.156.223.196:8080/project/LB-Automotive-Dashboard`
- [ ] Trigger: ☑ Push events
- [ ] Click **Add webhook**

#### Option B: Polling (If webhook not available)

- [ ] Already configured in pipeline job (H/5 * * * *)
- [ ] Jenkins will check for changes every 5 minutes

---

## Phase 4: Testing

### 4.1 Test Pipeline Manually

- [ ] Go to Jenkins → `LB-Automotive-Dashboard` job
- [ ] Click **Build Now**
- [ ] Click on build number (e.g., #1)
- [ ] Click **Console Output**
- [ ] Verify each stage completes:
  - [ ] ✓ Checkout
  - [ ] ✓ Setup Python Environment
  - [ ] ✓ Backend Tests
  - [ ] ✓ Setup Node Environment
  - [ ] ✓ Frontend Tests
  - [ ] ✓ Build Docker Images
  - [ ] ✓ Deploy to Production
  - [ ] ✓ Verify Deployment
- [ ] Build completes with **SUCCESS** status

### 4.2 Verify Deployment

After successful build:

- [ ] Backend health check: `curl http://178.156.223.196:8000/health`
- [ ] Frontend check: `curl http://178.156.223.196/`
- [ ] Check containers: `docker compose -f /opt/lb-automotive-dashboard/deployment/docker/docker-compose.yml ps`
- [ ] Verify all containers are **Up**
- [ ] Check backend logs: `docker logs lb-auto-backend --tail 50`
- [ ] Check frontend logs: `docker logs lb-auto-frontend --tail 50`

### 4.3 Test Automatic Builds

- [ ] Make a small code change (e.g., update a comment)
- [ ] Commit and push to your branch
- [ ] Wait for Jenkins to detect change (up to 5 min if polling)
- [ ] Verify build triggers automatically
- [ ] Verify deployment succeeds
- [ ] Verify application is updated

---

## Phase 5: Migration Completion

### 5.1 Disable GitHub Actions

Choose one option:

**Option A: Stop Self-Hosted Runner**
- [ ] SSH to server
- [ ] `cd /opt/actions-runner`
- [ ] `./svc.sh stop`
- [ ] `./svc.sh uninstall`
- [ ] Verify stopped: `./svc.sh status`

**Option B: Disable Workflow in GitHub**
- [ ] Go to repository → **Actions**
- [ ] Click on workflow
- [ ] Click **...** menu → **Disable workflow**

**Option C: Delete Workflow File** (Most permanent)
- [ ] `git rm .github/workflows/gamebox-engine.yaml`
- [ ] `git commit -m "chore: Migrate to Jenkins CI/CD"`
- [ ] `git push`

### 5.2 Update Documentation

- [ ] Update `CLAUDE.md` with Jenkins info
- [ ] Remove/update GitHub Actions references
- [ ] Add Jenkins URLs and access info
- [ ] Update deployment instructions

### 5.3 Security Hardening

- [ ] Restrict Jenkins UI access to your IP:
  ```bash
  sudo ufw allow from YOUR_IP to any port 8080 proto tcp
  sudo ufw deny 8080
  ```
- [ ] Set up Jenkins user permissions (if needed)
- [ ] Enable CSRF protection (enabled by default)
- [ ] Configure SSL/TLS for Jenkins (optional)

### 5.4 Backup Setup

- [ ] Create Jenkins backup script:
  ```bash
  docker exec lb-jenkins tar -czf /tmp/jenkins_backup.tar.gz /var/jenkins_home
  docker cp lb-jenkins:/tmp/jenkins_backup.tar.gz ./jenkins_backup_$(date +%Y%m%d).tar.gz
  ```
- [ ] Test restore procedure
- [ ] Schedule regular backups (cron job)
- [ ] Store backups securely

---

## Phase 6: Post-Migration

### 6.1 Monitoring Setup

- [ ] Set up build notifications (email/Slack)
  - Navigate to: **Manage Jenkins** → **Configure System**
  - Configure email server or Slack integration
  - Add notifications to Jenkinsfile if desired

- [ ] Monitor Jenkins resources:
  ```bash
  docker stats lb-jenkins
  ```

- [ ] Set up Jenkins monitoring dashboard (optional)
  - Consider Prometheus + Grafana integration

### 6.2 Performance Optimization

- [ ] Configure build discard policy:
  - Job → **Configure** → **Discard old builds**
  - Keep last 10 builds
- [ ] Clean Docker images regularly:
  ```bash
  docker system prune -a
  ```
- [ ] Monitor disk usage: `df -h`
- [ ] Set up log rotation for Jenkins

### 6.3 Team Onboarding

- [ ] Document Jenkins access for team:
  - URL: `http://178.156.223.196:8080`
  - How to view builds
  - How to trigger manual builds
  - How to access logs

- [ ] Create team accounts in Jenkins (if needed)
- [ ] Set up appropriate permissions
- [ ] Share documentation (README.md, QUICKSTART.md)

### 6.4 Validation Period

Run for 1-2 weeks and verify:

- [ ] All builds succeed automatically
- [ ] Deployments work reliably
- [ ] No issues with secrets/credentials
- [ ] Performance is acceptable
- [ ] Team is comfortable with new setup
- [ ] Backups are working
- [ ] Monitoring is effective

---

## Rollback Plan (If Needed)

If issues arise, you can quickly rollback:

### Rollback to GitHub Actions:

1. [ ] Re-enable GitHub Actions workflow:
   ```bash
   git revert <commit-hash>  # If workflow was deleted
   git push
   ```

2. [ ] Restart self-hosted runner:
   ```bash
   cd /opt/actions-runner
   ./svc.sh install
   ./svc.sh start
   ```

3. [ ] Verify GitHub Actions is working
4. [ ] Stop Jenkins (but keep for investigation):
   ```bash
   cd /opt/jenkins
   docker compose stop
   ```

---

## Completion Checklist

### Final Verification:

- [ ] Jenkins is running and accessible
- [ ] All tests pass in Jenkins pipeline
- [ ] Deployments work automatically
- [ ] Application is running correctly
- [ ] GitHub Actions is disabled
- [ ] Documentation is updated
- [ ] Team is onboarded
- [ ] Backups are configured
- [ ] Monitoring is in place
- [ ] Security is hardened

### Success Criteria:

✅ Jenkins builds trigger automatically on git push
✅ All stages complete successfully
✅ Application deploys correctly
✅ No manual intervention needed for deployments
✅ Team can access and use Jenkins
✅ Old GitHub Actions workflow is disabled

---

## Troubleshooting Reference

### Common Issues:

| Issue | Solution |
|-------|----------|
| Jenkins UI not accessible | Check: `docker ps`, firewall rules |
| Build fails on SSH step | Run: `deployment/jenkins/configure-ssh.sh` |
| Credentials not found | Verify credential IDs match exactly |
| Permission denied | Check SSH keys and authorized_keys |
| Deployment fails | Check logs: `docker logs lb-jenkins` |
| Tests fail | Verify environment variables are set |

### Getting Help:

1. **Check logs:**
   ```bash
   docker logs lb-jenkins -f
   docker logs lb-auto-backend -f
   ```

2. **Review console output** in Jenkins UI

3. **Verify SSH connection:**
   ```bash
   ssh -i ~/.ssh/jenkins_deploy_key lb-admin@178.156.223.196
   ```

4. **Check documentation:**
   - `deployment/jenkins/README.md` (full docs)
   - `deployment/jenkins/QUICKSTART.md` (quick guide)

---

## Migration Timeline

**Total Estimated Time:** 2-3 hours

| Phase | Duration | Can Skip If |
|-------|----------|------------|
| Phase 1: Preparation | 30 min | - |
| Phase 2: Jenkins Setup | 30 min | - |
| Phase 3: Configuration | 30 min | - |
| Phase 4: Testing | 30 min | - |
| Phase 5: Migration | 30 min | - |
| Phase 6: Post-Migration | Ongoing | Not mission-critical |

---

## Notes

- Keep GitHub Actions disabled but intact for first week (rollback option)
- Monitor Jenkins closely for first few deployments
- Document any custom configurations or issues encountered
- Consider setting up staging environment first

---

**Status:** Ready to migrate
**Risk Level:** Low (rollback plan available)
**Recommended Time:** Outside business hours

Good luck with the migration! 🚀
