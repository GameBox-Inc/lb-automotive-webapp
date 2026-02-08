# Migration Guide: GitHub Actions → Jenkins + ArgoCD

## Executive Summary

**Current:** GitHub Actions handles both CI and CD, deploying via SSH to server running docker-compose.

**Proposed:** Jenkins handles CI (build/test), ArgoCD handles CD (Kubernetes deployment).

**Timeline:** 1-2 days for initial setup, 1 week for full migration and testing.

**Risk Level:** Medium (requires Kubernetes cluster, but can run parallel to existing setup)

## Why Migrate?

### Current Pain Points
- ❌ GitHub Actions + docker-compose not ideal for production K8s
- ❌ Manual rollbacks difficult
- ❌ No drift detection
- ❌ Deployment state not in Git (server state can drift)
- ❌ SSH-based deployment less secure
- ❌ Limited deployment visibility

### Benefits of Jenkins + ArgoCD
- ✅ True GitOps workflow (all state in Git)
- ✅ Automatic drift detection and healing
- ✅ Easy rollbacks (git revert)
- ✅ Better for Kubernetes (native K8s deployment)
- ✅ Separation of concerns (CI vs CD)
- ✅ Visual deployment tracking (ArgoCD UI)
- ✅ Self-healing deployments
- ✅ Multi-environment support (dev/staging/prod)

## Prerequisites

### Required Infrastructure
- [ ] Kubernetes cluster (K3s, K8s, EKS, GKE, etc.)
- [ ] `kubectl` access to cluster
- [ ] Jenkins server (you already have this)
- [ ] GitHub Container Registry access

### Current Status
- ✅ Jenkins server running
- ✅ Docker images pushed to GHCR
- ✅ K8s manifests exist (`deployment/k8s/`)
- ✅ ArgoCD manifests prepared (`deployment/argocd/`)
- ⚠️ Jenkins pipeline needs fixing (in progress)
- ❌ Kubernetes cluster not yet running
- ❌ ArgoCD not installed

## Migration Checklist

### Phase 1: Kubernetes Setup (Day 1)

#### 1.1 Install Kubernetes on Server

Choose one:

**Option A: K3s (Recommended for single-server)**
```bash
# On server (178.156.223.196)
curl -sfL https://get.k3s.io | sh -

# Verify
sudo k3s kubectl get nodes

# Get kubeconfig
sudo cat /etc/rancher/k3s/k3s.yaml

# Copy kubeconfig to local machine for kubectl access
```

**Option B: Full Kubernetes**
```bash
# Follow official K8s installation
# More complex but production-ready
```

**Option C: Cloud Kubernetes (Managed)**
- AWS EKS
- Google GKE  
- Azure AKS
- DigitalOcean Kubernetes

#### 1.2 Verify Kubernetes

```bash
# Check nodes
kubectl get nodes

# Check system pods
kubectl get pods -A

# Create test deployment
kubectl run nginx --image=nginx
kubectl get pods
kubectl delete pod nginx
```

#### 1.3 Install Basic Components

```bash
# Install Nginx Ingress Controller
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.8.1/deploy/static/provider/cloud/deploy.yaml

# Verify ingress
kubectl get pods -n ingress-nginx
```

### Phase 2: ArgoCD Setup (Day 1-2)

#### 2.1 Install ArgoCD

```bash
# Create namespace
kubectl create namespace argocd

# Install ArgoCD
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Wait for ready
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=argocd-server -n argocd --timeout=300s

# Verify
kubectl get pods -n argocd
```

#### 2.2 Access ArgoCD UI

```bash
# Port forward (temporary)
kubectl port-forward svc/argocd-server -n argocd 8080:443

# Get initial password
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d

# Access: https://localhost:8080
# Username: admin
# Password: (from above)
```

#### 2.3 Configure GitHub Access

```bash
# Generate deploy key for ArgoCD
ssh-keygen -t ed25519 -C "argocd@lb-automotive" -f argocd-deploy-key -N ""

# Add public key to GitHub:
# https://github.com/GameBox-Inc/lb-automotive-webapp/settings/keys

# Add to ArgoCD
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
$(cat argocd-deploy-key | sed 's/^/    /')
EOF
```

#### 2.4 Deploy Application

```bash
# Apply ArgoCD application
kubectl apply -f deployment/argocd/application.yaml

# Check status
kubectl get application -n argocd
kubectl describe application lb-automotive -n argocd
```

### Phase 3: Update Jenkins Pipeline (Day 2)

#### 3.1 Fix Current Jenkins Issues

**Current Status:** Jenkins pipeline failing with "not in a git directory" error.

**Options:**
1. ✅ **Manual git checkout** (recommended for now)
2. Continue debugging SCM plugin
3. Recreate Jenkins job completely

#### 3.2 Add GitHub Token to Jenkins

Jenkins needs to push manifest updates:

```bash
# Create GitHub token with 'repo' scope
# In Jenkins:
# 1. Manage Jenkins → Credentials → Add
# 2. Kind: Secret text
# 3. Secret: (GitHub token)
# 4. ID: github-token
```

#### 3.3 Switch to New Pipeline

```bash
# Option A: Rename new pipeline file
git mv Jenkinsfile Jenkinsfile.old
git mv Jenkinsfile.argocd Jenkinsfile

# Option B: Update Jenkins job to use Jenkinsfile.argocd
# (Configure → Script Path → Jenkinsfile.argocd)
```

#### 3.4 Test Jenkins Build

1. Push changes to `release/v0.1`
2. Trigger Jenkins build
3. Verify:
   - ✅ Code builds
   - ✅ Tests run
   - ✅ Images pushed to GHCR
   - ✅ Manifests updated
   - ✅ Changes pushed to Git

### Phase 4: Configure Secrets (Day 2)

#### 4.1 Create Kubernetes Secrets

```bash
# Create namespace
kubectl create namespace lb-automotive

# GitHub Container Registry pull secret
kubectl create secret docker-registry ghcr-secret \
  --docker-server=ghcr.io \
  --docker-username=gamebox-inc \
  --docker-password=YOUR_GITHUB_TOKEN \
  -n lb-automotive

# Anthropic API key
kubectl create secret generic anthropic-secrets \
  --from-literal=api-key=YOUR_ANTHROPIC_API_KEY \
  -n lb-automotive

# App secrets (JWT secret, etc.)
kubectl create secret generic app-secrets \
  --from-literal=SECRET_KEY=YOUR_SECRET_KEY \
  --from-literal=ALLOWED_ORIGINS=https://kozytherocket.space \
  -n lb-automotive
```

#### 4.2 Update K8s Manifests to Use Secrets

Update `deployment/k8s/backend.yaml` and `deployment/k8s/frontend.yaml` to reference secrets.

### Phase 5: End-to-End Testing (Day 2-3)

#### 5.1 Test Full Pipeline

```bash
# Make a test change
echo "# Test change" >> README.md
git add README.md
git commit -m "test: trigger Jenkins + ArgoCD pipeline"
git push origin release/v0.1
```

#### 5.2 Monitor Deployment

```bash
# Watch Jenkins build
# http://178.156.223.196:8080/job/LB-Automotive-Dashboard-Pipeline/

# Watch ArgoCD sync
kubectl get application lb-automotive -n argocd -w

# Watch pods deploy
kubectl get pods -n lb-automotive -w

# Check pod logs
kubectl logs -f deployment/backend -n lb-automotive
kubectl logs -f deployment/frontend -n lb-automotive
```

#### 5.3 Verify Application

```bash
# Port forward to test locally
kubectl port-forward svc/frontend -n lb-automotive 8080:80
kubectl port-forward svc/backend -n lb-automotive 8000:8000

# Access:
# Frontend: http://localhost:8080
# Backend: http://localhost:8000/docs
```

#### 5.4 Test Rollback

```bash
# Rollback via Git
git revert HEAD
git push origin release/v0.1

# Watch ArgoCD deploy previous version
kubectl get application lb-automotive -n argocd -w
```

### Phase 6: Production Cutover (Week 2)

#### 6.1 Setup Ingress

```yaml
# deployment/k8s/ingress.yaml already exists
# Update with correct domain and apply
kubectl apply -f deployment/k8s/ingress.yaml
```

#### 6.2 DNS Update

```bash
# Point kozytherocket.space to Kubernetes ingress IP
kubectl get svc -n ingress-nginx

# Update DNS A record:
# kozytherocket.space → (ingress external IP)
```

#### 6.3 SSL Certificates

```bash
# Install cert-manager for Let's Encrypt
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml

# Configure Let's Encrypt issuer
# (See deployment/k8s/ingress.yaml for cert-manager annotations)
```

#### 6.4 Disable GitHub Actions

```bash
# Rename workflow file to disable
git mv .github/workflows/gamebox-engine.yaml .github/workflows/gamebox-engine.yaml.disabled

# Or delete the workflow file
git rm .github/workflows/gamebox-engine.yaml
```

#### 6.5 Update Documentation

Update the following files:
- `README.md` - Update deployment instructions
- `CLAUDE.md` - Update architecture and deployment info
- `deployment/PRODUCTION_SETUP.md` - Document new setup

### Phase 7: Monitoring & Maintenance

#### 7.1 Setup Monitoring

```bash
# Install Prometheus + Grafana
kubectl apply -f prometheus.yml

# Configure ArgoCD metrics
# ArgoCD exports Prometheus metrics by default
```

#### 7.2 Configure Alerts

- Slack/email notifications for deployment failures
- ArgoCD out-of-sync alerts
- Pod crash alerts

#### 7.3 Backup Strategy

```bash
# Backup strategy:
# 1. All config in Git (GitOps) ✅
# 2. Database backups (persistent volumes)
# 3. ArgoCD backup (export applications)

# Backup ArgoCD applications
kubectl get applications -n argocd -o yaml > argocd-backup.yaml
```

## Rollback Plan

If migration fails, rollback is simple:

```bash
# 1. Re-enable GitHub Actions workflow
git mv .github/workflows/gamebox-engine.yaml.disabled .github/workflows/gamebox-engine.yaml

# 2. Keep docker-compose deployment running
cd /opt/lb-automotive-dashboard/deployment/docker
docker compose up -d

# 3. Point DNS back to old server if needed
```

## Decision Matrix

Should you migrate?

| Factor | GitHub Actions | Jenkins + ArgoCD | Winner |
|--------|---------------|------------------|--------|
| **Current state** | Working | Needs setup | GH Actions |
| **Kubernetes native** | No | Yes | J+A |
| **GitOps** | No | Yes | J+A |
| **Rollback ease** | Hard | Easy (git revert) | J+A |
| **Multi-environment** | Complex | Simple | J+A |
| **Drift detection** | None | Automatic | J+A |
| **Setup time** | Done | 1-2 days | GH Actions |
| **Long-term maintainability** | Medium | High | J+A |
| **Cost** | Free (public) | Self-hosted | GH Actions |
| **Production ready** | OK for docker-compose | Better for K8s | J+A |

**Recommendation:** 

✅ **Migrate to Jenkins + ArgoCD** if:
- You plan to use Kubernetes in production
- You want true GitOps workflow
- You need multi-environment deployments
- You want better rollback capabilities

⚠️ **Stay with GitHub Actions** if:
- You're happy with current docker-compose setup
- You don't plan to use Kubernetes soon
- You want minimal maintenance
- Quick iteration is priority over production features

## Support

Once you decide, I can help with:
1. Fixing current Jenkins issues (still working on this)
2. Setting up Kubernetes cluster
3. Installing and configuring ArgoCD
4. Creating the new Jenkins pipeline
5. Testing the full pipeline
6. Migrating production traffic

## Next Steps

**Immediate actions:**
1. ✅ Review this migration guide
2. ⬜ Decide: Migrate or stay with GitHub Actions?
3. ⬜ If migrating: Set up Kubernetes cluster
4. ⬜ Fix current Jenkins pipeline issues
5. ⬜ Follow Phase 1-7 checklist above

Let me know your decision and I'll help with the next steps!
