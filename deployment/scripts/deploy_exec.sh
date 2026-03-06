#!/bin/bash
set -e

REMOTE_DIR='/opt/lb-automotive-dashboard'
DEPLOY_USER='lb-admin'

# 1. Extract
echo 'Extracting...'
tar -xzf "/home/$DEPLOY_USER/deploy.tar.gz" -C "$REMOTE_DIR"

# 2. Fix permissions/line-endings
# We are sudo allowed nopasswd
sudo chown -R "$DEPLOY_USER:$DEPLOY_USER" "$REMOTE_DIR"
find "$REMOTE_DIR/deployment/scripts" -name "*.sh" -exec sed -i 's/\r$//' {} +
chmod +x "$REMOTE_DIR/deployment/scripts/"*.sh

# 3. Create Dummy .env if needed
if [ ! -f "$REMOTE_DIR/.env" ]; then
    touch "$REMOTE_DIR/.env"
    echo "SECRET_KEY=replace_me_in_prod" >> "$REMOTE_DIR/.env"
fi

# 4. Start Services
echo 'Starting Services...'
cd "$REMOTE_DIR"
# Docker permissions should be fine via group
docker compose -f deployment/docker/docker-compose.yml up -d --build --remove-orphans

# 5. Setup Ollama
echo 'Setting up Ollama...'
"$REMOTE_DIR/deployment/scripts/setup_ollama.sh"
