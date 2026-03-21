"""
Store short-lived MP3 bytes for Twilio <Play> URLs (Redis preferred; in-process fallback for dev).
"""
from __future__ import annotations

import base64
import logging
import os
import threading
import time
import uuid
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import redis as redis_lib
except ImportError:
    redis_lib = None

_AUDIO_TTL_SECONDS = 600
_LOCAL: dict[str, tuple[float, bytes]] = {}
_LOCAL_LOCK = threading.Lock()
_LOCAL_MAX = 2000

_redis_client = None


def _get_redis():
    global _redis_client
    if _redis_client is False:
        return None
    if _redis_client is not None:
        return _redis_client
    url = (os.getenv("REDIS_URL") or "").strip()
    if not url or not redis_lib:
        return None
    try:
        _redis_client = redis_lib.from_url(url, decode_responses=True, socket_connect_timeout=2)
        _redis_client.ping()
        return _redis_client
    except Exception as e:
        logger.warning("TTS storage: Redis unavailable (%s); using in-process cache only.", e)
        _redis_client = False
        return None


def new_audio_id() -> str:
    return str(uuid.uuid4())


def put_audio(audio_id: str, data: bytes, ttl_seconds: int = _AUDIO_TTL_SECONDS) -> None:
    """Persist MP3 bytes under audio_id (Twilio will GET by opaque id)."""
    if not audio_id or not data:
        return
    r = _get_redis()
    key = f"ivr:tts:audio:{audio_id}"
    b64 = base64.b64encode(data).decode("ascii")
    if r:
        try:
            r.setex(key, ttl_seconds, b64)
            return
        except Exception as e:
            logger.warning("TTS Redis SET failed: %s", e)
    now = time.time()
    with _LOCAL_LOCK:
        _LOCAL[audio_id] = (now + ttl_seconds, data)
        if len(_LOCAL) > _LOCAL_MAX:
            _prune_local_unlocked(now)


def get_audio(audio_id: str) -> Optional[bytes]:
    """Return MP3 bytes or None if missing/expired."""
    if not _is_uuid(audio_id):
        return None
    r = _get_redis()
    key = f"ivr:tts:audio:{audio_id}"
    if r:
        try:
            b64 = r.get(key)
            if b64:
                return base64.b64decode(b64.encode("ascii"))
        except Exception as e:
            logger.warning("TTS Redis GET failed: %s", e)
    now = time.time()
    with _LOCAL_LOCK:
        _prune_local_unlocked(now)
        ent = _LOCAL.get(audio_id)
        if not ent:
            return None
        exp, data = ent
        if exp < now:
            del _LOCAL[audio_id]
            return None
        return data


def cache_lookup_audio_id(content_key: str) -> Optional[str]:
    """Return existing audio_id for a content hash key, if still present."""
    r = _get_redis()
    if not r:
        return None
    try:
        aid = r.get(f"ivr:tts:content:{content_key}")
        if aid and get_audio(aid):
            return aid
    except Exception as e:
        logger.warning("TTS content cache GET failed: %s", e)
    return None


def cache_store_audio_id(content_key: str, audio_id: str, ttl_seconds: int = 86400) -> None:
    r = _get_redis()
    if not r:
        return
    try:
        r.setex(f"ivr:tts:content:{content_key}", ttl_seconds, audio_id)
    except Exception as e:
        logger.warning("TTS content cache SET failed: %s", e)


def _prune_local_unlocked(now: float) -> None:
    dead = [k for k, (exp, _) in _LOCAL.items() if exp < now]
    for k in dead:
        del _LOCAL[k]


def _is_uuid(val: str) -> bool:
    try:
        uuid.UUID(val)
        return True
    except Exception:
        return False
