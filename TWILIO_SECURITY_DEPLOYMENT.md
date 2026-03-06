# Twilio Webhook Security Update - Deployment Instructions

## Changes Made
Updated `deployment/docker/nginx.conf` to restrict `/api/twilio/*` endpoints to only accept requests from Twilio's IP ranges.

## How to Deploy

### Option 1: Redeploy via Docker Compose (Recommended)
```bash
# SSH into your server
ssh root@178.156.223.196

# Navigate to project directory
cd /opt/lb-automotive-dashboard

# Pull latest changes (or upload the updated nginx.conf)
# If uploading manually:
# scp deployment/docker/nginx.conf root@178.156.223.196:/opt/lb-automotive-dashboard/deployment/docker/

# Rebuild and restart the frontend container
docker compose -f deployment/docker/docker-compose.yml up -d --build frontend

# Verify Nginx is running
docker compose -f deployment/docker/docker-compose.yml ps
```

### Option 2: Hot Reload Nginx (Faster, No Downtime)
```bash
# SSH into server
ssh root@178.156.223.196

# Copy new config into running container
docker cp /opt/lb-automotive-dashboard/deployment/docker/nginx.conf lb-auto-frontend:/etc/nginx/conf.d/default.conf

# Test configuration
docker exec lb-auto-frontend nginx -t

# Reload Nginx (no downtime)
docker exec lb-auto-frontend nginx -s reload
```

## Verification
Test that non-Twilio IPs are blocked:
```bash
# This should return 403 Forbidden
curl http://178.156.223.196/api/twilio/webhook
```

The webhook will only work when called from Twilio's servers.

## Security Note
- This configuration uses IP allowlisting as the first layer of defense
- For additional security, implement request signature validation in the backend
- Twilio IP ranges should be updated periodically (check their docs)
