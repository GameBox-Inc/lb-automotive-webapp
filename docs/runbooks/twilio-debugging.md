# Twilio Debugging Runbook

**Last Updated:** March 2026

---

## Debugging Priorities

1. **Never guess root cause without evidence.**
2. **Reproduce the issue first.**
3. **Collect logs before editing code.**
4. **Trace the full request path** (see below).

---

## Request Path

```
Twilio webhook/API
  → Cloudflare Tunnel (twilio.kozytherocket.space)
  → Traefik (Gateway API HTTPRoute)
  → Kubernetes service (backend:8000)
  → Pod/container
  → app route (/api/twilio/webhook)
  → AI/STT/TTS integration
  → TwiML or media response
```

---

## Checklist for Voice Issues

| Check | How |
|-------|-----|
| Webhook status code | Twilio Console → Monitor → Logs |
| TwiML validity | Inspect response XML; ensure no malformed tags |
| Call SID / correlation ID | Use `CallSid` to trace logs |
| Ingress routing | `kubectl get httproute -n gamebox-security` |
| Service endpoints | `kubectl get svc -n lb-automotive` |
| Pod readiness | `kubectl get pods -n lb-automotive` |
| Timeout | Backend default 8s gather; Twilio timeout config |
| Media/audio URL | Ensure URLs are reachable from Twilio |

---

## Common Commands

### Backend logs

```bash
ssh lb-admin@178.156.223.196
sudo k3s kubectl logs -n lb-automotive -l app=backend -c backend --tail=200 -f
```

### Filter by CallSid

```bash
sudo k3s kubectl logs -n lb-automotive -l app=backend -c backend --tail=500 | grep "CA123..."
```

### Check HTTPRoute

```bash
sudo k3s kubectl get httproute -n gamebox-security -o yaml
```

### Traefik logs

```bash
sudo k3s kubectl logs -n gamebox-security -l app.kubernetes.io/name=traefik -f
```

---

## Webhook URL Configuration

- **Twilio Console:** Voice webhook URL must be `https://twilio.kozytherocket.space/lb-automotive/api/twilio/webhook`
- **HTTPRoute:** Rewrites `/lb-automotive/api/twilio` → `/api/twilio` before backend
- **Validation:** Backend must receive URL with `/lb-automotive` for HMAC validation (see `validate_twilio_request`)

---

## Transfer not working

- **Check:** `ivr_transfer_number` in Admin → IVR Settings (or `settings` table). Must be E.164 (e.g. `+15551234567`). Leave blank to disable live transfer; callers then hear “unable to transfer” and hang up.
- **Check:** `ivr_transfer_timeout` (seconds to ring, 10–60). No-answer uses `transfer_no_answer` step (message + hangup).

---

## Validation Failures (403)

1. **X-Twilio-Signature** — HMAC of URL + params; URL must match what Twilio used.
2. **Proxy headers** — `x-forwarded-proto`, `x-forwarded-prefix`, `x-original-uri` used to reconstruct URL.
3. **Fallback** — If `twilio.kozytherocket.space` in URL but `/lb-automotive` missing, backend hardcodes prefix.

---

## Prefer Minimal Fixes

- Targeted changes over broad refactors
- After fixing: document root cause, proof, files changed, risks, verification steps
- If evidence is incomplete, state exactly what is missing

---

## Related

- [Voice Flow Architecture](../architecture/voice-flow.md)
- [Twilio Webhooks Contract](../contracts/twilio-webhooks.md)
- [Common Failures](../incidents/common-failures.md)
- [.cursor/rules/ivr-debugging.mdc](../../.cursor/rules/ivr-debugging.mdc)
