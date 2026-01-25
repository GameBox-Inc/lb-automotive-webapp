# Production Server Setup Guide

This guide walks you through setting up the LB Automotive Dashboard on your production server.

## Prerequisites

- Server with Docker and Docker Compose installed
- SSH access to the server
- Git installed on the server

## Quick Setup (Automated)

### Step 1: Connect to your server

```bash
ssh lb-admin@178.156.223.196
```

### Step 2: Navigate to the project directory

```bash
cd /opt/lb-automotive-dashboard
```

### Step 3: Pull the latest code

```bash
git fetch origin
git reset --hard origin/release/v0.1
```

### Step 4: Run the automated setup script

```bash
bash deployment/scripts/setup_env.sh
```

The script will:
- ✅ Generate a secure SECRET_KEY automatically
- ✅ Prompt you for your domain(s)
- ✅ Ask which LLM provider you want (Ollama or Anthropic)
- ✅ Optionally configure Twilio for IVR
- ✅ Create the `.env` file with proper permissions
- ✅ Backup any existing `.env` file

### Step 5: Deploy the application

The next GitHub Actions deployment will automatically:
- Pull the latest Docker images
- Run database migrations
- Start all containers

Or manually deploy:

```bash
cd deployment/docker
docker compose up -d --build
```

## Manual Setup (Alternative)

If you prefer to create the `.env` file manually:

### 1. Copy the example file

```bash
cd /opt/lb-automotive-dashboard/deployment/docker
cp .env.example .env
```

### 2. Generate a secure SECRET_KEY

```bash
openssl rand -hex 32
```

### 3. Edit the .env file

```bash
nano .env
# or
vim .env
```

### 4. Set required variables

```bash
SECRET_KEY=<paste the generated key>
ALLOWED_ORIGINS=https://kozytherocket.space,https://www.kozytherocket.space
LLM_PROVIDER=ollama
OLLAMA_HOST=http://ollama:11434
OLLAMA_MODEL=smollm2:135m
```

### 5. Save and secure the file

```bash
chmod 600 .env
```

## Environment Variables Reference

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `SECRET_KEY` | JWT token signing key | Generate with `openssl rand -hex 32` |
| `ALLOWED_ORIGINS` | CORS allowed origins | `https://kozytherocket.space` |

### LLM Configuration

**Option 1: Ollama (Local, Free)**
```bash
LLM_PROVIDER=ollama
OLLAMA_HOST=http://ollama:11434
OLLAMA_MODEL=smollm2:135m
```

**Option 2: Anthropic Claude (Cloud, Paid)**
```bash
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-xxxxx
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
```

### Twilio IVR (Optional)

```bash
TWILIO_ACCOUNT_SID=ACxxxxx
TWILIO_AUTH_TOKEN=xxxxx
TWILIO_PHONE_NUMBER=+1234567890
```

## Verifying the Setup

### Check if .env file exists

```bash
ls -la /opt/lb-automotive-dashboard/deployment/docker/.env
```

You should see:
```
-rw------- 1 lb-admin lb-admin 456 Jan 25 10:00 .env
```

### Test the configuration

```bash
cd /opt/lb-automotive-dashboard/deployment/docker
docker compose config
```

This will show the resolved configuration with environment variables.

### Check container status

```bash
docker compose ps
```

All containers should be "Up" and healthy.

### Test the backend API

```bash
curl http://localhost:8000/health
```

Should return: `{"status":"healthy"}`

### Test the frontend

```bash
curl http://localhost/
```

Should return the HTML of the frontend application.

## Troubleshooting

### Backend won't start - "SECRET_KEY required"

**Cause:** `.env` file missing or `SECRET_KEY` not set

**Fix:** Run `bash deployment/scripts/setup_env.sh`

### Permission denied errors

**Cause:** Incorrect file permissions

**Fix:**
```bash
chmod 600 /opt/lb-automotive-dashboard/deployment/docker/.env
chown lb-admin:lb-admin /opt/lb-automotive-dashboard/deployment/docker/.env
```

### CORS errors in browser

**Cause:** Domain not in `ALLOWED_ORIGINS`

**Fix:** Edit `.env` and add your domain to `ALLOWED_ORIGINS`, then restart:
```bash
cd /opt/lb-automotive-dashboard/deployment/docker
docker compose restart backend
```

### Database migrations not running

**Fix:** Run migrations manually:
```bash
docker exec lb-auto-backend python migrate_business_hours.py
```

## Updating the Application

GitHub Actions will automatically deploy when you push to `release/v0.1`:

```bash
git push origin release/v0.1
```

Or manually update:

```bash
cd /opt/lb-automotive-dashboard
git pull origin release/v0.1
cd deployment/docker
docker compose pull
docker compose up -d --build --force-recreate
```

## Security Best Practices

1. **Never commit the .env file to git** - It contains secrets
2. **Use strong SECRET_KEY** - Generated with `openssl rand -hex 32`
3. **Restrict file permissions** - `.env` should be `600` (owner read/write only)
4. **Regular backups** - Backup the database and .env file
5. **Keep secrets secure** - Don't share API keys or tokens
6. **Update regularly** - Keep Docker images and dependencies updated

## Support

For issues or questions:
- Check logs: `docker logs lb-auto-backend --tail 100`
- Review the [main README](../../README.md)
- Check [API documentation](../../API_REFERENCE.md)
- Review [CLAUDE.md](../../CLAUDE.md) for project overview
