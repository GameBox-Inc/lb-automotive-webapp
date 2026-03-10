# Twilio Webhooks Contract

**Last Updated:** March 2026  
**Endpoint:** `POST /api/twilio/webhook`

---

## Public URL

```
https://twilio.kozytherocket.space/lb-automotive/api/twilio/webhook
```

Traefik rewrites `/lb-automotive/api/twilio` → `/api/twilio` before forwarding to backend.

---

## Request Format

Twilio sends `application/x-www-form-urlencoded` POST.

### Required Form Fields

| Field | Type | Description |
|-------|------|-------------|
| `CallSid` | string | Unique call identifier |

### Optional (per request)

| Field | Type | Description |
|-------|------|-------------|
| `From` | string | Caller phone number |
| `Digits` | string | DTMF input (e.g. "1", "2") |
| `SpeechResult` | string | Speech-to-text result |
| `step` | string | Current IVR step (query param; default `"start"`) |

### Query Parameters

| Param | Description |
|-------|-------------|
| `step` | Current node in decision tree (e.g. `start`, `collect_vehicle`, `select_time`) |

---

## Response Format

**Content-Type:** `application/xml` (TwiML)

### Valid TwiML Examples

```xml
<!-- Say and hang up -->
<Response>
  <Say voice="Polly.Matthew">Your appointment is confirmed. Goodbye.</Say>
  <Hangup/>
</Response>

<!-- Gather (speech + DTMF) -->
<Response>
  <Gather action="https://twilio.kozytherocket.space/lb-automotive/api/twilio/webhook?step=start"
         input="speech dtmf" numDigits="1" timeout="8" speechTimeout="auto">
    <Say voice="Polly.Matthew">Welcome to L-B Automotive. How can we help?</Say>
  </Gather>
  <Say voice="Polly.Matthew">We didn't receive any input. Goodbye.</Say>
  <Hangup/>
</Response>

<!-- Redirect -->
<Response>
  <Redirect>https://twilio.kozytherocket.space/lb-automotive/api/twilio/webhook?step=select_time</Redirect>
</Response>
```

---

## Security

- **HMAC validation:** `X-Twilio-Signature` header
- **Token:** `TWILIO_AUTH_TOKEN` from Vault
- **URL:** Must match exactly (scheme, host, path, query) for signature validation
- **Proxy:** Backend uses `x-forwarded-proto`, `x-original-uri` to reconstruct URL

---

## Error Handling

- 403: Invalid signature or validation error
- 200: Always return TwiML (even on error) — say "An error occurred" and hang up

---

## Related

- [Voice Flow Architecture](../architecture/voice-flow.md)
- [Twilio Debugging Runbook](../runbooks/twilio-debugging.md)
