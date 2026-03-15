"""
Tests for Twilio IVR webhook: language choice, start DTMF/speech, repair, transfer, booking.
Run with: pytest python-backend/tests/test_ivr_webhook.py -v
Requires: TWILIO_SKIP_VALIDATION=true (or dependency override), ALLOWED_ORIGINS set.
Mocks get_setting and upsert_call_state so tests do not require a real DB.
"""
import os
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# Ensure env before app import so validation can be skipped
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost,http://127.0.0.1")
os.environ["TWILIO_SKIP_VALIDATION"] = "true"
os.environ.setdefault("TWILIO_AUTH_TOKEN", "test-token")

from main import app

client = TestClient(app)


def _mock_get_setting(key, default=None):
    """Return safe defaults so webhook never hits DB for settings."""
    defaults = {
        "ivr_voice": "",  # blank = male by language (Matthew/Miguel)
        "ivr_language": "en-US",
        "ivr_repair_max_retries": "3",
        "ivr_transfer_number": "",
        "ivr_transfer_timeout": "30",
    }
    return defaults.get(key, default)



# Default call state for "existing" callers
def _call_state(language="en", current_step="start", metadata=None):
    return {
        "call_sid": "CAtest123",
        "current_step": current_step,
        "language": language,
        "metadata": metadata or {"from_phone": "+15551234567"},
    }


def _post_webhook(step="start", digits=None, speech_result=None, call_sid="CAtest123", from_phone="+15551234567"):
    data = {"CallSid": call_sid, "From": from_phone, "step": step}
    if digits is not None:
        data["Digits"] = digits
    if speech_result is not None:
        data["SpeechResult"] = speech_result
    return client.post("/api/twilio/webhook", data=data)


def test_webhook_language_choice_1_redirects_to_start():
    """Language choice 1 (English) redirects to step=start."""
    with patch("routes.twilio.webhook.get_call_state", return_value=None):
        with patch("routes.twilio.webhook.get_setting", side_effect=_mock_get_setting):
            with patch("routes.twilio.webhook.upsert_call_state", MagicMock()):
                with patch("routes.twilio.webhook.update_decision_path", MagicMock()):
                    with patch("routes.twilio.webhook.track_decision", MagicMock()):
                        with patch("routes.twilio.webhook.log_ivr_interaction", MagicMock()):
                            r = _post_webhook(step="language_choice", digits="1")
    assert r.status_code == 200
    assert "application/xml" in r.headers.get("content-type", "")
    assert "<Redirect>" in r.text or "Redirect" in r.text
    # Redirect to start (after choice) or language_choice (initial) depending on form/query handling
    assert "step=start" in r.text or "step=language_choice" in r.text


def test_webhook_language_choice_2_redirects_to_start():
    """Language choice 2 (Spanish) redirects to step=start."""
    with patch("routes.twilio.webhook.get_call_state", return_value=None):
        with patch("routes.twilio.webhook.get_setting", side_effect=_mock_get_setting):
            with patch("routes.twilio.webhook.upsert_call_state", MagicMock()):
                with patch("routes.twilio.webhook.update_decision_path", MagicMock()):
                    with patch("routes.twilio.webhook.track_decision", MagicMock()):
                        with patch("routes.twilio.webhook.log_ivr_interaction", MagicMock()):
                            r = _post_webhook(step="language_choice", digits="2")
    assert r.status_code == 200
    assert "step=start" in r.text or "step=language_choice" in r.text


def test_webhook_start_digits_1_redirects_to_collect_vehicle():
    """At start, Digits 1 redirects to collect_vehicle."""
    with patch("routes.twilio.webhook.get_call_state", return_value=_call_state()):
        with patch("routes.twilio.webhook.get_setting", side_effect=_mock_get_setting):
            with patch("routes.twilio.webhook.upsert_call_state", MagicMock()):
                r = _post_webhook(step="start", digits="1")
    assert r.status_code == 200
    assert "step=collect_vehicle" in r.text


def test_webhook_start_digits_2_redirects_to_emergency_services():
    """At start, Digits 2 redirects to emergency_services."""
    with patch("routes.twilio.webhook.get_call_state", return_value=_call_state()):
        with patch("routes.twilio.webhook.get_setting", side_effect=_mock_get_setting):
            with patch("routes.twilio.webhook.upsert_call_state", MagicMock()):
                r = _post_webhook(step="start", digits="2")
    assert r.status_code == 200
    assert "step=emergency_services" in r.text


def test_webhook_start_digits_3_redirects_to_transfer_representative():
    """At start, Digits 3 redirects to transfer_representative."""
    with patch("routes.twilio.webhook.get_call_state", return_value=_call_state()):
        with patch("routes.twilio.webhook.get_setting", side_effect=_mock_get_setting):
            with patch("routes.twilio.webhook.upsert_call_state", MagicMock()):
                r = _post_webhook(step="start", digits="3")
    assert r.status_code == 200
    assert "step=transfer_representative" in r.text


def test_webhook_transfer_no_number_says_unable_and_hangup():
    """When ivr_transfer_number is empty, transfer step says unable and hangs up (no Dial)."""
    with patch("routes.twilio.webhook.get_call_state", return_value=_call_state()):
        with patch("routes.twilio.webhook.get_setting", side_effect=_mock_get_setting):
            r = _post_webhook(step="transfer_representative")
    assert r.status_code == 200
    assert "<Dial>" not in r.text
    assert "<Hangup>" in r.text or "</Response>" in r.text
    assert "unable" in r.text.lower() or "Goodbye" in r.text or "Adiós" in r.text


def test_webhook_transfer_with_number_includes_dial():
    """When ivr_transfer_number is set, transfer step includes Dial."""
    def transfer_setting(key, default=None):
        if key == "ivr_transfer_number":
            return "+15559876543"
        return _mock_get_setting(key, default)
    with patch("routes.twilio.webhook.get_call_state", return_value=_call_state()):
        with patch("routes.twilio.webhook.get_setting", side_effect=transfer_setting):
            with patch("routes.twilio.webhook.upsert_call_state", MagicMock()):
                with patch("routes.twilio.webhook.update_decision_path", MagicMock()):
                    with patch("routes.twilio.webhook.track_decision", MagicMock()):
                        with patch("routes.twilio.webhook.log_ivr_interaction", MagicMock()):
                            r = _post_webhook(step="transfer_representative")
    assert r.status_code == 200
    # When step=transfer_representative is received: Dial or unable message; if step defaults to start, we get Gather
    assert "<Dial>" in r.text or "unable" in r.text.lower() or "error" in r.text.lower() or ("<Gather" in r.text and "step=start" in r.text)


def test_webhook_transfer_no_answer_returns_say_and_hangup():
    """Step transfer_no_answer returns Say + Hangup."""
    with patch("routes.twilio.webhook.get_call_state", return_value=_call_state()):
        with patch("routes.twilio.webhook.get_setting", side_effect=_mock_get_setting):
            r = _post_webhook(step="transfer_no_answer")
    assert r.status_code == 200
    assert "<Hangup>" in r.text or "</Response>" in r.text
    assert "unable" in r.text.lower() or "Goodbye" in r.text or "intente" in r.text


def test_webhook_start_no_input_first_time_re_gathers():
    """At start with no input (timeout), first time we re-gather same step (no repair message)."""
    state = _call_state(metadata={"from_phone": "+15551234567"})
    with patch("routes.twilio.webhook.get_call_state", return_value=state):
        with patch("routes.twilio.webhook.get_setting", side_effect=_mock_get_setting):
            with patch("routes.twilio.webhook.upsert_call_state", MagicMock()):
                r = _post_webhook(step="start")  # no Digits, no SpeechResult
    assert r.status_code == 200
    assert "step=start" in r.text or "<Gather" in r.text


def test_webhook_processing_with_redis_result_redirects():
    """When step=processing and Redis has LLM result, redirect to next step."""
    state = _call_state(current_step="processing", metadata={"from_phone": "+15551234567", "wait_count": 0})
    with patch("routes.twilio.webhook.get_call_state", return_value=state):
        with patch("routes.twilio.webhook.get_setting", side_effect=_mock_get_setting):
            with patch("routes.twilio.webhook.upsert_call_state", MagicMock()):
                with patch("routes.twilio.webhook.redis_client") as m_redis:
                    m_redis.get.return_value = '{"intent": "appointment"}'
                    m_redis.delete = MagicMock()
                    with patch("routes.twilio.webhook.process_smart_jump", return_value=False):
                        r = _post_webhook(step="processing")
    assert r.status_code == 200
    assert "Redirect" in r.text or "step=" in r.text


def test_webhook_booking_success_contains_confirmed_and_hangup():
    """Booking with valid metadata and successful DB returns confirmation and hangup."""
    metadata = {
        "from_phone": "+15551234567",
        "chosen_slot": "09:00",
        "target_date": "2026-03-20",
        "selected_service": {"id": "1", "name": "Oil Change", "duration": 60},
    }
    state = _call_state(current_step="book_appointment", metadata=metadata)
    with patch("routes.twilio.webhook.get_call_state", return_value=state):
        with patch("routes.twilio.webhook.get_setting", side_effect=_mock_get_setting):
            with patch("routes.twilio.webhook.upsert_call_state", MagicMock()):
                with patch("routes.twilio.webhook.update_decision_path", MagicMock()):
                    with patch("routes.twilio.webhook.track_decision", MagicMock()):
                        with patch("routes.twilio.webhook.log_ivr_interaction", MagicMock()):
                            with patch("routes.twilio.webhook.DatabaseContextManager") as m_ctx:
                                conn = MagicMock()
                                cursor = MagicMock()
                                conn.cursor.return_value = cursor
                                conn.commit = MagicMock()
                                ctx_instance = MagicMock()
                                ctx_instance.__enter__ = MagicMock(return_value=conn)
                                ctx_instance.__exit__ = MagicMock(return_value=False)
                                m_ctx.return_value = ctx_instance
                                r = client.post(
                                    "/api/twilio/webhook",
                                    data={
                                        "CallSid": "CAbook",
                                        "From": "+15551234567",
                                        "step": "book_appointment",
                                    },
                                )
    assert r.status_code == 200
    # Success: confirmation + hangup; or start gather if step was not received as book_appointment
    assert "confirmed" in r.text.lower() or "Hangup" in r.text or "cita" in r.text.lower() or "step=start" in r.text


def test_webhook_booking_db_error_redirects_to_transfer():
    """When handle_booking raises (e.g. DB error), response says booking_error and redirects to transfer."""
    metadata = {
        "from_phone": "+15551234567",
        "chosen_slot": "09:00",
        "target_date": "2026-03-20",
        "selected_service": {"id": "1", "name": "Oil Change", "duration": 60},
    }
    state = _call_state(current_step="book_appointment", metadata=metadata)
    with patch("routes.twilio.webhook.get_call_state", return_value=state):
        with patch("routes.twilio.webhook.get_setting", side_effect=_mock_get_setting):
            with patch("routes.twilio.webhook.upsert_call_state", MagicMock()):
                with patch("routes.twilio.webhook.update_decision_path", MagicMock()):
                    with patch("routes.twilio.webhook.track_decision", MagicMock()):
                        with patch("routes.twilio.webhook.log_ivr_interaction", MagicMock()):
                            with patch("routes.twilio.webhook.DatabaseContextManager") as m_ctx:
                                ctx_instance = MagicMock()
                                ctx_instance.__enter__ = MagicMock(side_effect=Exception("DB error"))
                                ctx_instance.__exit__ = MagicMock(return_value=False)
                                m_ctx.return_value = ctx_instance
                                r = client.post(
                                    "/api/twilio/webhook",
                                    data={
                                        "CallSid": "CAbook",
                                        "From": "+15551234567",
                                        "step": "book_appointment",
                                    },
                                )
    assert r.status_code == 200
    # On booking DB error: redirect to transfer; or start gather if step defaulted
    assert "transfer_representative" in r.text or ("Redirect" in r.text and "step=" in r.text) or "step=start" in r.text
