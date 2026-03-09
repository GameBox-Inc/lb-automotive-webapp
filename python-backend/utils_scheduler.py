from datetime import datetime, timedelta, time
from typing import Optional
from database import get_db_connection, fmt_query
import os

def get_business_hours_for_day(day_of_week: int) -> tuple[Optional[time], Optional[time], bool]:
    """
    Get business hours for a specific day of week from database.
    
    Args:
        day_of_week: 0=Monday, 6=Sunday
    
    Returns:
        Tuple of (opening_time, closing_time, is_closed)
        Returns (None, None, True) if day is closed or not configured
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(fmt_query("""
        SELECT opening_time, closing_time, is_closed
        FROM business_hours
        WHERE day_of_week = ?
    """), (day_of_week,))
    
    row = cursor.fetchone()
    conn.close()
    
    if not row or row["is_closed"]:
        return (None, None, True)
    
    if not row["opening_time"] or not row["closing_time"]:
        return (None, None, True)
    
    try:
        open_time = datetime.strptime(row["opening_time"], "%H:%M").time()
        close_time = datetime.strptime(row["closing_time"], "%H:%M").time()
        return (open_time, close_time, False)
    except (ValueError, TypeError):
        return (None, None, True)


def get_available_slots_logic(date_str: str, service_id: str):
    """
    Core logic to calculate available 15-minute slots.
    Returns a list of 'HH:MM' strings.
    """
    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return []

    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Get Service Duration
    cursor.execute(fmt_query("SELECT duration FROM services WHERE id = ?"), (service_id,))
    service_row = cursor.fetchone()
    if not service_row:
        conn.close()
        return []
    duration_minutes = service_row["duration"]

    # 2. Check business hours for this day
    day_of_week = target_date.weekday()
    open_time, close_time, is_closed = get_business_hours_for_day(day_of_week)
    
    if is_closed or not open_time or not close_time:
        conn.close()
        return []  # Business is closed on this day
    
    cursor.execute(fmt_query("""
        SELECT s.id as staff_id, s.name, ss.start_time, ss.end_time 
        FROM staff s
        JOIN staff_schedules ss ON s.id = ss.staff_id
        WHERE s.active = 1 AND ss.day_of_week = ? AND ss.is_off = 0
    """), (day_of_week,))
    
    staff_schedules = cursor.fetchall()
    
    if not staff_schedules:
        conn.close()
        return []

    # 3. Get existing appointments
    date_fn = "DATE" if os.getenv("DATABASE_URL", "").startswith("postgres") else "date"
    cursor.execute(fmt_query(f"""
        SELECT a.appointment_time, a.service_type, a.duration 
        FROM appointments a
        LEFT JOIN services s ON a.service_type = s.id OR a.service_type = s.name
        WHERE {date_fn}(a.appointment_time) = ? AND a.status != 'cancelled'
    """), (date_str,))
    
    existing_appointments = cursor.fetchall()
    conn.close()

    # 4. Generate candidate slots
    def parse_time(t_str):
        h, m = map(int, t_str.split(':'))
        return h, m

    global_start_min = 24 * 60
    global_end_min = 0

    for schedule in staff_schedules:
        sh, sm = parse_time(schedule["start_time"])
        eh, em = parse_time(schedule["end_time"])
        global_start_min = min(global_start_min, sh * 60 + sm)
        global_end_min = max(global_end_min, eh * 60 + em)

    # Use business hours to constrain slot generation
    # Ensure slots are within business hours, not just staff schedules
    business_start = datetime.combine(target_date, open_time)
    business_end = datetime.combine(target_date, close_time)
    
    # Constrain to business hours
    slot_start_time = max(
        datetime.combine(target_date, datetime.min.time()) + timedelta(minutes=global_start_min),
        business_start
    )
    slot_end_time = min(
        datetime.combine(target_date, datetime.min.time()) + timedelta(minutes=global_end_min),
        business_end
    )
    
    available_slots = []
    current_time = slot_start_time
    interval = timedelta(minutes=15)

    while current_time + timedelta(minutes=duration_minutes) <= slot_end_time:
        slot_start = current_time
        slot_end = current_time + timedelta(minutes=duration_minutes)
        
        # Conflict check
        conflicts = 0
        for appt in existing_appointments:
            try:
                appt_start = datetime.fromisoformat(appt["appointment_time"])
            except ValueError:
                continue
            
            appt_end = appt_start + timedelta(minutes=appt["duration"])
            
            # Allow abutment (start == end) but not overlap
            if slot_start < appt_end and slot_end > appt_start:
                conflicts += 1
        
        # Staff coverage check
        staff_coverage = 0
        for s in staff_schedules:
            sh, sm = parse_time(s["start_time"])
            eh, em = parse_time(s["end_time"])
            ss = datetime.combine(target_date, datetime.min.time().replace(hour=sh, minute=sm))
            se = datetime.combine(target_date, datetime.min.time().replace(hour=eh, minute=em))
            
            if slot_start >= ss and slot_end <= se:
                staff_coverage += 1
        
        if conflicts < staff_coverage:
            available_slots.append(slot_start.strftime("%H:%M"))
            
        current_time += interval

    return available_slots
