# Ngrok Setup for Twilio Webhook

## Quick Start

1. **Get Ngrok Auth Token (Optional but Recommended)**
   - Visit: https://dashboard.ngrok.com/get-started/your-authtoken
   - Sign up for free account
   - Copy your authtoken

2. **Add to `.env` file:**
   ```bash
   NGROK_AUTHTOKEN=your_token_here
   ```

3. **Start Services:**
   ```bash
   docker-compose up -d ngrok
   ```

4. **Get Your Public URL:**
   - Visit: http://localhost:4040
   - Look for the "Forwarding" URL (e.g., https://abc123.ngrok.io)
   - OR run: `curl http://localhost:4040/api/tunnels | jq -r '.tunnels[0].public_url'`

5. **Configure Twilio:**
   - Go to Twilio Console → Phone Numbers
   - Select your phone number
   - Under "Voice & Fax" → "A CALL COMES IN"
   - Set Webhook URL to: `https://YOUR_NGROK_URL/api/twilio/webhook?step=welcome`
   - Method: `HTTP POST`
   - Save

## Without Auth Token

If you don't provide an auth token, ngrok will still work but:
- URLs change every restart
- Session expires after 2 hours
- Limited to 40 connections/minute

## Viewing Ngrok Dashboard

Access the ngrok web interface at: **http://localhost:4040**

Features:
- See all HTTP requests/responses
- Inspect request details
- Replay requests for testing
- View connection status

## Testing the Webhook

Once ngrok is running, test the webhook:

```bash
# Get your ngrok URL
curl http://localhost:4040/api/tunnels

# Test the webhook
curl -X POST "https://YOUR_NGROK_URL/api/twilio/webhook?step=welcome" \
  -d "CallSid=TEST123" \
  -d "From=+1234567890"
```

## Troubleshooting

**Ngrok not starting?**
```bash
docker-compose logs ngrok
```

**Check if backend is accessible:**
```bash
docker-compose exec ngrok curl http://python-backend:8000/health
```

**Restart ngrok:**
```bash
docker-compose restart ngrok
```

## Production Notes

For production, consider:
- **Ngrok Paid Plan**: Static URLs, custom domains, higher limits
- **Alternative**: Use Cloudflare Tunnel, Tailscale Funnel, or deploy to cloud with public IP
- **Security**: Implement Twilio request validation (X-Twilio-Signature header)
