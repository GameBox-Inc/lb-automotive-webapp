#!/bin/bash
# Configure SSH keys in Jenkins container for deployment
# Run this after Jenkins is set up

set -e

echo "========================================"
echo "🔐 Configuring SSH for Jenkins"
echo "========================================"

# Check if Jenkins is running
if ! docker ps | grep -q lb-jenkins; then
    echo "❌ Jenkins container is not running"
    echo "Start it with: cd /opt/jenkins && docker compose up -d"
    exit 1
fi

# SSH key location
SSH_KEY="$HOME/.ssh/jenkins_deploy_key"

if [ ! -f "$SSH_KEY" ]; then
    echo "❌ SSH key not found at: $SSH_KEY"
    echo "Generate it first with: ssh-keygen -t rsa -b 4096 -f $SSH_KEY"
    exit 1
fi

echo "📋 Found SSH key at: $SSH_KEY"

# Create .ssh directory in Jenkins if it doesn't exist
echo "📁 Creating .ssh directory in Jenkins container..."
docker exec lb-jenkins mkdir -p /var/jenkins_home/.ssh
docker exec lb-jenkins chown jenkins:jenkins /var/jenkins_home/.ssh
docker exec lb-jenkins chmod 700 /var/jenkins_home/.ssh

# Copy SSH keys to Jenkins container
echo "📤 Copying SSH keys to Jenkins container..."
docker cp "$SSH_KEY" lb-jenkins:/var/jenkins_home/.ssh/id_rsa
docker cp "$SSH_KEY.pub" lb-jenkins:/var/jenkins_home/.ssh/id_rsa.pub

# Set correct permissions
echo "🔒 Setting correct permissions..."
docker exec lb-jenkins chown jenkins:jenkins /var/jenkins_home/.ssh/id_rsa
docker exec lb-jenkins chown jenkins:jenkins /var/jenkins_home/.ssh/id_rsa.pub
docker exec lb-jenkins chmod 600 /var/jenkins_home/.ssh/id_rsa
docker exec lb-jenkins chmod 644 /var/jenkins_home/.ssh/id_rsa.pub

# Add server to known_hosts
echo "📝 Adding server to known_hosts..."
docker exec lb-jenkins ssh-keyscan -H 178.156.223.196 > /tmp/known_hosts_temp
docker exec lb-jenkins ssh-keyscan -H localhost >> /tmp/known_hosts_temp
docker cp /tmp/known_hosts_temp lb-jenkins:/var/jenkins_home/.ssh/known_hosts
docker exec lb-jenkins chown jenkins:jenkins /var/jenkins_home/.ssh/known_hosts
rm /tmp/known_hosts_temp

# Test SSH connection from Jenkins
echo ""
echo "🔍 Testing SSH connection from Jenkins container..."
if docker exec -u jenkins lb-jenkins ssh -o StrictHostKeyChecking=no -i /var/jenkins_home/.ssh/id_rsa $USER@178.156.223.196 "echo 'SSH test successful'" 2>/dev/null; then
    echo "✅ SSH connection works!"
else
    echo "⚠️  SSH connection failed"
    echo ""
    echo "Troubleshooting:"
    echo "1. Verify public key is in ~/.ssh/authorized_keys:"
    echo "   cat $SSH_KEY.pub >> ~/.ssh/authorized_keys"
    echo ""
    echo "2. Check SSH service is running:"
    echo "   sudo systemctl status ssh"
    echo ""
    echo "3. Test manually:"
    echo "   ssh -i $SSH_KEY $USER@178.156.223.196"
fi

echo ""
echo "========================================"
echo "✅ SSH Configuration Complete"
echo "========================================"
echo ""
echo "SSH keys have been configured in Jenkins container"
echo "Jenkins can now deploy to: $USER@178.156.223.196"
echo ""
echo "Next: Configure Jenkins pipeline in the UI"
echo "See: deployment/jenkins/README.md"
echo "========================================"
