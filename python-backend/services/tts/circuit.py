"""
Circuit breaker for ElevenLabs TTS: after repeated failures, temporarily disable API calls.

Uses Redis when available so multiple backend pods share state; falls back to in-process.
"""
from __future__ import annotations

import logging
import os
import threading
import time
logger = logging.getLogger(__name__)

try:
    import redis as redis_lib
except ImportError:
    redis_lib = None

_BREAKER_KEY = "ivr:tts:cb:open"
_FAIL_WINDOW_KEY = "ivr:tts:cb:fails"

_local_open_until: float = 0.0
_local_fails: int = 0
_local_fail_window_start: float = 0.0
_lock = threading.Lock()


def _redis():
    url = (os.getenv("REDIS_URL") or "").strip()
    if not url or not redis_lib:
        return None
    try:
        return redis_lib.from_url(url, decode_responses=True, socket_connect_timeout=2)
    except Exception:
        return None


def _threshold() -> int:
    try:
        return max(1, int(os.getenv("IVR_TTS_CB_FAILURE_THRESHOLD", "5")))
    except ValueError:
        return 5


def _window_seconds() -> float:
    try:
        return max(5.0, float(os.getenv("IVR_TTS_CB_WINDOW_SECONDS", "60")))
    except ValueError:
        return 60.0


def _open_seconds() -> int:
    try:
        return max(30, int(os.getenv("IVR_TTS_CB_OPEN_SECONDS", "120")))
    except ValueError:
        return 120


def is_open() -> bool:
    r = _redis()
    if r:
        try:
            if r.get(_BREAKER_KEY):
                return True
        except Exception as e:
            logger.debug("CB redis get: %s", e)
    with _lock:
        return time.time() < _local_open_until


def record_success() -> None:
    r = _redis()
    if r:
        try:
            r.delete(_BREAKER_KEY)
            r.delete(_FAIL_WINDOW_KEY)
        except Exception:
            pass
    global _local_open_until, _local_fails, _local_fail_window_start
    with _lock:
        _local_open_until = 0.0
        _local_fails = 0
        _local_fail_window_start = 0.0


def record_failure() -> None:
    """Increment failure count; trip breaker if threshold exceeded."""
    r = _redis()
    now = time.time()
    window = _window_seconds()
    thresh = _threshold()
    open_sec = _open_seconds()

    if r:
        try:
            count = r.incr(_FAIL_WINDOW_KEY)
            if int(count) == 1:
                r.expire(_FAIL_WINDOW_KEY, int(window) + 5)
            if int(count) >= thresh:
                r.setex(_BREAKER_KEY, open_sec, "1")
                logger.warning(
                    "IVR TTS circuit breaker OPEN (Redis): %s failures in window, breaker TTL %ss",
                    count,
                    open_sec,
                )
            return
        except Exception as e:
            logger.debug("CB redis incr: %s", e)

    global _local_open_until, _local_fails, _local_fail_window_start
    with _lock:
        if now - _local_fail_window_start > window:
            _local_fails = 0
            _local_fail_window_start = now
        _local_fails += 1
        if _local_fails >= thresh:
            _local_open_until = now + open_sec
            logger.warning(
                "IVR TTS circuit breaker OPEN (local): %s failures, open %ss",
                _local_fails,
                open_sec,
            )
            _local_fails = 0
