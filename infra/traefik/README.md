# Traefik Ingress

Traefik v3 Gateway API configuration for LB Automotive:

- **Canonical path:** `deployment/k8s/gamebox-security/traefik/`
- **Files:** `gateway.yaml`, `lb-automotive-routes.yaml`, `middlewares.yaml`, `traefik-helm-values.yaml`

Apply with:

```bash
kubectl apply -f deployment/k8s/gamebox-security/traefik/gateway.yaml
kubectl apply -f deployment/k8s/gamebox-security/traefik/lb-automotive-routes.yaml
```
