"""Unit tests for IVR TTS router: Polly fallback, ElevenLabs success path (mocked)."""
import os
from unittest.mock import patch

os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost")
os.environ.setdefault("TWILIO_WEBHOOK_BASE_URL", "https://example.com/lb-automotive/api/twilio/webhook")
os.environ.setdefault("TWILIO_SKIP_VALIDATION", "true")

from twilio.twiml.voice_response import VoiceResponse

from services.tts import router as r


def test_speak_or_play_twilio_default_no_elevenlabs():
    vr = VoiceResponse()

    def gs(key, default=""):
        d = {
            "ivr_tts_provider": "twilio",
            "ivr_tts_canary_prompts": "welcome",
        }
        return d.get(key, default)

    with patch("services.tts.router.get_setting", side_effect=gs):
        r.speak_or_play(vr, "Hello", "Polly.Matthew", "en", prompt_key="welcome")
    xml = str(vr)
    assert "<Say" in xml
    assert "Hello" in xml
    assert "<Play" not in xml


def test_speak_or_play_elevenlabs_success_mocked():
    vr = VoiceResponse()
    fake_mp3 = b"\xff" * 200

    def gs(key, default=""):
        d = {
            "ivr_tts_provider": "elevenlabs",
            "ivr_tts_canary_prompts": "welcome",
            "elevenlabs_voice_id_en": "voice123",
            "elevenlabs_model_id": "eleven_multilingual_v2",
            "ivr_tts_audio_ttl_seconds": "600",
        }
        return d.get(key, default)

    with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-key"}):
        with patch("services.tts.router.get_setting", side_effect=gs):
            with patch("services.tts.router.cb.is_open", return_value=False):
                with patch("services.tts.router.el.synthesize_to_mp3", return_value=fake_mp3):
                    with patch("services.tts.router.tstore.cache_lookup_audio_id", return_value=None):
                        with patch("services.tts.router.tstore.new_audio_id", return_value="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"):
                            with patch("services.tts.router.tstore.put_audio"):
                                with patch("services.tts.router.tstore.cache_store_audio_id"):
                                    with patch("services.tts.router.cb.record_success"):
                                        r.speak_or_play(vr, "Welcome", "Polly.Matthew", "en", prompt_key="welcome")
    xml = str(vr)
    assert "<Play" in xml
    assert "tts-audio/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee" in xml


def test_speak_or_play_elevenlabs_falls_back_on_api_error():
    vr = VoiceResponse()

    def gs(key, default=""):
        d = {
            "ivr_tts_provider": "elevenlabs",
            "ivr_tts_canary_prompts": "welcome",
            "elevenlabs_voice_id_en": "voice123",
        }
        return d.get(key, default)

    from services.tts import elevenlabs as el

    with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-key"}):
        with patch("services.tts.router.get_setting", side_effect=gs):
            with patch("services.tts.router.cb.is_open", return_value=False):
                with patch("services.tts.router.tstore.cache_lookup_audio_id", return_value=None):
                    with patch(
                        "services.tts.router.el.synthesize_to_mp3",
                        side_effect=el.ElevenLabsHttpError("fail", status_code=500),
                    ):
                        with patch("services.tts.router.cb.record_failure"):
                            r.speak_or_play(vr, "Welcome", "Polly.Matthew", "en", prompt_key="welcome")
    xml = str(vr)
    assert "<Say" in xml
    assert "<Play" not in xml


def test_tts_audio_route_404():
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)
    r = client.get("/api/twilio/tts-audio/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404
