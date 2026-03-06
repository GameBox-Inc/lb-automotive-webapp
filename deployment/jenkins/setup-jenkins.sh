#!/bin/bash
# Quick setup script for Jenkins CI/CD server
# Run this on your server (178.156.223.196) as lb-admin user

set -e

echo "========================================"
echo "🚀 Jenkins Setup for LB Automotive"
echo "========================================"

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo "⚠️  Please run as lb-admin user, not root"
    exit 1
fi

# Check Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

# Check Docker Compose is installed
if ! command -v docker compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Create Jenkins directory
JENKINS_DIR="/opt/jenkins"
echo "📁 Creating Jenkins directory at $JENKINS_DIR..."

if [ ! -d "$JENKINS_DIR" ]; then
    sudo mkdir -p "$JENKINS_DIR"
    sudo chown $USER:$USER "$JENKINS_DIR"
    echo "✅ Directory created"
else
    echo "✅ Directory already exists"
fi

cd "$JENKINS_DIR"

# Copy docker-compose.yml
echo "📋 Creating docker-compose.yml..."
cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  jenkins:
    image: jenkins/jenkins:lts-jdk17
    container_name: lb-jenkins
    restart: unless-stopped
    privileged: true
    user: root
    ports:
      - "8080:8080"   # Jenkins Web UI
      - "50000:50000" # Jenkins agent port
    volumes:
      - jenkins-data:/var/jenkins_home
      - /var/run/docker.sock:/var/run/docker.sock
    environment:
      - JAVA_OPTS=-Djenkins.install.runSetupWizard=true
    networks:
      - jenkins-network

networks:
  jenkins-network:
    driver: bridge

volumes:
  jenkins-data:
    driver: local
EOF

echo "✅ docker-compose.yml created"

# Start Jenkins
echo "🚀 Starting Jenkins..."
docker compose up -d

# Wait for Jenkins to start
echo "⏳ Waiting for Jenkins to initialize (this may take 1-2 minutes)..."
sleep 30

# Check if Jenkins is running
if docker ps | grep -q lb-jenkins; then
    echo "✅ Jenkins is running"
else
    echo "❌ Jenkins failed to start. Check logs with: docker logs lb-jenkins"
    exit 1
fi

# Get initial admin password
echo ""
echo "========================================"
echo "📋 Initial Setup Information"
echo "========================================"
echo ""
echo "Jenkins URL: http://178.156.223.196:8080"
echo ""
echo "Initial Admin Password:"
echo "----------------------------------------"
sleep 5  # Give Jenkins time to create the password file
docker exec lb-jenkins cat /var/jenkins_home/secrets/initialAdminPassword 2>/dev/null || echo "⚠️  Password not ready yet. Run: docker exec lb-jenkins cat /var/jenkins_home/secrets/initialAdminPassword"
echo "----------------------------------------"
echo ""
echo "Next Steps:"
echo "1. Open Jenkins in browser: http://178.156.223.196:8080"
echo "2. Use the password above to unlock Jenkins"
echo "3. Install suggested plugins"
echo "4. Create admin user"
echo "5. Follow the setup guide in: deployment/jenkins/README.md"
echo ""
echo "========================================"

# Generate SSH key for deployment if it doesn't exist
SSH_KEY="$HOME/.ssh/jenkins_deploy_key"
if [ ! -f "$SSH_KEY" ]; then
    echo ""
    echo "🔑 Generating SSH key for Jenkins deployment..."
    ssh-keygen -t rsa -b 4096 -f "$SSH_KEY" -N "" -C "jenkins-deploy@lb-automotive"
    echo "✅ SSH key generated at: $SSH_KEY"
    echo ""
    echo "⚠️  IMPORTANT: Add this public key to authorized_keys:"
    echo "----------------------------------------"
    cat "$SSH_KEY.pub"
    echo "----------------------------------------"
    echo ""
    echo "Run this command to add it:"
    echo "cat $SSH_KEY.pub >> ~/.ssh/authorized_keys"
    echo ""
else
    echo ""
    echo "✅ SSH key already exists at: $SSH_KEY"
fi

# Test SSH connection
echo ""
echo "🔍 Testing SSH connection to localhost..."
if ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no $USER@localhost "echo 'SSH connection successful'" 2>/dev/null; then
    echo "✅ SSH connection works"
else
    echo "⚠️  SSH connection failed. Make sure to add the public key to authorized_keys"
fi

echo ""
echo "========================================"
echo "✅ Jenkins Setup Complete!"
echo "========================================"
echo ""
echo "Jenkins is now running at: http://178.156.223.196:8080"
echo ""
echo "To view logs: docker logs lb-jenkins -f"
echo "To stop: cd $JENKINS_DIR && docker compose down"
echo "To restart: cd $JENKINS_DIR && docker compose restart"
echo ""
echo "Full documentation: deployment/jenkins/README.md"
echo "========================================"
