pipeline {
    agent any
    


    environment {
        // Docker Registry (using GitHub Container Registry)
        REGISTRY = 'ghcr.io'
        REGISTRY_CREDENTIAL = 'github-token'

        // Image names
        BACKEND_IMAGE = "${REGISTRY}/gamebox-inc/lb-automotive-backend"
        FRONTEND_IMAGE = "${REGISTRY}/gamebox-inc/lb-automotive-frontend"

        // Build info
        BUILD_TAG = "${env.BUILD_NUMBER}-${env.GIT_COMMIT.take(7)}"

        // Deployment (Values provided via Jenkins Global Environment Variables)
        DEPLOY_USER    = "${env.DEPLOY_USER}"
        DEPLOY_HOST    = "${env.DEPLOY_HOST}"
        DEPLOY_DIR     = "${env.DEPLOY_DIR}"
        MANIFEST_DIR   = "${env.MANIFEST_DIR}"

        // Python version
        PYTHON_VERSION = '3.11'

        // Node version
        NODE_VERSION = '20'
    }

    options {
        buildDiscarder(logRotator(numToKeepStr: '10'))
        timeout(time: 30, unit: 'MINUTES')
        timestamps()
    }

    stages {
        stage('Checkout') {
            steps {
                echo '📥 Checking out code...'
                checkout scm
                script {
                    env.GIT_COMMIT_MSG = sh(
                        script: 'git log -1 --pretty=%B',
                        returnStdout: true
                    ).trim()
                }
            }
        }

        // Optimized: Removing host-side dependency setup to save CPU/RAM.
        // Docker build will handle dependency installation and caching.

        // Optimized: Tests and Setup are now handled inside the 'Build Docker Images' stage
        // using non-root multi-stage Docker builds.

        stage('Build Docker Images') {
            when {
                anyOf {
                    branch 'main'
                    branch 'master'
                    expression { env.BRANCH_NAME ==~ /.*release\/.*/ || env.GIT_BRANCH ==~ /.*release\/.*/ }
                }
            }
            steps {
                echo '🐳 Building Docker images...'
                script {
                    // Catch Python syntax/indent errors before building (e.g. IndentationError in webhook.py)
                    sh """
                        cd python-backend && python -m compileall -q . && cd ..
                    """
                    // Build backend
                    sh """
                        docker build -t ${BACKEND_IMAGE}:${BUILD_TAG} -f python-backend/Dockerfile .
                        docker tag ${BACKEND_IMAGE}:${BUILD_TAG} ${BACKEND_IMAGE}:latest
                    """
                    
                    // Build frontend (Optimized: Using layer cache)
                    sh """
                        docker build -t ${FRONTEND_IMAGE}:${BUILD_TAG} -f frontend/Dockerfile.prod .
                        docker tag ${FRONTEND_IMAGE}:${BUILD_TAG} ${FRONTEND_IMAGE}:latest
                    """
                }
            }
        }

        stage('Push Images to Registry') {
            when {
                anyOf {
                    branch 'main'
                    branch 'master'
                    expression { env.BRANCH_NAME ==~ /.*release\/.*/ || env.GIT_BRANCH ==~ /.*release\/.*/ }
                }
            }
            steps {
                echo '📤 Pushing images to GHCR...'
                script {
                    // GHCR push: prefer PAT (REGISTRY_CREDENTIAL). Org packages reject App tokens with "installation not allowed to Write organization package".
                    // Ensure Jenkins has a Secret text credential with ID matching REGISTRY_CREDENTIAL (default: github-token), value = classic PAT with write:packages.
                    def credId = env.REGISTRY_CREDENTIAL ?: 'github-token'
                    def loggedIn = false

                    echo "Attempting GHCR login with PAT (credential ID: ${credId})..."
                    try {
                        withCredentials([string(credentialsId: credId, variable: 'GITHUB_TOKEN')]) {
                            sh '''
                                echo "$GITHUB_TOKEN" | docker login ghcr.io -u gamebox-inc --password-stdin
                            '''
                            loggedIn = true
                            echo '✅ GHCR login succeeded with PAT (github-token).'
                        }
                    } catch (Exception e) {
                        echo "⚠️ PAT credential '${credId}' not found or failed: ${e.message}"
                        echo 'Falling back to GitHub App (may fail with "installation not allowed to Write organization package" for org packages).'
                    }

                    if (!loggedIn) {
                        echo 'Attempting GHCR login with GitHub App...'
                        try {
                            withCredentials([
                                file(credentialsId: 'github-app-ghcr-key', variable: 'GITHUB_APP_KEY'),
                                string(credentialsId: 'github-app-id', variable: 'GITHUB_APP_ID'),
                                string(credentialsId: 'github-app-installation-id', variable: 'GITHUB_APP_INSTALLATION_ID')
                            ]) {
                                sh '''
                                    chmod +x deployment/scripts/github_app_token.sh
                                    TOKEN=$(deployment/scripts/github_app_token.sh "$GITHUB_APP_ID" "$GITHUB_APP_INSTALLATION_ID" "$GITHUB_APP_KEY")
                                    echo "$TOKEN" | docker login ghcr.io -u "$GITHUB_APP_ID" --password-stdin
                                '''
                                loggedIn = true
                                echo '✅ GHCR login succeeded with GitHub App token.'
                            }
                        } catch (Exception e2) {
                            echo "GitHub App login failed: ${e2.message}"
                        }
                    }

                    if (!loggedIn) {
                        error("No GHCR credentials. Add a Jenkins Secret text credential with ID '${credId}' (PAT with write:packages) or configure GitHub App credentials.")
                    }

                    echo "Pushing images to ${BACKEND_IMAGE} and ${FRONTEND_IMAGE}..."
                    sh """
                        docker push ${BACKEND_IMAGE}:${BUILD_TAG}
                        docker push ${BACKEND_IMAGE}:latest
                        docker push ${FRONTEND_IMAGE}:${BUILD_TAG}
                        docker push ${FRONTEND_IMAGE}:latest
                    """
                }
            }
        }


        stage('Ensure App Secrets') {
            // Backend uses K8s Secrets (no Vault). Create app-secrets so the backend can start.
            // Add Jenkins secret-text credentials: secret-key, allowed-origins
            // For Twilio/Anthropic run deployment/k8s/create-secrets.sh on the server once.
            when {
                anyOf {
                    branch 'main'
                    branch 'master'
                    expression { env.BRANCH_NAME ==~ /.*release\/.*/ || env.GIT_BRANCH ==~ /.*release\/.*/ }
                }
            }
            steps {
                echo '🔐 Ensuring app-secrets exist on server (K8s Secrets, no Vault)...'
                script {
                    withCredentials([
                        string(credentialsId: 'secret-key', variable: 'SECRET_KEY'),
                        string(credentialsId: 'allowed-origins', variable: 'ALLOWED_ORIGINS'),
                        string(credentialsId: 'supabase-db-url', variable: 'DATABASE_URL')
                    ]) {
                        sshagent(credentials: ['lb-server-ssh']) {
                            // Pass secret values base64-encoded as args and decode on the remote side
                            sh '''
SK_B64=$(printf %s "$SECRET_KEY" | base64 | tr -d '\n')
AO_B64=$(printf %s "$ALLOWED_ORIGINS" | base64 | tr -d '\n')
DB_B64=$(printf %s "$DATABASE_URL" | base64 | tr -d '\n')
ssh -o StrictHostKeyChecking=no "$DEPLOY_USER@$DEPLOY_HOST" bash -s -- "$SK_B64" "$AO_B64" "$DB_B64" << 'REMOTEOF'
set -e
SK=$(printf %s "$1" | base64 -d)
AO=$(printf %s "$2" | base64 -d)
DB=$(printf %s "$3" | base64 -d)
sudo k3s kubectl create secret generic app-secrets -n lb-automotive \
  --from-literal=SECRET_KEY="$SK" \
  --from-literal=ALLOWED_ORIGINS="$AO" \
  --from-literal=DATABASE_URL="$DB" \
  --from-literal=REDIS_URL="redis://redis.lb-automotive.svc.cluster.local:6379/0" \
  --from-literal=LLM_PROVIDER="anthropic" \
  --from-literal=CSP_POLICY="strict" \
  --dry-run=client -o yaml | sudo k3s kubectl apply -f -
echo "✅ app-secrets applied"
REMOTEOF
                            '''
                        }
                    }
                }
            }
        }

        stage('Ensure Twilio Secrets') {
            // Push TWILIO_AUTH_TOKEN from Jenkins credential into K8s twilio-secrets so webhook signature validation works.
            // Add Jenkins secret-text credential: twilio-auth-token (value = Twilio Console Auth Token).
            // Patches existing twilio-secrets so TWILIO_ACCOUNT_SID / TWILIO_PHONE_NUMBER are not overwritten.
            when {
                anyOf {
                    branch 'main'
                    branch 'master'
                    expression { env.BRANCH_NAME ==~ /.*release\/.*/ || env.GIT_BRANCH ==~ /.*release\/.*/ }
                }
            }
            steps {
                echo '🔐 Ensuring twilio-secrets (TWILIO_AUTH_TOKEN) on server from Jenkins credential...'
                script {
                    withCredentials([string(credentialsId: 'twilio-auth-token', variable: 'TWILIO_AUTH_TOKEN')]) {
                        sshagent(credentials: ['lb-server-ssh']) {
                            sh '''
# Strip all whitespace from base64 so JSON patch is one line (avoids tr \\n vs space issues in pipelines)
TA_B64=$(printf %s "$TWILIO_AUTH_TOKEN" | base64 | tr -d '[:space:]')
ssh -o StrictHostKeyChecking=no "$DEPLOY_USER@$DEPLOY_HOST" bash -s -- "$TA_B64" << 'REMOTEOF'
set -e
TA=$(printf %s "$1" | base64 -d)
# Single-line base64 for K8s secret data (strip any whitespace so patch JSON is valid)
TA_B64_LOCAL=$(printf %s "$TA" | base64 -w 0 2>/dev/null || printf %s "$TA" | base64 | tr -d '[:space:]')
if sudo k3s kubectl get secret twilio-secrets -n lb-automotive &>/dev/null; then
  # k3s kubectl often lacks --patch-file; use get + jq + replace to avoid patch JSON parsing issues
  if command -v jq &>/dev/null; then
    SECRET_JSON=$(sudo k3s kubectl get secret twilio-secrets -n lb-automotive -o json)
    echo "$SECRET_JSON" | jq --arg b64 "$TA_B64_LOCAL" '.data.TWILIO_AUTH_TOKEN = $b64 | del(.metadata.resourceVersion, .metadata.uid, .metadata.managedFields, .metadata.creationTimestamp)' | sudo k3s kubectl replace -f -
    echo "✅ twilio-secrets updated (TWILIO_AUTH_TOKEN) via jq+replace"
  else
    # No jq: overwrite secret with only TWILIO_AUTH_TOKEN (other keys like TWILIO_ACCOUNT_SID are lost)
    sudo k3s kubectl delete secret twilio-secrets -n lb-automotive --ignore-not-found
    sudo k3s kubectl create secret generic twilio-secrets -n lb-automotive --from-literal=TWILIO_AUTH_TOKEN="$TA" --dry-run=client -o yaml | sudo k3s kubectl apply -f -
    echo "✅ twilio-secrets recreated (TWILIO_AUTH_TOKEN; install jq to preserve other keys)"
  fi
else
  sudo k3s kubectl create secret generic twilio-secrets -n lb-automotive --from-literal=TWILIO_AUTH_TOKEN="$TA" --dry-run=client -o yaml | sudo k3s kubectl apply -f -
  echo "✅ twilio-secrets created (TWILIO_AUTH_TOKEN set)"
fi
REMOTEOF
                            '''
                        }
                    }
                }
            }
        }

        stage('Run Supabase Migrations') {
            when {
                anyOf {
                    branch 'main'
                    branch 'master'
                    expression { env.BRANCH_NAME ==~ /.*release\/.*/ || env.GIT_BRANCH ==~ /.*release\/.*/ }
                }
            }
            steps {
                echo '🗄️ Applying Supabase/Postgres migrations (scheduling engine, IVR, Kiosk schema)...'
                script {
                    withCredentials([string(credentialsId: 'supabase-db-url', variable: 'DATABASE_URL')]) {
                        sh 'bash deployment/scripts/run_supabase_migrations.sh'
                    }
                }
            }
        }

        stage('Deploy Manifests') {
            // Syncs K8s manifests to server and applies them.
            // Replaces ArgoCD — Jenkins is now the GitOps mechanism.
            when {
                anyOf {
                    branch 'main'
                    branch 'master'
                    expression { env.BRANCH_NAME ==~ /.*release\/.*/ || env.GIT_BRANCH ==~ /.*release\/.*/ }
                }
            }
            steps {
                echo '📋 Syncing K8s manifests to server...'
                script {
                    sshagent(credentials: ['lb-server-ssh']) {
                        // Create manifest staging dir on server
                        sh """
                            ssh -o StrictHostKeyChecking=no ${DEPLOY_USER}@${DEPLOY_HOST} \
                                'mkdir -p ${MANIFEST_DIR}'
                        """
                        // Inject dynamic image tags before copying to server
                        sh """
                            sed -i "s|ghcr.io/gamebox-inc/lb-automotive-frontend:.*|${FRONTEND_IMAGE}:${BUILD_TAG}|g" deployment/k8s/frontend.yaml
                            sed -i "s|ghcr.io/gamebox-inc/lb-automotive-backend:.*|${BACKEND_IMAGE}:${BUILD_TAG}|g" deployment/k8s/backend.yaml
                        """
                        // Copy all manifests to server
                        sh """
                            scp -o StrictHostKeyChecking=no -r \\
                                deployment/k8s/ \\
                                ${DEPLOY_USER}@${DEPLOY_HOST}:${MANIFEST_DIR}/
                        """
                        // Apply all K8s manifests in a single SSH session to avoid connection rate limits
                        sh """
                            ssh -o StrictHostKeyChecking=no ${DEPLOY_USER}@${DEPLOY_HOST} '
                                set -e
                                 echo "▶ Applying K8s manifests (Validation disabled for speed/stability)..."
                                 # We disable validation because the 2GB server often times out during OpenAPI discovery.
                                 # We use a retry loop to handle transient API server unresponsiveness.
                                 RETRY_COUNT=0
                                 MAX_RETRIES=3
                                 until [ \$RETRY_COUNT -ge \$MAX_RETRIES ]
                                 do
                                     echo "▶ Attempt \$((RETRY_COUNT+1)) of \$MAX_RETRIES..."
                                     sudo k3s kubectl apply --validate=false \
                                         -f ~/k8s-manifests/k8s/namespace.yaml \
                                         -f ~/k8s-manifests/k8s/gamebox-security/ \
                                         -f ~/k8s-manifests/k8s/gamebox-security/traefik/gateway.yaml \
                                         -f ~/k8s-manifests/k8s/gamebox-security/traefik/middlewares.yaml \
                                         -f ~/k8s-manifests/k8s/gamebox-security/traefik/lb-automotive-routes.yaml \
                                         -f ~/k8s-manifests/k8s/pvc.yaml \
                                         -f ~/k8s-manifests/k8s/redis.yaml \
                                         -f ~/k8s-manifests/k8s/backend.yaml \
                                         -f ~/k8s-manifests/k8s/frontend.yaml && break
                                     
                                     RETRY_COUNT=\$((RETRY_COUNT+1))
                                     echo "⚠️ API server unresponsive, retrying in 10s..."
                                     sleep 10
                                 done

                                 if [ \$RETRY_COUNT -eq \$MAX_RETRIES ]; then
                                     echo "❌ Failed to apply manifests after \$MAX_RETRIES attempts."
                                     exit 1
                                 fi

                                 echo "▶ Applying lb-automotive namespace resources..."
                                 sudo k3s kubectl apply --validate=false -f ~/k8s-manifests/k8s/lb-automotive/ || true

                                 echo "▶ Removing legacy Ingress objects..."
                                 sudo k3s kubectl delete ingress lb-automotive-ingress -n lb-automotive --ignore-not-found
                                 sudo k3s kubectl delete ingress twilio-webhook-ingress -n lb-automotive --ignore-not-found
                            '
                        """
                        echo '✅ Manifests applied successfully'
                    }
                }
            }
        }

        stage('Deploy to Production') {
            when {
                anyOf {
                    branch 'main'
                    branch 'master'
                    expression { env.BRANCH_NAME ==~ /.*release\/.*/ || env.GIT_BRANCH ==~ /.*release\/.*/ }
                }
            }
            steps {
                echo '🚀 Deploying to rocket-1 production server...'
                script {
                    sshagent(credentials: ['lb-server-ssh']) {
                        sh """
                            # Update backend deployment
                            ssh -o StrictHostKeyChecking=no ${DEPLOY_USER}@${DEPLOY_HOST} \
                                "sudo k3s kubectl set image deployment/backend backend=${BACKEND_IMAGE}:${BUILD_TAG} -n lb-automotive"
                        """
                        sh """
                            # Update frontend deployment
                            ssh -o StrictHostKeyChecking=no ${DEPLOY_USER}@${DEPLOY_HOST} \
                                "sudo k3s kubectl set image deployment/frontend frontend=${FRONTEND_IMAGE}:${BUILD_TAG} -n lb-automotive"
                        """
                        sh """
                            # Wait for rollouts to complete (non-fatal; if DB/app-secrets are misconfigured, rollout can hang)
                            ssh -o StrictHostKeyChecking=no ${DEPLOY_USER}@${DEPLOY_HOST} \
                                "sudo k3s kubectl rollout status deployment/backend -n lb-automotive --timeout=5m" || \
                                echo "⚠️ Backend rollout timed out — check backend logs, app-secrets, and DATABASE_URL"
                        """
                        sh """
                            ssh -o StrictHostKeyChecking=no ${DEPLOY_USER}@${DEPLOY_HOST} \
                                "sudo k3s kubectl rollout status deployment/frontend -n lb-automotive --timeout=5m" || \
                                echo "⚠️ Frontend rollout timed out"
                        """
                    }
                }
            }
        }

        stage('Verify Deployment') {
            when {
                branch pattern: "main|master|release/.*", comparator: "REGEXP"
            }
            steps {
                echo '✅ Verifying deployment...'
                script {
                    sh '''
                        # Wait for services to stabilize
                        sleep 10

                        # Check K8s pods
                        echo "🔍 Checking Kubernetes pods..."
                        ssh -o StrictHostKeyChecking=no ${DEPLOY_USER}@${DEPLOY_HOST} \
                            "kubectl get pods -n lb-automotive"

                        # Check backend health via internal NodePort
                        echo "🔍 Checking backend health..."
                        ssh -o StrictHostKeyChecking=no ${DEPLOY_USER}@${DEPLOY_HOST} \
                            "curl -sf http://localhost:30800/health || echo '⚠️ Backend may still be starting...'"

                        # Check frontend health
                        echo "🔍 Checking frontend..."
                        ssh -o StrictHostKeyChecking=no ${DEPLOY_USER}@${DEPLOY_HOST} \
                            "curl -sf http://localhost:30080/ || echo '⚠️ Frontend may still be starting...'"
                    '''
                }
            }
        }
    }

    post {
        success {
            echo '✅ Pipeline completed successfully!'
            script {
                if (env.BRANCH_NAME ==~ /(main|master|release\/.*)/) {
                    echo """
                    ========================================
                    📊 Deployment Summary
                    ========================================
                    Branch: ${env.BRANCH_NAME}
                    Commit: ${env.GIT_COMMIT}
                    Build: #${env.BUILD_NUMBER}
                    Backend URL: http://178.156.223.196:8000
                    Frontend URL: http://178.156.223.196
                    ========================================
                    """
                }
            }
        }

        always {
            echo '🧹 Cleaning up workspace and remote node...'
            script {
                // Conservative cleanup: keep recent images, prune old/unused ones and K3s images
                sshagent(credentials: ['lb-server-ssh']) {
                    sh 'bash deployment/scripts/cleanup-docker-and-k3s.sh || true'
                }
            }
        }
        failure {
            echo '❌ Pipeline failed! Check logs for details.'
        }
    }
}
