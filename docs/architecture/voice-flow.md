# Voice Flow Architecture

**Last Updated:** March 2026  
**Status:** Production — Twilio IVR on K3s

---

## Overview

The LB Automotive IVR uses a **tree-driven decision engine** with speech (STT) and DTMF support. Twilio calls the webhook on each user input; the backend returns TwiML to drive the next prompt or action.

---

## Request Path

```
Twilio (Voice) → Cloudflare Tunnel → Traefik → backend:8000
                     ↓
              twilio.kozytherocket.space
              POST /lb-automotive/api/twilio/webhook
                     ↓
              URLRewrite: /lb-automotive/api/twilio → /api/twilio
                     ↓
              python-backend/routes/twilio/webhook.py
```

---

## Decision Tree Structure

Defined in `python-backend/routes/twilio_webhook.py` as `DECISION_TREE`.

### Node Types

| Type | Description |
|------|-------------|
| `gather` | Plays prompt, collects speech/DTMF, returns to webhook with `Digits` or `SpeechResult` |
| `dynamic` | Handler generates TwiML from DB or runtime logic |
| `function` | Handler performs action (e.g. Smart Jump, booking) |
| `terminal` | Says message and hangs up |

### Call entry sequence

1. **Welcome** — Short message: "Hi, welcome to L-B Automotive Repair. We're here to help." (from `responses.welcome` in `ivr_prompts.json`).
2. **Language selection** — "For English press 1. Para español press 2." Gather; 1 → English, 2 → Spanish; then redirect to `start`.
3. **How can we help** — Step `start` plays the main menu in the chosen language (appointment, status, representative, emergency) and gathers speech/DTMF.

### Main Flow

```
start (how can we help — after language chosen)
  ├── 1 / "appointment" → collect_vehicle
  ├── 2 / "emergency"   → emergency_services
  └── 3 / "speak to someone" → transfer_representative

collect_vehicle → collect_plate → select_time

select_time (dynamic)
  └── handle_time_selection → confirm_details

confirm_details
  ├── 1 → save_time_choice (resolve and confirm a specific slot, then ask for symptoms)
  └── 9 → select_time (choose a different time)

save_time_choice (function)
  └── Says a combined message: confirms {date_spoken} at {time_spoken} and, in the same prompt, asks the caller to briefly describe the issue. Opens a speech Gather posting to process_symptoms.

process_symptoms (function)
  └── Summarizes symptoms, stores them in call metadata, then moves to confirm_appointment → confirm_booking → completed
```

### Smart Jump

When speech is detected, the system uses an LLM to classify intent. If the user mentions a service (e.g. "I need brakes"), the flow can skip directly to `select_time` via `handle_smart_jump`.

---

## State Management

- **Call state** stored in `call_states` table (keyed by `CallSid`)
- **Fields:** `current_step`, `language`, `metadata` (vehicle, plate, appointment_id, etc.)
- **IVR logs** in `ivr_logs` for analytics

---

## Key Components

| Component | Location | Purpose |
|-----------|----------|---------|
| Webhook handler | `routes/twilio/webhook.py` | Entry point, validation, routing |
| Decision tree | `DECISION_TREE` dict | Node definitions and transitions |
| Smart Jump | `smart_jump_helper.py` | LLM intent → skip to time selection |
| LLM service | `llm_service` | `classify_intent`, `generate_response` |
| Scheduler | `scheduler.py` | Slot generation |

---

## Voice Configuration

- **Voice:** Male only for consistency: `Polly.Matthew` (en), `Polly.Miguel` (es)
- **Settings:** `ivr_voice`, `ivr_language`, `ivr_latency_masking_enabled`, `ivr_filler_mode`, `ivr_speech_timeout`, `ivr_repair_max_retries`, `ivr_transfer_number`, `ivr_transfer_timeout` from DB
- **24/7:** No business-hours blocking; calls accepted anytime
- **Transfer:** When `ivr_transfer_number` (E.164) is set, "speak to someone" uses TwiML `<Dial>` to connect the caller; on no-answer/timeout the `transfer_no_answer` step plays a message and hangs up. When not set, caller hears "unable to transfer" and hangs up.

---

## ElevenLabs TTS (optional)

**Mode (plan):** Phase 1 ships **on-demand ElevenLabs** → MP3 bytes cached in **Redis** (content-hash + short-lived audio id) → Twilio `<Play url="https://…/api/twilio/tts-audio/{uuid}">`. **Pre-generated static MP3s** are supported via settings `ivr_tts_static_url_{prompt}_{lang}` (HTTPS only) to skip API calls. Default remains **Twilio `<Say>` (Polly)** — no behavior change until configured.

| Setting / env | Purpose |
|----------------|--------|
| `ivr_tts_provider` | `twilio` (default) or `elevenlabs` |
| `ivr_tts_canary_prompts` | Comma-separated logical keys (e.g. `welcome`); use `*` only after validation |
| `elevenlabs_voice_id_en` / `elevenlabs_voice_id_es` | ElevenLabs voice IDs |
| `elevenlabs_model_id` | e.g. `eleven_multilingual_v2` |
| `ELEVENLABS_API_KEY` | K8s Secret only — never commit |
| `IVR_TTS_PUBLIC_BASE_URL` | Public HTTPS base Twilio can `GET` (e.g. `https://twilio.kozytherocket.space/lb-automotive`); else derived from `TWILIO_WEBHOOK_BASE_URL` |
| `ivr_tts_audio_ttl_seconds` | Redis TTL for audio blobs (default 600s) |

**Stability:** HTTP timeouts on synthesis, **circuit breaker** (env `IVR_TTS_CB_*`), automatic **fallback to Polly** on any failure. **Metrics:** `ivr_tts_requests_total`, `ivr_tts_duration_seconds` (Prometheus).

**Public audio URL:** `GET /api/twilio/tts-audio/{uuid}` — unauthenticated; security by unguessable id + TTL (same pattern as signed URLs in spirit). Twilio must reach this URL over **HTTPS** from the public internet (not VPN-only).

**Rollout:** Deploy with `ivr_tts_provider=twilio` → set API key + voice IDs → switch to `elevenlabs` and keep canary to `welcome` → expand `ivr_tts_canary_prompts` as needed. **Disable:** set `ivr_tts_provider=twilio` in Admin settings (no redeploy required if settings are read per request).

See **`docs/runbooks/ivr-elevenlabs.md`** for operations and verification.

---

## Conversational UX

- **Barge-in:** Speech `<Gather>` nodes use `bargeIn="true"` so callers can interrupt prompts.
- **Turn detection:** `speechTimeout` from node `gather_config` or `ivr_speech_timeout` (e.g. `auto`) controls when Twilio treats the caller as done speaking.
- **Latency masking:** After caller speech, the app returns immediately with a short acknowledgement (`ivr_filler_mode`: voice_only, sound_only, or hybrid with thinking sound); LLM runs async and the next request uses the result. **Processing audio:** If `ivr_thinking_sound_url` is set, it is played during the `processing` wait even when `ivr_filler_mode` is `voice_only` (combined with the spoken filler, same as hybrid).
- **No-input repeat:** On Gather timeout, callers hear `no_input_repeat` (“I didn’t hear a response…”) before the step prompt is replayed (tree gathers and language / confirm-intent / confirm-appointment handlers where applicable).
- **Repair:** On timeout/no input, the IVR says "Sorry, I didn't catch that. Let's try again." and re-gathers; after `ivr_repair_max_retries` it offers transfer.
- **Context:** `last_intent` is stored and passed to the classifier so follow-ups like "yes" or "that one" can be resolved.

See [IVR Conversational Upgrade](ivr-conversational-upgrade.md) for design and implementation details.

---

## Related Docs

- [Twilio Webhooks Contract](../contracts/twilio-webhooks.md)
- [Twilio Debugging Runbook](../runbooks/twilio-debugging.md)
- [IVR ElevenLabs Runbook](../runbooks/ivr-elevenlabs.md)
- [IVR Customer Journey](../../IVR_CUSTOMER_JOURNEY_REFINED.md)
