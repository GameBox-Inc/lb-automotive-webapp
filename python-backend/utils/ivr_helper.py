import json
import random
from typing import List, Optional
from security import redis_client

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
