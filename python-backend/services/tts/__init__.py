"""
TTS routing for IVR: Twilio Polly (<Say>) vs ElevenLabs MP3 (<Play>) with fallbacks.

See services/tts/router.py (speak_or_play), elevenlabs.py (API client), storage.py (Redis cache).
"""
from services.tts.router import gather_speak_or_play, get_public_tts_base_url, speak_or_play

__all__ = [
    "speak_or_play",
    "gather_speak_or_play",
    "get_public_tts_base_url",
]
