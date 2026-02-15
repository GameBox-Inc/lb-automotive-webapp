# GameBox Security Gateway - Quick Start Guide

## Overview

The GameBox Security Gateway is a centralized K8s namespace that provides security, monitoring, and public endpoint management for all GameBox Inc. customers.

## Architecture

```
Twilio → Cloudflare Edge → Cloudflare Tunnel → nginx-gateway → lb-automotive backend
```

**Security Layers:**
1. **Cloudflare Edge**: DDoS, WAF, SSL/TLS, Rate limiting
2. **Nginx Gateway**: Cloudflare IP whitelist, Honeypot detection
3. **Backend**: Twilio signature validation

## Quick Deployment

### 1. Deploy Security Gateway to K8s

```bash
ssh lb-admin@178.156.223.196

cd /path/to/lb-automotive-dashboard

# Deploy gamebox-security namespace and nginx gateway
bash deployment/scripts/deploy-security-gateway.sh
```

### 2. Set Up Cloudflare Tunnel

```bash
# Install and configure Cloudflare Tunnel
bash deployment/scripts/setup-cloudflare-tunnel.sh

# Follow the interactive prompts to:
# - Authenticate with Cloudflare
# - Create tunnel
# - Configure DNS
# - Install as system service
```

### 3. Update Twilio Webhook

1. Go to [Twilio Console](https://console.twilio.com/)
2. Navigate to **Phone Numbers** → **Active numbers**
3. Select your number
4. Update **Voice Configuration**:
   - **URL**: `https://twilio.yourdomain.com/lb-automotive/api/twilio/webhook`
   - **HTTP**: POST
5. Save

## Verification

### Test Cross-Namespace Communication

```bash
# From gamebox-security to lb-automotive
kubectl run -it --rm debug --image=curlimages/curl -n gamebox-security -- \
  curl http://backend.lb-automotive.svc.cluster.local:8000/api/health
```

### Test Honeypot Detection

```bash
# Should return 403
curl http://178.156.223.196:30880/random-path

# Check honeypot logs
kubectl logs -n gamebox-security -l app=nginx-gateway | grep honeypot
```

### Test Cloudflare Tunnel

```bash
# Check tunnel status
sudo systemctl status cloudflared

# View tunnel logs
sudo journalctl -u cloudflared -f
```

### Test Twilio Webhook

Make a test call to your Twilio number and check:

```bash
# Backend logs
kubectl logs -n lb-automotive -l app=backend --tail=50 -f

# Nginx gateway logs
kubectl logs -n gamebox-security -l app=nginx-gateway --tail=50 -f
```

## Monitoring

### View Nginx Gateway Logs

```bash
# All traffic
kubectl logs -n gamebox-security -l app=nginx-gateway -f

# Honeypot attacks only
kubectl logs -n gamebox-security -l app=nginx-gateway | grep honeypot

# Twilio webhooks only
kubectl logs -n gamebox-security -l app=nginx-gateway | grep twilio-webhook
```

### Check Pod Status

```bash
kubectl get pods -n gamebox-security
kubectl get pods -n lb-automotive
```

## Troubleshooting

### Nginx Gateway Not Starting

```bash
# Check pod events
kubectl describe pod -n gamebox-security -l app=nginx-gateway

# Check config
kubectl get configmap nginx-gateway-config -n gamebox-security -o yaml
```

### Cross-Namespace Communication Failing

```bash
# Verify network policies
kubectl get networkpolicy -n gamebox-security
kubectl get networkpolicy -n lb-automotive

# Test DNS resolution
kubectl run -it --rm debug --image=curlimages/curl -n gamebox-security -- \
  nslookup backend.lb-automotive.svc.cluster.local
```

### Cloudflare Tunnel Not Connecting

```bash
# Check service status
sudo systemctl status cloudflared

# View detailed logs
sudo journalctl -u cloudflared -n 100

# Restart service
sudo systemctl restart cloudflared
```

## Security Features

### Cloudflare IP Whitelist

Only traffic from Cloudflare edge IPs is allowed. Direct access to the origin is blocked.

### Honeypot Detection

All requests to non-whitelisted paths are logged for security analysis:

```bash
kubectl logs -n gamebox-security -l app=nginx-gateway | grep honeypot
```

### Rate Limiting

- Primary: Cloudflare edge (configurable in Cloudflare dashboard)
- Backup: Nginx (10 req/s per IP, burst of 10)

## Adding New Customers

To route webhooks for a new customer:

1. Add new location block to `nginx-config.yaml`:

```nginx
location /new-customer/api/webhook/ {
    proxy_pass http://backend.new-customer.svc.cluster.local:8000/api/webhook/;
}
```

2. Update network policy to allow traffic to new namespace
3. Apply changes: `kubectl apply -f deployment/k8s/gamebox-security/`

## URLs

**Public Endpoint:**
```
https://twilio.yourdomain.com/lb-automotive/api/twilio/webhook
```

**Nginx Gateway (NodePort):**
```
http://178.156.223.196:30880
```

**Health Check:**
```
http://178.156.223.196:30880/health
```
