#!/bin/bash
set -e

echo "🚀 GameBox Security Gateway - Complete Deployment"
echo "Domain: kozytherocket.space"
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Step 1: Deploy K8s Resources
echo -e "${BLUE}Step 1: Deploying K8s resources...${NC}"
bash deployment/scripts/deploy-security-gateway.sh

echo ""
echo -e "${GREEN}✅ K8s deployment complete${NC}"
echo ""

# Step 2: Cloudflare Tunnel Setup
echo -e "${BLUE}Step 2: Setting up Cloudflare Tunnel...${NC}"
echo ""

# Check if cloudflared is installed
if ! command -v cloudflared &> /dev/null; then
    echo "Installing cloudflared..."
    curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
    sudo dpkg -i cloudflared.deb
    rm cloudflared.deb
fi

echo -e "${GREEN}✅ cloudflared installed${NC}"
echo ""

# Authenticate
echo -e "${YELLOW}Authenticating with Cloudflare...${NC}"
echo "This will open a browser window. Please select 'kozytherocket.space' and authorize."
echo ""
read -p "Press Enter to continue..."

cloudflared tunnel login

echo ""
echo -e "${GREEN}✅ Authenticated${NC}"
echo ""

# Create tunnel
echo -e "${YELLOW}Creating tunnel 'gamebox-gateway'...${NC}"
TUNNEL_OUTPUT=$(cloudflared tunnel create gamebox-gateway 2>&1)
echo "$TUNNEL_OUTPUT"

# Extract tunnel ID
TUNNEL_ID=$(echo "$TUNNEL_OUTPUT" | grep -oP 'Created tunnel .* with id \K[a-f0-9-]+' || echo "")

if [ -z "$TUNNEL_ID" ]; then
    echo -e "${YELLOW}⚠️  Could not auto-detect tunnel ID${NC}"
    echo "Please enter your tunnel ID manually:"
    read TUNNEL_ID
fi

echo ""
echo -e "${GREEN}✅ Tunnel created: $TUNNEL_ID${NC}"
echo ""

# Update config file
echo -e "${YELLOW}Updating configuration files...${NC}"
sed -i "s/TUNNEL_ID_PLACEHOLDER/$TUNNEL_ID/g" deployment/cloudflare/cloudflared-config.yaml

# Copy files
sudo mkdir -p /etc/cloudflared
sudo cp deployment/cloudflare/cloudflared-config.yaml /etc/cloudflared/config.yml
sudo cp ~/.cloudflared/${TUNNEL_ID}.json /etc/cloudflared/credentials.json

echo -e "${GREEN}✅ Configuration updated${NC}"
echo ""

# Route DNS
echo -e "${YELLOW}Configuring DNS...${NC}"
cloudflared tunnel route dns gamebox-gateway twilio.kozytherocket.space

echo -e "${GREEN}✅ DNS configured${NC}"
echo ""

# Install service
echo -e "${YELLOW}Installing Cloudflare Tunnel as system service...${NC}"
sudo cloudflared service install
sudo systemctl start cloudflared
sudo systemctl enable cloudflared

echo ""
echo -e "${GREEN}✅ Service installed and started${NC}"
echo ""

# Verify
echo -e "${BLUE}Verifying deployment...${NC}"
echo ""

echo "Cloudflare Tunnel Status:"
sudo systemctl status cloudflared --no-pager | head -10
echo ""

echo "K8s Pods:"
kubectl get pods -n gamebox-security
echo ""

echo "K8s Services:"
kubectl get svc -n gamebox-security
echo ""

echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ GameBox Security Gateway Deployed!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "📋 Next Steps:"
echo ""
echo "1. Update Twilio webhook URL to:"
echo "   https://twilio.kozytherocket.space/lb-automotive/api/twilio/webhook"
echo ""
echo "2. Test the webhook:"
echo "   Make a test call to your Twilio number"
echo ""
echo "3. Monitor logs:"
echo "   kubectl logs -n gamebox-security -l app=nginx-gateway -f"
echo "   sudo journalctl -u cloudflared -f"
echo ""
echo "4. Verify Cloudflare dashboard:"
echo "   https://dash.cloudflare.com → kozytherocket.space → Traffic → Cloudflare Tunnel"
echo ""
