#!/bin/bash
set -e

echo "🔐 Setting up Cloudflare Tunnel for GameBox Security Gateway"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ Please run as root or with sudo"
    exit 1
fi

# Check if cloudflared is installed
if ! command -v cloudflared &> /dev/null; then
    echo "📦 Installing cloudflared..."
    curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
    dpkg -i cloudflared.deb
    rm cloudflared.deb
    echo "✅ cloudflared installed"
else
    echo "✅ cloudflared already installed"
fi

# Verify installation
cloudflared --version

echo ""
echo "📋 Next steps:"
echo ""
echo "1. Authenticate with Cloudflare:"
echo "   cloudflared tunnel login"
echo ""
echo "2. Create the tunnel:"
echo "   cloudflared tunnel create gamebox-gateway"
echo ""
echo "3. Note the Tunnel ID from the output"
echo ""
echo "4. Update deployment/cloudflare/cloudflared-config.yaml:"
echo "   - Replace TUNNEL_ID_PLACEHOLDER with your tunnel ID"
echo "   - Replace 'twilio.yourdomain.com' with your actual domain"
echo ""
echo "5. Copy configuration files:"
echo "   sudo mkdir -p /etc/cloudflared"
echo "   sudo cp deployment/cloudflare/cloudflared-config.yaml /etc/cloudflared/config.yml"
echo "   sudo cp ~/.cloudflared/YOUR_TUNNEL_ID.json /etc/cloudflared/credentials.json"
echo ""
echo "6. Route DNS:"
echo "   cloudflared tunnel route dns gamebox-gateway twilio.yourdomain.com"
echo ""
echo "7. Install as system service:"
echo "   sudo cloudflared service install"
echo "   sudo systemctl start cloudflared"
echo "   sudo systemctl enable cloudflared"
echo ""
echo "8. Check status:"
echo "   sudo systemctl status cloudflared"
echo "   sudo journalctl -u cloudflared -f"
echo ""
