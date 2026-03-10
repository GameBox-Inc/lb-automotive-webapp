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
              python-backend/routes/twilio_webhook.py
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

### Main Flow

```
start (conversational greeting)
  ├── 1 / "appointment" → collect_vehicle
  ├── 2 / "emergency"   → emergency_services
  └── 3 / "speak to someone" → transfer_representative

collect_vehicle → collect_plate → select_time

select_time (dynamic)
  └── handle_time_selection → confirm_details

confirm_details
  ├── 1 → collect_contact
  └── 9 → start (restart)

collect_contact → book_appointment → completed
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
| Webhook handler | `twilio_webhook.py` | Entry point, validation, routing |
| Decision tree | `DECISION_TREE` dict | Node definitions and transitions |
| Smart Jump | `smart_jump_helper.py` | LLM intent → skip to time selection |
| LLM service | `llm_service` | `classify_intent`, `generate_response` |
| Scheduler | `scheduler.py` | Slot generation |

---

## Voice Configuration

- **Voice:** `Polly.Matthew` (en), `Polly.Lupe` (es)
- **Settings:** `ivr_voice`, `ivr_language`, `ivr_latency_masking_enabled` from DB
- **24/7:** No business-hours blocking; calls accepted anytime

---

## Related Docs

- [Twilio Webhooks Contract](../contracts/twilio-webhooks.md)
- [Twilio Debugging Runbook](../runbooks/twilio-debugging.md)
- [IVR Customer Journey](../../IVR_CUSTOMER_JOURNEY_REFINED.md)
