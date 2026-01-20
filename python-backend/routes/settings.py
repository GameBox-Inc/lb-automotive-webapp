from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Dict, Any
from database import get_db_connection
from auth import get_current_active_user
from models import Setting, SettingUpdate
from security import sanitize_input
import logging

router = APIRouter(prefix="/api/settings", tags=["settings"])
logger = logging.getLogger(__name__)

@router.get("", response_model=List[Setting])
def get_settings(current_user: Dict[str, Any] = Depends(get_current_active_user)):
    """Get all settings (Admin only)."""
    if not current_user.get("is_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view settings"
        )
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM settings ORDER BY key")
    rows = cursor.fetchall()
    conn.close()
    
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
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Update a setting (Admin only)."""
    if not current_user.get("is_admin"):
        logger.warning(f"Unauthorized settings update attempt by {current_user.get('username')}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update settings"
        )
    
    # Sanitize input
    sanitized_value = sanitize_input(setting_update.value, "text")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if setting exists
    cursor.execute("SELECT * FROM settings WHERE key = ?", (key,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Setting '{key}' not found"
        )
    
    # Update setting
    cursor.execute("""
        UPDATE settings 
        SET value = ?, updated_at = CURRENT_TIMESTAMP, updated_by = ?
        WHERE key = ?
    """, (sanitized_value, current_user["username"], key))
    
    conn.commit()
    
    # Fetch updated
    cursor.execute("SELECT * FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    
    logger.info(f"Setting '{key}' updated by {current_user['username']} to '{sanitized_value}'")
    
    return Setting(
        key=row["key"],
        value=row["value"],
        description=row["description"],
        updated_at=row["updated_at"],
        updated_by=row["updated_by"]
    )
