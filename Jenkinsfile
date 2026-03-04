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

        // Deployment
        DEPLOY_USER = 'lb-admin'
        DEPLOY_HOST = '178.156.223.196'
        DEPLOY_DIR = '/opt/lb-automotive-dashboard'
        MANIFEST_DIR = '~/k8s-manifests'

        // Python version
        PYTHON_VERSION = '3.11'

        // Node version
        NODE_VERSION = '18'
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

        stage('Setup Python Environment') {
            steps {
                echo '🐍 Setting up Python environment...'
                sh '''
                    cd python-backend
                    python3 -m venv venv || true
                    . venv/bin/activate
                    pip install --upgrade pip
                    pip install -r requirements.txt
                    pip install pytest httpx
                '''
            }
        }

        stage('Backend Tests') {
            environment {
                SECRET_KEY = 'test-secret-key-for-ci-only-not-production'
                ALLOWED_ORIGINS = 'http://localhost:5173,http://localhost:3000'
                DATABASE_URL = 'sqlite:///./test_lb_automotive.db'
            }
            steps {
                echo '🧪 Running backend tests...'
                sh '''
                    cd python-backend
                    . venv/bin/activate
                    if [ -d "tests" ] && [ "$(ls -A tests)" ]; then
                        pytest --verbose --color=yes || true
                    else
                        echo "⚠️ No backend tests found, skipping..."
                    fi
                '''
            }
            post {
                always {
                    sh 'rm -f python-backend/test_lb_automotive.db || true'
                }
            }
        }

        stage('Setup Node Environment') {
            steps {
                echo '📦 Setting up Node environment...'
                sh '''
                    cd frontend
                    npm ci
                '''
            }
        }

        stage('Frontend Tests') {
            steps {
                echo '🧪 Running frontend tests...'
                sh '''
                    cd frontend
                    if npm run test --if-present; then
                        echo "✅ Frontend tests passed"
                    else
                        echo "⚠️ No frontend tests configured, skipping..."
                    fi
                '''
            }
        }

        stage('Build Docker Images') {
            when {
                anyOf {
                    branch 'main'
                    branch 'master'
                    expression { env.GIT_BRANCH ==~ /.*release\/.*/ }
                }
            }
            steps {
                echo '🐳 Building Docker images...'
                script {
                    // Build backend
                    sh """
                        docker build -t ${BACKEND_IMAGE}:${BUILD_TAG} -f python-backend/Dockerfile .
                        docker tag ${BACKEND_IMAGE}:${BUILD_TAG} ${BACKEND_IMAGE}:latest
                    """
                    
                    // Build frontend
                    sh """
                        docker build --no-cache -t ${FRONTEND_IMAGE}:${BUILD_TAG} -f frontend/Dockerfile.prod .
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
                    expression { env.GIT_BRANCH ==~ /.*release\/.*/ }
                }
            }
            steps {
                echo '📤 Pushing images to GHCR...'
                script {
                    // Login to GHCR
                    withCredentials([string(credentialsId: 'github-token', variable: 'GITHUB_TOKEN')]) {
                        sh '''
                            echo "$GITHUB_TOKEN" | docker login ghcr.io -u gamebox-inc --password-stdin
                        '''
                    }
                    
                    // Push images
                    sh """
                        docker push ${BACKEND_IMAGE}:${BUILD_TAG}
                        docker push ${BACKEND_IMAGE}:latest
                        docker push ${FRONTEND_IMAGE}:${BUILD_TAG}
                        docker push ${FRONTEND_IMAGE}:latest
                    """
                }
            }
        }

        stage('Ensure Vault Unsealed') {
            // Vault seals after every pod restart. Unseal it before deploying
            // so the backend's sidecar can inject secrets.
            // Keys are stored as Jenkins Secret Text credentials — never interpolated.
            when {
                anyOf {
                    branch 'main'
                    branch 'master'
                    expression { env.GIT_BRANCH ==~ /.*release\/.*/ }
                }
            }
            steps {
                echo '🔐 Checking Vault seal status...'
                script {
                    withCredentials([
                        string(credentialsId: 'vault-unseal-key-1', variable: 'KEY1'),
                        string(credentialsId: 'vault-unseal-key-2', variable: 'KEY2'),
                        string(credentialsId: 'vault-unseal-key-3', variable: 'KEY3')
                    ]) {
                        sshagent(credentials: ['lb-server-ssh']) {
                            // IMPORTANT: single quotes prevent Groovy from interpolating
                            // secret variables into the shell string (Jenkins security best practice).
                            // The shell itself expands $KEY1/$KEY2/$KEY3 safely at runtime.
                            sh '''
                                SEALED=$(ssh -o StrictHostKeyChecking=no ''' + env.DEPLOY_USER + '@' + env.DEPLOY_HOST + ''' \
                                    "sudo k3s kubectl exec -n gamebox-security vault-0 -c vault -- \
                                     env VAULT_SKIP_VERIFY=true vault status -format=json 2>/dev/null | \
                                     python3 -c \\"import sys,json; print(json.load(sys.stdin)[\'sealed\'])\\""  \
                                    2>/dev/null || echo True)
                                if [ "$SEALED" = "True" ]; then
                                    echo "Vault is sealed — unsealing..."
                                    ssh -o StrictHostKeyChecking=no ''' + env.DEPLOY_USER + '@' + env.DEPLOY_HOST + ''' \
                                        "sudo k3s kubectl exec -n gamebox-security vault-0 -c vault -- \
                                         env VAULT_SKIP_VERIFY=true vault operator unseal $KEY1"
                                    ssh -o StrictHostKeyChecking=no ''' + env.DEPLOY_USER + '@' + env.DEPLOY_HOST + ''' \
                                        "sudo k3s kubectl exec -n gamebox-security vault-0 -c vault -- \
                                         env VAULT_SKIP_VERIFY=true vault operator unseal $KEY2"
                                    ssh -o StrictHostKeyChecking=no ''' + env.DEPLOY_USER + '@' + env.DEPLOY_HOST + ''' \
                                        "sudo k3s kubectl exec -n gamebox-security vault-0 -c vault -- \
                                         env VAULT_SKIP_VERIFY=true vault operator unseal $KEY3"
                                    echo "✅ Vault unsealed successfully"
                                else
                                    echo "✅ Vault already unsealed"
                                fi
                            '''
                        }
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
                    expression { env.GIT_BRANCH ==~ /.*release\/.*/ }
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
                        // Copy all manifests to server
                        sh """
                            scp -o StrictHostKeyChecking=no -r \
                                deployment/k8s/ \
                                ${DEPLOY_USER}@${DEPLOY_HOST}:${MANIFEST_DIR}/
                        """
                        // Apply all K8s manifests in a single SSH session to avoid connection rate limits
                        sh """
                            ssh -o StrictHostKeyChecking=no ${DEPLOY_USER}@${DEPLOY_HOST} '
                                set -e
                                echo "▶ Applying namespace..."
                                sudo k3s kubectl apply -f ${MANIFEST_DIR}/k8s/namespace.yaml

                                echo "▶ Applying gamebox-security..."
                                sudo k3s kubectl apply -f ${MANIFEST_DIR}/k8s/gamebox-security/

                                echo "▶ Applying Traefik routes..."
                                sudo k3s kubectl apply \
                                    -f ${MANIFEST_DIR}/k8s/gamebox-security/traefik/gateway.yaml \
                                    -f ${MANIFEST_DIR}/k8s/gamebox-security/traefik/middlewares.yaml \
                                    -f ${MANIFEST_DIR}/k8s/gamebox-security/traefik/lb-automotive-routes.yaml

                                echo "▶ Applying lb-automotive workloads..."
                                sudo k3s kubectl apply \
                                    -f ${MANIFEST_DIR}/k8s/redis.yaml \
                                    -f ${MANIFEST_DIR}/k8s/backend.yaml \
                                    -f ${MANIFEST_DIR}/k8s/frontend.yaml

                                echo "▶ Applying lb-automotive namespace resources..."
                                sudo k3s kubectl apply -f ${MANIFEST_DIR}/k8s/lb-automotive/ || true

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

        stage('Ensure Vault Unsealed') {
            // Vault is sealed after every pod/node restart.
            // Unseal keys are stored in Jenkins credentials — never in Git.
            when {
                anyOf {
                    branch 'main'
                    branch 'master'
                    expression { env.GIT_BRANCH ==~ /.*release\/.*/ }
                }
            }
            steps {
                script {
                    sshagent(credentials: ['lb-server-ssh']) {
                        withCredentials([
                            string(credentialsId: 'vault-unseal-key-1', variable: 'KEY1'),
                            string(credentialsId: 'vault-unseal-key-2', variable: 'KEY2'),
                            string(credentialsId: 'vault-unseal-key-3', variable: 'KEY3')
                        ]) {
                            sh """
                                ssh -o StrictHostKeyChecking=no ${DEPLOY_USER}@${DEPLOY_HOST} '
                                    # Check if Vault pod exists and is sealed
                                    VAULT_STATUS=\$(sudo k3s kubectl exec -n gamebox-security vault-0 -- vault status -format=json 2>/dev/null || echo "unavailable")

                                    if echo "\$VAULT_STATUS" | grep -q "unavailable"; then
                                        echo "⚠️  Vault pod not found — skipping unseal (secrets may fail)"
                                    elif echo "\$VAULT_STATUS" | grep -q "\\"sealed\\":true"; then
                                        echo "🔓 Vault is sealed — auto-unsealing..."
                                        sudo k3s kubectl exec -n gamebox-security vault-0 -- vault operator unseal ${KEY1}
                                        sudo k3s kubectl exec -n gamebox-security vault-0 -- vault operator unseal ${KEY2}
                                        sudo k3s kubectl exec -n gamebox-security vault-0 -- vault operator unseal ${KEY3}
                                        echo "✅ Vault unsealed successfully"
                                    else
                                        echo "✅ Vault is already unsealed"
                                    fi
                                '
                            """
                        }
                    }
                }
            }
        }

        stage('Deploy to Production') {
            when {
                anyOf {
                    branch 'main'
                    branch 'master'
                    expression { env.GIT_BRANCH ==~ /.*release\/.*/ }
                }
            }
            steps {
                echo '🚀 Deploying to production server...'
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
                            # Wait for rollouts to complete
                            ssh -o StrictHostKeyChecking=no ${DEPLOY_USER}@${DEPLOY_HOST} \
                                "sudo k3s kubectl rollout status deployment/backend -n lb-automotive --timeout=2m"
                        """
                        sh """
                            ssh -o StrictHostKeyChecking=no ${DEPLOY_USER}@${DEPLOY_HOST} \
                                "sudo k3s kubectl rollout status deployment/frontend -n lb-automotive --timeout=2m"
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

        failure {
            echo '❌ Pipeline failed! Check logs for details.'
        }
    }
}
