# 🚀 Deploy LB Automotive with Jenkins + ArgoCD

**Complete deployment guide for the Jenkins CI + ArgoCD CD pipeline**

---

## 📋 Prerequisites Checklist

✅ K3s installed and running (`kubectl get nodes` shows Ready)  
✅ ArgoCD installed in `argocd` namespace  
✅ Jenkins running with custom image (Python, Node, Docker CLI)  
✅ GitHub SSH credentials configured in Jenkins  
✅ GitHub personal access token (for GHCR)

---

## 🔐 Step 1: Configure Kubernetes Secrets

Run the interactive script to create all required secrets:

```bash
cd /opt/lb-automotive-dashboard
bash deployment/k8s/create-secrets.sh
```

**The script will prompt you for:**
- GitHub username and token (for GHCR image pulling)
- SECRET_KEY (or auto-generate)
- ALLOWED_ORIGINS (default: `https://kozytherocket.space`)
- Twilio credentials (optional)
- LLM provider (Anthropic or Ollama)
- Anthropic API key (if using Claude)

**Verify secrets created:**
```bash
kubectl get secrets -n lb-automotive
```

You should see:
- `ghcr-secret` (Docker registry)
- `app-secrets` (Application config)
- `anthropic-secrets` (optional, LLM)
- `twilio-secrets` (optional, IVR)

---

## 🔄 Step 2: Configure ArgoCD Repository Access

ArgoCD needs SSH access to your GitHub repository to watch for changes.

### Option A: Using SSH Key (Recommended)

```bash
# 1. Generate SSH key for ArgoCD (if not exists)
ssh-keygen -t ed25519 -C "argocd@lb-automotive" -f ~/.ssh/argocd_deploy_key -N ""

# 2. Add public key to GitHub
#    Go to: https://github.com/GameBox-Inc/lb-automotive-webapp/settings/keys
#    Click "Add deploy key"
#    Paste contents of:
cat ~/.ssh/argocd_deploy_key.pub

#    ✅ Check "Allow write access" (for status updates)

# 3. Create ArgoCD repository secret
kubectl create secret generic repo-secret \
  --from-file=sshPrivateKey=~/.ssh/argocd_deploy_key \
  --namespace=argocd \
  --dry-run=client -o yaml | kubectl apply -f -

# 4. Add repository to ArgoCD
kubectl apply -f - <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: lb-automotive-repo
  namespace: argocd
  labels:
    argocd.argoproj.io/secret-type: repository
stringData:
  type: git
  url: git@github.com:GameBox-Inc/lb-automotive-webapp.git
  sshPrivateKey: |
$(cat ~/.ssh/argocd_deploy_key | sed 's/^/    /')
EOF
```

### Option B: Using Personal Access Token

```bash
# Create secret with token
kubectl create secret generic lb-automotive-repo \
  --from-literal=type=git \
  --from-literal=url=https://github.com/GameBox-Inc/lb-automotive-webapp.git \
  --from-literal=username=gamebox-inc \
  --from-literal=password=<YOUR_GITHUB_TOKEN> \
  --namespace=argocd \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl label secret lb-automotive-repo \
  argocd.argoproj.io/secret-type=repository \
  --namespace=argocd
```

**Verify repository connection:**
```bash
# Check ArgoCD can access the repo
kubectl logs -n argocd deployment/argocd-repo-server | grep "lb-automotive"
```

---

## 📦 Step 3: Deploy Application via ArgoCD

Deploy the ArgoCD Application resource:

```bash
cd /opt/lb-automotive-dashboard
kubectl apply -f deployment/argocd/lb-automotive-app.yaml
```

**Monitor deployment:**
```bash
# Watch ArgoCD sync the application
kubectl get applications -n argocd -w

# Check application status
kubectl get pods -n lb-automotive -w

# View ArgoCD logs
kubectl logs -n argocd deployment/argocd-application-controller -f
```

**Access ArgoCD UI (Optional):**
```bash
# Port-forward ArgoCD UI
kubectl port-forward svc/argocd-server -n argocd 8080:443

# Get admin password
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d

# Open browser to: https://localhost:8080
# Username: admin
# Password: (from command above)
```

---

## 🔨 Step 4: Configure Jenkins Pipeline

### 4.1: Add GHCR Token to Jenkins

1. Open Jenkins: `http://<server-ip>:8080`
2. Go to **Manage Jenkins** → **Credentials** → **(global)**
3. Click **Add Credentials**
4. Create:
   - **Kind**: Secret text
   - **Secret**: `<your-github-token>`
   - **ID**: `ghcr-token`
   - **Description**: GitHub Container Registry Token

### 4.2: Verify Existing Credentials

Ensure you have:
- ✅ `github-ssh-key` (SSH credentials for Git clone/push)
- ✅ `ghcr-token` (Secret text for Docker login)

### 4.3: Create/Update Jenkins Pipeline Job

1. **New Item** → **Pipeline** → Name: `LB-Automotive-ArgoCD-Pipeline`
2. **Pipeline** section:
   - **Definition**: Pipeline script
   - **Script**: Copy contents from `deployment/jenkins/Jenkinsfile.argocd`
3. **Save**

---

## 🧪 Step 5: Test Complete Pipeline

### 5.1: Trigger Jenkins Build

```bash
# Method 1: Trigger from Jenkins UI
# Click "Build Now" on the pipeline

# Method 2: Trigger via CLI (if Jenkins CLI configured)
java -jar jenkins-cli.jar -s http://localhost:8080/ build LB-Automotive-ArgoCD-Pipeline

# Method 3: Push to release/v0.1 branch (triggers webhook if configured)
cd /opt/lb-automotive-dashboard
echo "# Test deployment" >> README.md
git add README.md
git commit -m "Test: Trigger Jenkins build"
git push origin release/v0.1
```

### 5.2: Monitor Build Progress

**Jenkins side:**
```bash
# Watch Jenkins logs
docker logs -f lb-jenkins

# Check build status
curl -u admin:<jenkins-token> http://localhost:8080/job/LB-Automotive-ArgoCD-Pipeline/lastBuild/api/json | jq
```

**ArgoCD side:**
```bash
# Watch for manifest updates
kubectl get applications -n argocd -w

# Check if ArgoCD detected changes
kubectl describe application lb-automotive -n argocd | grep -A 10 "Sync Status"

# Watch pods rolling update
kubectl get pods -n lb-automotive -w
```

### 5.3: Expected Flow

1. ✅ Jenkins clones repo
2. ✅ Runs backend tests (pytest)
3. ✅ Runs frontend tests (npm test)
4. ✅ Builds Docker images
5. ✅ Pushes to GHCR (`ghcr.io/gamebox-inc/lb-automotive-{backend,frontend}:<tag>`)
6. ✅ Updates K8s manifests with new image tags
7. ✅ Commits and pushes manifest changes to Git
8. ✅ ArgoCD detects Git changes
9. ✅ ArgoCD syncs application (pulls new images, updates pods)
10. ✅ New version running in K8s

---

## 🌐 Step 6: Configure Ingress (Production Traffic)

Once deployment is working, expose the application:

### 6.1: Update Ingress with Your Domain

Edit `deployment/k8s/ingress.yaml`:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: lb-automotive-ingress
  namespace: lb-automotive
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
    kubernetes.io/ingress.class: traefik
spec:
  tls:
  - hosts:
    - kozytherocket.space
    secretName: lb-automotive-tls
  rules:
  - host: kozytherocket.space
    http:
      paths:
      - path: /api
        pathType: Prefix
        backend:
          service:
            name: backend
            port:
              number: 8000
      - path: /
        pathType: Prefix
        backend:
          service:
            name: frontend
            port:
              number: 80
```

Apply:
```bash
kubectl apply -f deployment/k8s/ingress.yaml
```

### 6.2: Test Application Access

```bash
# Check ingress status
kubectl get ingress -n lb-automotive

# Test backend API
curl http://<server-ip>/api/health

# Test frontend
curl http://<server-ip>/

# If using domain, update DNS A record to point to server IP
# Then test:
curl https://kozytherocket.space/api/health
```

---

## 📊 Step 7: Monitor & Verify

### 7.1: Check All Components

```bash
# K3s cluster
kubectl get nodes
kubectl top nodes

# ArgoCD
kubectl get applications -n argocd
kubectl get pods -n argocd

# Application pods
kubectl get pods -n lb-automotive
kubectl get svc -n lb-automotive
kubectl get ingress -n lb-automotive

# Persistent volumes
kubectl get pvc -n lb-automotive
```

### 7.2: Check Application Logs

```bash
# Backend logs
kubectl logs -n lb-automotive deployment/backend -f

# Frontend logs
kubectl logs -n lb-automotive deployment/frontend -f

# Check for errors
kubectl get events -n lb-automotive --sort-by='.lastTimestamp'
```

### 7.3: Test Application Functionality

1. ✅ Login works
2. ✅ Appointments CRUD
3. ✅ Customer management
4. ✅ Services management
5. ✅ IVR integration (if Twilio configured)

---

## 🔄 Step 8: Continuous Deployment Workflow

From now on, deployments are fully automated:

### Developer Workflow:
```bash
# 1. Make code changes
vim python-backend/routes/appointments.py

# 2. Commit and push to release/v0.1
git add .
git commit -m "feat: Add appointment notifications"
git push origin release/v0.1

# 3. Jenkins automatically:
#    - Runs tests
#    - Builds images
#    - Updates K8s manifests
#    - Pushes manifest changes

# 4. ArgoCD automatically:
#    - Detects manifest changes
#    - Syncs application
#    - Rolls out new version

# 5. Monitor deployment
kubectl get pods -n lb-automotive -w
```

### Manual Sync (if needed):
```bash
# Trigger manual ArgoCD sync
kubectl patch application lb-automotive \
  -n argocd \
  --type merge \
  -p '{"operation":{"initiatedBy":{"username":"admin"},"sync":{"revision":"HEAD"}}}'
```

---

## 🚨 Troubleshooting

### Jenkins Build Fails

```bash
# Check Jenkins logs
docker logs lb-jenkins --tail 100

# Check workspace
docker exec lb-jenkins ls -la /var/jenkins_home/workspace/LB-Automotive-ArgoCD-Pipeline/

# Check credentials
docker exec lb-jenkins cat /var/jenkins_home/.ssh/known_hosts
```

### ArgoCD Not Syncing

```bash
# Check repository connection
kubectl get secrets -n argocd | grep repo

# Check application status
kubectl describe application lb-automotive -n argocd

# Check ArgoCD logs
kubectl logs -n argocd deployment/argocd-repo-server -f
kubectl logs -n argocd deployment/argocd-application-controller -f
```

### Pods Not Starting

```bash
# Check pod status
kubectl describe pod <pod-name> -n lb-automotive

# Check image pull
kubectl get events -n lb-automotive | grep "Failed to pull"

# Verify secrets exist
kubectl get secrets -n lb-automotive
```

### Image Pull Errors

```bash
# Verify GHCR secret
kubectl get secret ghcr-secret -n lb-automotive -o yaml

# Test image pull manually
docker login ghcr.io -u gamebox-inc -p <token>
docker pull ghcr.io/gamebox-inc/lb-automotive-backend:latest

# Recreate secret if needed
kubectl delete secret ghcr-secret -n lb-automotive
bash deployment/k8s/create-secrets.sh
```

---

## 📝 Post-Deployment Checklist

- [ ] Secrets configured and working
- [ ] ArgoCD connected to GitHub
- [ ] Application deployed and healthy
- [ ] Jenkins pipeline tested successfully
- [ ] Ingress configured (if production)
- [ ] DNS pointing to server (if using domain)
- [ ] Monitoring enabled
- [ ] Backup strategy in place
- [ ] Rollback plan documented

---

## 🎯 Success Criteria

Your deployment is successful when:

1. ✅ `kubectl get pods -n lb-automotive` shows all pods Running
2. ✅ `kubectl get applications -n argocd` shows "Synced" and "Healthy"
3. ✅ Pushing code to `release/v0.1` triggers automatic deployment
4. ✅ Application accessible via ingress/domain
5. ✅ No errors in pod logs

---

## 🔙 Rollback Plan

If deployment fails:

### Quick Rollback via ArgoCD:
```bash
# Sync to previous Git commit
kubectl patch application lb-automotive \
  -n argocd \
  --type merge \
  -p '{"spec":{"source":{"targetRevision":"<previous-commit-sha>"}}}'
```

### Emergency: Switch Back to Docker Compose:
```bash
cd /opt/lb-automotive-dashboard/deployment/docker
docker-compose up -d
```

---

## 📚 Additional Resources

- ArgoCD Docs: https://argo-cd.readthedocs.io/
- Jenkins Pipeline Syntax: https://www.jenkins.io/doc/book/pipeline/
- K3s Docs: https://docs.k3s.io/
- GitHub Actions → Jenkins migration guide: `JENKINS_ARGOCD_MIGRATION.md`

---

**🎉 You now have a production-ready Jenkins + ArgoCD CI/CD pipeline!**

For questions or issues, check:
- `JENKINS_ARGOCD_MIGRATION.md` for migration details
- `deployment/argocd/SETUP.md` for ArgoCD configuration
- `deployment/STORAGE_OPTIMIZATION.md` for disk management
