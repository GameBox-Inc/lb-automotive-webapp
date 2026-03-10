# Ingress & Service Endpoints Runbook

**Last Updated:** March 2026  
**Related:** [K8s Debugging](k8s-debugging.md) | [Twilio 503](twilio-503.md)

---

## Request Path

```
Twilio → twilio.kozytherocket.space
  → Cloudflare Tunnel (gamebox-security)
  → Traefik (Gateway API HTTPRoute)
  → backend service (lb-automotive)
  → backend pod
```

---

## Checklist

1. **HTTPRoute exists and is correct**
   ```bash
   sudo k3s kubectl get httproute -n gamebox-security
   sudo k3s kubectl describe httproute lb-automotive-routes -n gamebox-security
   ```
   - Must reference backend service in `lb-automotive` namespace
   - ReferenceGrant may be needed for cross-namespace

2. **Backend service has endpoints**
   ```bash
   sudo k3s kubectl get endpoints -n lb-automotive backend
   ```
   - Must show pod IPs; empty means no Ready pods

3. **Traefik Service port**
   - Traefik K8s Service maps port **80** → container port **8000**
   - Internal references use port 80 for the Service

4. **URLRewrite for /lb-automotive**
   - HTTPRoute uses `ReplacePrefixMatch` to strip `/lb-automotive`
   - Backend sees `/api/twilio/webhook` not `/lb-automotive/api/twilio/webhook`

5. **Cloudflared config**
   - Ingress host must match `twilio.kozytherocket.space`
   - Service must point to Traefik (port 80)

---

## Quick Commands

```bash
# Full status
npm run debug:k8s

# Services and endpoints
sudo k3s kubectl get svc,endpoints -n lb-automotive
sudo k3s kubectl get svc -n gamebox-security

# HTTPRoutes
sudo k3s kubectl get httproute -n gamebox-security
sudo k3s kubectl get gateway -n gamebox-security

# Traefik logs
npm run logs:ingress
```
