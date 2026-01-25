"""
Migration script to populate business_hours table from existing settings.
Run this after deploying the new business_hours table schema.
"""
from database import get_db_connection, init_db
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate_business_hours():
    """Migrate existing opening_time/closing_time settings to business_hours table."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Ensure business_hours table exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS business_hours (
            day_of_week INTEGER PRIMARY KEY,
            opening_time TEXT,
            closing_time TEXT,
            is_closed INTEGER DEFAULT 0,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_by TEXT
        )
    """)
    
    # Get existing settings
    cursor.execute("SELECT value FROM settings WHERE key = 'opening_time'")
    opening_row = cursor.fetchone()
    opening_time = opening_row["value"] if opening_row else "08:00"
    
    cursor.execute("SELECT value FROM settings WHERE key = 'closing_time'")
    closing_row = cursor.fetchone()
    closing_time = closing_row["value"] if closing_row else "18:00"
    
    logger.info(f"Migrating business hours: {opening_time} - {closing_time}")
    
    # Default: Monday-Friday open, Saturday-Sunday closed
    default_hours = [
        (0, opening_time, closing_time, 0),  # Monday
        (1, opening_time, closing_time, 0),  # Tuesday
        (2, opening_time, closing_time, 0),  # Wednesday
        (3, opening_time, closing_time, 0),  # Thursday
        (4, opening_time, closing_time, 0),  # Friday
        (5, None, None, 1),                   # Saturday - Closed
        (6, None, None, 1),                   # Sunday - Closed
    ]
    
    # Insert or update business hours
    for day, open_time, close_time, is_closed in default_hours:
        cursor.execute("""
            INSERT OR REPLACE INTO business_hours (day_of_week, opening_time, closing_time, is_closed)
            VALUES (?, ?, ?, ?)
        """, (day, open_time, close_time, is_closed))
        logger.info(f"Migrated day {day}: {'Closed' if is_closed else f'{open_time} - {close_time}'}")
    
    conn.commit()
    conn.close()
    logger.info("Business hours migration completed successfully!")


if __name__ == "__main__":
    print("Running business hours migration...")
    migrate_business_hours()
    print("Migration complete!")
