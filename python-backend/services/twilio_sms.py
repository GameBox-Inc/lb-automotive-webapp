import logging
import os
from typing import Optional, Dict, Any

from twilio.rest import Client

from security import PHONE_PATTERN, redis_client


logger = logging.getLogger(__name__)


TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
SMS_ENABLED = os.getenv("SMS_ENABLED", "false").lower() == "true"


def _is_configured() -> bool:
    if not SMS_ENABLED:
        logger.info("SMS sending is disabled (SMS_ENABLED=false). Skipping SMS send.")
        return False

    if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_PHONE_NUMBER):
        logger.warning(
            "Twilio SMS not configured: missing TWILIO_ACCOUNT_SID/TWILIO_AUTH_TOKEN/TWILIO_PHONE_NUMBER."
        )
        return False
    return True


def _is_opted_out(phone_number: str) -> bool:
    """Check Redis-backed global SMS opt-out for a phone number."""
    if not redis_client:
        return False
    try:
        key = f"sms:opt_out:{phone_number}"
        return bool(redis_client.get(key))
    except Exception:
        # Failing open here avoids breaking core flows due to Redis issues.
        logger.exception("Failed to check SMS opt-out in Redis")
        return False


def send_sms(to: str, body: str, metadata: Optional[Dict[str, Any]] = None) -> None:
    """
    Send an SMS via Twilio using the existing telephony configuration.

    - Respects SMS_ENABLED flag.
    - Skips invalid phone numbers.
    - Skips globally opted-out numbers (Redis key sms:opt_out:<phone>).
    """
    meta = metadata or {}

    if not _is_configured():
        return

    if not to:
        logger.warning("SMS not sent: empty phone number. Metadata=%s", meta)
        return

    to = to.strip()
    if not PHONE_PATTERN.match(to):
        logger.warning("SMS not sent: invalid phone number format '%s'. Metadata=%s", to, meta)
        return

    if _is_opted_out(to):
        logger.info("SMS not sent: phone number %s is opted out. Metadata=%s", to, meta)
        return

    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        message = client.messages.create(
            to=to,
            from_=TWILIO_PHONE_NUMBER,
            body=body,
        )
        logger.info(
            "SMS sent",
            extra={
                "phone_number": to,
                "sms_sid": getattr(message, "sid", None),
                "metadata": meta,
                "sms_type": meta.get("sms_type"),
            },
        )
    except Exception as exc:
        logger.error(
            "Failed to send SMS",
            extra={"phone_number": to, "metadata": meta, "error": str(exc)},
            exc_info=True,
        )

