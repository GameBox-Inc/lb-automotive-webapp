# GitHub Secrets Setup Guide

This guide explains how to configure GitHub Secrets for automated deployment without SSH access to the server.

## Overview

The deployment workflow automatically creates the `.env` file from GitHub Secrets, eliminating the need to SSH to the server. This is perfect for VPN-only access scenarios where the server only exposes port 10.100.0.1.

## Required Secrets

### 1. SECRET_KEY (Required)

**What it is:** JWT token signing key for authentication

**How to generate:**
```bash
openssl rand -hex 32
```

**How to add:**
1. Go to: https://github.com/GameBox-Inc/lb-automotive-webapp/settings/secrets/actions
2. Click **"New repository secret"**
3. **Name:** `SECRET_KEY`
4. **Value:** Paste the output from the openssl command
5. Click **"Add secret"**

### 2. ALLOWED_ORIGINS (Required)

**What it is:** Comma-separated list of allowed CORS origins

**Example value:**
```
https://kozytherocket.space,https://www.kozytherocket.space
```

**How to add:**
1. Go to: https://github.com/GameBox-Inc/lb-automotive-webapp/settings/secrets/actions
2. Click **"New repository secret"**
3. **Name:** `ALLOWED_ORIGINS`
4. **Value:** Your domain(s) - comma-separated, no spaces
5. Click **"Add secret"**

## Optional Secrets

### 3. LLM_PROVIDER (Optional)

**What it is:** Choose between 'ollama' (local) or 'anthropic' (cloud)

**Default if not set:** `ollama`

**Possible values:**
- `ollama` - Use local Ollama (free, no API key needed)
- `anthropic` - Use Claude API (requires ANTHROPIC_API_KEY)

**How to add:**
1. Go to: https://github.com/GameBox-Inc/lb-automotive-webapp/settings/secrets/actions
2. Click **"New repository secret"**
3. **Name:** `LLM_PROVIDER`
4. **Value:** `ollama` or `anthropic`
5. Click **"Add secret"**

### 4. ANTHROPIC_API_KEY (Optional, required if LLM_PROVIDER=anthropic)

**What it is:** API key for Claude AI

**Where to get it:** https://console.anthropic.com/

**How to add:**
1. Go to: https://github.com/GameBox-Inc/lb-automotive-webapp/settings/secrets/actions
2. Click **"New repository secret"**
3. **Name:** `ANTHROPIC_API_KEY`
4. **Value:** Your Anthropic API key (starts with `sk-ant-`)
5. Click **"Add secret"**

### 5. TWILIO_ACCOUNT_SID (Optional, for IVR phone system)

**What it is:** Twilio account identifier

**Where to get it:** https://console.twilio.com/

**How to add:**
1. Go to: https://github.com/GameBox-Inc/lb-automotive-webapp/settings/secrets/actions
2. Click **"New repository secret"**
3. **Name:** `TWILIO_ACCOUNT_SID`
4. **Value:** Your Twilio Account SID (starts with `AC`)
5. Click **"Add secret"**

### 6. TWILIO_AUTH_TOKEN (Optional, for IVR phone system)

**What it is:** Twilio authentication token

**Where to get it:** https://console.twilio.com/

**How to add:**
1. Go to: https://github.com/GameBox-Inc/lb-automotive-webapp/settings/secrets/actions
2. Click **"New repository secret"**
3. **Name:** `TWILIO_AUTH_TOKEN`
4. **Value:** Your Twilio Auth Token
5. Click **"Add secret"**

### 7. TWILIO_PHONE_NUMBER (Optional, for IVR phone system)

**What it is:** Your Twilio phone number

**Format:** Include country code, e.g., `+12345678901`

**How to add:**
1. Go to: https://github.com/GameBox-Inc/lb-automotive-webapp/settings/secrets/actions
2. Click **"New repository secret"**
3. **Name:** `TWILIO_PHONE_NUMBER`
4. **Value:** Your Twilio phone number with `+` and country code
5. Click **"Add secret"**

## Quick Setup Checklist

Minimum required for deployment:

- [ ] `SECRET_KEY` - Generate with `openssl rand -hex 32`
- [ ] `ALLOWED_ORIGINS` - Your production domain(s)

Optional but recommended:

- [ ] `LLM_PROVIDER` - Set to `ollama` (default) or `anthropic`
- [ ] `ANTHROPIC_API_KEY` - Only if using Claude AI
- [ ] `TWILIO_ACCOUNT_SID` - Only if using IVR phone system
- [ ] `TWILIO_AUTH_TOKEN` - Only if using IVR phone system
- [ ] `TWILIO_PHONE_NUMBER` - Only if using IVR phone system

## Verifying Your Setup

After adding secrets:

1. Go to: https://github.com/GameBox-Inc/lb-automotive-webapp/settings/secrets/actions
2. You should see your secrets listed (values are hidden for security)
3. Push a commit to `release/v0.1` branch
4. Watch the deployment in Actions tab
5. The workflow will automatically create the `.env` file from your secrets

## Updating Secrets

To change a secret value:

1. Go to: https://github.com/GameBox-Inc/lb-automotive-webapp/settings/secrets/actions
2. Click the secret name
3. Click **"Update secret"**
4. Enter the new value
5. Click **"Update secret"**
6. Push a new commit or manually trigger the workflow to apply changes

## Security Notes

✅ **DO:**
- Use strong, randomly generated SECRET_KEY
- Keep secrets in GitHub Secrets (encrypted at rest)
- Rotate secrets periodically
- Use minimum required permissions

❌ **DON'T:**
- Commit secrets to the repository
- Share secrets in public channels
- Use weak or predictable secret keys
- Reuse secrets across environments

## Troubleshooting

### Deployment fails with "SECRET_KEY secret not set"

**Solution:** Add the `SECRET_KEY` secret in GitHub repository settings

### Deployment fails with "ALLOWED_ORIGINS secret not set"

**Solution:** Add the `ALLOWED_ORIGINS` secret in GitHub repository settings

### Backend starts but can't connect to Claude AI

**Solution:**
1. Check that `LLM_PROVIDER` is set to `anthropic`
2. Verify `ANTHROPIC_API_KEY` is set correctly
3. Check the backend logs: `docker logs lb-auto-backend`

### Twilio IVR not working

**Solution:**
1. Verify all three Twilio secrets are set: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`
2. Check phone number format includes `+` and country code
3. Check the backend logs: `docker logs lb-auto-backend`

## Example Minimal Setup

For a basic deployment with Ollama (no Anthropic, no Twilio):

```bash
# 1. Generate SECRET_KEY
openssl rand -hex 32
# Output: abc123def456... (copy this)

# 2. Add to GitHub Secrets:
#    Name: SECRET_KEY
#    Value: abc123def456... (paste the generated key)

# 3. Add ALLOWED_ORIGINS:
#    Name: ALLOWED_ORIGINS
#    Value: https://kozytherocket.space,https://www.kozytherocket.space

# 4. Push to trigger deployment
git push origin release/v0.1
```

That's it! The deployment will succeed with just these two secrets.

## Advanced: Environment-Specific Secrets

If you want different configurations for staging/production:

1. Use GitHub Environments (Settings → Environments)
2. Create separate environments (e.g., "staging", "production")
3. Add environment-specific secrets to each
4. Update workflow to use appropriate environment

## Support

For issues:
- Check GitHub Actions logs: https://github.com/GameBox-Inc/lb-automotive-webapp/actions
- Review deployment logs in the Actions tab
- Check container logs: `docker logs lb-auto-backend`
- Review [PRODUCTION_SETUP.md](./PRODUCTION_SETUP.md) for server-side setup
