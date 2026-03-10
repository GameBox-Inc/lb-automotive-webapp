import sqlite3
import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime
from models import Appointment, AppointmentCreate, AppointmentUpdate
from database import DatabaseContextManager, fmt_query

class AppointmentRepository:
    def __init__(self):
        pass

    def close(self):
        pass

    def list_appointments(self, status_filter: Optional[str] = None, current_user: Optional[Dict[str, Any]] = None) -> List[Appointment]:
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
        
        if status_filter:
            conditions.append("a.status = ?")
            params.append(status_filter)
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY a.appointment_time ASC"
        
        with DatabaseContextManager(read_only=True) as conn:
            cursor = conn.cursor()
            cursor.execute(fmt_query(query), params)
            rows = cursor.fetchall()
        
        appointments = []
        for row in rows:
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
                user_id=row["user_id"] if "user_id" in row.keys() else None,
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                started_at=row["started_at"] if "started_at" in row.keys() else None
            ))
        return appointments

    def get_appointment(self, appointment_id: str) -> Optional[Appointment]:
        query = """
            SELECT a.*, s.name as service_name_joined
            FROM appointments a
            LEFT JOIN services s ON a.service_type = s.id
            WHERE a.id = ?
        """
        with DatabaseContextManager(read_only=True) as conn:
            cursor = conn.cursor()
            cursor.execute(fmt_query(query), (appointment_id,))
            row = cursor.fetchone()
        
        if not row:
            return None
            
        service_display = row["service_name_joined"] if row["service_name_joined"] else row["service_type"]
        
        # Note: Access control checks (RLS) should typically be done in the service/route layer 
        # or by passing user context to the repository method. 
        # For get_appointment, we return the data, caller decides if user can see it.
        # However, to be safe, we return the raw user_id/fields so caller can check ownership.
        
        return Appointment(
            id=row["id"],
            customer_name=row["customer_name"],
            phone_number=row["phone_number"],
            appointment_time=row["appointment_time"],
            service_type=service_display,
            notes=row["notes"],
            status=row["status"],
            emergency_request=bool(row["emergency_request"]),
            assigned_staff_id=row["assigned_staff_id"] if "assigned_staff_id" in row.keys() else None,
            user_id=row["user_id"] if "user_id" in row.keys() else None,
            created_at=row["created_at"],
            updated_at=row["updated_at"]
        )

    def create_appointment(self, appointment_data: Dict[str, Any], user_id: Optional[str] = None) -> Appointment:
        appointment_id = str(uuid.uuid4())
        
        with DatabaseContextManager(read_only=False) as conn:
            cursor = conn.cursor()
            cursor.execute(fmt_query("""
                INSERT INTO appointments (
                    id, customer_name, phone_number, appointment_time,
                    service_type, notes, emergency_request, user_id, assigned_staff_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """), (
                appointment_id,
                appointment_data["customer_name"],
                appointment_data["phone_number"],
                appointment_data["appointment_time"],
                appointment_data["service_type"],
                appointment_data.get("notes"),
                int(appointment_data.get("emergency_request", False)),
                user_id,
                None
            ))
            conn.commit()
        
        return self.get_appointment(appointment_id)

    def update_appointment(self, appointment_id: str, updates: AppointmentUpdate) -> Optional[Appointment]:
        # Build update query
        update_fields = []
        params = []
        
        if updates.customer_name is not None:
            update_fields.append("customer_name = ?")
            params.append(updates.customer_name)
        
        if updates.phone_number is not None:
            update_fields.append("phone_number = ?")
            params.append(updates.phone_number)
        
        if updates.appointment_time is not None:
            update_fields.append("appointment_time = ?")
            params.append(updates.appointment_time.isoformat())
        
        if updates.service_type is not None:
            update_fields.append("service_type = ?")
            params.append(updates.service_type)
        
        if updates.notes is not None:
            update_fields.append("notes = ?")
            params.append(updates.notes)
        
        if updates.status is not None:
            update_fields.append("status = ?")
            params.append(updates.status)
            
            # Side effect: Case tracking (business logic, but tied to update)
            # Ideally this belongs in a Service, but for Repository Pattern step 1, we can keep simple DB triggers here
            # or better: return the updated object and let Route/Service handle side effects.
            # I will keep the side effect here for parity with existing logic for now, 
            # or move it to explicit 'update_status' method.
            if updates.status == 'in_progress':
                with DatabaseContextManager(read_only=False) as conn:
                    cursor = conn.cursor()
                    cursor.execute(fmt_query("""
                        UPDATE cases 
                        SET started_at = CURRENT_TIMESTAMP 
                        WHERE appointment_id = ? AND started_at IS NULL
                    """), (appointment_id,))
                    conn.commit()
        
        if updates.emergency_request is not None:
            update_fields.append("emergency_request = ?")
            params.append(int(updates.emergency_request))
        
        if not update_fields:
            return self.get_appointment(appointment_id)

        update_fields.append("updated_at = CURRENT_TIMESTAMP")
        params.append(appointment_id)
        
        query = f"UPDATE appointments SET {', '.join(update_fields)} WHERE id = ?"  # nosec B608
        with DatabaseContextManager(read_only=False) as conn:
            cursor = conn.cursor()
            cursor.execute(fmt_query(query), params)
            conn.commit()
        
        return self.get_appointment(appointment_id)

    def delete_appointment(self, appointment_id: str) -> bool:
        with DatabaseContextManager(read_only=False) as conn:
            cursor = conn.cursor()
            cursor.execute(fmt_query("DELETE FROM appointments WHERE id = ?"), (appointment_id,))
            conn.commit()
            rowCount = cursor.rowcount
        return rowCount > 0
