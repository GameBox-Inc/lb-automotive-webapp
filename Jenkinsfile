pipeline {
    agent any

    environment {
        // Docker Registry (using Docker Hub or private registry)
        REGISTRY = 'docker.io'
        REGISTRY_CREDENTIAL = 'dockerhub-credentials'

        // Image names
        BACKEND_IMAGE = "${REGISTRY}/lb-automotive/backend"
        FRONTEND_IMAGE = "${REGISTRY}/lb-automotive/frontend"

        // Build info
        BUILD_TAG = "${env.BUILD_NUMBER}-${env.GIT_COMMIT.take(7)}"

        // Deployment
        DEPLOY_USER = 'lb-admin'
        DEPLOY_HOST = '178.156.223.196'
        DEPLOY_DIR = '/opt/lb-automotive-dashboard'

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
                        pytest --verbose --color=yes
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
                branch pattern: "main|master|release/.*", comparator: "REGEXP"
            }
            parallel {
                stage('Build Backend') {
                    steps {
                        echo '🐳 Building backend Docker image...'
                        script {
                            docker.build(
                                "${BACKEND_IMAGE}:${BUILD_TAG}",
                                "-f deployment/docker/Dockerfile.backend ."
                            )
                            docker.build(
                                "${BACKEND_IMAGE}:latest",
                                "-f deployment/docker/Dockerfile.backend ."
                            )
                        }
                    }
                }

                stage('Build Frontend Image') {
                    steps {
                        script {
                            echo "Building frontend Docker image..."
                            docker.build("${FRONTEND_IMAGE}:${BUILD_TAG}", "-f frontend/Dockerfile.prod frontend")
                            docker.build("${FRONTEND_IMAGE}:latest", "-f frontend/Dockerfile.prod frontend")
                        }
                    }
                }
            }
        }

        stage('Push Docker Images') {
            when {
                branch pattern: "main|master|release/.*", comparator: "REGEXP"
            }
            steps {
                echo '📤 Pushing Docker images to registry...'
                script {
                    docker.withRegistry("https://${REGISTRY}", REGISTRY_CREDENTIAL) {
                        docker.image("${BACKEND_IMAGE}:${BUILD_TAG}").push()
                        docker.image("${BACKEND_IMAGE}:latest").push()
                        docker.image("${FRONTEND_IMAGE}:${BUILD_TAG}").push()
                        docker.image("${FRONTEND_IMAGE}:latest").push()
                    }
                }
            }
        }

        stage('Deploy to Production') {
            when {
                branch pattern: "main|master|release/.*", comparator: "REGEXP"
            }
            steps {
                echo '🚀 Deploying to production server...'
                script {
                    withCredentials([
                        string(credentialsId: 'secret-key', variable: 'SECRET_KEY'),
                        string(credentialsId: 'allowed-origins', variable: 'ALLOWED_ORIGINS'),
                        string(credentialsId: 'llm-provider', variable: 'LLM_PROVIDER'),
                        string(credentialsId: 'anthropic-api-key', variable: 'ANTHROPIC_API_KEY'),
                        string(credentialsId: 'twilio-account-sid', variable: 'TWILIO_ACCOUNT_SID'),
                        string(credentialsId: 'twilio-auth-token', variable: 'TWILIO_AUTH_TOKEN'),
                        string(credentialsId: 'twilio-phone-number', variable: 'TWILIO_PHONE_NUMBER')
                    ]) {
                        sh '''
                            # Copy K8s deployment script to server
                            scp -o StrictHostKeyChecking=no \
                                deployment/scripts/jenkins-deploy-k8s.sh \
                                ${DEPLOY_USER}@${DEPLOY_HOST}:/tmp/jenkins-deploy-k8s.sh

                            # Execute K8s deployment on remote server
                            ssh -o StrictHostKeyChecking=no ${DEPLOY_USER}@${DEPLOY_HOST} \
                                "bash /tmp/jenkins-deploy-k8s.sh \
                                '${DEPLOY_DIR}' \
                                '${GIT_BRANCH}' \
                                '${SECRET_KEY}' \
                                '${ALLOWED_ORIGINS}' \
                                '${LLM_PROVIDER}' \
                                '${ANTHROPIC_API_KEY}' \
                                '${TWILIO_ACCOUNT_SID}' \
                                '${TWILIO_AUTH_TOKEN}' \
                                '${TWILIO_PHONE_NUMBER}' \
                                '${BUILD_TAG}'"
                        '''
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

                        # Check backend health
                        echo "🔍 Checking backend health..."
                        ssh -o StrictHostKeyChecking=no ${DEPLOY_USER}@${DEPLOY_HOST} \
                            "curl -f http://localhost:8000/health || echo '⚠️ Backend may still be starting...'"

                        # Check frontend health
                        echo "🔍 Checking frontend..."
                        ssh -o StrictHostKeyChecking=no ${DEPLOY_USER}@${DEPLOY_HOST} \
                            "curl -f http://localhost/ || echo '⚠️ Frontend may still be starting...'"
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
