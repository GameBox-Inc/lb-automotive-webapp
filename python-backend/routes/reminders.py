import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List

from fastapi import APIRouter, Depends, HTTPException, status

from auth import get_current_admin_user
from database import DatabaseContextManager, fmt_query
from observability.tracing import update_phase, PHASE_BOOKING_CREATE
from security import redis_client
from services.twilio_sms import send_sms
from services.sms_templates import build_reminder_message
from utils.time_utils import get_business_timezone


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/reminders", tags=["reminders"])


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _fetch_appointments_in_window(
    start: datetime,
    end: datetime,
) -> List[Dict[str, Any]]:
    start_str = start.strftime("%Y-%m-%dT%H:%M:%S")
    end_str = end.strftime("%Y-%m-%dT%H:%M:%S")

    with DatabaseContextManager(read_only=False) as conn:
        cursor = conn.cursor()
        cursor.execute(
            fmt_query(
                """
                SELECT id, customer_name, phone_number, appointment_time
                FROM appointments
                WHERE status IN ('pending', 'scheduled')
                  AND appointment_time BETWEEN ? AND ?
                ORDER BY appointment_time ASC
                """
            ),
            (start_str, end_str),
        )
        rows = cursor.fetchall() or []
        return [dict(row) for row in rows]


def _already_reminded(appointment_id: str, window: str) -> bool:
    if not redis_client:
        return False
    key = f"sms:reminder:{window}:{appointment_id}"
    try:
        return bool(redis_client.get(key))
    except Exception:
        logger.exception("Failed to read reminder flag from Redis")
        return False


def _mark_reminded(appointment_id: str, window: str) -> None:
    if not redis_client:
        return
    key = f"sms:reminder:{window}:{appointment_id}"
    try:
        # Keep for 14 days to avoid duplicates across short outages
        redis_client.set(key, "1", ex=14 * 24 * 60 * 60)
    except Exception:
        logger.exception("Failed to write reminder flag to Redis")


def run_sms_reminders_internal(now: datetime) -> Dict[str, Any]:
    """
    Core reminder logic so it can be tested independently of FastAPI.
    """
    tz = get_business_timezone()

    # Windows: [now + 24h, now + 24h + 10m) and [now + 2h, now + 2h + 10m)
    window_minutes = 10

    windows = {
        "24h": (now + timedelta(hours=24), now + timedelta(hours=24, minutes=window_minutes)),
        "2h": (now + timedelta(hours=2), now + timedelta(hours=2, minutes=window_minutes)),
    }

    summary = {"24h": {"attempted": 0, "sent": 0}, "2h": {"attempted": 0, "sent": 0}}

    for label, (start, end) in windows.items():
        appts = _fetch_appointments_in_window(start, end)
        summary[label]["attempted"] = len(appts)

        for row in appts:
            appt_id = row["id"]
            phone = row.get("phone_number")
            if not phone:
                continue

            if _already_reminded(appt_id, label):
                continue

            try:
                # Convert stored appointment_time to business timezone if parseable
                appt_time_raw = row["appointment_time"]
                if isinstance(appt_time_raw, datetime):
                    appt_dt = appt_time_raw
                else:
                    # Fallback for string storage
                    appt_dt = datetime.fromisoformat(str(appt_time_raw))
                appt_dt_local = appt_dt.astimezone(tz) if appt_dt.tzinfo else appt_dt

                body = build_reminder_message(
                    shop_name="L-B Automotive",
                    appointment_time=appt_dt_local,
                    window=label,  # type: ignore[arg-type]
                )
                send_sms(
                    to=phone,
                    body=body,
                    metadata={
                        "sms_type": f"appointment_reminder_{label}",
                        "appointment_id": appt_id,
                    },
                )
                _mark_reminded(appt_id, label)
                summary[label]["sent"] += 1
            except Exception:
                logger.exception(
                    "Failed to send %s reminder for appointment %s", label, appt_id
                )

    return summary


@router.post("/run-sms", status_code=status.HTTP_200_OK)
def run_sms_reminders(current_user: Dict[str, Any] = Depends(get_current_admin_user)):
    """
    Trigger SMS appointment reminders for the 24h and 2h windows.

    Intended to be called by a cron job or external scheduler every few minutes.
    """
    try:
        update_phase(PHASE_BOOKING_CREATE)
        now = _now_utc()
        result = run_sms_reminders_internal(now)
        return {"status": "ok", "now": now.isoformat(), "summary": result}
    except Exception as exc:
        logger.exception("run_sms_reminders failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to run SMS reminders.",
        )

