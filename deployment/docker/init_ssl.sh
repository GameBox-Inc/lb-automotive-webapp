#!/bin/bash
# Generate self-signed SSL certificates for Nginx if they don't exist

# Set the target directory to the script's directory
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

# Set the Common Name (CN) to the VPN IP
DOMAIN="10.100.0.1"

echo "Checking for SSL certificates in $DIR..."

# Check if certificates already exist
if [ -f "nginx-selfsigned.crt" ] && [ -f "nginx-selfsigned.key" ]; then
    echo "✅ Certificates already exist. Skipping generation."
else
    echo "⚠️  Certificates missing. Generating self-signed certificates for $DOMAIN..."
    
    # Check for openssl
    if ! command -v openssl &> /dev/null; then
        echo "❌ Error: openssl could not be found. Please install openssl."
        exit 1
    fi

    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout nginx-selfsigned.key \
    -out nginx-selfsigned.crt \
    -subj "/C=US/ST=State/L=City/O=Organization/CN=$DOMAIN"
    
    if [ $? -eq 0 ]; then
        echo "✅ Certificates generated successfully."
    else
        echo "❌ Error generating certificates."
        exit 1
    fi
fi
