import json
import random
import re
from typing import List, Optional
from security import redis_client

# Words/phrases that are not actionable intents; reject to avoid premature LLM processing.
FILLER_NOISE_WORDS = frozenset({
    "hello", "hi", "hey", "um", "uh", "hmm", "ah", "oh", "yeah", "ok", "okay",
    "yes", "no", "yea", "nah", "well", "so", "like", "huh", "what",
})

# First-turn keyword mapping: normalized phrase -> intent for direct routing (no LLM).
FIRST_TURN_KEYWORDS = {
    "appointment": ["appointment", "appointments", "schedule", "scheduling", "book", "booking", "oil change", "service", "services"],
    "status_update": ["status", "update", "check status", "my car", "car status", "appointment status"],
    "representative": ["representative", "someone", "human", "agent", "person", "speak to someone", "talk to someone"],
}

DEFAULT_FILLERS = [
    "One moment...",
    "Let me check that for you...",
    "Got it.",
    "Okay.",
    "One second."
]

def get_random_filler(fillers: Optional[List[str]] = None) -> str:
    """Return a random filler phrase."""
    source = fillers if fillers else DEFAULT_FILLERS
    return random.choice(source)


def parse_filler_phrases_setting(value: Optional[str]) -> List[str]:
    """Parse ivr_filler_phrases JSON from settings; return list or empty for default."""
    if not value or not value.strip():
        return []
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list) and all(isinstance(x, str) for x in parsed):
            return parsed
    except (json.JSONDecodeError, TypeError):
        pass
    return []


def apply_latency_mask(response, voice: str, mode: str, thinking_url: Optional[str] = None, filler_phrase: Optional[str] = None):
    """
    Add latency-masking content to the TwiML response.
    mode: voice_only | sound_only | hybrid
    - voice_only: one Say (filler_phrase or random default)
    - sound_only: one Play(thinking_url) if URL present
    - hybrid: short Say then Play if URL present
    """
    phrase = filler_phrase or get_random_filler()
    if mode == "sound_only":
        if thinking_url:
            response.play(thinking_url)
    elif mode == "hybrid":
        response.say(phrase, voice=voice)
        if thinking_url:
            response.play(thinking_url)
    else:
        response.say(phrase, voice=voice)

def get_redis_pending_key(call_sid: str) -> str:
    return f"ivr:pending:{call_sid}"

def get_redis_result_key(call_sid: str) -> str:
    return f"ivr:result:{call_sid}"

def clear_ivr_state(call_sid: str):
    """Clean up Redis state for a call."""
    if redis_client:
        redis_client.delete(get_redis_pending_key(call_sid))
        redis_client.delete(get_redis_result_key(call_sid))


def is_actionable_transcript(
    transcript: str,
    confidence: Optional[float] = None,
    min_length: int = 3,
    min_confidence: float = 0.0,
) -> bool:
    """
    Return True if the transcript is meaningful enough to send to the LLM.
    Rejects empty, too short, filler/noise, and low-confidence results.
    """
    if not transcript or not isinstance(transcript, str):
        return False
    text = transcript.strip()
    if len(text) < min_length:
        return False
    # Reject punctuation/symbol-only
    if re.sub(r"\W", "", text) == "":
        return False
    # Reject single character (or two identical)
    if len(text) <= 2 and not text.isalnum():
        return False
    normalized = text.lower().strip()
    if normalized in FILLER_NOISE_WORDS:
        return False
    # Optional: reject low Twilio confidence
    if confidence is not None and min_confidence > 0 and confidence < min_confidence:
        return False
    return True


def get_first_turn_intent(transcript: str) -> Optional[str]:
    """
    Map common first-turn phrases to intent for direct routing (no LLM).
    Returns 'appointment' | 'status_update' | 'representative' or None.
    """
    if not transcript or not isinstance(transcript, str):
        return None
    normalized = transcript.lower().strip()
    if not normalized:
        return None
    for intent, phrases in FIRST_TURN_KEYWORDS.items():
        for phrase in phrases:
            if phrase in normalized or normalized == phrase:
                return intent
    return None


def slot_to_minutes(s: str) -> int:
    """Convert 'HH:MM' to minutes since midnight for comparison."""
    try:
        parts = s.split(":")
        h, m = int(parts[0], 10), int(parts[1], 10) if len(parts) > 1 else 0
        return h * 60 + m
    except (ValueError, IndexError):
        return 0


def get_closest_slot(user_input: str, slots: List[str]) -> Optional[str]:
    """
    Map user speech or DTMF (1=morning, 2=afternoon) to the closest available slot.
    Supports: morning, afternoon, 1, 2, specific times like 3, 3 pm, 10 am, noon, earliest, etc.
    """
    if not slots:
        return None
    text = (user_input or "").strip().lower()
    if not text:
        return slots[0]

    # DTMF: 1 = morning, 2 = afternoon
    if text in ("1", "2"):
        if text == "1":
            morning = [s for s in slots if slot_to_minutes(s) < 12 * 60]
            return morning[0] if morning else slots[0]
        afternoon = [s for s in slots if slot_to_minutes(s) >= 12 * 60]
        return afternoon[0] if afternoon else slots[-1]

    # Explicit preferences
    if any(w in text for w in ("earliest", "soon", "first", "asap", "soonest")):
        return slots[0]
    if any(w in text for w in ("latest", "last", "end of day")):
        return slots[-1]
    if any(w in text for w in ("noon", "12", "midday")):
        target = 12 * 60
        return min(slots, key=lambda s: abs(slot_to_minutes(s) - target))
    if any(w in text for w in ("morning", "am")):
        morning = [s for s in slots if slot_to_minutes(s) < 12 * 60]
        return morning[0] if morning else slots[0]
    if any(w in text for w in ("afternoon", "evening", "pm")):
        afternoon = [s for s in slots if slot_to_minutes(s) >= 12 * 60]
        return afternoon[0] if afternoon else slots[-1]

    # Parse hour (and optional minute) from phrases like "3", "3 pm", "10 am", "3 o'clock"
    digits = re.findall(r"\d{1,2}", text)
    if digits:
        hour = int(digits[0], 10)
        if hour <= 12 and ("pm" in text or "p.m" in text or "afternoon" in text):
            if hour < 12:
                hour += 12
        elif hour == 12 and ("am" in text or "noon" in text):
            hour = 12
        elif hour == 12 and "pm" in text:
            hour = 12
        elif hour < 12 and ("am" in text or "a.m" in text or "morning" in text):
            pass  # keep hour as-is (already AM)
        elif hour <= 12 and not ("am" in text or "pm" in text):
            # No am/pm: assume reasonable default (e.g. 3 -> 3 pm, 10 -> 10 am)
            hour = hour + 12 if hour < 8 else hour
        if hour >= 24:
            hour = 23
        target = hour * 60 + (int(digits[1], 10) if len(digits) > 1 else 0)
        return min(slots, key=lambda s: abs(slot_to_minutes(s) - target))

    return slots[0]
