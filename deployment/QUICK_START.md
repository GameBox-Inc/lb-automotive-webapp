# ⚡ Quick Start: Jenkins + ArgoCD Deployment

**Fast track to get your pipeline running in under 10 minutes**

---

## 🚀 Run These Commands on Server

```bash
# 1. Clean up evicted pods
kubectl get pods -A | grep Evicted | awk '{print $2 " -n " $1}' | xargs -r kubectl delete pod

# 2. Pull latest code
cd /opt/lb-automotive-dashboard
git pull origin release/v0.1

# 3. Configure secrets (interactive)
bash deployment/k8s/create-secrets.sh

# 4. Configure ArgoCD repository access
# Generate SSH key for ArgoCD
ssh-keygen -t ed25519 -C "argocd@lb-automotive" -f ~/.ssh/argocd_deploy_key -N ""

# Add public key to GitHub
echo "Add this key to GitHub:"
cat ~/.ssh/argocd_deploy_key.pub
echo ""
echo "Go to: https://github.com/GameBox-Inc/lb-automotive-webapp/settings/keys"
echo "Press Enter when done..."
read

# Create ArgoCD repo secret
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

# 5. Deploy application via ArgoCD
kubectl apply -f deployment/argocd/lb-automotive-app.yaml

# 6. Watch deployment
kubectl get pods -n lb-automotive -w
```

---

## 🔨 Configure Jenkins (One-Time)

### Add GHCR Token:
1. Open Jenkins: `http://<server-ip>:8080`
2. **Manage Jenkins** → **Credentials** → **(global)** → **Add Credentials**
3. Create:
   - **Kind**: Secret text
   - **Secret**: `<your-github-token>`
   - **ID**: `ghcr-token`

### Create Pipeline Job:
1. **New Item** → **Pipeline** → Name: `LB-Automotive-ArgoCD-Pipeline`
2. **Pipeline** section → **Definition**: Pipeline script
3. Copy contents from `Jenkinsfile.argocd`
4. **Save** → **Build Now**

---

## ✅ Verify Everything Works

```bash
# Check K3s
kubectl get nodes

# Check ArgoCD
kubectl get applications -n argocd
kubectl get pods -n argocd

# Check application
kubectl get pods -n lb-automotive
kubectl get svc -n lb-automotive

# Test backend
kubectl port-forward svc/backend -n lb-automotive 8000:8000
curl http://localhost:8000/api/health

# Get ArgoCD admin password
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d
```

---

## 🎯 Test Full Pipeline

```bash
# Make a test change
cd /opt/lb-automotive-dashboard
echo "# Pipeline test" >> README.md
git add README.md
git commit -m "test: Trigger pipeline"
git push origin release/v0.1

# Watch Jenkins build (in Jenkins UI)
# Watch ArgoCD sync:
kubectl get applications -n argocd -w

# Watch pods update:
kubectl get pods -n lb-automotive -w
```

---

## 📚 Full Documentation

For detailed steps, troubleshooting, and advanced configuration, see:
- **`DEPLOY_JENKINS_ARGOCD.md`** - Complete deployment guide
- **`JENKINS_ARGOCD_MIGRATION.md`** - Migration strategy
- **`deployment/argocd/SETUP.md`** - ArgoCD configuration
- **`STORAGE_OPTIMIZATION.md`** - Disk management

---

**Questions? Issues?**
- Check logs: `kubectl logs -n <namespace> <pod-name>`
- Describe resources: `kubectl describe pod <pod-name> -n <namespace>`
- Check events: `kubectl get events -n <namespace> --sort-by='.lastTimestamp'`
