#!/bin/bash
# Quick deployment script to update Nginx configuration

set -e

SERVER="root@178.156.223.196"
SSH_KEY="$HOME/.ssh/lb-automotive-key"
REMOTE_DIR="/opt/lb-automotive-dashboard"

echo "📦 Uploading updated nginx-https.conf..."
scp -i "$SSH_KEY" deployment/docker/nginx-https.conf "$SERVER:$REMOTE_DIR/deployment/docker/"

echo "🔄 Rebuilding frontend container..."
ssh -i "$SSH_KEY" "$SERVER" << 'ENDSSH'
cd /opt/lb-automotive-dashboard
docker compose -f deployment/docker/docker-compose.yml up -d --build --force-recreate frontend
ENDSSH

echo "✅ Deployment complete! Access the dashboard at http://10.100.0.1"
