#!/bin/bash

# Fix line endings for other scripts (crucial for files uploaded from Windows)
sed -i 's/\r$//' /root/install_docker.sh
sed -i 's/\r$//' /root/setup_ollama.sh

# Make scripts executable
chmod +x /root/install_docker.sh
chmod +x /root/setup_ollama.sh

# Install Docker if not exists
if ! command -v docker &> /dev/null; then
    echo 'Docker not found. Installing...'
    /root/install_docker.sh
fi

# Prepare Directory
REMOTE_DIR="/opt/lb-automotive-dashboard"
mkdir -p "$REMOTE_DIR"

# Extract
echo 'Extracting files...'
tar -xzf /root/deploy.tar.gz -C "$REMOTE_DIR"

# Configure Env (Dummy .env if missing)
if [ ! -f "$REMOTE_DIR/.env" ]; then
    touch "$REMOTE_DIR/.env"
fi

# Setup Permissions for extracted scripts
chmod +x "$REMOTE_DIR/deployment/scripts/"*.sh

# Start Services
echo 'Starting Services...'
cd "$REMOTE_DIR"
docker compose -f deployment/docker/docker-compose.yml up -d --build --remove-orphans

# Setup Ollama
echo 'Initializing Ollama...'
# We execute this in the background or ensuring it doesn't block if it takes too long, 
# but for now synchronous is fine.
# sed fix for the extracted script too just in case
sed -i 's/\r$//' deployment/scripts/setup_ollama.sh
chmod +x deployment/scripts/setup_ollama.sh
./deployment/scripts/setup_ollama.sh
