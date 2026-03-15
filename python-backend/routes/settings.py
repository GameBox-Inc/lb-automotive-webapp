from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Dict, Any
from database import DatabaseContextManager, fmt_query
from auth import get_current_admin_user
from models import Setting, SettingUpdate
from security import sanitize_input
import logging

router = APIRouter(prefix="/api/settings", tags=["settings"])
logger = logging.getLogger(__name__)

@router.get("", response_model=List[Setting])
def get_settings(current_user: Dict[str, Any] = Depends(get_current_admin_user)):
    """Get all settings (Admin only)."""
    with DatabaseContextManager(read_only=True) as conn:
        cursor = conn.cursor()
        cursor.execute(fmt_query("SELECT * FROM settings ORDER BY key"))
        rows = cursor.fetchall()
    settings = []
    for row in rows:
        settings.append(Setting(
            key=row["key"],
            value=row["value"],
            description=row["description"],
            updated_at=row["updated_at"],
            updated_by=row["updated_by"]
        ))
    
    return settings


@router.put("/{key}", response_model=Setting)
def update_setting(
    key: str,
    setting_update: SettingUpdate,
    current_user: Dict[str, Any] = Depends(get_current_admin_user)
):
    """Update a setting (Admin only)."""
    # Sanitize input
    sanitized_value = sanitize_input(setting_update.value, "text")
    
    with DatabaseContextManager() as conn:
        cursor = conn.cursor()
        cursor.execute(fmt_query("SELECT * FROM settings WHERE key = ?"), (key,))
        if not cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Setting '{key}' not found"
            )
        cursor.execute(fmt_query("""
            UPDATE settings 
            SET value = ?, updated_at = CURRENT_TIMESTAMP, updated_by = ?
            WHERE key = ?
        """), (sanitized_value, current_user["username"], key))
        cursor.execute(fmt_query("SELECT * FROM settings WHERE key = ?"), (key,))
        row = cursor.fetchone()
    
    logger.info(f"Setting '{key}' updated by {current_user['username']} to '{sanitized_value}'")
    
    return Setting(
        key=row["key"],
        value=row["value"],
        description=row["description"],
        updated_at=row["updated_at"],
        updated_by=row["updated_by"]
    )
