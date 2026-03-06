# Quick deployment script to update Nginx configuration
$SERVER = "root@178.156.223.196"
$SSH_KEY = "$HOME\.ssh\lb-automotive-key"
$REMOTE_DIR = "/opt/lb-automotive-dashboard"

Write-Host "Uploading updated nginx-https.conf..." -ForegroundColor Cyan
scp -i $SSH_KEY deployment/docker/nginx-https.conf "${SERVER}:${REMOTE_DIR}/deployment/docker/"

Write-Host "Rebuilding frontend container..." -ForegroundColor Cyan
ssh -i $SSH_KEY $SERVER @"
cd $REMOTE_DIR
docker compose -f deployment/docker/docker-compose.yml up -d --build --force-recreate frontend
"@

Write-Host "Deployment complete! Access the dashboard at http://10.100.0.1" -ForegroundColor Green
