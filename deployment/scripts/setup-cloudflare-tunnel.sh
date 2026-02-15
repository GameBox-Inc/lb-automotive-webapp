#!/bin/bash
# Setup Cloudflare Tunnel for Twilio Webhooks
set -e

echo "========================================="
echo "🌐 Cloudflare Tunnel Setup for Twilio"
echo "========================================="

# Check if cloudflared is installed
if ! command -v cloudflared &> /dev/null; then
    echo "📥 Installing cloudflared..."
    curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
    sudo dpkg -i cloudflared.deb
    rm cloudflared.deb
    echo "✓ cloudflared installed"
fi

# Create config directory
sudo mkdir -p /etc/cloudflared

echo ""
echo "========================================="
echo "📋 Next Steps:"
echo "========================================="
echo "1. Login to Cloudflare:"
echo "   cloudflared tunnel login"
echo ""
echo "2. Create a tunnel:"
echo "   cloudflared tunnel create lb-automotive-twilio"
echo ""
echo "3. Copy the tunnel ID and credentials to /etc/cloudflared/"
echo ""
echo "4. Update deployment/cloudflare/cloudflared-config.yaml with:"
echo "   - Your tunnel ID"
echo "   - Your domain name"
echo ""
echo "5. Copy config to /etc/cloudflared/:"
echo "   sudo cp deployment/cloudflare/cloudflared-config.yaml /etc/cloudflared/config.yml"
echo ""
echo "6. Route DNS to tunnel:"
echo "   cloudflared tunnel route dns lb-automotive-twilio twilio.your-domain.com"
echo ""
echo "7. Install as service:"
echo "   sudo cloudflared service install"
echo "   sudo systemctl start cloudflared"
echo "   sudo systemctl enable cloudflared"
echo ""
echo "8. Apply Twilio ingress:"
echo "   kubectl apply -f deployment/k8s/twilio-ingress.yaml"
echo ""
echo "9. Update Twilio webhook URL to:"
echo "   https://twilio.your-domain.com/api/twilio/webhook"
echo "========================================="
