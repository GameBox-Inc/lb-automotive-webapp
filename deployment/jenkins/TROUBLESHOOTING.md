# Jenkins Pipeline Troubleshooting Guide

## Error: "fatal: not in a git directory"

### Symptoms
```
hudson.plugins.git.GitException: Command "git config remote.origin.url git@github.com:GameBox-Inc/lb-automotive-webapp.git" returned status code 128:
stderr: fatal: not in a git directory
```

### Root Cause
Jenkins cannot authenticate with GitHub to clone the repository. The SSH key credential is either:
1. Not configured in Jenkins
2. Not added to GitHub
3. Not accessible to the Jenkins process

### Solution Options

#### Option 1: Manual UI Configuration (Quickest)

1. **Generate or locate your GitHub SSH key:**
   ```bash
   # If you don't have one, generate it:
   ssh-keygen -t ed25519 -C "jenkins@lb-automotive" -f ~/.ssh/github_lb_automotive
   
   # Display the public key:
   cat ~/.ssh/github_lb_automotive.pub
   ```

2. **Add the public key to GitHub:**
   - Go to https://github.com/settings/keys
   - Click "New SSH key"
   - Paste your public key
   - Give it a title like "Jenkins LB Automotive"
   - Click "Add SSH key"

3. **Add the SSH credential to Jenkins:**
   - Go to Jenkins UI: http://178.156.223.196:8080
   - Navigate to: **Manage Jenkins** → **Manage Credentials**
   - Click on **(global)** domain
   - Click **Add Credentials**
   - Fill in:
     - **Kind**: SSH Username with private key
     - **ID**: `github-ssh-key`
     - **Username**: `git`
     - **Private Key**: Select "Enter directly"
     - Paste your **private key** (from `~/.ssh/github_lb_automotive`)
     - **Description**: GitHub SSH Deploy Key
   - Click **Create**

4. **Verify the pipeline job uses this credential:**
   - Go to your pipeline job: **LB-Automotive-Dashboard-Pipeline**
   - Click **Configure**
   - Under **Pipeline** → **Definition** → **SCM** → **Git**
   - Verify **Credentials** is set to `git (github-ssh-key)`
   - Click **Save**

5. **Test the connection:**
   - Click **Build Now** on your pipeline job

#### Option 2: Automated Script Configuration

Run the provided script to automatically configure GitHub SSH:

```bash
# On your server (178.156.223.196)
cd /path/to/lb-automotive-dashboard
chmod +x deployment/jenkins/configure-github-ssh.sh
./deployment/jenkins/configure-github-ssh.sh
```

Then manually add the credential in Jenkins UI (steps 3-5 from Option 1).

#### Option 3: Use HTTPS Instead of SSH

If you prefer to avoid SSH key management:

1. **Update the repository URL in Jenkins:**
   - Go to your pipeline job configuration
   - Change the Git URL from:
     - `git@github.com:GameBox-Inc/lb-automotive-webapp.git`
     - To: `https://github.com/GameBox-Inc/lb-automotive-webapp.git`

2. **Add GitHub credentials:**
   - Create a GitHub Personal Access Token:
     - Go to https://github.com/settings/tokens
     - Click "Generate new token (classic)"
     - Select scopes: `repo` (full control)
     - Copy the token
   
   - Add to Jenkins:
     - **Manage Jenkins** → **Manage Credentials** → **Add Credentials**
     - **Kind**: Username with password
     - **Username**: Your GitHub username
     - **Password**: Your personal access token
     - **ID**: `github-https-token`
     - Click **Create**

3. **Update pipeline job to use HTTPS credential**

4. **Update `jenkins-casc.yaml`:**
   ```yaml
   git {
     remote {
       url('https://github.com/GameBox-Inc/lb-automotive-webapp.git')
       credentials('github-https-token')
     }
     branch('*/release/v0.1')
   }
   ```

---

## Other Common Jenkins Issues

### Issue: Docker build fails

**Error**: `docker.build()` syntax error

**Fix**: Update Jenkinsfile lines 120-143 to use correct syntax:

```groovy
script {
    def backendImage = docker.build(
        "${BACKEND_IMAGE}:${BUILD_TAG}",
        "-f deployment/docker/Dockerfile.backend ."
    )
    backendImage.tag("latest")
}
```

### Issue: SSH deployment fails

**Error**: Permission denied when deploying to server

**Fix**: Ensure deployment SSH keys are configured:

```bash
./deployment/jenkins/configure-ssh.sh
```

### Issue: Pipeline doesn't trigger on push

**Fix**: Configure GitHub webhook:
1. Go to your GitHub repository settings
2. Navigate to **Webhooks** → **Add webhook**
3. Payload URL: `http://178.156.223.196:8080/github-webhook/`
4. Content type: `application/json`
5. Select: "Just the push event"
6. Click **Add webhook**

---

## Verification Steps

After fixing the SSH issue, verify everything works:

1. **Test GitHub SSH connection from Jenkins container:**
   ```bash
   docker exec -u jenkins lb-jenkins ssh -T git@github.com
   ```
   
   Expected output: `Hi GameBox-Inc! You've successfully authenticated...`

2. **Manually trigger a build:**
   - Go to Jenkins UI
   - Click on your pipeline job
   - Click **Build Now**
   - Watch the console output

3. **Check the logs:**
   ```bash
   docker logs lb-jenkins -f
   ```

---

## Quick Reference

### Useful Commands

```bash
# View Jenkins logs
docker logs lb-jenkins -f

# Restart Jenkins
cd /opt/jenkins && docker compose restart

# Access Jenkins container
docker exec -it lb-jenkins bash

# Test SSH from Jenkins
docker exec -u jenkins lb-jenkins ssh -T git@github.com

# View Jenkins home directory
docker exec lb-jenkins ls -la /var/jenkins_home/.ssh/
```

### Important Paths

- Jenkins home: `/var/jenkins_home`
- SSH keys in container: `/var/jenkins_home/.ssh/`
- Configuration: `/var/jenkins_home/jenkins.yaml`
- Credentials: Stored in Jenkins (encrypted)

### Important URLs

- Jenkins UI: http://178.156.223.196:8080
- GitHub SSH Keys: https://github.com/settings/keys
- GitHub Tokens: https://github.com/settings/tokens
- Repository: https://github.com/GameBox-Inc/lb-automotive-webapp
