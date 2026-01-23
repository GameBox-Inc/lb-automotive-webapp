"""
Scheduler module for managing appointment time slots.
Generates available slots in 15-minute increments.
"""
import sqlite3
from datetime import datetime, timedelta, time
from typing import List, Dict, Optional
from database import get_db_connection
import logging

logger = logging.getLogger(__name__)

# Business hours configuration
BUSINESS_HOURS_START = time(8, 0)  # 8:00 AM
BUSINESS_HOURS_END = time(18, 0)   # 6:00 PM
SLOT_INCREMENT_MINUTES = 15


def get_available_slots_15min(
    service_id: str,
    target_date: str,
    limit: int = 20
) -> List[Dict[str, str]]:
    """
    Get available time slots in 15-minute increments for a given date and service.
    
    Args:
        service_id: The ID of the service to book
        target_date: Date in 'YYYY-MM-DD' format
        limit: Maximum number of slots to return (default: 20)
    
    Returns:
        List of slot dictionaries with 'time', '24h', and 'timestamp' keys
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get service duration
    cursor.execute("SELECT duration FROM services WHERE id = ?", (service_id,))
    service_row = cursor.fetchone()
    if not service_row:
        conn.close()
        return []
    
    service_duration = service_row["duration"]  # in minutes
    
    # Get all staff schedules for the target day
    target_datetime = datetime.strptime(target_date, "%Y-%m-%d")
    day_of_week = target_datetime.strftime("%A")
    
    cursor.execute("""
        SELECT staff_id FROM staff_schedules 
        WHERE day_of_week = ? AND is_off = 0
    """, (day_of_week,))
    available_staff_ids = [row["staff_id"] for row in cursor.fetchall()]
    
    if not available_staff_ids:
        logger.warning(f"No staff available on {day_of_week}")
        conn.close()
        return []
    
    # Get existing appointments for that date
    cursor.execute("""
        SELECT appointment_time, service_type, assigned_staff_id
        FROM appointments
        WHERE date(appointment_time) = ?
    """, (target_date,))
    existing_appointments = cursor.fetchall()
    conn.close()
    
    # Build a map of occupied time ranges per staff member
    occupied_ranges = {}
    for apt in existing_appointments:
        staff_id = apt["assigned_staff_id"]
        if staff_id not in occupied_ranges:
            occupied_ranges[staff_id] = []
        
        apt_time = datetime.fromisoformat(apt["appointment_time"])
        # Assume 30-minute default if duration not stored
        apt_end = apt_time + timedelta(minutes=30)
        occupied_ranges[staff_id].append((apt_time, apt_end))
    
    # Generate slots
    slots = []
    current_dt = datetime.combine(target_datetime.date(), BUSINESS_HOURS_START)
    end_dt = datetime.combine(target_datetime.date(), BUSINESS_HOURS_END)
    
    while current_dt < end_dt and len(slots) < limit:
        slot_end = current_dt + timedelta(minutes=service_duration)
        
        # Check if slot end extends beyond business hours
        if slot_end.time() > BUSINESS_HOURS_END:
            break
        
        # Check if ANY staff member is available for this slot
        slot_available = False
        for staff_id in available_staff_ids:
            # Check if this slot conflicts with existing appointments for this staff
            conflicts = False
            for occupied_start, occupied_end in occupied_ranges.get(staff_id, []):
                # Check for overlap
                if not (slot_end <= occupied_start or current_dt >= occupied_end):
                    conflicts = True
                    break
            
            if not conflicts:
                slot_available = True
                break  # Found at least one available staff member
        
        if slot_available:
            slots.append({
                "time": current_dt.strftime("%I:%M %p").lstrip("0"),  # "9:00 AM"
                "24h": current_dt.strftime("%H:%M"),  # "09:00"
                "timestamp": current_dt.isoformat(),  # Full ISO timestamp
                "display": current_dt.strftime("%I:%M %p").lstrip("0")
            })
        
        # Move to next slot
        current_dt += timedelta(minutes=SLOT_INCREMENT_MINUTES)
    
    return slots


def group_adjacent_slots(slots: List[Dict[str, str]], max_groups: int = 5) -> List[Dict[str, str]]:
    """
    Group adjacent time slots for more concise presentation.
    
    Args:
        slots: List of slot dictionaries
        max_groups: Maximum number of groups to return
    
    Returns:
        List of grouped slots with 'display' and 'slots' keys
    """
    if not slots:
        return []
    
    groups = []
    current_group_start = slots[0]
    current_group_slots = [slots[0]]
    
    for i in range(1, len(slots)):
        prev_slot = slots[i - 1]
        curr_slot = slots[i]
        
        # Parse timestamps to check if they're adjacent
        prev_time = datetime.fromisoformat(prev_slot["timestamp"])
        curr_time = datetime.fromisoformat(curr_slot["timestamp"])
        
        # If slots are 15 minutes apart, add to current group
        if (curr_time - prev_time).total_seconds() / 60 == SLOT_INCREMENT_MINUTES:
            current_group_slots.append(curr_slot)
        else:
            # Save current group and start a new one
            if len(current_group_slots) > 3:
                # Group has multiple slots
                display = f"{current_group_start['time']} to {current_group_slots[-1]['time']}"
            else:
                # Small group, just list the times
                display = current_group_start['time']
            
            groups.append({
                "display": display,
                "slots": current_group_slots,
                "first_slot": current_group_start
            })
            
            current_group_start = curr_slot
            current_group_slots = [curr_slot]
            
            if len(groups) >= max_groups:
                break
    
    # Add the last group
    if current_group_slots and len(groups) < max_groups:
        if len(current_group_slots) > 3:
            display = f"{current_group_start['time']} to {current_group_slots[-1]['time']}"
        else:
            display = current_group_start['time']
        
        groups.append({
            "display": display,
            "slots": current_group_slots,
            "first_slot": current_group_start
        })
    
    return groups


def is_slot_available(slot_time: datetime, service_id: str, target_date: str) -> bool:
    """
    Check if a specific slot is available.
    
    Args:
        slot_time: The datetime for the slot
        service_id: The service ID
        target_date: Date in 'YYYY-MM-DD' format
    
    Returns:
        True if slot is available, False otherwise
    """
    slots = get_available_slots_15min(service_id, target_date, limit=100)
    slot_timestamp = slot_time.isoformat()
    
    for slot in slots:
        if slot["timestamp"] == slot_timestamp:
            return True
    
    return False
