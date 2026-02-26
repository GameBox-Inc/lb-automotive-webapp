# GameBox Security Gateway

## Architecture

```
[Internet / Twilio]
      │
      ▼
Cloudflare Edge (DDoS, WAF, SSL)
      │
      ▼
Cloudflare Tunnel (outbound-only, no inbound ports exposed)
      │
      ▼
Traefik Gateway (gamebox-security namespace)
      │
      └─ twilio.kozytherocket.space POST /lb-automotive/api/twilio/** → backend:8000
      └─ everything else → 404 (explicit deny)

[WireGuard VPN — 10.100.0.1]
      │
      └─ :30080 → Frontend (React SPA)
      └─ :30800 → Backend REST API
```

## Security Policy

> **Customer apps are INTERNAL-FACING ONLY.**
>
> The only publicly accessible endpoint is the Twilio webhook on `twilio.kozytherocket.space`.
> The frontend and backend API are accessible exclusively via WireGuard VPN.

| Endpoint | Access |
|---|---|
| `https://twilio.kozytherocket.space/lb-automotive/api/twilio/webhook` | Public — Twilio POST only |
| `https://kozytherocket.space` | Blocked (404) |
| `http://10.100.0.1:30080` | VPN only — Frontend |
| `http://10.100.0.1:30800` | VPN only — Backend API |

## Deployment

Jenkins pipeline handles all K8s manifest deployment. To deploy manually from the repo root:

```bash
bash deployment/scripts/deploy-security-gateway.sh
```

The script applies manifests in dependency order:
1. GatewayClass + Gateway
2. Middlewares + ReferenceGrant
3. HTTPRoutes (Twilio webhook + deny rules)
4. Deletes legacy Ingress objects
5. Cloudflare Tunnel K8s deployment

## Verify HTTPRoutes are accepted

```bash
kubectl get httproute -n gamebox-security -o wide
```

All routes should show `Accepted: True`.

## Verify Twilio webhook

```bash
# Backend logs during a live call
kubectl logs -n lb-automotive -l app=backend -f

# Traefik access logs
kubectl logs -n gamebox-security -l app.kubernetes.io/name=traefik -f
```

## Adding a New Customer App

1. Create an HTTPRoute in `gamebox-security` scoped to **only** the webhook subdomain
2. Never add routes for `*.kozytherocket.space` root domain — apps are VPN-only
3. Add a `ReferenceGrant` in the customer namespace
4. Add a `NetworkPolicy` allowing traffic from `gamebox-security` to the customer namespace
