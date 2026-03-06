#!/bin/bash
set -e

echo "🔧 Applying Jenkins Configuration as Code..."

# Load environment variables
if [ -f "/opt/lb-automotive-dashboard/.env" ]; then
    export $(cat /opt/lb-automotive-dashboard/.env | grep -v '^#' | xargs)
else
    echo "❌ .env file not found at /opt/lb-automotive-dashboard/.env"
    exit 1
fi

# Get GitHub SSH private key
export GITHUB_SSH_KEY=$(cat ~/.ssh/github_deploy_key)

# Create Jenkins configuration directory if it doesn't exist
docker exec lb-jenkins mkdir -p /var/jenkins_home/casc_configs

# Copy JCasC configuration to Jenkins container with environment variable substitution
cat /opt/lb-automotive-dashboard/deployment/jenkins/jenkins-casc.yaml | \
    envsubst > /tmp/jenkins-casc-expanded.yaml

docker cp /tmp/jenkins-casc-expanded.yaml lb-jenkins:/var/jenkins_home/casc_configs/jenkins.yaml

# Clean up temporary file
rm /tmp/jenkins-casc-expanded.yaml

# Install required plugins
echo "📦 Installing required Jenkins plugins..."
docker exec lb-jenkins jenkins-plugin-cli --plugins \
    configuration-as-code \
    credentials \
    credentials-binding \
    plain-credentials \
    ssh-credentials \
    git \
    github \
    pipeline-model-definition \
    workflow-aggregator \
    docker-workflow \
    job-dsl

# Set CASC configuration path
docker exec lb-jenkins sh -c 'echo "CASC_JENKINS_CONFIG=/var/jenkins_home/casc_configs" >> /var/jenkins_home/.env'

# Restart Jenkins to apply configuration
echo "🔄 Restarting Jenkins to apply configuration..."
docker restart lb-jenkins

echo "⏳ Waiting for Jenkins to start..."
sleep 20

# Wait for Jenkins to be ready
until curl -s http://localhost:8080/login > /dev/null 2>&1; do
    echo "   Waiting for Jenkins..."
    sleep 5
done

echo "✅ Jenkins configuration applied successfully!"
echo ""
echo "📊 Access Jenkins at: http://178.156.223.196:8080"
echo ""
echo "Next steps:"
echo "1. Log into Jenkins"
echo "2. Your pipeline 'LB-Automotive-Dashboard-Pipeline' should be created"
echo "3. Click 'Build Now' to trigger the first build"
