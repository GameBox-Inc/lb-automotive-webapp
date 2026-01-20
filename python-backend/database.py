import sqlite3
import os
import json
from datetime import datetime
from typing import Optional, Dict, Any, List
from contextvars import ContextVar

# Context variable to store current user for RLS
current_user_context: ContextVar[Optional[Dict[str, Any]]] = ContextVar('current_user', default=None)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./lb_automotive.db")
DB_PATH = DATABASE_URL.replace("sqlite:///", "").replace("sqlite://", "")


def get_db_connection():
    """Get a database connection."""
    conn = sqlite3.connect(DB_PATH, timeout=20.0) # Increased timeout
    conn.execute("PRAGMA journal_mode=WAL") # Enable Write-Ahead Logging
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize the database with schema."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Create users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            email TEXT,
            hashed_password TEXT NOT NULL,
            is_admin INTEGER DEFAULT 0,
            staff_id TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (staff_id) REFERENCES staff (id)
        )
    """)

    # Create services table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS services (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            duration INTEGER NOT NULL,
            price REAL NOT NULL,
            is_emergency INTEGER DEFAULT 0,
            category TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create appointments table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS appointments (
            id TEXT PRIMARY KEY,
            customer_name TEXT NOT NULL,
            phone_number TEXT NOT NULL,
            appointment_time TEXT NOT NULL,
            service_type TEXT NOT NULL,
            notes TEXT,
            status TEXT DEFAULT 'pending',
            emergency_request INTEGER DEFAULT 0,
            assigned_staff_id TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            user_id TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (assigned_staff_id) REFERENCES staff (id)
        )
    """)

    # Create call_states table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS call_states (
            id TEXT PRIMARY KEY,
            call_sid TEXT UNIQUE NOT NULL,
            current_step TEXT NOT NULL,
            language TEXT DEFAULT 'en',
            metadata TEXT DEFAULT '{}',
            appointment_id TEXT,
            last_response_time TEXT DEFAULT CURRENT_TIMESTAMP,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (appointment_id) REFERENCES appointments (id)
        )
    """)

    # Create ivr_logs table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ivr_logs (
            id TEXT PRIMARY KEY,
            call_sid TEXT NOT NULL,
            step TEXT NOT NULL,
            input TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_appointments_phone ON appointments(phone_number)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_appointments_time ON appointments(appointment_time)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_call_states_sid ON call_states(call_sid)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ivr_logs_sid ON ivr_logs(call_sid)")

    # Create cases table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cases (
            id TEXT PRIMARY KEY,
            case_number INTEGER,
            appointment_id TEXT UNIQUE NOT NULL,
            status TEXT DEFAULT 'open',
            customer_signature TEXT,
            metadata TEXT DEFAULT '{}',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            closed_at TEXT,
            FOREIGN KEY (appointment_id) REFERENCES appointments (id)
        )
    """)

    # Create case_notes table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS case_notes (
            id TEXT PRIMARY KEY,
            case_id TEXT NOT NULL,
            staff_id TEXT NOT NULL,
            note TEXT NOT NULL,
            is_internal INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (case_id) REFERENCES cases (id),
            FOREIGN KEY (staff_id) REFERENCES staff (id)
        )
    """)

    # Create case_parts table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS case_parts (
            id TEXT PRIMARY KEY,
            case_id TEXT NOT NULL,
            part_name TEXT NOT NULL,
            quantity INTEGER DEFAULT 1,
            price REAL DEFAULT 0.0,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (case_id) REFERENCES cases (id)
        )
    """)

    # Create staff_schedules table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS staff_schedules (
            id TEXT PRIMARY KEY,
            staff_id TEXT NOT NULL,
            day_of_week INTEGER NOT NULL, -- 0=Monday, 6=Sunday
            start_time TEXT NOT NULL, -- HH:MM
            end_time TEXT NOT NULL, -- HH:MM
            is_off INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (staff_id) REFERENCES staff (id),
            UNIQUE(staff_id, day_of_week)
        )
    """)

    conn.commit()
    conn.commit()
    # Create settings table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            description TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_by TEXT
        )
    """)

    conn.commit()
    conn.close()
    print("Database initialized successfully!")


def seed_data():
    """Seed the database with initial data."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Create staff table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS staff (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            role TEXT DEFAULT 'mechanic',
            active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create customers table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            phone TEXT UNIQUE NOT NULL,
            email TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Check if services already exist
    cursor.execute("SELECT COUNT(*) FROM services")
    if cursor.fetchone()[0] == 0:
        # Insert sample services
        services = [
            ('srv_oil_change', 'Oil Change', 'Standard oil change and filter replacement', 60, 49.99, 0, 'Maintenance'),
            ('srv_tire_rotation', 'Tire Rotation', 'Rotate all four tires to ensure even wear', 30, 29.99, 0, 'Maintenance'),
            ('srv_brake_inspection', 'Brake Inspection', 'Comprehensive brake system inspection', 45, 39.99, 0, 'Safety'),
            ('srv_emergency_roadside', 'Emergency Roadside Assistance', '24/7 roadside assistance', 15, 99.99, 1, 'Emergency'),
            ('srv_flat_tire', 'Flat Tire Repair', 'Flat tire repair or replacement', 30, 49.99, 1, 'Emergency'),
            ('srv_battery', 'Battery Replacement', 'Car battery replacement', 45, 79.99, 1, 'Emergency'),
        ]

        cursor.executemany("""
            INSERT INTO services (id, name, description, duration, price, is_emergency, category)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, services)

    # Seed initial staff if empty
    cursor.execute("SELECT COUNT(*) FROM staff")
    if cursor.fetchone()[0] == 0:
        import uuid
        staff_members = [
            (str(uuid.uuid4()), 'John Mechanic', 'mechanic', 1),
            (str(uuid.uuid4()), 'Sarah Advisor', 'advisor', 1),
            (str(uuid.uuid4()), 'Mike Tech', 'mechanic', 1)
        ]
        cursor.executemany("INSERT INTO staff (id, name, role, active) VALUES (?, ?, ?, ?)", staff_members)

    # Check if admin user exists
    cursor.execute("SELECT COUNT(*) FROM users WHERE username = 'admin'")
    if cursor.fetchone()[0] == 0:
        # Insert default admin user (password: admin123)
        from passlib.context import CryptContext
        import uuid
        
        pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")
        admin_id = str(uuid.uuid4())
        admin_password = pwd_context.hash("admin123")
        
        cursor.execute("""
            INSERT INTO users (id, username, email, hashed_password, is_admin)
            VALUES (?, ?, ?, ?, ?)
        """, (admin_id, "admin", "admin@lbautomotive.com", admin_password, 1))

    # Seed default settings if they don't exist
    default_settings = [
        ('opening_time', '08:00', 'Business opening time (HH:MM)'),
        ('closing_time', '18:00', 'Business closing time (HH:MM)'),
        ('ivr_greeting', 'Welcome to LB Automotive. Press 1 for appointments, 2 for emergency services.', 'Main IVR greeting message'),
        ('ivr_closed_message', 'We are currently closed. Our hours are 8 AM to 6 PM. Please call back during business hours.', 'Message played when closed'),
        ('ivr_voice', 'alice', 'Voice for text-to-speech (alice, man, woman)'),
        ('ivr_language', 'en-US', 'Language for text-to-speech'),
        ('staff_count', '5', 'Number of staff members available per day')
    ]

    for key, value, desc in default_settings:
        cursor.execute("INSERT OR IGNORE INTO settings (key, value, description) VALUES (?, ?, ?)", (key, value, desc))

    conn.commit()
    conn.close()
    print("Database seeded successfully!")


def apply_rls_filter(query: str, table: str, user: Optional[Dict[str, Any]]) -> str:
    """
    Apply Row-Level Security filter to SQL query.
    This is a simplified RLS implementation for SQLite.
    """
    if not user:
        # No user context, allow only public data
        return query
    
    if user.get("is_admin"):
        # Admins can see everything
        return query
    
    # For appointments table, filter by user_id or phone_number
    if "appointments" in table.lower():
        if "WHERE" in query.upper():
            query += f" AND (user_id = '{user['id']}' OR phone_number = '{user.get('phone_number', '')}')"
        else:
            query += f" WHERE (user_id = '{user['id']}' OR phone_number = '{user.get('phone_number', '')}')"
    
    return query


def get_call_state(call_sid: str) -> Optional[dict]:
    """Get call state from database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, call_sid, current_step, language, metadata, appointment_id, 
               last_response_time, created_at, updated_at
        FROM call_states WHERE call_sid = ?
    """, (call_sid,))
    row = cursor.fetchone()
    conn.close()
    
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
            "updated_at": row["updated_at"]
        }
    return None


def upsert_call_state(call_sid: str, current_step: str, language: str = "en", 
                      metadata: dict = None, appointment_id: str = None):
    """Create or update call state."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    existing = get_call_state(call_sid)
    metadata_json = json.dumps(metadata or {})
    
    import uuid
    if existing:
        cursor.execute("""
            UPDATE call_states 
            SET current_step = ?, language = ?, metadata = ?, appointment_id = ?,
                last_response_time = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE call_sid = ?
        """, (current_step, language, metadata_json, appointment_id, call_sid))
    else:
        state_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO call_states (id, call_sid, current_step, language, metadata, appointment_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (state_id, call_sid, current_step, language, metadata_json, appointment_id))
    
    conn.commit()
    conn.close()


def update_appointment_status(appointment_id: str, status: str):
    """Update appointment status."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE appointments SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (status, appointment_id))
    conn.commit()
    conn.close()


if __name__ == "__main__":
    print("Initializing database...")
    init_db()
    seed_data()
