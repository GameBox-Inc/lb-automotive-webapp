# IVR ElevenLabs TTS — Runbook

**Last updated:** March 2026  
**Scope:** Optional ElevenLabs TTS with Twilio `<Play>`; fallback to Polly `<Say>`.

---

## Quick disable (production incident)

1. **Admin → Settings** (or DB `settings`): set `ivr_tts_provider` = `twilio`.
2. Confirm calls hear Polly only (no `<Play>` to ElevenLabs URLs).
3. Optional: remove `ELEVENLABS_API_KEY` from the deployment after provider is `twilio` (not required for safety).

No pod restart required if the app reads `settings` each request.

---

## Prerequisites

- Kubernetes: optional Secret **`elevenlabs-secrets`** with key `ELEVENLABS_API_KEY` (see `deployment/k8s/backend.yaml` `envFrom` optional ref), or add the key to `app-secrets`.
- **Redis:** Required for cross-pod MP3 cache and circuit-breaker counters; without Redis, in-process audio cache is used for dev only (multi-pod: may miss cache).
- **Public HTTPS URL:** Twilio must `GET` `https://<host>/lb-automotive/api/twilio/tts-audio/<uuid>` (or your `IVR_TTS_PUBLIC_BASE_URL` + path). Verify from an external host:

```bash
curl -sI "https://twilio.kozytherocket.space/lb-automotive/api/twilio/tts-audio/<uuid>"
```

Expect `404` for unknown ids; expect `200` + `audio/mpeg` after a real call generates audio.

---

## Configuration checklist

| Item | Notes |
|------|--------|
| `ivr_tts_provider` | `elevenlabs` only after validation |
| `ivr_tts_canary_prompts` | Start with `welcome` |
| `elevenlabs_voice_id_en` / `elevenlabs_voice_id_es` | From ElevenLabs dashboard |
| `ELEVENLABS_API_KEY` | K8s Secret only |
| `IVR_TTS_PUBLIC_BASE_URL` | Must match Traefik public URL (HTTPS) |
| `TWILIO_WEBHOOK_BASE_URL` | Used to derive public base if `IVR_TTS_PUBLIC_BASE_URL` unset |

---

## Observability

**Prometheus metrics** (scrape `/metrics`):

- `ivr_tts_requests_total{provider="twilio|elevenlabs|elevenlabs_static",result="say|play|fallback_say|error"}`
- `ivr_tts_duration_seconds` — ElevenLabs synthesis latency

**Alerts (suggested):**

- High rate of `result="fallback_say"` with `provider="elevenlabs"` → API errors, breaker, or missing voice IDs.
- High `ivr_tts_duration_seconds` p95 → risk of slow webhook response (TwiML still returns quickly if cache hit; first miss depends on ElevenLabs).

**Logs:** correlate with `callSid` / `requestId` (existing webhook logging). Do not log API keys or full prompt text in production debug.

---

## Staging verification

1. Set provider `twilio`, deploy, smoke-test IVR.
2. Set `elevenlabs` + canary `welcome` + valid voice IDs + API key.
3. Place test call; confirm TwiML contains `<Play>` with `tts-audio` URL for welcome step.
4. `curl` the Play URL from the public internet (not only VPN).

---

## Rollout order

1. **Dark launch:** code deployed, `ivr_tts_provider=twilio`.
2. **Canary:** `elevenlabs` + `ivr_tts_canary_prompts=welcome` only.
3. **Expand:** add prompt keys to `ivr_tts_canary_prompts` or use `*` (after load testing).
4. **Static clips (optional):** set `ivr_tts_static_url_welcome_en` / `es` to skip API for fixed copy.

---

## Files

| File | Role |
|------|------|
| `python-backend/services/tts/elevenlabs.py` | HTTP client |
| `python-backend/services/tts/router.py` | `speak_or_play` / `gather_speak_or_play` |
| `python-backend/services/tts/storage.py` | Redis + in-process MP3 store |
| `python-backend/services/tts/circuit.py` | Circuit breaker |
| `python-backend/routes/twilio/tts_audio.py` | `GET /api/twilio/tts-audio/{id}` |
| `python-backend/routes/twilio/webhook.py` | IVR (canary: `welcome`) |

---

## Related

- [Voice flow architecture](../architecture/voice-flow.md)
- [Twilio debugging](../runbooks/twilio-debugging.md)
