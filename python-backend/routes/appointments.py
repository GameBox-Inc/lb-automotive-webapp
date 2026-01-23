import uuid
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from models import Appointment, AppointmentCreate, AppointmentUpdate
from auth import get_current_active_user, get_optional_user
from database import get_db_connection, current_user_context
from security import sanitize_input, validate_appointment_data
import traceback

router = APIRouter(prefix="/api/appointments", tags=["appointments"])


@router.get("", response_model=List[Appointment])
def list_appointments(
    status_filter: Optional[str] = None,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user)
):
    """List all appointments with optional status filter and proper RLS."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Update query to join services and cases
    query = """
        SELECT a.*, s.name as service_name_joined, c.started_at
        FROM appointments a 
        LEFT JOIN services s ON a.service_type = s.id
        LEFT JOIN cases c ON a.id = c.appointment_id
    """
    
    params = []
    conditions = []
    
    # Apply RLS based on user type
    if current_user:
        if current_user.get("is_admin"):
            # Admins see all appointments
            pass
        elif current_user.get("staff_id"):
            # Staff members see appointments assigned to them OR unassigned appointments
            conditions.append("(a.assigned_staff_id = ? OR a.assigned_staff_id IS NULL)")
            params.append(current_user["staff_id"])
        else:
            # Regular customers see only their own appointments
            conditions.append("(a.user_id = ? OR a.phone_number = ?)")
            params.extend([current_user["id"], current_user.get("phone_number", "")])
    
    # Add status filter if provided
    if status_filter:
        conditions.append("a.status = ?")
        params.append(status_filter)
    
    # Build final query
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    
    query += " ORDER BY a.appointment_time ASC"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    appointments = []
    for row in rows:
        # If we joined a service name, use it. Otherwise fall back to the raw column value (legacy text)
        service_display = row["service_name_joined"] if row["service_name_joined"] else row["service_type"]
        
        appointments.append(Appointment(
            id=row["id"],
            customer_name=row["customer_name"],
            phone_number=row["phone_number"],
            appointment_time=row["appointment_time"],
            service_type=service_display,
            notes=row["notes"],
            status=row["status"],
            emergency_request=bool(row["emergency_request"]),
            assigned_staff_id=row["assigned_staff_id"] if "assigned_staff_id" in row.keys() else None,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            started_at=row["started_at"] if "started_at" in row.keys() else None
        ))
    
    return appointments


@router.get("/available-slots")
def get_available_slots(
    date: str,
    service_id: str,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user)
):
    """
    Get available appointment slots for a given date and service.
    Availability is determined by:
    1. Staff schedules (StaffSchedule table)
    2. Existing appointments (Appointments table)
    3. Service duration
    """
    from datetime import datetime, timedelta, date as d_date
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    # 1. Get Service Duration
    cursor.execute("SELECT duration FROM services WHERE id = ?", (service_id,))
    service_row = cursor.fetchone()
    if not service_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Service not found")
    duration_minutes = service_row["duration"]

    # 2. Get Staff Working on this day
    # day_of_week: 0=Monday, 6=Sunday
    day_of_week = target_date.weekday()
    
    cursor.execute("""
        SELECT s.id as staff_id, s.name, ss.start_time, ss.end_time 
        FROM staff s
        JOIN staff_schedules ss ON s.id = ss.staff_id
        WHERE s.active = 1 AND ss.day_of_week = ? AND ss.is_off = 0
    """, (day_of_week,))
    
    staff_schedules = cursor.fetchall()
    
    if not staff_schedules:
        # No staff working today
        conn.close()
        return []

    # 3. Get existing appointments for this date
    # We fetch all appointments that overlap with the day
    cursor.execute("""
        SELECT appointment_time, service_type, duration 
        FROM appointments a
        JOIN services s ON a.service_type = s.id
        WHERE date(appointment_time) = ? AND status != 'cancelled'
    """, (date,))
    
    existing_appointments = cursor.fetchall()
    conn.close()

    # 4. Generate candidate slots
    # We'll use a set of 15-minute intervals for start times
    # Range is determined by the earilest start and latest end of all staff
    
    available_slots = []
    
    def parse_time(t_str):
        h, m = map(int, t_str.split(':'))
        return h, m

    # Find global start and end time for the shop on this day
    global_start_min = 24 * 60
    global_end_min = 0

    for schedule in staff_schedules:
        sh, sm = parse_time(schedule["start_time"])
        eh, em = parse_time(schedule["end_time"])
        global_start_min = min(global_start_min, sh * 60 + sm)
        global_end_min = max(global_end_min, eh * 60 + em)

    # Generate slots logic
    # Iterate from global_start to global_end - duration in 15 min steps
    current_min = global_start_min
    interval = timedelta(minutes=15)
    
    start_time_obj = datetime.combine(target_date, datetime.min.time())
    
    current_time = start_time_obj + timedelta(minutes=global_start_min)
    end_time = start_time_obj + timedelta(minutes=global_end_min)

    while current_time + timedelta(minutes=duration_minutes) <= end_time:
        slot_start = current_time
        slot_end = current_time + timedelta(minutes=duration_minutes)
        
        # Check if slot is viable
        # A slot is viable if at least ONE staff member is working AND free
        
        # Simplification: We check if total concurrent appointments < total staff working at this time
        # This assumes any staff can do any service (which is true for now)
        
        # Count overlapping appointments
        conflicts = 0
        for appt in existing_appointments:
            try:
                appt_start = datetime.fromisoformat(appt["appointment_time"])
            except ValueError:
                continue 
                
            appt_end = appt_start + timedelta(minutes=appt["duration"])
            
            if slot_start < appt_end and slot_end > appt_start:
                conflicts += 1
        
        # Count staff working covering this FULL slot
        staff_working_count = 0
        for s in staff_schedules:
            sh, sm = parse_time(s["start_time"])
            eh, em = parse_time(s["end_time"])
            ss = datetime.combine(target_date, datetime.min.time().replace(hour=sh, minute=sm))
            se = datetime.combine(target_date, datetime.min.time().replace(hour=eh, minute=em))
            if slot_start >= ss and slot_end <= se:
                staff_working_count += 1
        
        if conflicts < staff_working_count:
            available_slots.append(slot_start.strftime("%H:%M"))
            
        current_time += interval

    return available_slots


@router.get("/{appointment_id}", response_model=Appointment)
def get_appointment(
    appointment_id: str,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user)
):
    """Get a specific appointment by ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT a.*, s.name as service_name_joined
        FROM appointments a
        LEFT JOIN services s ON a.service_type = s.id
        WHERE a.id = ?
    """, (appointment_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="Appointment not found")
    
    # Check RLS
    if current_user and not current_user.get("is_admin"):
        if row["user_id"] != current_user["id"] and row["phone_number"] != current_user.get("phone_number", ""):
            raise HTTPException(status_code=403, detail="Not authorized to view this appointment")
            
    service_display = row["service_name_joined"] if row["service_name_joined"] else row["service_type"]
    
    return Appointment(
        id=row["id"],
        customer_name=row["customer_name"],
        phone_number=row["phone_number"],
        appointment_time=row["appointment_time"],
        service_type=service_display,
        notes=row["notes"],
        status=row["status"],
        emergency_request=bool(row["emergency_request"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"]
    )


@router.post("", response_model=Appointment, status_code=status.HTTP_201_CREATED)
def create_appointment(
    appointment: AppointmentCreate,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user)
):
    """Create a new appointment."""
    try:
        # Validate and sanitize input
        appointment_data = validate_appointment_data(appointment.dict())
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        appointment_id = str(uuid.uuid4())
        user_id = current_user["id"] if current_user else None
        
        cursor.execute("""
            INSERT INTO appointments (
                id, customer_name, phone_number, appointment_time,
                service_type, notes, emergency_request, user_id, assigned_staff_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            appointment_id,
            appointment_data["customer_name"],
            appointment_data["phone_number"],
            appointment.appointment_time.isoformat(),
            appointment_data["service_type"],
            appointment_data.get("notes"),
            int(appointment.emergency_request),
            user_id,
            None
        ))
        
        conn.commit()
        
        # Fetch the created appointment (with service name join)
        cursor.execute("""
            SELECT a.*, s.name as service_name_joined 
            FROM appointments a 
            LEFT JOIN services s ON a.service_type = s.id 
            WHERE a.id = ?
        """, (appointment_id,))
        row = cursor.fetchone()
        conn.close()
        
        service_display = row["service_name_joined"] if row["service_name_joined"] else row["service_type"]
        
        return Appointment(
            id=row["id"],
            customer_name=row["customer_name"],
            phone_number=row["phone_number"],
            appointment_time=row["appointment_time"],
            service_type=service_display,
            notes=row["notes"],
            status=row["status"],
            emergency_request=bool(row["emergency_request"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"]
        )
    except Exception as e:
        print(f"Error creating appointment: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to create appointment: {str(e)}")


@router.put("/{appointment_id}", response_model=Appointment)
def update_appointment(
    appointment_id: str,
    appointment_update: AppointmentUpdate,
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Update an existing appointment."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if appointment exists
    cursor.execute("SELECT * FROM appointments WHERE id = ?", (appointment_id,))
    existing = cursor.fetchone()
    
    if not existing:
        conn.close()
        raise HTTPException(status_code=404, detail="Appointment not found")
    
    # Check RLS
    if not current_user.get("is_admin"):
        is_owner = existing["user_id"] == current_user["id"]
        # Check if user is staff and assigned to this appointment
        is_assigned_staff = False
        if current_user.get("staff_id"):
             # If staff_id is present in user profile
             is_assigned_staff = existing["assigned_staff_id"] == current_user["staff_id"]
        
        if not (is_owner or is_assigned_staff):
            conn.close()
            raise HTTPException(status_code=403, detail="Not authorized to update this appointment")
    
    # Build update query
    update_fields = []
    params = []
    
    if appointment_update.customer_name is not None:
        update_fields.append("customer_name = ?")
        params.append(appointment_update.customer_name)
    
    if appointment_update.phone_number is not None:
        update_fields.append("phone_number = ?")
        params.append(appointment_update.phone_number)
    
    if appointment_update.appointment_time is not None:
        update_fields.append("appointment_time = ?")
        params.append(appointment_update.appointment_time.isoformat())
    
    if appointment_update.service_type is not None:
        update_fields.append("service_type = ?")
        params.append(appointment_update.service_type)
    
    if appointment_update.notes is not None:
        update_fields.append("notes = ?")
        params.append(appointment_update.notes)
    
    if appointment_update.status is not None:
        update_fields.append("status = ?")
        params.append(appointment_update.status)
        
        # New Requirement: Track actual repair start time in cases table
        if appointment_update.status == 'in_progress':
            cursor.execute("""
                UPDATE cases 
                SET started_at = CURRENT_TIMESTAMP 
                WHERE appointment_id = ? AND started_at IS NULL
            """, (appointment_id,))
    
    if appointment_update.emergency_request is not None:
        update_fields.append("emergency_request = ?")
        params.append(int(appointment_update.emergency_request))
    
    update_fields.append("updated_at = CURRENT_TIMESTAMP")
    params.append(appointment_id)
    
    query = f"UPDATE appointments SET {', '.join(update_fields)} WHERE id = ?"
    cursor.execute(query, params)
    conn.commit()
    
    # Fetch updated appointment
    cursor.execute("""
        SELECT a.*, s.name as service_name_joined
        FROM appointments a
        LEFT JOIN services s ON a.service_type = s.id
        WHERE a.id = ?
    """, (appointment_id,))
    row = cursor.fetchone()
    conn.close()
    
    service_display = row["service_name_joined"] if row["service_name_joined"] else row["service_type"]
    
    return Appointment(
        id=row["id"],
        customer_name=row["customer_name"],
        phone_number=row["phone_number"],
        appointment_time=row["appointment_time"],
        service_type=service_display,
        notes=row["notes"],
        status=row["status"],
        emergency_request=bool(row["emergency_request"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"]
    )


@router.delete("/{appointment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_appointment(
    appointment_id: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Delete an appointment."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if appointment exists
    cursor.execute("SELECT * FROM appointments WHERE id = ?", (appointment_id,))
    existing = cursor.fetchone()
    
    if not existing:
        conn.close()
        raise HTTPException(status_code=404, detail="Appointment not found")
    
    # Check RLS
    if not current_user.get("is_admin"):
        if existing["user_id"] != current_user["id"]:
            conn.close()
            raise HTTPException(status_code=403, detail="Not authorized to delete this appointment")
    
    cursor.execute("DELETE FROM appointments WHERE id = ?", (appointment_id,))
    conn.commit()
    conn.close()
    
    return None
