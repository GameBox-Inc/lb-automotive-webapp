#!/bin/bash
# Configure GitHub SSH key in Jenkins
# This adds your GitHub SSH key to Jenkins so it can clone the repository

set -e

echo "========================================"
echo "🔑 Configuring GitHub SSH for Jenkins"
echo "========================================"

# Check if Jenkins is running
if ! docker ps | grep -q lb-jenkins; then
    echo "❌ Jenkins container is not running"
    echo "Start it with: cd /opt/jenkins && docker compose up -d"
    exit 1
fi

# Default GitHub SSH key location
GITHUB_SSH_KEY="${HOME}/.ssh/id_rsa"

# Check if user wants to specify a different key
if [ -n "$1" ]; then
    GITHUB_SSH_KEY="$1"
fi

# Check if key exists
if [ ! -f "$GITHUB_SSH_KEY" ]; then
    echo "❌ GitHub SSH key not found at: $GITHUB_SSH_KEY"
    echo ""
    echo "Options:"
    echo "1. Generate a new SSH key:"
    echo "   ssh-keygen -t ed25519 -C 'jenkins@lb-automotive' -f ~/.ssh/github_lb_automotive"
    echo ""
    echo "2. Use an existing key:"
    echo "   $0 /path/to/your/github/key"
    echo ""
    echo "3. Add the public key to GitHub:"
    echo "   https://github.com/settings/keys"
    exit 1
fi

echo "📋 Using GitHub SSH key: $GITHUB_SSH_KEY"
echo ""

# Show the public key
echo "📌 Your public key (add this to GitHub if you haven't already):"
echo "----------------------------------------"
cat "${GITHUB_SSH_KEY}.pub"
echo "----------------------------------------"
echo ""
echo "Add this key to GitHub:"
echo "https://github.com/settings/keys"
echo ""
read -p "Press Enter once you've added the key to GitHub..."

# Create .ssh directory in Jenkins if it doesn't exist
echo "📁 Setting up .ssh directory in Jenkins container..."
docker exec lb-jenkins mkdir -p /var/jenkins_home/.ssh
docker exec lb-jenkins chown jenkins:jenkins /var/jenkins_home/.ssh
docker exec lb-jenkins chmod 700 /var/jenkins_home/.ssh

# Copy GitHub SSH key to Jenkins container
echo "📤 Copying GitHub SSH key to Jenkins container..."
docker cp "$GITHUB_SSH_KEY" lb-jenkins:/var/jenkins_home/.ssh/github_id_rsa
docker cp "${GITHUB_SSH_KEY}.pub" lb-jenkins:/var/jenkins_home/.ssh/github_id_rsa.pub

# Set correct permissions
echo "🔒 Setting correct permissions..."
docker exec lb-jenkins chown jenkins:jenkins /var/jenkins_home/.ssh/github_id_rsa
docker exec lb-jenkins chown jenkins:jenkins /var/jenkins_home/.ssh/github_id_rsa.pub
docker exec lb-jenkins chmod 600 /var/jenkins_home/.ssh/github_id_rsa
docker exec lb-jenkins chmod 644 /var/jenkins_home/.ssh/github_id_rsa.pub

# Add GitHub to known_hosts
echo "📝 Adding GitHub to known_hosts..."
docker exec lb-jenkins sh -c "ssh-keyscan -H github.com >> /var/jenkins_home/.ssh/known_hosts 2>/dev/null"
docker exec lb-jenkins chown jenkins:jenkins /var/jenkins_home/.ssh/known_hosts
docker exec lb-jenkins chmod 644 /var/jenkins_home/.ssh/known_hosts

# Test GitHub SSH connection
echo ""
echo "🔍 Testing GitHub SSH connection..."
if docker exec -u jenkins lb-jenkins ssh -T -i /var/jenkins_home/.ssh/github_id_rsa git@github.com 2>&1 | grep -q "successfully authenticated"; then
    echo "✅ GitHub SSH connection works!"
else
    echo "⚠️  GitHub SSH connection test (this is normal - GitHub doesn't allow shell access)"
    docker exec -u jenkins lb-jenkins ssh -T -i /var/jenkins_home/.ssh/github_id_rsa git@github.com 2>&1 || true
fi

echo ""
echo "========================================"
echo "✅ GitHub SSH Configuration Complete"
echo "========================================"
echo ""
echo "Next steps:"
echo "1. Update Jenkins job to use the SSH key"
echo "2. Go to Jenkins UI: http://178.156.223.196:8080"
echo "3. Navigate to your pipeline job configuration"
echo "4. Under 'Source Code Management' → 'Git'"
echo "5. Add credentials:"
echo "   - Kind: SSH Username with private key"
echo "   - ID: github-ssh-key"
echo "   - Username: git"
echo "   - Private Key: Enter directly"
echo "   - Copy the private key from: $GITHUB_SSH_KEY"
echo ""
echo "Or run the automated configuration:"
echo "   ./deployment/jenkins/apply-jenkins-config.sh"
echo "========================================"
