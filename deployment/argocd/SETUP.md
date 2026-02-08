# ArgoCD Setup Guide

This guide explains how to set up ArgoCD for GitOps-based deployment of LB Automotive Dashboard.

## Architecture Overview

```
GitHub → Jenkins (CI) → Push Images → Update Manifests → ArgoCD (CD) → Kubernetes
```

**Jenkins responsibilities (CI):**
- Build and test code
- Build Docker images
- Push images to GHCR
- Update K8s manifests with new image tags
- Push manifest changes to Git

**ArgoCD responsibilities (CD):**
- Monitor Git repo for manifest changes
- Deploy to Kubernetes automatically
- Health checks and rollbacks
- Drift detection and auto-healing

## Prerequisites

1. **Kubernetes cluster** (K3s, K8s, EKS, GKE, etc.)
2. **kubectl** configured to access your cluster
3. **Jenkins** with Docker and Git
4. **GitHub Container Registry** (GHCR) access

## Step 1: Install ArgoCD

Install ArgoCD on your Kubernetes cluster:

```bash
# Create argocd namespace
kubectl create namespace argocd

# Install ArgoCD
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Wait for pods to be ready
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=argocd-server -n argocd --timeout=300s

# Check installation
kubectl get pods -n argocd
```

## Step 2: Access ArgoCD UI

### Option A: Port Forward (Development)

```bash
# Port forward to access UI
kubectl port-forward svc/argocd-server -n argocd 8080:443

# Get admin password
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d

# Access UI: https://localhost:8080
# Username: admin
# Password: (from command above)
```

### Option B: Ingress (Production)

Create an ingress for ArgoCD:

```yaml
# argocd-ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: argocd-server-ingress
  namespace: argocd
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/backend-protocol: "HTTPS"
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - argocd.yourdomain.com
    secretName: argocd-tls
  rules:
  - host: argocd.yourdomain.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: argocd-server
            port:
              number: 443
```

Apply:
```bash
kubectl apply -f argocd-ingress.yaml
```

## Step 3: Configure GitHub Repository Access

ArgoCD needs access to your private GitHub repository.

### Option A: SSH Key (Recommended)

```bash
# Generate SSH key for ArgoCD
ssh-keygen -t ed25519 -C "argocd@lb-automotive" -f argocd-deploy-key -N ""

# Add public key to GitHub:
# 1. Go to: https://github.com/GameBox-Inc/lb-automotive-webapp/settings/keys
# 2. Click "Add deploy key"
# 3. Title: "ArgoCD Deploy Key"
# 4. Paste contents of argocd-deploy-key.pub
# 5. Check "Allow write access" if ArgoCD will commit back (not needed for this setup)

# Add private key to ArgoCD
kubectl create secret generic argocd-repo-creds \
  --from-file=sshPrivateKey=argocd-deploy-key \
  -n argocd

# Configure repository in ArgoCD
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

# Clean up local keys
rm argocd-deploy-key argocd-deploy-key.pub
```

### Option B: GitHub Token

```bash
# Create GitHub token with repo access
# Then create secret:
kubectl create secret generic github-repo-creds \
  --from-literal=username=gamebox-inc \
  --from-literal=password=YOUR_GITHUB_TOKEN \
  -n argocd
```

## Step 4: Deploy Application

Apply the ArgoCD application manifest:

```bash
cd deployment/argocd
kubectl apply -f application.yaml
```

This creates an ArgoCD application that:
- Monitors `deployment/k8s/` directory
- Automatically syncs changes
- Self-heals if drift detected
- Creates namespace if needed

## Step 5: Configure Jenkins

### 5.1 Add GitHub Token to Jenkins

Jenkins needs a GitHub token to push manifest updates:

1. Go to GitHub → Settings → Developer settings → Personal access tokens
2. Generate new token (classic) with `repo` scope
3. In Jenkins UI → Manage Jenkins → Credentials → Add Credentials
   - Kind: Secret text
   - Secret: (paste GitHub token)
   - ID: `github-token`

### 5.2 Update Jenkins Job

1. Go to Jenkins → Your pipeline → Configure
2. Change **Pipeline Definition** to: `Pipeline script from SCM`
3. **SCM:** Git
4. **Repository URL:** `git@github.com:GameBox-Inc/lb-automotive-webapp.git`
5. **Credentials:** Select SSH key
6. **Branch:** `*/release/v0.1`
7. **Script Path:** `Jenkinsfile.argocd`
8. Save

Alternatively, you can rename `Jenkinsfile.argocd` to `Jenkinsfile` to replace the existing pipeline.

## Step 6: Verify Setup

### Check ArgoCD Application

```bash
# Get application status
kubectl get applications -n argocd

# Detailed status
kubectl describe application lb-automotive -n argocd

# ArgoCD CLI (optional)
argocd app get lb-automotive
argocd app sync lb-automotive
```

### Check Deployed Resources

```bash
# Check namespace
kubectl get all -n lb-automotive

# Check pods
kubectl get pods -n lb-automotive

# Check deployments
kubectl get deployments -n lb-automotive

# Follow pod logs
kubectl logs -f deployment/backend -n lb-automotive
kubectl logs -f deployment/frontend -n lb-automotive
```

## Step 7: Test the Pipeline

1. Make a code change in your repository
2. Push to `release/v0.1` branch
3. Jenkins will:
   - Build and test code
   - Build Docker images
   - Push to GHCR
   - Update K8s manifests with new image tags
   - Push manifest changes to Git
4. ArgoCD will:
   - Detect manifest changes
   - Deploy to Kubernetes automatically
   - Report health status

Monitor the deployment:
```bash
# Watch ArgoCD application
kubectl get application lb-automotive -n argocd -w

# Watch pods
kubectl get pods -n lb-automotive -w

# ArgoCD UI for visual monitoring
```

## Comparison: GitHub Actions vs Jenkins + ArgoCD

| Feature | GitHub Actions | Jenkins + ArgoCD |
|---------|---------------|------------------|
| **CI/CD Separation** | Combined | Separated (Jenkins=CI, ArgoCD=CD) |
| **GitOps** | Manual | Native (ArgoCD) |
| **Deployment Method** | SSH + docker-compose | Kubernetes native |
| **Rollback** | Manual | Git revert (automatic) |
| **Drift Detection** | None | Automatic (ArgoCD) |
| **Multi-environment** | Complex workflow | Simple (multiple ArgoCD apps) |
| **Cost** | Free (public repos) | Self-hosted (your servers) |
| **Visual Deployment** | Actions logs | ArgoCD UI |
| **Self-healing** | None | Automatic (ArgoCD) |

## Troubleshooting

### ArgoCD can't access repository

```bash
# Check repository connection
kubectl get secret -n argocd | grep repo

# Test SSH connection from ArgoCD pod
kubectl exec -it -n argocd deployment/argocd-repo-server -- ssh -T git@github.com
```

### Application not syncing

```bash
# Force sync
kubectl patch application lb-automotive -n argocd \
  --type merge \
  -p '{"operation":{"initiatedBy":{"username":"admin"},"sync":{"revision":"HEAD"}}}'

# Or via ArgoCD CLI
argocd app sync lb-automotive --force
```

### Jenkins can't push to Git

- Check GitHub token has `repo` scope
- Verify Jenkins credential ID matches pipeline
- Ensure SSH key is added to Jenkins

### Images not pulling

```bash
# Create image pull secret for GHCR
kubectl create secret docker-registry ghcr-secret \
  --docker-server=ghcr.io \
  --docker-username=gamebox-inc \
  --docker-password=YOUR_GITHUB_TOKEN \
  -n lb-automotive

# Update deployments to use secret
kubectl patch serviceaccount default -n lb-automotive \
  -p '{"imagePullSecrets": [{"name": "ghcr-secret"}]}'
```

## Benefits Over Current Setup

### 1. **True GitOps**
- All state in Git
- Declarative configuration
- Easy rollbacks via Git

### 2. **Better Reliability**
- Self-healing (ArgoCD fixes drift)
- Health checks
- Automatic retries

### 3. **Improved Visibility**
- ArgoCD UI shows deployment status
- Diff view before deploy
- Clear audit trail

### 4. **Easier Multi-Environment**
- Create separate ArgoCD apps for dev/staging/prod
- Same pipeline, different namespaces
- Environment-specific overlays

### 5. **Kubernetes Native**
- No SSH to servers
- No docker-compose on K8s nodes
- Proper orchestration

## Next Steps

1. **Set up monitoring**: Integrate ArgoCD with Prometheus/Grafana
2. **Configure notifications**: Slack/email alerts for deployments
3. **Add environments**: Create dev/staging/prod ArgoCD apps
4. **Implement RBAC**: Restrict ArgoCD access per team
5. **Enable SSO**: Integrate with GitHub/Google OAuth

## References

- [ArgoCD Documentation](https://argo-cd.readthedocs.io/)
- [GitOps Principles](https://www.gitops.tech/)
- [ArgoCD Best Practices](https://argo-cd.readthedocs.io/en/stable/user-guide/best_practices/)
