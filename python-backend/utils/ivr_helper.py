import random
from typing import List, Optional
from security import redis_client

DEFAULT_FILLERS = [
    "One moment...",
    "Let me check that for you...",
    "Got it, one second...",
    "Understood, just a moment while I look into that.",
    "Checking our system, one second please."
]

def get_random_filler(fillers: Optional[List[str]] = None) -> str:
    """Return a random filler phrase."""
    source = fillers if fillers else DEFAULT_FILLERS
    return random.choice(source)

def get_redis_pending_key(call_sid: str) -> str:
    return f"ivr:pending:{call_sid}"

def get_redis_result_key(call_sid: str) -> str:
    return f"ivr:result:{call_sid}"

def clear_ivr_state(call_sid: str):
    """Clean up Redis state for a call."""
    if redis_client:
        redis_client.delete(get_redis_pending_key(call_sid))
        redis_client.delete(get_redis_result_key(call_sid))
