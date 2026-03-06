# Let's Encrypt SSL Setup - Quick Guide

## Prerequisites

✅ Domain name (e.g., `auto.yourdomain.com`)  
✅ DNS A record pointing to: `178.156.223.196`  
✅ SSH access to Hetzner server

---

## Step 1: Configure DNS

Point your domain's A record to your Hetzner server:

```
Type: A
Name: @ (or subdomain like "auto")
Value: 178.156.223.196
TTL: 3600
```

**Wait 5-15 minutes** for DNS propagation before proceeding.

**Test DNS**:
```powershell
nslookup yourdomain.com
```
Should return `178.156.223.196`

---

## Step 2: Upload Setup Script to Server

From your local machine:

```powershell
scp -i $HOME/.ssh/id_ed25519 deployment/scripts/setup_letsencrypt.sh lb-admin@178.156.223.196:/home/lb-admin/
```

---

## Step 3: Run Setup Script on Server

SSH to your Hetzner server:

```powershell
ssh -i $HOME/.ssh/id_ed25519 lb-admin@178.156.223.196
```

Then run:

```bash
sudo bash /home/lb-admin/setup_letsencrypt.sh
```

**Follow the prompts**:
- Enter your domain name
- Enter your email (for renewal notifications)
- Confirm

The script will:
1. Install Certbot
2. Generate SSL certificate
3. Set up auto-renewal
4. Update docker-compose.yml and nginx configs

---

## Step 4: Restart Services

```bash
cd /opt/lb-automotive-dashboard/deployment/docker
sudo docker compose down
sudo docker compose up -d
```

---

## Step 5: Test

### Desktop Test:
```powershell
curl -I https://yourdomain.com
```

Should return `200 OK` with no certificate errors.

### Mobile Test:
Open `https://yourdomain.com` on your phone. You should see:
- ✅ Lock icon in address bar
- ✅ No "Not Secure" warning
- ✅ Site loads normally

---

## Troubleshooting

### Certificate Generation Failed

**Error**: "Failed ACME challenge"

**Solution**: Check DNS:
```bash
nslookup yourdomain.com
```
Must return `178.156.223.196`. If not, wait longer for DNS propagation.

---

### Port 80 Blocked

**Error**: "Port 80 connection refused"

**Solution**: Ensure port 80 is open:
```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
```

---

### Container Won't Start

**Error**: "Cannot find certificate file"

**Solution**: Verify certificates exist:
```bash
sudo ls -la /etc/letsencrypt/live/yourdomain.com/
```

Should show `fullchain.pem` and `privkey.pem`

---

## Renewal

Certificates auto-renew via cron job. To test:

```bash
sudo certbot renew --dry-run
```

Should show "Cert not due for renewal, but simulating renewal for testing purposes."

---

## Manual Steps (If Script Fails)

If the automated script doesn't work, follow manual steps:

### 1. Install Certbot
```bash
sudo apt-get update
sudo apt-get install -y certbot
```

### 2. Stop Frontend
```bash
sudo docker stop lb-auto-frontend
```

### 3. Generate Certificate
```bash
sudo certbot certonly --standalone \
  --preferred-challenges http \
  --email your@email.com \
  --agree-tos \
  -d yourdomain.com
```

### 4. Update docker-compose.yml
```yaml
volumes:
  - /etc/letsencrypt/live/yourdomain.com/fullchain.pem:/etc/nginx/ssl/cert.pem:ro
  - /etc/letsencrypt/live/yourdomain.com/privkey.pem:/etc/nginx/ssl/key.pem:ro
```

### 5. Update nginx-https.conf
```nginx
server_name yourdomain.com;
ssl_certificate /etc/nginx/ssl/cert.pem;
ssl_certificate_key /etc/nginx/ssl/key.pem;
```

### 6. Restart
```bash
cd /opt/lb-automotive-dashboard/deployment/docker
sudo docker compose up -d
```
