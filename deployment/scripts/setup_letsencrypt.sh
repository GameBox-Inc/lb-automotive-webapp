#!/bin/bash
set -e

# Let's Encrypt SSL Setup Script for LB Automotive Dashboard
# This script must be run on the Hetzner server with sudo privileges

echo "======================================"
echo "Let's Encrypt SSL Certificate Setup"
echo "======================================"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "ERROR: Please run as root (use sudo)"
    exit 1
fi

# Prompt for domain and email
read -p "Enter your domain name (e.g., auto.example.com): " DOMAIN
read -p "Enter your email address for renewal notifications: " EMAIL

if [ -z "$DOMAIN" ] || [ -z "$EMAIL" ]; then
    echo "ERROR: Domain and email are required"
    exit 1
fi

echo ""
echo "Domain: $DOMAIN"
echo "Email: $EMAIL"
echo ""
read -p "Is this correct? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Setup cancelled"
    exit 0
fi

echo ""
echo "Step 1/5: Installing Certbot..."
apt-get update -qq
apt-get install -y certbot

echo ""
echo "Step 2/5: Stopping frontend container..."
docker stop lb-auto-frontend 2>/dev/null || echo "Container not running"

echo ""
echo "Step 3/5: Generating SSL certificate..."
echo "This will verify that $DOMAIN points to this server..."

certbot certonly --standalone \
  --preferred-challenges http \
  --email "$EMAIL" \
  --agree-tos \
  --no-eff-email \
  --non-interactive \
  -d "$DOMAIN"

if [ $? -ne 0 ]; then
    echo ""
    echo "ERROR: Certificate generation failed!"
    echo ""
    echo "Common issues:"
    echo "  1. Domain DNS not pointing to this server IP (178.156.223.196)"
    echo "  2. Port 80 blocked by firewall"
    echo "  3. Domain not fully propagated yet (wait 15-30 minutes)"
    echo ""
    exit 1
fi

echo ""
echo "Step 4/5: Setting up auto-renewal..."

# Create renewal hook script
cat > /etc/letsencrypt/renewal-hooks/post/restart-nginx.sh << 'EOF'
#!/bin/bash
docker restart lb-auto-frontend 2>/dev/null || true
EOF

chmod +x /etc/letsencrypt/renewal-hooks/post/restart-nginx.sh

# Add cron job for renewal (if not exists)
CRON_CMD="0 0 * * * certbot renew --quiet"
(crontab -l 2>/dev/null | grep -F "$CRON_CMD") || (crontab -l 2>/dev/null; echo "$CRON_CMD") | crontab -

echo ""
echo "Step 5/5: Updating configuration files..."

# Update docker-compose.yml with correct domain
COMPOSE_FILE="/opt/lb-automotive-dashboard/deployment/docker/docker-compose.yml"
if [ -f "$COMPOSE_FILE" ]; then
    sed -i "s|./nginx-selfsigned.crt:/etc/nginx/ssl/nginx-selfsigned.crt:ro|/etc/letsencrypt/live/$DOMAIN/fullchain.pem:/etc/nginx/ssl/cert.pem:ro|g" "$COMPOSE_FILE"
    sed -i "s|./nginx-selfsigned.key:/etc/nginx/ssl/nginx-selfsigned.key:ro|/etc/letsencrypt/live/$DOMAIN/privkey.pem:/etc/nginx/ssl/key.pem:ro|g" "$COMPOSE_FILE"
    sed -i 's|"10.100.0.1:443:443"|"443:443"|g' "$COMPOSE_FILE"
    sed -i 's|"10.100.0.1:80:80"|"80:80"|g' "$COMPOSE_FILE"
    echo "✓ Updated docker-compose.yml"
else
    echo "WARNING: docker-compose.yml not found at expected location"
fi

# Update nginx config with domain
NGINX_CONF="/opt/lb-automotive-dashboard/deployment/docker/nginx-https.conf"
if [ -f "$NGINX_CONF" ]; then
    sed -i "s|server_name 10.100.0.1;|server_name $DOMAIN;|g" "$NGINX_CONF"
    sed -i 's|ssl_certificate /etc/nginx/ssl/nginx-selfsigned.crt;|ssl_certificate /etc/nginx/ssl/cert.pem;|g' "$NGINX_CONF"
    sed -i 's|ssl_certificate_key /etc/nginx/ssl/nginx-selfsigned.key;|ssl_certificate_key /etc/nginx/ssl/key.pem;|g' "$NGINX_CONF"
    echo "✓ Updated nginx-https.conf"
else
    echo "WARNING: nginx-https.conf not found at expected location"
fi

echo ""
echo "======================================"
echo "✓ SSL Certificate Setup Complete!"
echo "======================================"
echo ""
echo "Certificate Details:"
echo "  Domain: $DOMAIN"
echo "  Certificate: /etc/letsencrypt/live/$DOMAIN/fullchain.pem"
echo "  Private Key: /etc/letsencrypt/live/$DOMAIN/privkey.pem"
echo "  Expires: ~90 days (auto-renews)"
echo ""
echo "Next Steps:"
echo "  1. Restart services: cd /opt/lb-automotive-dashboard/deployment/docker && docker compose up -d"
echo "  2. Test HTTPS: curl -I https://$DOMAIN"
echo "  3. Test on mobile browser: https://$DOMAIN"
echo ""
echo "To test renewal: certbot renew --dry-run"
echo ""
