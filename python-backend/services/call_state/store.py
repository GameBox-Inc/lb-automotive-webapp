"""Call state and IVR analytics persistence."""
import json
import logging
import uuid

from database import upsert_call_state as _upsert_call_state, fmt_query, DatabaseContextManager

logger = logging.getLogger(__name__)


def upsert_call_state(call_sid: str, step: str, language: str, metadata: dict = None, appointment_id: str = None):
    """Upsert call state (delegates to database)."""
    _upsert_call_state(call_sid, step, language, metadata or {}, appointment_id)


def get_setting(key: str, default: str = "") -> str:
    """Get setting from database."""
    from database import get_setting as _get_setting
    return _get_setting(key, default) or default


def get_call_state(call_sid: str):
    """Get call state from database."""
    try:
        with DatabaseContextManager(read_only=True) as conn:
            cursor = conn.cursor()
            cursor.execute(
                fmt_query("""
                    SELECT id, call_sid, current_step, language, metadata, appointment_id,
                           last_response_time, created_at, updated_at
                    FROM call_states WHERE call_sid = ?
                """),
                (call_sid,),
            )
            row = cursor.fetchone()

        if row:
            return {
                "id": row["id"],
                "call_sid": row["call_sid"],
                "current_step": row["current_step"],
                "language": row["language"],
                "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
                "appointment_id": row["appointment_id"],
                "last_response_time": row["last_response_time"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        return None
    except Exception as e:
        logger.error(f"Error fetching call state: {e}")
        return None


def log_ivr_interaction(call_sid: str, step: str, input_data: str = None):
    """Log IVR interaction."""
    try:
        with DatabaseContextManager(read_only=False) as conn:
            cursor = conn.cursor()
            cursor.execute(
                fmt_query("INSERT INTO ivr_logs (id, call_sid, step, input) VALUES (?, ?, ?, ?)"),
                (str(uuid.uuid4()), call_sid, step, input_data),
            )
            conn.commit()
    except Exception as e:
        logger.error(f"Error logging IVR interaction: {e}")


def track_decision(call_sid: str, node_name: str, decision_taken: str = None, duration_seconds: int = None):
    """Track IVR decision in analytics table."""
    try:
        with DatabaseContextManager(read_only=False) as conn:
            cursor = conn.cursor()
            cursor.execute(
                fmt_query("""
                    INSERT INTO ivr_analytics (id, call_sid, node_name, decision_taken, duration_seconds)
                    VALUES (?, ?, ?, ?, ?)
                """),
                (str(uuid.uuid4()), call_sid, node_name, decision_taken, duration_seconds),
            )
            conn.commit()
    except Exception as e:
        logger.error(f"Error tracking decision: {e}")


def update_decision_path(call_sid: str, node_name: str):
    """Update the decision path in call_states."""
    try:
        with DatabaseContextManager(read_only=False) as conn:
            cursor = conn.cursor()
            cursor.execute(fmt_query("SELECT decision_path FROM call_states WHERE call_sid = ?"), (call_sid,))
            row = cursor.fetchone()
            if row:
                current_path = json.loads(row["decision_path"]) if row["decision_path"] else []
                current_path.append(node_name)
                cursor.execute(
                    fmt_query("UPDATE call_states SET decision_path = ? WHERE call_sid = ?"),
                    (json.dumps(current_path), call_sid),
                )
                conn.commit()
    except Exception as e:
        logger.error(f"Error updating decision path: {e}")
