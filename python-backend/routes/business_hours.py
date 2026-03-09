from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from database import get_db_connection, fmt_query
from auth import get_current_active_user
from models import BusinessHours, BusinessHoursUpdate
from security import sanitize_input
import logging

router = APIRouter(prefix="/api/business-hours", tags=["business-hours"])
logger = logging.getLogger(__name__)

# Day names mapping
DAY_NAMES = {
    0: "Monday",
    1: "Tuesday",
    2: "Wednesday",
    3: "Thursday",
    4: "Friday",
    5: "Saturday",
    6: "Sunday"
}


@router.get("", response_model=List[BusinessHours])
def get_business_hours(current_user: dict = Depends(get_current_active_user)):
    """Get all business hours (one per day of week)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(fmt_query("""
        SELECT day_of_week, opening_time, closing_time, is_closed, updated_at, updated_by
        FROM business_hours
        ORDER BY day_of_week
    """))
    rows = cursor.fetchall()
    conn.close()
    
    business_hours = []
    for row in rows:
        business_hours.append(BusinessHours(
            day_of_week=row["day_of_week"],
            day_name=DAY_NAMES.get(row["day_of_week"], f"Day {row['day_of_week']}"),
            opening_time=row["opening_time"],
            closing_time=row["closing_time"],
            is_closed=bool(row["is_closed"]),
            updated_at=row["updated_at"],
            updated_by=row["updated_by"]
        ))
    
    return business_hours


@router.put("/{day_of_week}", response_model=BusinessHours)
def update_business_hours(
    day_of_week: int,
    hours_update: BusinessHoursUpdate,
    current_user: dict = Depends(get_current_active_user)
):
    """Update business hours for a specific day (Admin only)."""
    if not current_user.get("is_admin"):
        logger.warning(f"Unauthorized business hours update attempt by {current_user.get('username')}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update business hours"
        )
    
    if day_of_week < 0 or day_of_week > 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="day_of_week must be between 0 (Monday) and 6 (Sunday)"
        )
    
    # Validate times if not closed
    if not hours_update.is_closed:
        if not hours_update.opening_time or not hours_update.closing_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="opening_time and closing_time are required when is_closed is False"
            )
        
        # Validate time format (HH:MM)
        try:
            from datetime import datetime
            datetime.strptime(hours_update.opening_time, "%H:%M")
            datetime.strptime(hours_update.closing_time, "%H:%M")
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Times must be in HH:MM format (e.g., '08:00', '18:00')"
            )
    
    # Sanitize inputs
    opening_time = sanitize_input(hours_update.opening_time, "text") if hours_update.opening_time else None
    closing_time = sanitize_input(hours_update.closing_time, "text") if hours_update.closing_time else None
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if record exists
    cursor.execute(fmt_query("SELECT * FROM business_hours WHERE day_of_week = ?"), (day_of_week,))
    if not cursor.fetchone():
        # Create if doesn't exist
        cursor.execute(fmt_query("""
            INSERT INTO business_hours (day_of_week, opening_time, closing_time, is_closed, updated_by)
            VALUES (?, ?, ?, ?, ?)
        """), (day_of_week, opening_time, closing_time, int(hours_update.is_closed), current_user["username"]))
    else:
        # Update existing
        cursor.execute(fmt_query("""
            UPDATE business_hours 
            SET opening_time = ?, closing_time = ?, is_closed = ?, 
                updated_at = CURRENT_TIMESTAMP, updated_by = ?
            WHERE day_of_week = ?
        """), (opening_time, closing_time, int(hours_update.is_closed), current_user["username"], day_of_week))
    
    conn.commit()
    
    # Fetch updated
    cursor.execute(fmt_query("SELECT * FROM business_hours WHERE day_of_week = ?"), (day_of_week,))
    row = cursor.fetchone()
    conn.close()
    
    logger.info(f"Business hours for {DAY_NAMES.get(day_of_week)} updated by {current_user['username']}")
    
    return BusinessHours(
        day_of_week=row["day_of_week"],
        day_name=DAY_NAMES.get(row["day_of_week"], f"Day {row['day_of_week']}"),
        opening_time=row["opening_time"],
        closing_time=row["closing_time"],
        is_closed=bool(row["is_closed"]),
        updated_at=row["updated_at"],
        updated_by=row["updated_by"]
    )


@router.get("/day/{day_of_week}", response_model=BusinessHours)
def get_business_hours_for_day(day_of_week: int):
    """Get business hours for a specific day (public endpoint for IVR/scheduling)."""
    if day_of_week < 0 or day_of_week > 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="day_of_week must be between 0 (Monday) and 6 (Sunday)"
        )
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(fmt_query("""
        SELECT day_of_week, opening_time, closing_time, is_closed, updated_at, updated_by
        FROM business_hours
        WHERE day_of_week = ?
    """), (day_of_week,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        # Return default if not configured
        return BusinessHours(
            day_of_week=day_of_week,
            day_name=DAY_NAMES.get(day_of_week, f"Day {day_of_week}"),
            opening_time="08:00",
            closing_time="18:00",
            is_closed=False
        )
    
    return BusinessHours(
        day_of_week=row["day_of_week"],
        day_name=DAY_NAMES.get(row["day_of_week"], f"Day {row['day_of_week']}"),
        opening_time=row["opening_time"],
        closing_time=row["closing_time"],
        is_closed=bool(row["is_closed"]),
        updated_at=row["updated_at"],
        updated_by=row["updated_by"]
    )
