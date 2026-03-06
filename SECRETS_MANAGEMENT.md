# Server Setup Instructions

## 1. Credentials
Before deployment, manually copy the following files to the server at `/opt/lb-automotive-dashboard`:

- `deployment/docker/nginx-selfsigned.key`
- `deployment/docker/nginx-selfsigned.crt`
- `deployment/argocd/github-app.pem` (Delete after configuring secret)

## 2. Generate on Server (Preferred)
Run this on the server to generate fresh self-signed certs:
```bash
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout deployment/docker/nginx-selfsigned.key \
  -out deployment/docker/nginx-selfsigned.crt
```
