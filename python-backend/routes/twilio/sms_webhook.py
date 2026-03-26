import logging
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import Response
from twilio.twiml.messaging_response import MessagingResponse

from database import DatabaseContextManager, fmt_query
from routes.twilio.webhook import validate_twilio_request, ivr_service_context
from security import PHONE_PATTERN, redis_client
from phone_normalization import phone_digit_variants


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/twilio", tags=["twilio"])


def _normalize_phone(phone: str) -> Optional[str]:
    if not phone:
        return None
    phone = phone.strip()
    if not PHONE_PATTERN.match(phone):
        return None
    return phone


def _find_next_upcoming_appointment(phone_number: str) -> Optional[str]:
    """
    Find the next upcoming appointment ID for a given phone number.
    Matches digit forms so E.164 (+1...) aligns with 10-digit stored rows.
    """
    variants = phone_digit_variants(phone_number)
    if not variants:
        return None
    placeholders = ", ".join(["?"] * len(variants))
    with DatabaseContextManager(read_only=False) as conn:
        cursor = conn.cursor()
        cursor.execute(
            fmt_query(
                f"""
                SELECT id
                FROM appointments
                WHERE regexp_replace(coalesce(phone_number, ''), '[^0-9]', '', 'g') IN ({placeholders})
                  AND appointment_time >= CURRENT_TIMESTAMP
                  AND status IN ('pending', 'scheduled', 'confirmed')
                ORDER BY appointment_time ASC
                LIMIT 1
                """
            ),
            tuple(variants),
        )
        row = cursor.fetchone()
        return row["id"] if row else None


def _update_appointment_status(appointment_id: str, status: str) -> None:
    with DatabaseContextManager(read_only=False) as conn:
        cursor = conn.cursor()
        cursor.execute(
            fmt_query(
                "UPDATE appointments "
                "SET status = ?, updated_at = CURRENT_TIMESTAMP "
                "WHERE id = ?"
            ),
            (status, appointment_id),
        )
        conn.commit()


@router.post(
    "/sms-webhook",
    dependencies=[Depends(validate_twilio_request), Depends(ivr_service_context)],
)
async def twilio_sms_webhook(
    request: Request,
    From: str = Form(...),
    Body: str = Form(...),
) -> Response:
    """
    Handle inbound SMS from Twilio:
    - '1' => confirm next upcoming appointment
    - '2' => cancel next upcoming appointment
    - 'STOP' and variants => global SMS opt-out for this phone number
    """
    phone = _normalize_phone(From)
    body_raw = Body or ""
    body = body_raw.strip().lower()

    resp = MessagingResponse()

    if not phone:
        logger.warning("SMS webhook: invalid or missing From phone number: %s", From)
        resp.message("We could not process your message due to an invalid phone number.")
        return Response(content=str(resp), media_type="application/xml")

    # Handle STOP-style opt-out first (Twilio standard keywords)
    if body in {"stop", "stopall", "unsubscribe", "cancel", "end", "quit"}:
        if redis_client:
            try:
                key = f"sms:opt_out:{phone}"
                redis_client.set(key, "1")
            except Exception:
                logger.exception("Failed to record SMS opt-out in Redis for %s", phone)

        resp.message("You have been opted out of SMS notifications from L-B Automotive.")
        logger.info("SMS opt-out recorded for %s", phone)
        return Response(content=str(resp), media_type="application/xml")

    # Look up the most relevant appointment for this phone
    appointment_id = _find_next_upcoming_appointment(phone)

    if not appointment_id:
        resp.message(
            "We couldn't find an upcoming appointment for this number. "
            "If you think this is an error, please call the shop."
        )
        logger.info(
            "SMS webhook: no upcoming appointment found for %s. Body=%s",
            phone,
            body_raw,
        )
        return Response(content=str(resp), media_type="application/xml")

    if body == "1":
        _update_appointment_status(appointment_id, "confirmed")
        resp.message("Thanks! Your appointment is confirmed.")
        logger.info(
            "SMS webhook: appointment %s confirmed via SMS from %s",
            appointment_id,
            phone,
        )
    elif body == "2":
        _update_appointment_status(appointment_id, "cancelled")
        resp.message("Your appointment has been cancelled. Reply CALL if you need to reschedule.")
        logger.info(
            "SMS webhook: appointment %s cancelled via SMS from %s",
            appointment_id,
            phone,
        )
    else:
        # Fallback: unrecognized keyword
        resp.message(
            "We didn't recognize that reply. Reply 1 to confirm, 2 to cancel. "
            "Reply STOP to opt out of messages."
        )
        logger.info(
            "SMS webhook: unrecognized reply from %s. Body=%s, appointment_id=%s",
            phone,
            body_raw,
            appointment_id,
        )

    return Response(content=str(resp), media_type="application/xml")

