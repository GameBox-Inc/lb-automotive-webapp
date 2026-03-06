#!/bin/bash
set -e

# Jenkins Configuration via REST API
# Usage: ./configure-jenkins-api.sh <jenkins-user> <jenkins-api-token>

if [ $# -lt 2 ]; then
    echo "Usage: $0 <jenkins-user> <jenkins-api-token>"
    echo ""
    echo "To get an API token:"
    echo "1. Log into Jenkins at http://178.156.223.196:8080"
    echo "2. Click your username (top right) → Configure"
    echo "3. Click 'Add new Token' under API Token section"
    echo "4. Copy the generated token"
    exit 1
fi

JENKINS_USER="$1"
JENKINS_TOKEN="$2"
JENKINS_URL="http://178.156.223.196:8080"

echo "🔧 Configuring Jenkins via REST API..."

# Load environment variables
if [ -f "/opt/lb-automotive-dashboard/.env" ]; then
    export $(cat /opt/lb-automotive-dashboard/.env | grep -v '^#' | xargs)
else
    echo "❌ .env file not found"
    exit 1
fi

# Function to create secret text credential
create_secret_credential() {
    local cred_id="$1"
    local secret="$2"
    local description="$3"

    echo "  Adding credential: $cred_id"

    curl -s -X POST "$JENKINS_URL/credentials/store/system/domain/_/createCredentials" \
        --user "$JENKINS_USER:$JENKINS_TOKEN" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        --data-urlencode "json={
            \"\": \"0\",
            \"credentials\": {
                \"scope\": \"GLOBAL\",
                \"id\": \"$cred_id\",
                \"secret\": \"$secret\",
                \"description\": \"$description\",
                \"\$class\": \"org.jenkinsci.plugins.plaincredentials.impl.StringCredentialsImpl\"
            }
        }" > /dev/null && echo "    ✅ $cred_id added" || echo "    ⚠️  $cred_id may already exist"
}

# Function to create SSH credential
create_ssh_credential() {
    local cred_id="$1"
    local username="$2"
    local private_key="$3"
    local description="$4"

    echo "  Adding SSH credential: $cred_id"

    # Escape the private key for JSON
    local escaped_key=$(echo "$private_key" | jq -Rs .)

    curl -s -X POST "$JENKINS_URL/credentials/store/system/domain/_/createCredentials" \
        --user "$JENKINS_USER:$JENKINS_TOKEN" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        --data-urlencode "json={
            \"\": \"0\",
            \"credentials\": {
                \"scope\": \"GLOBAL\",
                \"id\": \"$cred_id\",
                \"username\": \"$username\",
                \"privateKeySource\": {
                    \"privateKey\": $escaped_key,
                    \"stapler-class\": \"com.cloudbees.jenkins.plugins.sshcredentials.impl.BasicSSHUserPrivateKey\$DirectEntryPrivateKeySource\"
                },
                \"description\": \"$description\",
                \"stapler-class\": \"com.cloudbees.jenkins.plugins.sshcredentials.impl.BasicSSHUserPrivateKey\"
            }
        }" > /dev/null && echo "    ✅ $cred_id added" || echo "    ⚠️  $cred_id may already exist"
}

echo "📋 Creating Jenkins credentials..."

# Create secret credentials
create_secret_credential "secret-key" "$SECRET_KEY" "JWT signing secret"
create_secret_credential "allowed-origins" "$ALLOWED_ORIGINS" "CORS allowed origins"
create_secret_credential "llm-provider" "$LLM_PROVIDER" "LLM provider selection"
create_secret_credential "anthropic-api-key" "${ANTHROPIC_API_KEY:-}" "Anthropic Claude API key"
create_secret_credential "twilio-account-sid" "$TWILIO_ACCOUNT_SID" "Twilio Account SID"
create_secret_credential "twilio-auth-token" "$TWILIO_AUTH_TOKEN" "Twilio Auth Token"
create_secret_credential "twilio-phone-number" "$TWILIO_PHONE_NUMBER" "Twilio Phone Number"

# Create SSH credential
GITHUB_SSH_KEY=$(cat ~/.ssh/github_deploy_key)
create_ssh_credential "github-ssh-key" "git" "$GITHUB_SSH_KEY" "GitHub SSH Deploy Key"

echo ""
echo "📦 Creating Pipeline Job..."

# Create pipeline job XML
cat > /tmp/jenkins-job.xml << 'EOF'
<?xml version='1.1' encoding='UTF-8'?>
<flow-definition plugin="workflow-job">
  <description>CI/CD Pipeline for LB Automotive Dashboard - Automated testing and deployment</description>
  <keepDependencies>false</keepDependencies>
  <properties>
    <jenkins.model.BuildDiscarderProperty>
      <strategy class="hudson.tasks.LogRotator">
        <daysToKeep>-1</daysToKeep>
        <numToKeep>10</numToKeep>
        <artifactDaysToKeep>-1</artifactDaysToKeep>
        <artifactNumToKeep>-1</artifactNumToKeep>
      </strategy>
    </jenkins.model.BuildDiscarderProperty>
    <org.jenkinsci.plugins.workflow.job.properties.PipelineTriggersJobProperty>
      <triggers>
        <com.cloudbees.jenkins.GitHubPushTrigger plugin="github">
          <spec></spec>
        </com.cloudbees.jenkins.GitHubPushTrigger>
      </triggers>
    </org.jenkinsci.plugins.workflow.job.properties.PipelineTriggersJobProperty>
  </properties>
  <definition class="org.jenkinsci.plugins.workflow.cps.CpsScmFlowDefinition" plugin="workflow-cps">
    <scm class="hudson.plugins.git.GitSCM" plugin="git">
      <configVersion>2</configVersion>
      <userRemoteConfigs>
        <hudson.plugins.git.UserRemoteConfig>
          <url>git@github.com:GameBox-Inc/lb-automotive-webapp.git</url>
          <credentialsId>github-ssh-key</credentialsId>
        </hudson.plugins.git.UserRemoteConfig>
      </userRemoteConfigs>
      <branches>
        <hudson.plugins.git.BranchSpec>
          <name>*/release/v0.1</name>
        </hudson.plugins.git.BranchSpec>
      </branches>
    </scm>
    <scriptPath>Jenkinsfile</scriptPath>
    <lightweight>true</lightweight>
  </definition>
  <triggers/>
  <disabled>false</disabled>
</flow-definition>
EOF

# Create the job
curl -s -X POST "$JENKINS_URL/createItem?name=LB-Automotive-Dashboard-Pipeline" \
    --user "$JENKINS_USER:$JENKINS_TOKEN" \
    -H "Content-Type: application/xml" \
    --data-binary @/tmp/jenkins-job.xml > /dev/null \
    && echo "  ✅ Pipeline job created" \
    || echo "  ⚠️  Pipeline job may already exist"

rm /tmp/jenkins-job.xml

echo ""
echo "✅ Jenkins configured successfully via REST API!"
echo ""
echo "📊 Access Jenkins at: $JENKINS_URL"
echo "🚀 Pipeline: $JENKINS_URL/job/LB-Automotive-Dashboard-Pipeline/"
echo ""
echo "Next steps:"
echo "1. Visit the pipeline URL above"
echo "2. Click 'Build Now' to trigger the first build"
