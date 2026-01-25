#!/bin/bash

# LB Automotive Dashboard - Environment Setup Script
# This script creates the .env file with required configuration

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
ENV_FILE="$PROJECT_ROOT/deployment/docker/.env"
ENV_EXAMPLE="$PROJECT_ROOT/deployment/docker/.env.example"

echo "========================================"
echo "LB Automotive Dashboard - Setup"
echo "========================================"
echo ""

# Check if .env already exists
if [ -f "$ENV_FILE" ]; then
    echo "⚠️  Warning: .env file already exists at:"
    echo "    $ENV_FILE"
    echo ""
    read -p "Do you want to overwrite it? (y/N): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Setup cancelled. Existing .env file preserved."
        exit 0
    fi
    # Backup existing file
    cp "$ENV_FILE" "$ENV_FILE.backup.$(date +%Y%m%d_%H%M%S)"
    echo "✅ Backed up existing .env file"
fi

echo "🔧 Configuring environment variables..."
echo ""

# Generate SECRET_KEY
echo "📝 Generating secure SECRET_KEY..."
SECRET_KEY=$(openssl rand -hex 32)
echo "✅ SECRET_KEY generated"
echo ""

# Get domain for ALLOWED_ORIGINS
echo "🌐 Configure ALLOWED_ORIGINS"
echo "Enter your production domain(s), comma-separated"
echo "Example: https://kozytherocket.space,https://www.kozytherocket.space"
read -p "Domain(s) [https://kozytherocket.space]: " DOMAINS
ALLOWED_ORIGINS=${DOMAINS:-https://kozytherocket.space}
echo ""

# LLM Provider selection
echo "🤖 Configure LLM Provider"
echo "Choose your LLM provider:"
echo "  1) Ollama (local, free)"
echo "  2) Anthropic Claude (cloud, requires API key)"
read -p "Enter choice [1]: " LLM_CHOICE
LLM_CHOICE=${LLM_CHOICE:-1}
echo ""

if [ "$LLM_CHOICE" = "2" ]; then
    LLM_PROVIDER="anthropic"
    read -p "Enter Anthropic API Key: " ANTHROPIC_API_KEY
    echo ""
    echo "Choose Claude model:"
    echo "  1) claude-3-5-sonnet-20241022 (recommended)"
    echo "  2) claude-3-opus-20240229"
    echo "  3) claude-3-haiku-20240307"
    read -p "Enter choice [1]: " MODEL_CHOICE
    MODEL_CHOICE=${MODEL_CHOICE:-1}
    case $MODEL_CHOICE in
        2) ANTHROPIC_MODEL="claude-3-opus-20240229" ;;
        3) ANTHROPIC_MODEL="claude-3-haiku-20240307" ;;
        *) ANTHROPIC_MODEL="claude-3-5-sonnet-20241022" ;;
    esac
    echo ""
else
    LLM_PROVIDER="ollama"
    OLLAMA_HOST="http://ollama:11434"
    OLLAMA_MODEL="smollm2:135m"
fi

# Twilio configuration (optional)
echo "📞 Configure Twilio (optional, for IVR phone system)"
read -p "Do you want to configure Twilio? (y/N): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    read -p "Twilio Account SID: " TWILIO_ACCOUNT_SID
    read -p "Twilio Auth Token: " TWILIO_AUTH_TOKEN
    read -p "Twilio Phone Number (with +country code): " TWILIO_PHONE_NUMBER
    echo ""
fi

# Create .env file
echo "📄 Creating .env file..."
cat > "$ENV_FILE" << EOF
# LB Automotive Dashboard - Production Environment Variables
# Generated on $(date)

# REQUIRED: JWT Secret Key
SECRET_KEY=$SECRET_KEY

# REQUIRED: Allowed CORS Origins
ALLOWED_ORIGINS=$ALLOWED_ORIGINS

# LLM Configuration
LLM_PROVIDER=$LLM_PROVIDER
EOF

# Add provider-specific config
if [ "$LLM_PROVIDER" = "anthropic" ]; then
    cat >> "$ENV_FILE" << EOF

# Anthropic Configuration
ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY
ANTHROPIC_MODEL=$ANTHROPIC_MODEL
EOF
else
    cat >> "$ENV_FILE" << EOF

# Ollama Configuration
OLLAMA_HOST=$OLLAMA_HOST
OLLAMA_MODEL=$OLLAMA_MODEL
EOF
fi

# Add Twilio config if provided
if [ -n "$TWILIO_ACCOUNT_SID" ]; then
    cat >> "$ENV_FILE" << EOF

# Twilio Configuration
TWILIO_ACCOUNT_SID=$TWILIO_ACCOUNT_SID
TWILIO_AUTH_TOKEN=$TWILIO_AUTH_TOKEN
TWILIO_PHONE_NUMBER=$TWILIO_PHONE_NUMBER
EOF
fi

# Add default values
cat >> "$ENV_FILE" << EOF

# Database (managed by Docker volume)
DATABASE_URL=sqlite:////app/data/lb_automotive.db

# Redis (managed by Docker)
REDIS_URL=redis://redis:6379/0

# Content Security Policy
CSP_POLICY=strict
EOF

echo "✅ .env file created at: $ENV_FILE"
echo ""

# Set proper permissions
chmod 600 "$ENV_FILE"
echo "🔒 Set secure permissions (600) on .env file"
echo ""

echo "========================================"
echo "✅ Setup Complete!"
echo "========================================"
echo ""
echo "Your .env file has been created with:"
echo "  ✓ Secure SECRET_KEY (auto-generated)"
echo "  ✓ ALLOWED_ORIGINS: $ALLOWED_ORIGINS"
echo "  ✓ LLM Provider: $LLM_PROVIDER"
if [ -n "$TWILIO_ACCOUNT_SID" ]; then
    echo "  ✓ Twilio integration configured"
fi
echo ""
echo "Next steps:"
echo "  1. Review the .env file: nano $ENV_FILE"
echo "  2. Deploy the application: cd deployment/docker && docker compose up -d"
echo ""
echo "To reconfigure, run this script again or edit .env manually."
echo ""
