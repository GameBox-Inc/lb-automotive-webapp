# IVR Conversational Upgrade — Design & Implementation

**Last Updated:** March 2026  
**Objective:** Make the Twilio IVR feel like a natural conversation: low latency, minimal dead air, human-like turn-taking, strong observability.

---

## 1. Architectural approach (summary)

- **Request path:** Twilio → Traefik → backend pod → webhook → (optional async LLM in background) → TwiML with `<Gather>` / `<Say>` / `<Redirect>`.
- **Latency masking:** Always return immediately with a short acknowledgement (voice and/or sound); use async LLM + polling so the caller never hears silence while the AI thinks.
- **Turn detection:** Use Twilio’s `speechTimeout="auto"` (and optional numeric override from settings) so Twilio decides end-of-utterance; avoid cutting callers off or long pauses.
- **Barge-in:** Set `bargeIn="true"` on every speech `<Gather>` so callers can interrupt prompts; ensure `gather_config` in the tree drives the actual TwiML (today it does not).
- **Context:** Store `last_intent` and `last_step` in call-state metadata; pass a short context string into the classifier so it can avoid repeating and handle “same again” / “yes” / “no”.
- **Repair:** On timeout or empty input, play a short repair phrase (“Sorry, I didn’t catch that.”) and re-Gather the same step; after N repeats, offer transfer.
- **Observability:** One structured log per webhook response with phase, step, latency_ms, callSid, and requestId so bottlenecks (e.g. LLM vs DB) are obvious.

---

## 2. Assumptions about the current codebase

| Assumption | Evidence |
|------------|----------|
| Single webhook entrypoint; no Media Streams | `webhook.py` single POST handler; `stream.py` is placeholder. |
| STT/TTS are Twilio’s; we only return TwiML | No custom STT/TTS in app; Twilio does speech in `<Gather input="speech">`. |
| LLM is synchronous HTTP (Anthropic); no streaming | `classify_intent()` is sync; `process_ivr_intent_async` runs it in executor. |
| Call state is in DB + Redis (LLM result) | `call_states` table; Redis key `ivr:result:{call_sid}`. |
| Filler is voice-only today | `get_random_filler()` returns a phrase; `ivr_filler_mode` and `ivr_thinking_sound_url` exist in settings but are not used in masking. |
| Barge-in and speechTimeout are in tree but not applied | `gather_config` has `bargein` and `speech_timeout`; the `Gather()` call in the webhook does not pass them. |
| No explicit timeout/empty-input handling | Default transition is used when Twilio sends empty; no “Sorry, I didn’t catch that” flow. |
| Tracing has phase and IDs | `observability/tracing.py` has callSid, requestId, phase, latencyMs; not logged at every webhook exit. |

---

## 3. Specific conversational improvements

- **Barge-in and turn detection:** Apply `barge_in` and `speech_timeout` from each node’s `gather_config` to the TwiML `<Gather>` (and optional global defaults from settings).
- **Latency masking:** Support `ivr_filler_mode`: `voice_only` (current), `sound_only` (Play thinking.mp3), `hybrid` (short Say + Play). Use `ivr_filler_phrases` from settings for voice.
- **Micro-acknowledgements:** Keep short phrases (“Got it.”, “One moment.”) and randomize so the same phrase isn’t repeated every time.
- **Repair on timeout/no input:** If `step` is a gather and `input_data` is empty, play “Sorry, I didn’t catch that. Let’s try again.” and re-present the same step; increment a retry counter in metadata.
- **Anti-loop:** If the same step is hit more than N times (e.g. 3), say “Let me connect you to someone who can help.” and redirect to transfer.
- **Conversational prompts:** Shorten and naturalize tree prompts (e.g. “How can we help?” instead of long “You can say things like…”); keep one short example where helpful.
- **Context for LLM:** Add `last_intent` and `last_step` to metadata; pass a one-line context into `classify_intent` so the model can resolve “yes”/“that one”/“same time”.
- **Clarification:** For ambiguous intents, classifier can return `intent: "clarify"` with a suggested prompt; webhook can play it and re-gather (future: add one clarify step in the tree).

---

## 4. File-by-file implementation plan

| File | Change |
|------|--------|
| `routes/twilio/webhook.py` | Apply `barge_in`/`speech_timeout` to `Gather`; add timeout/repair and anti-loop; use `get_latency_mask_*` for filler_mode; shorten key prompts in DECISION_TREE; pass context into intent when calling smart jump; log phase+latency at each return. |
| `utils/ivr_helper.py` | Add `get_filler_phrases_from_settings(get_setting)`; add `build_latency_mask_twiml(response, voice, mode, thinking_url)` (Say and/or Play). |
| `services/llm/llm.py` | Add optional `conversation_context: str` to `classify_intent` and include in the user message. |
| `services/call_state/store.py` | No change; metadata already stores arbitrary dict. |
| `observability/tracing.py` | Optional: `log_phase(phase, step, extra)` helper that logs with trace context. |
| `database.py` | Add settings: `ivr_speech_timeout` (e.g. `auto` or `3`), `ivr_repair_max_retries` (e.g. `3`), `ivr_anti_loop_threshold` (e.g. `3`). |
| `docs/architecture/voice-flow.md` | Update to describe barge-in, turn detection, latency masking, and repair. |

---

## 5. Exact code changes (implemented)

- **`utils/ivr_helper.py`:** `parse_filler_phrases_setting()`, `apply_latency_mask(response, voice, mode, thinking_url, filler_phrase)` for voice_only / sound_only / hybrid.
- **`routes/twilio/webhook.py`:** Gather built with `barge_in` and `speech_timeout` from `gather_config` (and `ivr_speech_timeout` setting); timeout/repair when `input_data` empty on gather nodes (max retries then transfer); latency masking uses `ivr_filler_mode` and `apply_latency_mask`; conversational prompts (start, main_menu_en, collect_vehicle, collect_symptoms); `last_intent` stored in metadata and passed as `conversation_context` to async classifier; structured log at key returns with `get_trace_context()` and step.
- **`services/llm/llm.py`:** `classify_intent(text, conversation_context=None)` and `_classify_intent_impl`; cache used only when context is None.
- **`utils/background_tasks.py`:** `process_ivr_intent_async(..., conversation_context=None)` and pass-through to `classify_intent`.
- **`database.py`:** Settings `ivr_speech_timeout`, `ivr_repair_max_retries` in default_settings.

---

## 6. Logging / observability improvements

- **Structured log at webhook exit:** Before every `return Response(...)` in the webhook, log one line: `logger.info("IVR response", extra={**get_trace_context(), "step": step, "phase": phase, "latencyMs": latencyMs})`. Ensures every response is visible and latency is per-request.
- **Background task:** Already logs `LATENCY_TRACK: AI processing for {call_sid} took {duration}s`. Keep it.
- **TraceContextFilter:** Already adds callSid, requestId, phase, latencyMs to logs. Ensure `update_phase()` is called before each return so `latencyMs` reflects time since request start.
- **Debugging:** Filter logs by `callSid` for full call; by `phase=llm_complete` and `latencyMs` to find slow LLM responses.

---

## 7. Test plan

- **Unit:** `get_random_filler` with custom list; `build_latency_mask_twiml` for voice_only / sound_only / hybrid (response has Say and/or Play).
- **Integration:** POST webhook with `step=start`, `SpeechResult=appointment` and masking enabled: expect redirect to processing, then next request to processing returns main_menu or collect_vehicle; verify TwiML has `<Say>` and `<Redirect>`.
- **Gather attributes:** Generate TwiML for a gather node and assert `<Gather` contains `bargeIn="true"` and `speechTimeout="auto"` (or configured value).
- **Repair:** POST with `step=start`, no Digits/SpeechResult (or empty): expect repair message and same step re-gather; after N times, expect transfer.
- **Anti-loop:** Simulate same step 4 times; expect transfer message and redirect to transfer.
- **Manual:** Place test call; interrupt prompt (barge-in); stay silent (timeout); say “appointment” and verify short ack then menu.

---

## 8. Debugging recommendations

- **Correlate by CallSid:** `grep <CallSid> backend.log` or use log aggregation filter.
- **Latency:** Sort logs by `latencyMs` to find slow requests; compare `phase=webhook_received` vs `phase=tts_ready` for same request.
- **Missing or wrong TwiML:** Run `npm run debug:twiml` with captured TwiML; check for empty `<Response>` or missing `<Say>` on timeout path.
- **Twilio debugger:** Use Twilio Console → Monitor → Logs; check webhook URL and response time; confirm 200 and valid TwiML.
- **Runbooks:** Use `docs/runbooks/twiml-validation.md`, `twilio-503.md`, `audio-playback.md` for production issues.

---

## 9. Future-state: more natural real-time voice

- **Twilio Media Streams:** Move to WebSocket media stream; run custom VAD + STT (e.g. Whisper) and TTS (e.g. streaming synthesis) in the backend; send audio chunks back so the assistant can “talk over” silence and support true overlap and interruption.
- **Streaming LLM:** Use Anthropic streaming API; send first sentence to TTS as soon as it’s available so the reply starts playing before the full answer is ready.
- **Echo cancellation and VAD:** Dedicated VAD for end-of-utterance and barge-in detection instead of relying only on Twilio’s `speechTimeout`.
- **Conversation model:** Replace fixed tree with a single conversational LLM that outputs structured actions (say, gather, transfer, book); backend converts to TwiML and keeps state in metadata.
