
import os
import uuid
import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from models import Case, CaseCreate, CaseUpdate, CaseNote, CaseNoteCreate, CasePart, CasePartCreate, CaseHistoryEvent
from auth import get_current_active_user
from database import get_db_connection, fmt_query

router = APIRouter(prefix="/api/cases", tags=["cases"])


def _get_staff_id_for_audit(current_user: Dict[str, Any], conn=None) -> Optional[str]:
    """Resolve staff_id for audit trail (current user or System Admin if admin without staff)."""
    staff_id = current_user.get("staff_id")
    if staff_id:
        return staff_id
    if not current_user.get("is_admin"):
        return None
    # Admin without linked staff: use System Admin
    own_conn = conn is None
    if own_conn:
        conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(fmt_query("SELECT id FROM staff WHERE name = ?"), ("System Admin",))
        row = cursor.fetchone()
        if row:
            return row["id"] if isinstance(row, dict) else row[0]
        new_id = str(uuid.uuid4())
        cursor.execute(
            fmt_query("INSERT INTO staff (id, name, role, active) VALUES (?, 'System Admin', 'admin', 1)"),
            (new_id,),
        )
        conn.commit()
        return new_id
    finally:
        if own_conn and conn is not None:
            conn.close()
    return None

@router.post("", response_model=Case, status_code=status.HTTP_201_CREATED)
def create_case(
    case_data: CaseCreate,
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Create a new repair case from an appointment."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Verify appointment exists
    cursor.execute(fmt_query("SELECT * FROM appointments WHERE id = ?"), (case_data.appointment_id,))
    appointment = cursor.fetchone()
    if not appointment:
        conn.close()
        raise HTTPException(status_code=404, detail="Appointment not found")

    # Check if case already exists for this appointment
    cursor.execute(fmt_query("SELECT * FROM cases WHERE appointment_id = ?"), (case_data.appointment_id,))
    existing_case = cursor.fetchone()
    if existing_case:
        conn.close()
        raise HTTPException(status_code=400, detail="Case already exists for this appointment")

    case_id = str(uuid.uuid4())
    
    # Generate simple case number (auto-increment simulation)
    cursor.execute(fmt_query("SELECT MAX(case_number) AS max_num FROM cases"))
    row = cursor.fetchone()
    max_num = row.get("max_num") if row else None
    case_number = (max_num or 1000) + 1

    metadata_json = json.dumps(case_data.metadata or {})

    cursor.execute(fmt_query("""
        INSERT INTO cases (id, case_number, appointment_id, status, metadata)
        VALUES (?, ?, ?, 'open', ?)
    """), (case_id, case_number, case_data.appointment_id, metadata_json))

    # Audit trail: log case opened
    staff_id = _get_staff_id_for_audit(current_user, conn)
    hist_id = str(uuid.uuid4())
    cursor.execute(fmt_query("""
        INSERT INTO case_status_history (id, case_id, old_status, new_status, changed_by)
        VALUES (?, ?, NULL, 'open', ?)
    """), (hist_id, case_id, staff_id))
    
    conn.commit()
    
    # Fetch created case
    cursor.execute(fmt_query("SELECT * FROM cases WHERE id = ?"), (case_id,))
    row = cursor.fetchone()
    conn.close()

    return Case(
        id=row["id"],
        case_number=row["case_number"],
        appointment_id=row["appointment_id"],
        status=row["status"],
        customer_signature=row.get("customer_signature"),
        metadata=json.loads(row["metadata"] or "{}"),
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

    cursor.execute(fmt_query(query), params)
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

    cursor.execute(fmt_query("SELECT * FROM cases WHERE id = ?"), (case_id,))
    case_row = cursor.fetchone()
    
    if not case_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Case not found")

    # Fetch Notes
    cursor.execute(fmt_query("SELECT * FROM case_notes WHERE case_id = ? ORDER BY created_at ASC"), (case_id,))
    note_rows = cursor.fetchall()
    notes = [
        CaseNote(
            id=r["id"], case_id=r["case_id"], staff_id=r["staff_id"], 
            note=r["note"], is_internal=bool(r["is_internal"]), created_at=r["created_at"]
        ) for r in note_rows
    ]

    # Fetch Parts
    cursor.execute(fmt_query("SELECT * FROM case_parts WHERE case_id = ? ORDER BY created_at ASC"), (case_id,))
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


@router.get("/{case_id}/history", response_model=List[CaseHistoryEvent])
def get_case_history(
    case_id: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Return chronological repair history (audit trail) for a case: status changes, notes, parts."""
    # Validate access by fetching case (same permission as get_case)
    get_case(case_id, current_user)

    conn = get_db_connection()
    cursor = conn.cursor()

    events: List[CaseHistoryEvent] = []
    staff_ids = set()

    # Status history
    cursor.execute(
        fmt_query("SELECT old_status, new_status, changed_at, changed_by FROM case_status_history WHERE case_id = ? ORDER BY changed_at ASC"),
        (case_id,),
    )
    for r in cursor.fetchall() or []:
        rd = r if isinstance(r, dict) else {"old_status": r[0], "new_status": r[1], "changed_at": r[2], "changed_by": r[3]}
        if not isinstance(rd, dict):
            rd = {"old_status": r[0], "new_status": r[1], "changed_at": r[2], "changed_by": r[3]}
        sid = rd.get("changed_by")
        if sid:
            staff_ids.add(sid)
        ev_type = "case_created" if rd.get("old_status") is None and rd.get("new_status") == "open" else "status_change"
        events.append(
            CaseHistoryEvent(
                event_type=ev_type,
                at=rd.get("changed_at"),
                staff_id=sid,
                payload={"old_status": rd.get("old_status"), "new_status": rd.get("new_status")},
            )
        )

    # Notes
    cursor.execute(fmt_query("SELECT staff_id, note, is_internal, created_at FROM case_notes WHERE case_id = ? ORDER BY created_at ASC"), (case_id,))
    for r in cursor.fetchall() or []:
        rd = r if isinstance(r, dict) else {"staff_id": r[0], "note": r[1], "is_internal": r[2], "created_at": r[3]}
        if not isinstance(rd, dict):
            rd = {"staff_id": r[0], "note": r[1], "is_internal": r[2], "created_at": r[3]}
        if rd.get("staff_id"):
            staff_ids.add(rd["staff_id"])
        snippet = (rd.get("note") or "")[:200]
        if len(rd.get("note") or "") > 200:
            snippet += "..."
        events.append(
            CaseHistoryEvent(
                event_type="note_added",
                at=rd.get("created_at"),
                staff_id=rd.get("staff_id"),
                payload={"note": snippet, "is_internal": rd.get("is_internal")},
            )
        )

    # Parts
    cursor.execute(fmt_query("SELECT part_name, quantity, price, created_at FROM case_parts WHERE case_id = ? ORDER BY created_at ASC"), (case_id,))
    for r in cursor.fetchall() or []:
        rd = r if isinstance(r, dict) else {"part_name": r[0], "quantity": r[1], "price": r[2], "created_at": r[3]}
        if not isinstance(rd, dict):
            rd = {"part_name": r[0], "quantity": r[1], "price": r[2], "created_at": r[3]}
        events.append(
            CaseHistoryEvent(
                event_type="part_added",
                at=rd.get("created_at"),
                staff_id=None,
                payload={"part_name": rd.get("part_name"), "quantity": rd.get("quantity"), "price": rd.get("price")},
            )
        )

    # Resolve staff names
    staff_names = {}
    if staff_ids:
        for sid in staff_ids:
            cursor.execute(fmt_query("SELECT name FROM staff WHERE id = ?"), (sid,))
            srow = cursor.fetchone()
            if srow:
                staff_names[sid] = srow["name"] if isinstance(srow, dict) else srow[0]
            else:
                staff_names[sid] = "Unknown"

    # Attach staff names (build new list so Pydantic models stay immutable)
    out = []
    for e in events:
        name = staff_names.get(e.staff_id, "Unknown") if e.staff_id else None
        out.append(CaseHistoryEvent(
            event_type=e.event_type,
            at=e.at,
            staff_id=e.staff_id,
            staff_name=name,
            payload=e.payload,
        ))
    events = out

    # Sort by at (handle None: put at end)
    events.sort(key=lambda x: (x.at is None, x.at or datetime.min))

    conn.close()
    return events


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
            cursor.execute(fmt_query("SELECT id FROM staff WHERE name = ?"), ('System Admin',))
            row = cursor.fetchone()
            
            if row:
                staff_id = row["id"] if isinstance(row, dict) else row[0]
            else:
                # Create System Admin staff
                new_staff_id = str(uuid.uuid4())
                cursor.execute(fmt_query("""
                    INSERT INTO staff (id, name, role, active) 
                    VALUES (?, 'System Admin', 'admin', 1)
                """), (new_staff_id,))
                conn.commit()
                staff_id = new_staff_id
        finally:
            conn.close()

    if not staff_id:
         raise HTTPException(status_code=400, detail="Current user has no associated staff profile")

    conn = get_db_connection()
    cursor = conn.cursor()

    note_id = str(uuid.uuid4())
    cursor.execute(fmt_query("""
        INSERT INTO case_notes (id, case_id, staff_id, note, is_internal)
        VALUES (?, ?, ?, ?, ?)
    """), (note_id, case_id, staff_id, note_data.note, int(note_data.is_internal)))
    
    conn.commit()
    
    cursor.execute(fmt_query("SELECT * FROM case_notes WHERE id = ?"), (note_id,))
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
        # Audit trail: log status change
        cursor.execute(fmt_query("SELECT status FROM cases WHERE id = ?"), (case_id,))
        row = cursor.fetchone()
        old_status = row["status"] if row and isinstance(row, dict) else (row[0] if row else None)
        if old_status != case_update.status:
            staff_id = _get_staff_id_for_audit(current_user, conn)
            hist_id = str(uuid.uuid4())
            cursor.execute(fmt_query("""
                INSERT INTO case_status_history (id, case_id, old_status, new_status, changed_by)
                VALUES (?, ?, ?, ?, ?)
            """), (hist_id, case_id, old_status, case_update.status, staff_id))

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
    
    cursor.execute(fmt_query(query), params)
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
    cursor.execute(fmt_query("""
        INSERT INTO case_parts (id, case_id, part_name, quantity, price, status)
        VALUES (?, ?, ?, ?, ?, ?)
    """), (part_id, case_id, part_data.part_name, part_data.quantity, part_data.price, 'pending'))
    
    conn.commit()
    
    cursor.execute(fmt_query("SELECT * FROM case_parts WHERE id = ?"), (part_id,))
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
        # Audit trail: log status change to completed
        cursor.execute(fmt_query("SELECT status FROM cases WHERE id = ?"), (case_id,))
        row = cursor.fetchone()
        old_status = row["status"] if row and isinstance(row, dict) else (row[0] if row else None)
        if old_status != 'completed':
            staff_id = _get_staff_id_for_audit(current_user, conn)
            hist_id = str(uuid.uuid4())
            cursor.execute(fmt_query("""
                INSERT INTO case_status_history (id, case_id, old_status, new_status, changed_by)
                VALUES (?, ?, ?, 'completed', ?)
            """), (hist_id, case_id, old_status, staff_id))
        updates.append("status = 'completed'")
        updates.append("closed_at = CURRENT_TIMESTAMP")
    
    if not updates:
        conn.close()
        raise HTTPException(status_code=400, detail="No updates provided")

    query = f"UPDATE cases SET {', '.join(updates)} WHERE id = ?"  # nosec B608
    params.append(case_id)
    
    cursor.execute(fmt_query(query), params)
    conn.commit()
    
    # Send email (mock)
    # In a real app, trigger email task here
    
    cursor.execute(fmt_query("SELECT * FROM cases WHERE id = ?"), (case_id,))
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
    from services.llm import generate_repair_note
    
    if not request.text or len(request.text.strip()) < 5:
         raise HTTPException(status_code=400, detail="Input text too short")
         
    try:
        polished_note = generate_repair_note(request.text)
        return {"note": polished_note}
    except Exception as e:
        # Fallback if AI fails
        return {"note": request.text}
