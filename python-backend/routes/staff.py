from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from database import get_db_connection
from models import StaffSchedule, StaffScheduleUpdate, StaffCreate, StaffUpdate
from auth import get_current_active_user
import uuid
from datetime import datetime

router = APIRouter(prefix="/api/staff", tags=["staff"])

# Staff CRUD

@router.get("", response_model=List[Dict[str, Any]])
def list_staff(current_user: Dict[str, Any] = Depends(get_current_active_user)):
    """List all staff members."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM staff ORDER BY name")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

@router.post("", status_code=status.HTTP_201_CREATED)
def create_staff(staff: StaffCreate, current_user: Dict[str, Any] = Depends(get_current_active_user)):
    """Create a new staff member."""
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Not authorized")
        
    conn = get_db_connection()
    cursor = conn.cursor()
    staff_id = str(uuid.uuid4())
    cursor.execute(
        "INSERT INTO staff (id, name, role, active) VALUES (?, ?, ?, ?)",
        (staff_id, staff.name, staff.role, int(staff.active))
    )
    conn.commit()
    conn.close()
    return {"id": staff_id, **staff.model_dump()}

@router.put("/{staff_id}")
def update_staff(staff_id: str, staff: StaffUpdate, current_user: Dict[str, Any] = Depends(get_current_active_user)):
    """Update a staff member."""
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Not authorized")
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Build update query safely - only allow known columns
    allowed_columns = {"name": str, "role": str, "active": int}
    updates = []
    params = []
    
    if staff.name is not None:
        updates.append("name = ?")
        params.append(staff.name)
    if staff.role is not None:
        updates.append("role = ?")
        params.append(staff.role)
    if staff.active is not None:
        updates.append("active = ?")
        params.append(int(staff.active))
        
    if updates:
        params.append(staff_id)
        # Use parameterized query with safe column names
        query = f"UPDATE staff SET {', '.join(updates)} WHERE id = ?"  # nosec B608
        cursor.execute(query, params)
        conn.commit()
        
    conn.close()
    return {"id": staff_id, "message": "Updated successfully"}

@router.delete("/{staff_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_staff(staff_id: str, current_user: Dict[str, Any] = Depends(get_current_active_user)):
    """Delete a staff member."""
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Not authorized")
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM staff WHERE id = ?", (staff_id,))
    conn.commit()
    conn.close()

# Schedule Endpoints

@router.get("/{staff_id}/schedule", response_model=List[StaffSchedule])
def get_staff_schedule(staff_id: str, current_user: Dict[str, Any] = Depends(get_current_active_user)):
    """Get weekly schedule for a staff member."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM staff_schedules WHERE staff_id = ? ORDER BY day_of_week", (staff_id,))
    rows = cursor.fetchall()
    conn.close()
    
    schedules = []
    for row in rows:
        schedules.append(StaffSchedule(
            id=row["id"],
            staff_id=row["staff_id"],
            day_of_week=row["day_of_week"],
            start_time=row["start_time"],
            end_time=row["end_time"],
            is_off=bool(row["is_off"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"]
        ))
    return schedules

@router.put("/{staff_id}/schedule")
def update_staff_schedule(
    staff_id: str, 
    schedules: List[StaffScheduleUpdate], 
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Update schedule for a staff member (bulk)."""
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Not authorized")
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Verify staff exists
    cursor.execute("SELECT id FROM staff WHERE id = ?", (staff_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Staff not found")

    try:
        # Weupsert logic: unique constraint on (staff_id, day_of_week)
        for schedule in schedules:
            schedule_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO staff_schedules (id, staff_id, day_of_week, start_time, end_time, is_off, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(staff_id, day_of_week) DO UPDATE SET
                    start_time=excluded.start_time,
                    end_time=excluded.end_time,
                    is_off=excluded.is_off,
                    updated_at=CURRENT_TIMESTAMP
            """, (
                schedule_id, 
                staff_id, 
                schedule.day_of_week, 
                schedule.start_time, 
                schedule.end_time, 
                int(schedule.is_off)
            ))
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
        
    return {"message": "Schedule updated successfully"}

# Credentials Management

@router.get("/{staff_id}/credentials")
def get_staff_credentials(staff_id: str, current_user: Dict[str, Any] = Depends(get_current_active_user)):
    """Get credentials existence for a staff member."""
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Not authorized")
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, username, is_admin FROM users WHERE staff_id = ?", (staff_id,))
    user = cursor.fetchone()
    conn.close()
    
    if user:
        return {
            "has_account": True,
            "username": user["username"],
            "is_admin": bool(user["is_admin"])
        }
    return {"has_account": False}

@router.post("/{staff_id}/credentials")
def update_staff_credentials(
    staff_id: str, 
    credentials: Dict[str, Any], 
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Create or update staff credentials."""
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Not authorized")
        
    username = credentials.get("username")
    password = credentials.get("password")
    is_admin = credentials.get("is_admin", False)
    
    if not username:
        raise HTTPException(status_code=400, detail="Username is required")
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if username exists for OTHER user
    cursor.execute("SELECT id FROM users WHERE username = ? AND staff_id != ?", (username, staff_id))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="Username already taken")
        
    from passlib.context import CryptContext
    # LOW-2: Match auth.py hashing scheme. New passwords use argon2; existing sha256_crypt hashes still verify.
    pwd_context = CryptContext(schemes=["argon2", "sha256_crypt"], deprecated=["sha256_crypt"])
    
    # Check existing user for this staff
    cursor.execute("SELECT id FROM users WHERE staff_id = ?", (staff_id,))
    existing_user = cursor.fetchone()
    
    import uuid
    
    if existing_user:
        # Build update query safely
        updates = ["username = ?", "is_admin = ?"]
        params = [username, int(is_admin)]
        
        if password:
            updates.append("hashed_password = ?")
            params.append(pwd_context.hash(password))
            
        params.append(existing_user["id"])
        # Use parameterized query with safe column names
        query = f"UPDATE users SET {', '.join(updates)} WHERE id = ?"  # nosec B608
        cursor.execute(query, params)
    else:
        if not password:
             conn.close()
             raise HTTPException(status_code=400, detail="Password required for new account")
             
        user_id = str(uuid.uuid4())
        hashed = pwd_context.hash(password)
        cursor.execute("""
            INSERT INTO users (id, username, hashed_password, is_admin, staff_id)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, username, hashed, int(is_admin), staff_id))
        
    conn.commit()
    conn.close()
    
    return {"message": "Credentials updated successfully"}
