"""
ElevenLabs Text-to-Speech HTTP client.

Synthesizes speech to MP3 bytes via POST /v1/text-to-speech/{voice_id}.
Requires ELEVENLABS_API_KEY in the environment (never log the key).
"""
from __future__ import annotations

import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

ELEVENLABS_API_BASE = "https://api.elevenlabs.io/v1"


class ElevenLabsError(Exception):
    """Base error for ElevenLabs TTS failures."""


class ElevenLabsConfigError(ElevenLabsError):
    """Missing API key or invalid configuration."""


class ElevenLabsHttpError(ElevenLabsError):
    """HTTP error from ElevenLabs API."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


def _timeout_seconds() -> float:
    raw = os.getenv("ELEVENLABS_TIMEOUT_SECONDS", "12")
    try:
        return max(1.0, min(60.0, float(raw)))
    except ValueError:
        return 12.0


def synthesize_to_mp3(
    text: str,
    voice_id: str,
    model_id: str = "eleven_multilingual_v2",
    *,
    timeout: Optional[float] = None,
) -> bytes:
    """
    Call ElevenLabs to synthesize text to MP3 bytes.

    Raises:
        ElevenLabsConfigError: API key missing or empty text/voice_id.
        ElevenLabsHttpError: Non-2xx response or empty body.
        ElevenLabsError: Network / timeout errors.
    """
    api_key = (os.getenv("ELEVENLABS_API_KEY") or "").strip()
    if not api_key:
        raise ElevenLabsConfigError("ELEVENLABS_API_KEY is not set")

    t = (text or "").strip()
    if not t:
        raise ElevenLabsConfigError("TTS text is empty")

    vid = (voice_id or "").strip()
    if not vid:
        raise ElevenLabsConfigError("ElevenLabs voice_id is empty")

    mid = (model_id or "eleven_multilingual_v2").strip()
    t_out = timeout if timeout is not None else _timeout_seconds()

    url = f"{ELEVENLABS_API_BASE}/text-to-speech/{vid}"
    headers = {
        "xi-api-key": api_key,
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
    }
    body = {
        "text": t,
        "model_id": mid,
    }

    try:
        with httpx.Client(timeout=httpx.Timeout(connect=3.0, read=t_out, write=10.0, pool=5.0)) as client:
            resp = client.post(url, headers=headers, json=body)
    except httpx.TimeoutException as e:
        raise ElevenLabsError(f"ElevenLabs request timed out: {e}") from e
    except httpx.RequestError as e:
        raise ElevenLabsError(f"ElevenLabs request failed: {e}") from e

    if resp.status_code < 200 or resp.status_code >= 300:
        # Do not log response body (may contain echoes of input).
        raise ElevenLabsHttpError(
            f"ElevenLabs HTTP {resp.status_code}",
            status_code=resp.status_code,
        )

    data = resp.content
    if not data or len(data) < 64:
        raise ElevenLabsHttpError("ElevenLabs returned empty or truncated audio")

    return data
