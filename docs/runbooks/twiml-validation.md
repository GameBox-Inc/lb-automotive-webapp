# TwiML Validation Runbook

**Last Updated:** March 2026  
**Purpose:** Identify and fix code paths that produce invalid or empty TwiML.

---

## Summary

| Risk | Path | File | Line(s) | Issue |
|------|------|------|---------|-------|
| **Critical** | `collect_contact` function node | `webhook.py` | 654–660 | Handler `handle_contact_collection` not implemented → empty `<Response></Response>` |
| **High** | `select_service_detail` missing from tree | `webhook.py` | 368, 673–675 | Step not in DECISION_TREE → fallback "Goodbye." (wrong UX) |
| **High** | `confirm_emergency` missing from tree | `webhook.py` | 528, 673–675 | Step not in DECISION_TREE → fallback "Goodbye." (wrong UX) |
| **Medium** | Processing poll (no filler) | `webhook.py` | 597–604 | Returns only `<Redirect>` → dead air while waiting |
| **Medium** | Processing intent routing | `webhook.py` | 612–625 | Returns only `<Redirect>` → dead air |
| **Low** | Terminal node missing prompt | `webhook.py` | 667 | `node.get("prompt_en")` could be None if node malformed |
| **Low** | Gather prompt missing | `webhook.py` | 651 | Same for gather nodes |

---

## Critical: Empty TwiML (collect_contact)

**File:** `python-backend/routes/twilio/webhook.py`

**Path:** User presses 1 on `confirm_details` → redirect to `collect_contact` → webhook receives `step=collect_contact`.

**Cause:** `collect_contact` is a function node with `handler: "handle_contact_collection"`, but `handle_contact_collection` is **not implemented** in the handler chain (lines 655–660). Only these handlers are wired:

- `handle_smart_jump`
- `handle_save_time_choice`
- `handle_symptoms_processing`
- `handle_booking`

**Result:** `ns` stays `None`, no `response.redirect()`, no `response.say()`. The handler returns `Response(content=str(response), ...)` with an empty `VoiceResponse` → `<Response></Response>`.

**Impact:** Caller hears dead air; Twilio may treat as no-op or hang.

**Fix:** Implement `handle_contact_collection` and add it to the function handler chain, or remove `collect_contact` from the pipeline and route directly to `book_appointment`.

---

## High: Missing Tree Steps (select_service_detail, confirm_emergency)

**File:** `python-backend/routes/twilio/webhook.py`

**Cause:** `handle_service_category` and `handle_emergency` build Gather actions that POST to `step=select_service_detail` and `step=confirm_emergency`, but these steps are **not in DECISION_TREE**.

**Flow:**
1. `handle_service_category` (line 368): `action=f"...?step=select_service_detail"`
2. `handle_emergency` (line 528): `action=f"...?step=confirm_emergency"`

When Twilio POSTs with these steps, `get_tree_node(step)` returns `None`, so execution falls through to the fallback (lines 673–675):

```python
response.say("Goodbye.", voice=voice)
response.hangup()
```

**Result:** Valid TwiML, but wrong UX: caller is hung up instead of seeing service list or emergency confirmation.

**Fix:** Add `select_service_detail` and `confirm_emergency` nodes to DECISION_TREE with appropriate handlers (e.g. show services for selected category, confirm emergency selection).

---

## Medium: Dead Air (Redirect-Only Responses)

**File:** `python-backend/routes/twilio/webhook.py`

**Paths:**
1. **Processing poll** (lines 597–604): When LLM result not ready and timeout not exceeded, returns only `<Redirect>` to `?step=processing`.
2. **Processing intent routing** (lines 612–625): After `handle_smart_jump`, returns only `<Redirect>` to `main_menu_{language}` or `step={ns}`.

**Result:** Valid TwiML (Redirect is a verb), but caller hears nothing while waiting. See [audio-playback.md](audio-playback.md) for filler insertion.

---

## Low: Missing Prompts

**File:** `python-backend/routes/twilio/webhook.py`

**Paths:**
- Line 651: `gather.say(node.get(f"prompt_{language}", node.get("prompt_en")), voice=voice)`
- Line 667: `response.say(node.get(f"prompt_{language}", node.get("prompt_en")), voice=voice)`

If a node is malformed and has no `prompt_en` or `prompt_{language}`, `.get()` returns `None`. `response.say(None, ...)` may produce invalid TwiML or unexpected behavior.

**Fix:** Add fallback: `node.get(f"prompt_{language}", node.get("prompt_en")) or "Please hold."`

---

## All TwiML Return Points

| Location | Content | Valid? |
|----------|---------|--------|
| 579 | Say (filler) + Redirect | Yes |
| 604 | Redirect only | Valid, dead air |
| 617 | Redirect only | Valid, dead air |
| 621 | Redirect only | Valid, dead air |
| 625 | Redirect only | Valid, dead air |
| 641 | Redirect only | Valid |
| 647 | Redirect only | Valid |
| 671 | Varies (handler output) | **Empty if collect_contact** |
| 675 | Say + Hangup | Yes |
| 681 | Say + Hangup (error) | Yes |

---

## Related

- [twilio-webhooks.md](../contracts/twilio-webhooks.md) – Response format
- [audio-playback.md](audio-playback.md) – Dead air / filler
- [voice-flow.md](../architecture/voice-flow.md) – IVR flow
