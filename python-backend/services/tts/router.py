"""
Route IVR speech to Twilio <Say> (Polly) or ElevenLabs + <Play> with strict fallback.

Phase 1 (plan): on-demand ElevenLabs + Redis-backed audio URLs + content cache;
optional static HTTPS URLs via settings; default provider remains twilio (dark launch).
"""
from __future__ import annotations

import hashlib
import logging
import os
import time
from typing import Optional
from urllib.parse import urlparse

from twilio.twiml.voice_response import Gather, VoiceResponse

from services.call_state import get_setting
from services.tts import circuit as cb
from services.tts import elevenlabs as el
from services.tts import storage as tstore
from observability.monitoring import ivr_tts_duration_seconds, ivr_tts_requests_total

logger = logging.getLogger(__name__)

_HTTPS_PREFIX = "https://"


def get_public_tts_base_url() -> str:
    """
    Base URL (HTTPS, Twilio-reachable) for GET /api/twilio/tts-audio/{id}.
    Prefer IVR_TTS_PUBLIC_BASE_URL; else derive from TWILIO_WEBHOOK_BASE_URL
    by stripping the /api/twilio/... suffix.
    """
    explicit = (os.getenv("IVR_TTS_PUBLIC_BASE_URL") or "").strip()
    if explicit:
        return explicit.rstrip("/")
    w = os.getenv(
        "TWILIO_WEBHOOK_BASE_URL",
        "https://twilio.kozytherocket.space/lb-automotive/api/twilio/webhook",
    )
    p = urlparse(w)
    idx = p.path.find("/api/twilio")
    if idx != -1:
        path = p.path[:idx]
    else:
        path = ""
    return f"{p.scheme}://{p.netloc}{path}".rstrip("/")


def _canary_prompts() -> set[str]:
    raw = (get_setting("ivr_tts_canary_prompts", "welcome") or "welcome").strip().lower()
    if raw in ("*", "all"):
        return {"*"}
    return {p.strip() for p in raw.split(",") if p.strip()}


def _should_use_elevenlabs(prompt_key: Optional[str]) -> bool:
    prompts = _canary_prompts()
    if "*" in prompts:
        return True
    if not prompt_key:
        return False
    return prompt_key.lower() in prompts


def _voice_id_for_language(language: str) -> str:
    if language == "es":
        return (get_setting("elevenlabs_voice_id_es", "") or "").strip()
    return (get_setting("elevenlabs_voice_id_en", "") or "").strip()


def _model_id() -> str:
    return (get_setting("elevenlabs_model_id", "eleven_multilingual_v2") or "eleven_multilingual_v2").strip()


def _static_prompt_url(prompt_key: Optional[str], language: str) -> Optional[str]:
    """Optional pre-hosted MP3 URLs (phase A — no API call)."""
    if not prompt_key:
        return None
    pk = prompt_key.lower().strip()
    lang = "es" if language == "es" else "en"
    for key in (f"ivr_tts_static_url_{pk}_{lang}", f"ivr_tts_static_url_{pk}"):
        u = (get_setting(key, "") or "").strip()
        if u.startswith(_HTTPS_PREFIX):
            return u
    return None


def _content_cache_key(text: str, voice_id: str, model_id: str) -> str:
    h = hashlib.sha256(f"{text}|{voice_id}|{model_id}".encode("utf-8")).hexdigest()
    return h


def _say_polly(response: VoiceResponse, text: str, voice: str) -> None:
    """Twilio native <Say> path (Polly)."""
    ivr_tts_requests_total.labels(provider="twilio", result="say").inc()
    response.say(text, voice=voice)


def _say_after_elevenlabs_miss(response: VoiceResponse, text: str, voice: str) -> None:
    """Fallback to Polly after ElevenLabs path declined or failed (single metric)."""
    ivr_tts_requests_total.labels(provider="elevenlabs", result="fallback_say").inc()
    response.say(text, voice=voice)


def speak_or_play(
    response: VoiceResponse,
    text: str,
    voice: str,
    language: str,
    *,
    prompt_key: Optional[str] = None,
) -> None:
    """
    Append TwiML: either <Say> (Polly) or <Play> (ElevenLabs MP3 URL).
    Never raises — always falls back to <Say> on any failure.
    """
    provider = (get_setting("ivr_tts_provider", "twilio") or "twilio").strip().lower()
    if provider not in ("twilio", "elevenlabs"):
        provider = "twilio"

    if provider == "twilio" or not _should_use_elevenlabs(prompt_key):
        _say_polly(response, text, voice)
        return

    static_url = _static_prompt_url(prompt_key, language)
    if static_url:
        ivr_tts_requests_total.labels(provider="elevenlabs_static", result="play").inc()
        response.play(static_url)
        return

    if not (os.getenv("ELEVENLABS_API_KEY") or "").strip():
        logger.info("IVR TTS: elevenlabs selected but ELEVENLABS_API_KEY missing; using Say")
        _say_after_elevenlabs_miss(response, text, voice)
        return

    if cb.is_open():
        logger.warning("IVR TTS: circuit breaker open; using Say")
        _say_after_elevenlabs_miss(response, text, voice)
        return

    voice_id = _voice_id_for_language(language)
    if not voice_id:
        logger.info("IVR TTS: no elevenlabs_voice_id_* for language=%s; using Say", language)
        _say_after_elevenlabs_miss(response, text, voice)
        return

    model_id = _model_id()
    ck = _content_cache_key(text, voice_id, model_id)
    audio_id = tstore.cache_lookup_audio_id(ck)
    if not audio_id:
        t0 = time.perf_counter()
        try:
            mp3 = el.synthesize_to_mp3(text, voice_id, model_id)
        except el.ElevenLabsError as e:
            dt = time.perf_counter() - t0
            ivr_tts_duration_seconds.labels(result="error").observe(dt)
            cb.record_failure()
            ivr_tts_requests_total.labels(provider="elevenlabs", result="error").inc()
            logger.warning("IVR TTS ElevenLabs failed: %s", type(e).__name__, exc_info=True)
            _say_after_elevenlabs_miss(response, text, voice)
            return
        dt = time.perf_counter() - t0
        ivr_tts_duration_seconds.labels(result="success").observe(dt)
        cb.record_success()
        audio_id = tstore.new_audio_id()
        ttl = 600
        try:
            ttl = max(60, int(get_setting("ivr_tts_audio_ttl_seconds", "600")))
        except ValueError:
            pass
        tstore.put_audio(audio_id, mp3, ttl_seconds=ttl)
        tstore.cache_store_audio_id(ck, audio_id)

    base = get_public_tts_base_url()
    url = f"{base}/api/twilio/tts-audio/{audio_id}"
    if not url.startswith(_HTTPS_PREFIX):
        logger.warning("IVR TTS: Play URL not HTTPS (%s); using Say for Twilio safety", url[:48])
        _say_after_elevenlabs_miss(response, text, voice)
        return

    ivr_tts_requests_total.labels(provider="elevenlabs", result="play").inc()
    response.play(url)


def gather_speak_or_play(
    gather: Gather,
    text: str,
    voice: str,
    language: str,
    *,
    prompt_key: Optional[str] = None,
) -> None:
    """Same routing as speak_or_play but appends to a Gather verb."""
    provider = (get_setting("ivr_tts_provider", "twilio") or "twilio").strip().lower()
    if provider not in ("twilio", "elevenlabs"):
        provider = "twilio"

    if provider == "twilio" or not _should_use_elevenlabs(prompt_key):
        ivr_tts_requests_total.labels(provider="twilio", result="say").inc()
        gather.say(text, voice=voice)
        return

    static_url = _static_prompt_url(prompt_key, language)
    if static_url:
        ivr_tts_requests_total.labels(provider="elevenlabs_static", result="play").inc()
        gather.play(static_url)
        return

    if not (os.getenv("ELEVENLABS_API_KEY") or "").strip():
        ivr_tts_requests_total.labels(provider="elevenlabs", result="fallback_say").inc()
        gather.say(text, voice=voice)
        return

    if cb.is_open():
        ivr_tts_requests_total.labels(provider="elevenlabs", result="fallback_say").inc()
        gather.say(text, voice=voice)
        return

    voice_id = _voice_id_for_language(language)
    if not voice_id:
        ivr_tts_requests_total.labels(provider="elevenlabs", result="fallback_say").inc()
        gather.say(text, voice=voice)
        return

    model_id = _model_id()
    ck = _content_cache_key(text, voice_id, model_id)
    audio_id = tstore.cache_lookup_audio_id(ck)
    if not audio_id:
        t0 = time.perf_counter()
        try:
            mp3 = el.synthesize_to_mp3(text, voice_id, model_id)
        except el.ElevenLabsError as e:
            dt = time.perf_counter() - t0
            ivr_tts_duration_seconds.labels(result="error").observe(dt)
            cb.record_failure()
            ivr_tts_requests_total.labels(provider="elevenlabs", result="error").inc()
            logger.warning("IVR TTS ElevenLabs failed (gather): %s", type(e).__name__, exc_info=True)
            ivr_tts_requests_total.labels(provider="elevenlabs", result="fallback_say").inc()
            gather.say(text, voice=voice)
            return
        dt = time.perf_counter() - t0
        ivr_tts_duration_seconds.labels(result="success").observe(dt)
        cb.record_success()
        audio_id = tstore.new_audio_id()
        ttl = 600
        try:
            ttl = max(60, int(get_setting("ivr_tts_audio_ttl_seconds", "600")))
        except ValueError:
            pass
        tstore.put_audio(audio_id, mp3, ttl_seconds=ttl)
        tstore.cache_store_audio_id(ck, audio_id)

    base = get_public_tts_base_url()
    url = f"{base}/api/twilio/tts-audio/{audio_id}"
    if not url.startswith(_HTTPS_PREFIX):
        ivr_tts_requests_total.labels(provider="elevenlabs", result="fallback_say").inc()
        gather.say(text, voice=voice)
        return

    ivr_tts_requests_total.labels(provider="elevenlabs", result="play").inc()
    gather.play(url)
