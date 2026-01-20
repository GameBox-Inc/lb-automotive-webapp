from datetime import datetime, timedelta
from database import get_db_connection

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
    cursor.execute("SELECT duration FROM services WHERE id = ?", (service_id,))
    service_row = cursor.fetchone()
    if not service_row:
        conn.close()
        return []
    duration_minutes = service_row["duration"]

    # 2. Get Staff Working on this day
    day_of_week = target_date.weekday()
    
    cursor.execute("""
        SELECT s.id as staff_id, s.name, ss.start_time, ss.end_time 
        FROM staff s
        JOIN staff_schedules ss ON s.id = ss.staff_id
        WHERE s.active = 1 AND ss.day_of_week = ? AND ss.is_off = 0
    """, (day_of_week,))
    
    staff_schedules = cursor.fetchall()
    
    if not staff_schedules:
        conn.close()
        return []

    # 3. Get existing appointments
    cursor.execute("""
        SELECT appointment_time, service_type, duration 
        FROM appointments a
        JOIN services s ON a.service_type = s.id
        WHERE date(appointment_time) = ? AND status != 'cancelled'
    """, (date_str,))
    
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

    available_slots = []
    current_min = global_start_min
    start_time_obj = datetime.combine(target_date, datetime.min.time())
    
    current_time = start_time_obj + timedelta(minutes=global_start_min)
    end_time = start_time_obj + timedelta(minutes=global_end_min)
    
    interval = timedelta(minutes=15)

    while current_time + timedelta(minutes=duration_minutes) <= end_time:
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
