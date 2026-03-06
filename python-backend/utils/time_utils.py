from datetime import datetime
import pytz
from database import get_db_connection

def get_business_timezone() -> str:
    """Fetch the business timezone from settings, default to America/New_York."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = 'timezone'")
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return row["value"]
    return "America/New_York"

def get_current_business_time() -> datetime:
    """Get the current time in the business timezone."""
    tz_name = get_business_timezone()
    tz = pytz.timezone(tz_name)
    return datetime.now(tz)

def to_utc(dt: datetime) -> datetime:
    """Convert a datetime to UTC."""
    if dt.tzinfo is None:
        # Assume it's in business time if naive? Or UTC? 
        # Safer to assume naive = business time for this app context if input from frontend is just "HH:MM"
        # But if it's a full ISO from DB...
        pass
    return dt.astimezone(pytz.UTC)
