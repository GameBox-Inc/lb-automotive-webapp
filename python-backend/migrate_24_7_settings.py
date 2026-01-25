#!/usr/bin/env python3
"""
Migration script to update IVR settings for 24/7 booking availability.
Removes confusing time-based messages and updates settings for seamless booking.
"""

import sqlite3
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from database import get_db_connection

def migrate_24_7_settings():
    """Update IVR settings for 24/7 booking."""
    print("Starting 24/7 IVR settings migration...")

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Update ivr_closed_message to reflect 24/7 availability
        cursor.execute("""
            UPDATE settings
            SET value = 'Thank you for calling LB Automotive. We accept appointments 24/7 for your convenience.',
                description = 'Welcome message (24/7 booking available)'
            WHERE key = 'ivr_closed_message'
        """)

        # Update ivr_greeting to be more welcoming
        cursor.execute("""
            UPDATE settings
            SET value = 'Welcome to LB Automotive. We are available 24/7 to schedule your appointment.',
                description = 'Main IVR greeting message (24/7 service)'
            WHERE key = 'ivr_greeting'
        """)

        # Add or update 24/7 availability setting
        cursor.execute("""
            INSERT OR REPLACE INTO settings (key, value, description)
            VALUES ('ivr_24_7_enabled', '1', 'Enable 24/7 booking via IVR (1=enabled, 0=disabled)')
        """)

        # Log the changes
        cursor.execute("SELECT key, value FROM settings WHERE key IN ('ivr_closed_message', 'ivr_greeting', 'ivr_24_7_enabled')")
        settings = cursor.fetchall()

        print("\nUpdated settings:")
        for row in settings:
            print(f"   {row['key']}: {row['value'][:50]}...")

        conn.commit()
        print("\nMigration completed successfully!")
        print("   Customers can now book appointments 24/7 via the IVR system.")

    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_24_7_settings()
