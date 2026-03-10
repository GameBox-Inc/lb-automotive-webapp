# TwiML Validation Runbook

**Last Updated:** March 2026  
**Related:** [Twilio Debugging](twilio-debugging.md) | [Twilio 503](twilio-503.md)

---

## Quick Validate

```bash
npm run debug:twiml
```

Runs `scripts/validate-twiml.js` to check TwiML structure.

---

## Common TwiML Issues

1. **Malformed XML**
   - Unclosed tags, invalid nesting
   - Special characters in text (`<`, `>`, `&`) must be escaped

2. **Invalid `<Say>` / `<Gather>` attributes**
   - `voice` must be valid (e.g. `Polly.Matthew`, `alice`)
   - `language` format: `en-US`, `es`

3. **`<Play>` URL problems**
   - Must be absolute URL
   - Must be reachable from Twilio (public, no auth)
   - Supported formats: MP3, WAV, GSM, ulaw, alaw

4. **`<Redirect>` URL**
   - Must be full URL when behind proxy
   - `WEBHOOK_BASE_URL` must include `/lb-automotive` if Traefik strips it

5. **Empty or null response**
   - Webhook must always return valid TwiML
   - 500 errors return HTML, not TwiML → Twilio fails

---

## Manual Validation

```bash
# Simulate webhook and inspect response
curl -X POST "$TWILIO_WEBHOOK_BASE_URL?step=start" \
  -d "CallSid=CA123" -d "From=+15551234567" \
  -H "Content-Type: application/x-www-form-urlencoded"
```

Check response is valid XML and starts with `<?xml` or `<Response>`.
