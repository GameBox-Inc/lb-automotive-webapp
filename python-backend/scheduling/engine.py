import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any, Union

from database import get_db_connection, fmt_query
from observability.tracing import update_phase, PHASE_AVAILABILITY_COMPUTE

logger = logging.getLogger(__name__)

# #region agent log
def _ivr_debug(data: dict) -> None:
    try:
        log_path = Path(__file__).resolve().parent.parent.parent / "debug-49c9c0.log"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"sessionId": "49c9c0", "timestamp": int(datetime.now().timestamp() * 1000), **data}) + "\n")
    except Exception:
        pass
# #endregion


@dataclass
class TimeSlot:
    start: datetime
    end: datetime
    technician_id: Optional[str]
    service_id: Optional[str]
    source: str = "engine"


def _parse_time(value: Union[str, datetime], *, default_tz: str = "America/New_York") -> datetime:
    """Parse ISO or 'YYYY-MM-DD HH:MM' style strings into naive datetimes. Accepts datetime from DB."""
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo else value
    if not isinstance(value, str):
        # Postgres may return time/datetime; stringify so callers can use with date
        value = str(value)
    try:
        return datetime.fromisoformat(value.replace("Z", ""))
    except Exception:
        return datetime.strptime(value[:19].replace("T", " "), "%Y-%m-%d %H:%M")


def _minutes(duration: Optional[int]) -> int:
    return int(duration or 0)


def _is_day_closed(is_closed_val: Any) -> bool:
    """Normalize is_closed from DB (Postgres can return int 0/1 or boolean)."""
    if is_closed_val is None:
        return False
    if isinstance(is_closed_val, bool):
        return is_closed_val
    if isinstance(is_closed_val, (int, float)):
        return bool(is_closed_val)
    return str(is_closed_val).strip() not in ("0", "false", "no", "")


def _time_to_str(value: Any) -> str:
    """Stringify time from DB (Postgres may return time/datetime)."""
    if value is None:
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%H:%M")
    return str(value).strip()


def _end_time_for_day(value: Any) -> str:
    """Normalize end time: 00:00 / midnight is treated as end of day (23:59). Empty stays empty."""
    s = _time_to_str(value)
    if not s:
        return ""
    if s in ("00:00", "00:00:00", "0:00"):
        return "23:59"
    return s


def _day_of_week_int(value: Any) -> int:
    """Normalize day_of_week to 0-6 int (Postgres may return string or decimal)."""
    if value is None:
        return 0
    if isinstance(value, int) and 0 <= value <= 6:
        return value
    try:
        return int(value) % 7
    except (TypeError, ValueError):
        return 0


def compute_availability(
    *,
    service_id: Optional[str],
    date: datetime,
    technician_id: Optional[str] = None,
    horizon_days: int = 1,
) -> List[TimeSlot]:
    """
    Compute available slots for a given service on a given date range.

    Availability is driven by the same data as the admin UI:
    - business_hours: per-day shop open/close (and Settings per-day hours).
    - staff_schedules: the table written by Admin > Staff & Schedule > Schedules
      when you click "Save Schedule". If no rows or table missing, slots are
      derived from business_hours only (so weekdays still get times).
    - appointments (start_time/end_time) and blackouts further restrict slots.

    Respects existing appointments and blackouts; assumes a single location.
    """
    update_phase(PHASE_AVAILABILITY_COMPUTE)
    # #region agent log
    _ivr_debug({"location": "engine.py:compute_availability:entry", "message": "IVR availability entry", "data": {"service_id": str(service_id) if service_id else None, "date_str": date.strftime("%Y-%m-%d"), "day_of_week": date.weekday()}, "hypothesisId": "H1"})
    # #endregion
    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        start_day = date.date()
        end_day = start_day + timedelta(days=horizon_days)

        # Load service duration (fallback to 60 minutes if unknown).
        # Be backwards compatible with schemas that don't yet have duration_minutes.
        service_duration_min = 60
        if service_id:
            try:
                cursor.execute(
                    fmt_query("SELECT duration_minutes, duration FROM services WHERE id = ?"),
                    (service_id,),
                )
                row = cursor.fetchone()
                if row:
                    duration_minutes = row.get("duration_minutes")
                    duration = row.get("duration")
                    service_duration_min = _minutes(duration_minutes) or _minutes(duration) or 60
            except Exception as e:
                logger.warning("duration_minutes not available, falling back to duration only: %s", e)
                cursor.execute(
                    fmt_query("SELECT duration FROM services WHERE id = ?"),
                    (service_id,),
                )
                row = cursor.fetchone()
                if row:
                    # RealDictCursor returns dict; SQLite row is indexable by key or position.
                    duration = row.get("duration") if isinstance(row, dict) else row[0]
                    service_duration_min = _minutes(duration) or 60

        # Load business hours (same data as Settings / per-day hours; table may be missing before migrations)
        business_hours: Dict[int, Dict[str, Any]] = {}
        try:
            cursor.execute(
                fmt_query(
                    """
                    SELECT day_of_week, opening_time, closing_time, is_closed
                    FROM business_hours
                """
                )
            )
            bh_rows = cursor.fetchall()
            for r in bh_rows:
                dow = _day_of_week_int(r.get("day_of_week"))
                business_hours[dow] = {
                    "opening_time": r.get("opening_time"),
                    "closing_time": r.get("closing_time"),
                    "is_closed": r.get("is_closed"),
                }
        except Exception as e:
            logger.warning("business_hours table missing or error, using default Mon-Fri 08:00-18:00: %s", e)
        # If no business_hours rows (e.g. fresh DB), use default Mon-Fri 8-6 so slots still show
        bh_empty = not business_hours
        if not business_hours:
            for dow in range(7):
                if dow < 5:  # Mon-Fri
                    business_hours[dow] = {"opening_time": "08:00", "closing_time": "18:00", "is_closed": 0}
                else:
                    business_hours[dow] = {"opening_time": None, "closing_time": None, "is_closed": 1}
            logger.info("business_hours empty; using default Mon-Fri 08:00-18:00")
        # #region agent log
        _ivr_debug({"location": "engine.py:compute_availability:bh", "message": "business_hours state", "data": {"bh_empty": bh_empty, "using_default_bh": bh_empty, "day_of_week_for_date": start_day.weekday()}, "hypothesisId": "H2"})
        # #endregion

        # Load staff schedules from same table as Admin > Staff & Schedule > Schedules (Save Schedule).
        # If table missing or error, use empty schedules so we fall back to business_hours-only slots.
        schedule_rows: List[Dict[str, Any]] = []
        try:
            if technician_id:
                cursor.execute(
                    fmt_query(
                        """
                        SELECT staff_id, day_of_week, start_time, end_time, is_off
                        FROM staff_schedules
                        WHERE staff_id = ?
                    """
                    ),
                    (technician_id,),
                )
            else:
                cursor.execute(
                    fmt_query(
                        """
                        SELECT staff_id, day_of_week, start_time, end_time, is_off
                        FROM staff_schedules
                    """
                    )
                )
            schedule_rows = cursor.fetchall() or []
        except Exception as e:
            logger.warning("staff_schedules table missing or error, using business_hours-only slots: %s", e)

        schedules: Dict[int, List[Dict[str, Any]]] = {}
        for r in schedule_rows:
            dow = _day_of_week_int(r.get("day_of_week"))
            schedules.setdefault(dow, []).append(
                {
                    "staff_id": r.get("staff_id"),
                    "start_time": r.get("start_time"),
                    "end_time": r.get("end_time"),
                    "is_off": r.get("is_off"),
                }
            )

        # Load existing appointments overlapping horizon.
        # Prefer new start_time/end_time fields, but gracefully fall back to appointment_time
        # for legacy schemas.
        try:
            cursor.execute(
                fmt_query(
                    """
                    SELECT id, technician_id, start_time, end_time
                    FROM appointments
                    WHERE start_time IS NOT NULL
                """
                )
            )
            appt_rows = cursor.fetchall()
            use_legacy_appointments = False
        except Exception as e:
            logger.warning("start_time/end_time not available, falling back to appointment_time: %s", e)
            cursor.execute(
                fmt_query(
                    """
                    SELECT id, assigned_staff_id AS technician_id, appointment_time
                    FROM appointments
                    WHERE appointment_time IS NOT NULL
                """
                )
            )
            appt_rows = cursor.fetchall()
            use_legacy_appointments = True

        existing: List[TimeSlot] = []
        for r in appt_rows:
            try:
                if use_legacy_appointments:
                    start_raw = r["appointment_time"]
                    end_raw = r["appointment_time"]
                else:
                    start_raw = r["start_time"]
                    end_raw = r["end_time"] or r["start_time"]

                s = _parse_time(start_raw)
                e = _parse_time(end_raw)
                existing.append(
                    TimeSlot(
                        start=s,
                        end=e,
                        technician_id=r.get("technician_id"),
                        service_id=None,
                        source="existing",
                    )
                )
            except Exception:
                continue

        # Load blackouts (if table exists; otherwise treat as none).
        blackout_rows = []
        try:
            cursor.execute(
                fmt_query(
                    """
                    SELECT start_time, end_time, scope, technician_id
                    FROM blackouts
                """
                )
            )
            blackout_rows = cursor.fetchall()
        except Exception as e:
            logger.warning("blackouts table not available, continuing without blackouts: %s", e)
        blackouts: List[TimeSlot] = []
        for r in blackout_rows:
            try:
                s = _parse_time(r["start_time"])
                e = _parse_time(r["end_time"])
                blackouts.append(
                    TimeSlot(
                        start=s,
                        end=e,
                        technician_id=r["technician_id"],
                        service_id=None,
                        source=f"blackout:{r['scope']}",
                    )
                )
            except Exception:
                continue

        slots: List[TimeSlot] = []

        # Default for a day missing from business_hours (e.g. Sunday not in DB) so IVR/web still get slots
        _default_day = {"opening_time": "08:00", "closing_time": "18:00", "is_closed": 0}

        day = start_day
        while day < end_day:
            dow = day.weekday()
            bh = business_hours.get(dow)
            if bh is None and business_hours:
                bh = _default_day
            if not bh or _is_day_closed(bh.get("is_closed")):
                day = day + timedelta(days=1)
                continue

            open_str = _time_to_str(bh.get("opening_time"))
            close_str = _end_time_for_day(bh.get("closing_time"))
            if not open_str or not close_str:
                day = day + timedelta(days=1)
                continue

            try:
                open_dt = _parse_time(f"{day.isoformat()} {open_str}")
                close_dt = _parse_time(f"{day.isoformat()} {close_str}")
            except Exception:
                day = day + timedelta(days=1)
                continue

            technicians_for_day = schedules.get(dow, [])
            if technician_id:
                technicians_for_day = [s for s in technicians_for_day if s["staff_id"] == technician_id]

            slots_before = len(slots)
            # If no staff schedules for this day, fall back to business-hours-only slots
            # so Kiosk and appointment forms show times when the shop is open.
            if not technicians_for_day:
                window_start = open_dt
                window_end = close_dt
                cursor_time = window_start
                while cursor_time + timedelta(minutes=service_duration_min) <= window_end:
                    candidate_end = cursor_time + timedelta(minutes=service_duration_min)
                    candidate = TimeSlot(
                        start=cursor_time,
                        end=candidate_end,
                        technician_id=None,
                        service_id=service_id,
                    )
                    if not _has_conflict(candidate, existing, blackouts):
                        slots.append(candidate)
                    cursor_time = cursor_time + timedelta(minutes=15)
            else:
                for sched in technicians_for_day:
                    if _is_day_closed(sched.get("is_off")):
                        continue

                    try:
                        tech_start = _parse_time(f"{day.isoformat()} {_time_to_str(sched.get('start_time'))}")
                        tech_end = _parse_time(f"{day.isoformat()} {_end_time_for_day(sched.get('end_time'))}")
                    except Exception:
                        continue

                    window_start = max(open_dt, tech_start)
                    window_end = min(close_dt, tech_end)
                    if window_end <= window_start:
                        continue
                    cursor_time = window_start

                    while cursor_time + timedelta(minutes=service_duration_min) <= window_end:
                        candidate_end = cursor_time + timedelta(minutes=service_duration_min)
                        candidate = TimeSlot(
                            start=cursor_time,
                            end=candidate_end,
                            technician_id=sched["staff_id"],
                            service_id=service_id,
                        )
                        if not _has_conflict(candidate, existing, blackouts):
                            slots.append(candidate)
                        cursor_time = cursor_time + timedelta(minutes=15)

            # If shop is open but we added no slots (e.g. all staff off or parse errors), use business-hours-only
            if len(slots) == slots_before and (open_dt is not None and close_dt is not None):
                cursor_time = open_dt
                while cursor_time + timedelta(minutes=service_duration_min) <= close_dt:
                    candidate_end = cursor_time + timedelta(minutes=service_duration_min)
                    candidate = TimeSlot(
                        start=cursor_time,
                        end=candidate_end,
                        technician_id=None,
                        service_id=service_id,
                    )
                    if not _has_conflict(candidate, existing, blackouts):
                        slots.append(candidate)
                    cursor_time = cursor_time + timedelta(minutes=15)

            day = day + timedelta(days=1)

        # #region agent log
        _ivr_debug({"location": "engine.py:compute_availability:return", "message": "slots computed", "data": {"slots_count": len(slots)}, "hypothesisId": "H3"})
        # #endregion
        if len(slots) == 0:
            logger.info(
                "compute_availability: 0 slots for date=%s service_id=%s (check business_hours and staff_schedules for that day)",
                date.strftime("%Y-%m-%d"),
                service_id,
            )
        return slots
    except Exception as e:
        logger.exception("compute_availability failed: %s", e)
        # #region agent log
        _ivr_debug({"location": "engine.py:compute_availability:exception", "message": "compute_availability exception", "data": {"error": str(e)}, "hypothesisId": "H3"})
        # #endregion
        # Fail closed (no slots) rather than 500 to callers like kiosk/IVR.
        return []
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _overlaps(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    return not (a_end <= b_start or b_end <= a_start)


def _has_conflict(slot: TimeSlot, existing: List[TimeSlot], blackouts: List[TimeSlot]) -> bool:
    """Check if proposed slot overlaps any appointment or blackout."""
    for appt in existing:
        if appt.technician_id and slot.technician_id and appt.technician_id != slot.technician_id:
            continue
        if _overlaps(slot.start, slot.end, appt.start, appt.end):
            return True

    for bo in blackouts:
        # Technician-scoped blackout
        if bo.technician_id:
            if slot.technician_id and bo.technician_id != slot.technician_id:
                continue
        if _overlaps(slot.start, slot.end, bo.start, bo.end):
            return True

    return False


def check_conflicts(candidate: TimeSlot) -> bool:
    """
    Public helper to check if a candidate slot is free.
    Returns True if there IS a conflict, False if safe.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Mirror the same legacy-safe logic used in compute_availability.
    try:
        cursor.execute(
            fmt_query(
                """
                SELECT technician_id, start_time, end_time
                FROM appointments
                WHERE start_time IS NOT NULL
            """
            )
        )
        appt_rows = cursor.fetchall()
        use_legacy_appointments = False
    except Exception as e:
        logger.warning("check_conflicts falling back to appointment_time: %s", e)
        cursor.execute(
            fmt_query(
                """
                SELECT assigned_staff_id AS technician_id, appointment_time
                FROM appointments
                WHERE appointment_time IS NOT NULL
            """
            )
        )
        appt_rows = cursor.fetchall()
        use_legacy_appointments = True
    existing: List[TimeSlot] = []
    for r in appt_rows:
        try:
            if use_legacy_appointments:
                start_raw = r["appointment_time"]
                end_raw = r["appointment_time"]
            else:
                start_raw = r["start_time"]
                end_raw = r["end_time"] or r["start_time"]

            s = _parse_time(start_raw)
            e = _parse_time(end_raw)
            existing.append(
                TimeSlot(
                    start=s,
                    end=e,
                    technician_id=r.get("technician_id"),
                    service_id=None,
                    source="existing",
                )
            )
        except Exception:
            continue

    # Blackouts: tolerate missing table.
    blackout_rows = []
    try:
        cursor.execute(
            fmt_query(
                """
                SELECT start_time, end_time, scope, technician_id
                FROM blackouts
            """
            )
        )
        blackout_rows = cursor.fetchall()
    except Exception as e:
        logger.warning("check_conflicts: blackouts table not available, skipping: %s", e)
    blackouts: List[TimeSlot] = []
    for r in blackout_rows:
        try:
            s = _parse_time(r["start_time"])
            e = _parse_time(r["end_time"])
            blackouts.append(
                TimeSlot(
                    start=s,
                    end=e,
                    technician_id=r["technician_id"],
                    service_id=None,
                    source=f"blackout:{r['scope']}",
                )
            )
        except Exception:
            continue

    conn.close()
    return _has_conflict(candidate, existing, blackouts)

