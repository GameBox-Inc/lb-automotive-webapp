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


        stage('Patch Vault Seal Token') {
            // ── Why this stage exists ──────────────────────────────────────────
            // token_file is NOT a valid HCL parameter in Vault 1.21.2 — it is
            // silently ignored.  The seal "transit" stanza requires token= set
            // directly in the HCL.  The checked-in values file contains a
            // PLACEHOLDER_TRANSIT_TOKEN sentinel.  This stage patches the live
            // ConfigMap with the real token from a Jenkins credential so that:
            //   - the real token is never stored in Git
            //   - any helm upgrade cannot revert it without this stage re-applying it
            //   - the patch is idempotent: vault-0 is only restarted when the token
            //     has actually changed
            //
            // PREREQUISITE: Create a Jenkins secret-text credential with ID
            //   'vault-transit-token' containing the transit token from Unseal Vault.
            // ──────────────────────────────────────────────────────────────────
            when {
                anyOf {
                    branch 'main'
                    branch 'master'
                    expression { env.BRANCH_NAME ==~ /.*release\/.*/ || env.GIT_BRANCH ==~ /.*release\/.*/ }
                }
            }
            steps {
                echo '🔐 Patching Vault transit seal token in ConfigMap...'
                script {
                    withCredentials([string(credentialsId: 'vault-transit-token', variable: 'TRANSIT_TOKEN')]) {
                        sshagent(credentials: ['lb-server-ssh']) {
                            sh """
                                # Pass the sensitive token as a positional argument to the remote shell
                                # to avoid insecure Groovy interpolation and leaking secrets in process trees.
                                ssh -o StrictHostKeyChecking=no ${DEPLOY_USER}@${DEPLOY_HOST} "bash -s -- \$TRANSIT_TOKEN" <<'REMOTEOF'
                                    set -e
                                    TOKEN="\$1"
                                    NS="gamebox-security"
                                    CM="vault"

                                    echo "▶ Reading current ConfigMap..."
                                    CURRENT=\$(sudo k3s kubectl get configmap "\$CM" -n "\$NS" \
                                        -o jsonpath="{.data.extraconfig-from-values\\\\.hcl}" 2>/dev/null || echo "")

                                    if echo "\$CURRENT" | grep -q "PLACEHOLDER_TRANSIT_TOKEN"; then
                                        echo "▶ PLACEHOLDER found — patching token into ConfigMap..."
                                        NEW=\$(echo "\$CURRENT" | sed "s|PLACEHOLDER_TRANSIT_TOKEN|\$TOKEN|g")
                                        sudo k3s kubectl patch configmap "\$CM" -n "\$NS" \
                                            --type merge \
                                            -p "{\\"data\\":{\\"extraconfig-from-values.hcl\\":\\"\$NEW\\"}}"
                                        
                                        echo "▶ ConfigMap patched — deleting vault-0 to pick up new config..."
                                        sudo k3s kubectl delete pod vault-0 -n "\$NS" --ignore-not-found
                                        
                                        echo "▶ Waiting for vault-0 to become ready..."
                                        sudo k3s kubectl wait pod vault-0 -n "\$NS" \
                                            --for=condition=Ready --timeout=120s
                                    else
                                        echo "▶ Token already patched — no restart needed"
                                    fi

                                    echo "▶ Verifying Vault seal status..."
                                    sleep 5
                                    sudo k3s kubectl exec -n "\$NS" vault-0 -c vault -- \
                                        env VAULT_SKIP_VERIFY=true vault status -format=json | \
                                        grep -E "\\\"sealed\\\":|\\\"type\\\":"
REMOTEOF
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
                    expression { env.BRANCH_NAME ==~ /.*release\/.*/ || env.GIT_BRANCH ==~ /.*release\/.*/ }
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
                                "sudo k3s kubectl rollout status deployment/backend -n lb-automotive --timeout=5m"
                        """
                        sh """
                            ssh -o StrictHostKeyChecking=no ${DEPLOY_USER}@${DEPLOY_HOST} \
                                "sudo k3s kubectl rollout status deployment/frontend -n lb-automotive --timeout=5m"
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
            sh 'docker image prune -f || true'
            sshagent(credentials: ['lb-server-ssh']) {
                sh """
                    ssh -o StrictHostKeyChecking=no ${DEPLOY_USER}@${DEPLOY_HOST} '
                        echo "▶ Pruning remote images..."
                        sudo k3s crictl rmi --prune || true
                        
                        echo "▶ Cleaning up completed/failed pods..."
                        sudo k3s kubectl delete pods --all-namespaces --field-selector=status.phase==Succeeded --ignore-not-found || true
                        sudo k3s kubectl delete pods --all-namespaces --field-selector=status.phase==Failed --ignore-not-found || true
                    '
                """
            }
        }
        failure {
            echo '❌ Pipeline failed! Check logs for details.'
        }
    }
}
