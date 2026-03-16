from datetime import datetime
from typing import Literal


def _format_dt(dt: datetime) -> str:
    """
    Format a datetime for SMS: 'Mon Jan 2 at 3:30 PM'.
    Assumes dt is already in the business' local timezone.
    """
    return dt.strftime("%a %b %-d at %-I:%M %p") if hasattr(dt, "strftime") else str(dt)


def build_confirmation_message(
    *,
    shop_name: str,
    appointment_time: datetime,
) -> str:
    when = _format_dt(appointment_time)
    return (
        f"{shop_name}: Your appointment is scheduled for {when}. "
        "Reply 1 to confirm, 2 to cancel. Reply STOP to opt out."
    )


def build_reminder_message(
    *,
    shop_name: str,
    appointment_time: datetime,
    window: Literal["24h", "2h"],
) -> str:
    when = _format_dt(appointment_time)
    if window == "24h":
        prefix = "Reminder: You have an appointment tomorrow"
    else:
        prefix = "Reminder: You have an upcoming appointment"

    return (
        f"{shop_name}: {prefix} on {when}. "
        "Reply 1 to confirm, 2 to cancel. Reply STOP to opt out."
    )

