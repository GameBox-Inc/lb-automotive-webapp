# Kubernetes Manifests

K8s manifests for LB Automotive are located at:

- **Canonical path:** `deployment/k8s/`
- **Jenkins:** SCPs from `deployment/k8s/` to `${MANIFEST_DIR}` on the server

This directory is the logical boundary for K8s infrastructure. Apply manifests with:

```bash
kubectl apply -f deployment/k8s/namespace.yaml
kubectl apply -f deployment/k8s/redis.yaml
kubectl apply -f deployment/k8s/backend.yaml
kubectl apply -f deployment/k8s/frontend.yaml
# etc.
```
