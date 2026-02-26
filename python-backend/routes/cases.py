
import os
import uuid
import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from models import Case, CaseCreate, CaseUpdate, CaseNote, CaseNoteCreate, CasePart, CasePartCreate
from auth import get_current_active_user
from database import get_db_connection

router = APIRouter(prefix="/api/cases", tags=["cases"])

@router.post("", response_model=Case, status_code=status.HTTP_201_CREATED)
def create_case(
    case_data: CaseCreate,
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Create a new repair case from an appointment."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Verify appointment exists
    cursor.execute("SELECT * FROM appointments WHERE id = ?", (case_data.appointment_id,))
    appointment = cursor.fetchone()
    if not appointment:
        conn.close()
        raise HTTPException(status_code=404, detail="Appointment not found")

    # Check if case already exists for this appointment
    cursor.execute("SELECT * FROM cases WHERE appointment_id = ?", (case_data.appointment_id,))
    existing_case = cursor.fetchone()
    if existing_case:
        conn.close()
        raise HTTPException(status_code=400, detail="Case already exists for this appointment")

    case_id = str(uuid.uuid4())
    
    # Generate simple case number (auto-increment simulation or random)
    # For SQLite simplicity, we'll just use a random int or timestamp based
    # Better approach: SELECT MAX(case_number) + 1
    cursor.execute("SELECT MAX(case_number) FROM cases")
    max_num = cursor.fetchone()[0]
    case_number = (max_num or 1000) + 1

    metadata_json = json.dumps(case_data.metadata or {})

    cursor.execute("""
        INSERT INTO cases (id, case_number, appointment_id, status, metadata)
        VALUES (?, ?, ?, 'open', ?)
    """, (case_id, case_number, case_data.appointment_id, metadata_json))
    
    conn.commit()
    
    # Fetch created case
    cursor.execute("SELECT * FROM cases WHERE id = ?", (case_id,))
    row = cursor.fetchone()
    conn.close()

    return Case(
        id=row["id"],
        case_number=row["case_number"],
        appointment_id=row["appointment_id"],
        status=row["status"],
        customer_signature=row["customer_signature"],
        metadata=json.loads(row["metadata"]),
        created_at=row["created_at"],
        closed_at=row["closed_at"]
    )

@router.get("", response_model=List[Case])
def list_cases(
    staff_id: Optional[str] = None,
    status_filter: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """List cases with optional filters and proper RLS."""
    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
        SELECT c.* 
        FROM cases c
        JOIN appointments a ON c.appointment_id = a.id
    """
    params = []
    conditions = []

    # Apply explicit filters
    if staff_id:
        conditions.append("a.assigned_staff_id = ?")
        params.append(staff_id)
    
    if status_filter:
        conditions.append("c.status = ?")
        params.append(status_filter)

    # Apply RLS based on user role
    if current_user.get("is_admin"):
        # Admins see all cases
        pass
    elif current_user.get("staff_id"):
        # Staff members see cases assigned to them OR unassigned cases
        conditions.append("(a.assigned_staff_id = ? OR a.assigned_staff_id IS NULL)")
        params.append(current_user["staff_id"])
    else:
        # Regular customers see only their own cases
        conditions.append("(a.user_id = ? OR a.phone_number = ?)")
        params.extend([current_user["id"], current_user.get("phone_number", "")])

    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    
    query += " ORDER BY c.created_at DESC"

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    cases = []
    for row in rows:
        cases.append(Case(
            id=row["id"],
            case_number=row["case_number"],
            appointment_id=row["appointment_id"],
            status=row["status"],
            customer_signature=row["customer_signature"],
            metadata=json.loads(row["metadata"] or '{}'),
            created_at=row["created_at"],
            closed_at=row["closed_at"]
        ))
    return cases

@router.get("/{case_id}", response_model=Case)
def get_case(
    case_id: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Get full case details including notes and parts."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM cases WHERE id = ?", (case_id,))
    case_row = cursor.fetchone()
    
    if not case_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Case not found")

    # Fetch Notes
    cursor.execute("SELECT * FROM case_notes WHERE case_id = ? ORDER BY created_at ASC", (case_id,))
    note_rows = cursor.fetchall()
    notes = [
        CaseNote(
            id=r["id"], case_id=r["case_id"], staff_id=r["staff_id"], 
            note=r["note"], is_internal=bool(r["is_internal"]), created_at=r["created_at"]
        ) for r in note_rows
    ]

    # Fetch Parts
    cursor.execute("SELECT * FROM case_parts WHERE case_id = ? ORDER BY created_at ASC", (case_id,))
    part_rows = cursor.fetchall()
    parts = [
        CasePart(
            id=r["id"], case_id=r["case_id"], part_name=r["part_name"], 
            quantity=r["quantity"], price=r["price"], status=r["status"], created_at=r["created_at"]
        ) for r in part_rows
    ]

    conn.close()

    return Case(
        id=case_row["id"],
        case_number=case_row["case_number"],
        appointment_id=case_row["appointment_id"],
        status=case_row["status"],
        customer_signature=case_row["customer_signature"],
        metadata=json.loads(case_row["metadata"] or '{}'),
        created_at=case_row["created_at"],
        closed_at=case_row["closed_at"],
        notes=notes,
        parts=parts
    )

@router.post("/{case_id}/notes", response_model=CaseNote)
def add_case_note(
    case_id: str,
    note_data: CaseNoteCreate,
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Add a note to a case."""
    if not current_user.get("staff_id") and not current_user.get("is_admin"):
        raise HTTPException(status_code=400, detail="User must be linked to a staff profile or be admin")
    
    staff_id = current_user.get("staff_id")
    
    # Handle Admin user without linked staff profile
    if not staff_id and current_user.get("is_admin"):
        # Auto-create or fetch a "System Admin" staff profile
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM staff WHERE name = 'System Admin'")
            row = cursor.fetchone()
            
            if row:
                staff_id = row[0]
            else:
                # Create System Admin staff
                new_staff_id = str(uuid.uuid4())
                cursor.execute("""
                    INSERT INTO staff (id, name, role, active) 
                    VALUES (?, 'System Admin', 'admin', 1)
                """, (new_staff_id,))
                conn.commit()
                staff_id = new_staff_id
        finally:
            conn.close()

    if not staff_id:
         raise HTTPException(status_code=400, detail="Current user has no associated staff profile")

    conn = get_db_connection()
    cursor = conn.cursor()

    note_id = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO case_notes (id, case_id, staff_id, note, is_internal)
        VALUES (?, ?, ?, ?, ?)
    """, (note_id, case_id, staff_id, note_data.note, int(note_data.is_internal)))
    
    conn.commit()
    
    cursor.execute("SELECT * FROM case_notes WHERE id = ?", (note_id,))
    row = cursor.fetchone()
    conn.close()

    return CaseNote(
        id=row["id"], case_id=row["case_id"], staff_id=row["staff_id"], 
        note=row["note"], is_internal=bool(row["is_internal"]), created_at=row["created_at"]
    )

@router.put("/{case_id}", response_model=Case)
def update_case(
    case_id: str,
    case_update: CaseUpdate,
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Update general case info (status, metadata)."""
    conn = get_db_connection()
    cursor = conn.cursor()

    updates = []
    params = []

    if case_update.status is not None:
        updates.append("status = ?")
        params.append(case_update.status)
        
        # If closing the case, set closed_at
        if case_update.status == 'completed':
            updates.append("closed_at = CURRENT_TIMESTAMP")
    
    if case_update.metadata is not None:
        updates.append("metadata = ?")
        params.append(json.dumps(case_update.metadata))

    if not updates:
        conn.close()
        return get_case(case_id, current_user)

    query = f"UPDATE cases SET {', '.join(updates)} WHERE id = ?"  # nosec B608
    params.append(case_id)
    
    cursor.execute(query, params)
    conn.commit()
    
    conn.close()
    return get_case(case_id, current_user)

@router.post("/{case_id}/parts", response_model=CasePart)
def add_case_part(
    case_id: str,
    part_data: CasePartCreate,
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Add a part to a case."""
    conn = get_db_connection()
    cursor = conn.cursor()

    part_id = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO case_parts (id, case_id, part_name, quantity, price, status)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (part_id, case_id, part_data.part_name, part_data.quantity, part_data.price, 'pending'))
    
    conn.commit()
    
    cursor.execute("SELECT * FROM case_parts WHERE id = ?", (part_id,))
    row = cursor.fetchone()
    conn.close()

    return CasePart(
        id=row["id"], case_id=row["case_id"], part_name=row["part_name"], 
        quantity=row["quantity"], price=row["price"], status=row["status"], created_at=row["created_at"]
    )

@router.post("/{case_id}/sign", response_model=Case)
def sign_and_close_case(
    case_id: str,
    case_update: CaseUpdate,
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Add customer signature and close the case."""
    conn = get_db_connection()
    cursor = conn.cursor()

    updates = []
    params = []

    if case_update.customer_signature:
        updates.append("customer_signature = ?")
        params.append(case_update.customer_signature)

    if case_update.status == 'completed':
        updates.append("status = 'completed'")
        updates.append("closed_at = CURRENT_TIMESTAMP")
    
    if not updates:
        conn.close()
        raise HTTPException(status_code=400, detail="No updates provided")

    query = f"UPDATE cases SET {', '.join(updates)} WHERE id = ?"  # nosec B608
    params.append(case_id)
    
    cursor.execute(query, params)
    conn.commit()
    
    # Send email (mock)
    # In a real app, trigger email task here
    
    cursor.execute("SELECT * FROM cases WHERE id = ?", (case_id,))
    row = cursor.fetchone()
    conn.close()

    return Case(
        id=row["id"],
        case_number=row["case_number"],
        appointment_id=row["appointment_id"],
        status=row["status"],
        customer_signature=row["customer_signature"],
        metadata=json.loads(row["metadata"] or '{}'),
        created_at=row["created_at"],
        closed_at=row["closed_at"]
    )

from pydantic import BaseModel

class NoteGenerationRequest(BaseModel):
    text: str

@router.post("/{case_id}/generate-note")
def generate_note_api(
    case_id: str,
    request: NoteGenerationRequest,
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Generate a professional repair note from rough text using AI."""
    from llm_service import generate_repair_note
    
    if not request.text or len(request.text.strip()) < 5:
         raise HTTPException(status_code=400, detail="Input text too short")
         
    try:
        polished_note = generate_repair_note(request.text)
        return {"note": polished_note}
    except Exception as e:
        # Fallback if AI fails
        return {"note": request.text}
