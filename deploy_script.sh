    set -e
    
    # 1. Prepare Directory
    mkdir -p /opt/lb-automotive-dashboard
    
    # 2. Extract
    echo 'Extracting...'
    tar -xzf /root/deploy.tar.gz -C /opt/lb-automotive-dashboard
    
    # 3. Fix Line Endings (Critical for scripts uploaded from Windows)
    echo 'Fixing line endings...'
    find /opt/lb-automotive-dashboard/deployment/scripts -name "*.sh" -exec sed -i 's/\r$//' {} +
    chmod +x /opt/lb-automotive-dashboard/deployment/scripts/*.sh
    
    # 4. Install Docker if missing
    if ! command -v docker &> /dev/null; then
        echo 'Installing Docker...'
        /opt/lb-automotive-dashboard/deployment/scripts/install_docker.sh
    fi
    
    # 5. Create Dummy .env if needed
    if [ ! -f "/opt/lb-automotive-dashboard/.env" ]; then
        touch "/opt/lb-automotive-dashboard/.env"
    fi
    
    # 6. Start Services
    echo 'Starting Services...'
    cd /opt/lb-automotive-dashboard
    # Ensure docker compose plugin is used (docker compose) or standalone (docker-compose)
    if command -v docker-compose &> /dev/null; then
        docker-compose -f deployment/docker/docker-compose.yml up -d --build --remove-orphans
    else
        docker compose -f deployment/docker/docker-compose.yml up -d --build --remove-orphans
    fi

    # 7. Setup Ollama
    echo 'Setting up Ollama...'
    # Run in background or just run it? It pulls a model, might take time.
    /opt/lb-automotive-dashboard/deployment/scripts/setup_ollama.sh
