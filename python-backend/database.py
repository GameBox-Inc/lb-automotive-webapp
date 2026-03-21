import os
import json
import threading
from datetime import datetime
from typing import Optional, Dict, Any, List
from contextvars import ContextVar
import uuid

# Context variable to store current user for RLS
current_user_context: ContextVar[Optional[Dict[str, Any]]] = ContextVar('current_user', default=None)
# Context for IVR/cron: when True, RLS policies allow full access via app.service_request
service_request_context: ContextVar[bool] = ContextVar('service_request', default=False)

# Strict database enforcement: PostgreSQL/Supabase only.
# Priority 1: Environment variable
# Priority 2: Vault injected secret at /vault/secrets/supabase.env
DATABASE_URL = os.getenv("DATABASE_URL")
DATABASE_READ_URL = os.getenv("DATABASE_READ_URL")
APP_DATABASE_URL = os.getenv("APP_DATABASE_URL")
APP_DATABASE_READ_URL = os.getenv("APP_DATABASE_READ_URL")

# Check for Vault-injected Supabase secret
SUPABASE_ENV = "/vault/secrets/supabase.env"
if os.path.exists(SUPABASE_ENV):
    try:
        with open(SUPABASE_ENV, "r") as f:
            for line in f:
                # Handle both 'export KEY="VAL"' and 'KEY="VAL"' formats
                clean_line = line.strip().replace("export ", "")
                if "DATABASE_URL=" in clean_line and not DATABASE_URL:
                    val = clean_line.split("=", 1)[1].strip().strip('"').strip("'")
                    if val: DATABASE_URL = val
                if "DATABASE_READ_URL=" in clean_line and not DATABASE_READ_URL:
                    val = clean_line.split("=", 1)[1].strip().strip('"').strip("'")
                    if val: DATABASE_READ_URL = val
                if "APP_DATABASE_URL=" in clean_line and not APP_DATABASE_URL:
                    val = clean_line.split("=", 1)[1].strip().strip('"').strip("'")
                    if val: APP_DATABASE_URL = val
                if "APP_DATABASE_READ_URL=" in clean_line and not APP_DATABASE_READ_URL:
                    val = clean_line.split("=", 1)[1].strip().strip('"').strip("'")
                    if val: APP_DATABASE_READ_URL = val
    except Exception as e:
        print(f"Error reading Vault secret: {e}")

# App uses lb_app role when APP_DATABASE_URL is set (RLS enforced); else uses DATABASE_URL (e.g. postgres, bypasses RLS).
_APP_BASE = (APP_DATABASE_URL or DATABASE_URL) or ""
_APP_READ = (APP_DATABASE_READ_URL or APP_DATABASE_URL or DATABASE_READ_URL or DATABASE_URL) or ""

# Defer hard failure to first DB use so the process can start and /ready can respond;
# otherwise K8s rollout hangs when app-secrets are not yet injected or misconfigured.
def _validate_db_url():
    url = _APP_BASE or DATABASE_URL
    if not url or not url.startswith("postgres"):
        raise ValueError("Valid PostgreSQL/Supabase connection string required (DATABASE_URL or APP_DATABASE_URL).")

DB_TYPE = "postgresql" if (_APP_BASE.startswith("postgres") or (DATABASE_URL and DATABASE_URL.startswith("postgres"))) else None
DB_PATH = _APP_BASE if _APP_BASE.startswith("postgres") else (DATABASE_URL if (DATABASE_URL and DATABASE_URL.startswith("postgres")) else None)
DB_READ_PATH = (_APP_READ if _APP_READ.startswith("postgres") else (DATABASE_READ_URL or DATABASE_URL)) if DB_PATH else None

# Standardize placeholders for PostgreSQL
SQL_PARAM = "%s"

# Mask credentials for security
def mask_url(url):
    if url and "@" in url:
        return "postgresql://*****@" + url.split("@")[-1]
    return url

if DB_PATH:
    print(f"DATABASE TYPE: {DB_TYPE}")
    print(f"PRIMARY DB: {mask_url(DB_PATH)}")
    if DB_READ_PATH:
        print(f"READ REPLICA: {mask_url(DB_READ_PATH)}")
else:
    print("DATABASE_URL not set or invalid; app will start but DB calls will fail until secrets are fixed.")


def fmt_query(query: str) -> str:
    """
    Format query placeholders based on database type.
    Replaces all '?' with '%s' if using PostgreSQL.
    """
    if DB_TYPE == "postgresql":
        return query.replace("?", "%s")
    return query


def _set_rls_session_vars(conn):
    """
    Set Postgres session variables for RLS (app.service_request, app.current_user_id, app.is_admin, app.staff_id).
    Called after opening a connection so lb_app role policies can allow/deny rows.
    """
    cur = conn.cursor()
    try:
        service = service_request_context.get()
        user = current_user_context.get() if not service else None
        if service:
            cur.execute("SET app.service_request = 'true'")
            cur.execute("SET app.is_admin = 'false'")
            cur.execute("SET app.current_user_id = ''")
            cur.execute("SET app.staff_id = ''")
        elif user:
            uid = (user.get("id") or "") if isinstance(user.get("id"), str) else str(user.get("id") or "")
            admin = "true" if user.get("is_admin") else "false"
            sid = (user.get("staff_id") or "") if isinstance(user.get("staff_id"), str) else str(user.get("staff_id") or "")
            cur.execute("SET app.service_request = 'false'")
            cur.execute("SET app.current_user_id = %s", (uid,))
            cur.execute("SET app.is_admin = %s", (admin,))
            cur.execute("SET app.staff_id = %s", (sid,))
        else:
            cur.execute("SET app.service_request = 'false'")
            cur.execute("SET app.is_admin = 'false'")
            cur.execute("SET app.current_user_id = ''")
            cur.execute("SET app.staff_id = ''")
    finally:
        cur.close()


_pool_lock = threading.Lock()
# One pool per distinct DSN (app primary, app read replica, admin primary, admin read).
_pools: Dict[str, Any] = {}


def _db_pool_enabled() -> bool:
    """Use psycopg2 ThreadedConnectionPool for PostgreSQL (disable via DB_POOL_ENABLED=false)."""
    return os.getenv("DB_POOL_ENABLED", "true").lower() in ("1", "true", "yes")


def _db_pool_bounds() -> tuple:
    mn = max(1, int(os.getenv("DB_POOL_MIN", "1")))
    mx = max(mn, int(os.getenv("DB_POOL_MAX", "20")))
    return mn, mx


def _resolve_connection_dsn(read_only: bool, use_app_role: bool) -> str:
    if use_app_role:
        return DB_READ_PATH if (read_only and DB_READ_PATH) else DB_PATH
    return (DATABASE_READ_URL or DATABASE_URL) if read_only else DATABASE_URL


class _PooledConnection:
    """
    Returned from get_db_connection when pooling is on. Delegates to the real psycopg2 connection;
    close() returns the connection to the pool (rollback first so session is clean).
    """

    __slots__ = ("_conn", "_pool", "_closed")

    def __init__(self, conn, pool):
        self._conn = conn
        self._pool = pool
        self._closed = False

    def close(self):
        if self._closed:
            return
        self._closed = True
        try:
            self._conn.rollback()
        except Exception:
            pass
        try:
            self._pool.putconn(self._conn)
        except Exception:
            try:
                self._conn.close()
            except Exception:
                pass

    def __getattr__(self, name):
        return getattr(self._conn, name)


def _get_threaded_pool(dsn: str):
    """Lazily create a ThreadedConnectionPool for this DSN."""
    import psycopg2.pool
    from psycopg2.extras import RealDictCursor

    with _pool_lock:
        if dsn not in _pools:
            mn, mx = _db_pool_bounds()
            _pools[dsn] = psycopg2.pool.ThreadedConnectionPool(
                mn,
                mx,
                dsn,
                cursor_factory=RealDictCursor,
            )
        return _pools[dsn]


def close_all_db_pools():
    """Close all pools (tests / graceful shutdown). New get_db_connection calls recreate pools."""
    global _pools
    with _pool_lock:
        to_close = list(_pools.values())
        _pools.clear()
        for p in to_close:
            try:
                p.closeall()
            except Exception:
                pass


def get_db_connection(read_only: bool = False, use_app_role: bool = True):
    """
    Get a PostgreSQL/Supabase database connection.
    If read_only is True and a read replica URL is set, use it.
    When use_app_role=True (default), uses APP_DATABASE_URL or DATABASE_URL and sets RLS session vars.
    When use_app_role=False (e.g. init_db/migrations), uses DATABASE_URL only and does not set RLS vars.

    When DB_POOL_ENABLED is true (default), connections come from a per-DSN ThreadedConnectionPool.
    RLS session variables are applied on every checkout for use_app_role=True so pooled connections
    never leak identity between requests.
    """
    _validate_db_url()
    import psycopg2
    from psycopg2.extras import RealDictCursor

    target_url = _resolve_connection_dsn(read_only, use_app_role)
    if not target_url or not str(target_url).startswith("postgres"):
        raise ValueError("Valid PostgreSQL connection string required for get_db_connection.")

    if _db_pool_enabled():
        pool = _get_threaded_pool(target_url)
        conn = pool.getconn()
        try:
            if use_app_role:
                _set_rls_session_vars(conn)
            return _PooledConnection(conn, pool)
        except Exception:
            try:
                pool.putconn(conn)
            except Exception:
                try:
                    conn.close()
                except Exception:
                    pass
            raise

    conn = psycopg2.connect(target_url, cursor_factory=RealDictCursor)
    if use_app_role:
        _set_rls_session_vars(conn)
    return conn


class DatabaseContextManager:
    """
    Context manager for database connections to ensure proper cleanup.
    Use this for all request-scoped DB access; avoids connection leaks on exception.

    Usage:
        with DatabaseContextManager() as conn:
            cursor = conn.cursor()
            cursor.execute(...)
        # commit on success, rollback and close on exception

    For read-only operations use read_only=True to prefer the read replica when configured.
    """
    def __init__(self, read_only: bool = False):
        self.conn = None
        self.read_only = read_only
    
    def __enter__(self):
        self.conn = get_db_connection(read_only=self.read_only)
        return self.conn
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            if exc_type:
                self.conn.rollback()
            else:
                self.conn.commit()
            self.conn.close()
        return False


def init_db():
    """Initialize the database with schema (uses postgres/DATABASE_URL, not app RLS role)."""
    conn = get_db_connection(use_app_role=False)
    cursor = conn.cursor()

    # Create staff table first (for foreign keys)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS staff (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            role TEXT DEFAULT 'mechanic',
            active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

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
            vehicle_make TEXT,
            vehicle_model TEXT,
            vehicle_color TEXT,
            vehicle_year INTEGER,
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
            started_at TEXT,
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

    # Create case_status_history table (audit trail for repair chain)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS case_status_history (
            id TEXT PRIMARY KEY,
            case_id TEXT NOT NULL,
            old_status TEXT,
            new_status TEXT NOT NULL,
            changed_at TEXT DEFAULT CURRENT_TIMESTAMP,
            changed_by TEXT,
            FOREIGN KEY (case_id) REFERENCES cases (id)
        )
    """)

    # Create staff_schedules table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS staff_schedules (
            id TEXT PRIMARY KEY,
            staff_id TEXT NOT NULL,
            day_of_week INTEGER NOT NULL, 
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            is_off INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (staff_id) REFERENCES staff (id),
            UNIQUE(staff_id, day_of_week)
        )
    """)

    # Blackout periods: shop-wide or per-technician blocks where no bookings allowed
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS blackouts (
            id TEXT PRIMARY KEY,
            reason TEXT,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            scope TEXT DEFAULT 'shop', -- 'shop' | 'technician'
            technician_id TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (technician_id) REFERENCES staff (id)
        )
    """)

    # ---- Schema migrations for central scheduling engine (idempotent) ----
    # Services: ensure duration_minutes exists to support variable durations
    cursor.execute(fmt_query("ALTER TABLE services ADD COLUMN IF NOT EXISTS duration_minutes INTEGER"))

    # Staff: ensure role and active flags exist (for legacy DBs that predate staff table evolution)
    cursor.execute(fmt_query("ALTER TABLE staff ADD COLUMN IF NOT EXISTS role TEXT DEFAULT 'mechanic'"))
    cursor.execute(fmt_query("ALTER TABLE staff ADD COLUMN IF NOT EXISTS active INTEGER DEFAULT 1"))

    # Appointments: enrich with scheduling engine fields
    cursor.execute(fmt_query("ALTER TABLE appointments ADD COLUMN IF NOT EXISTS service_id TEXT"))
    cursor.execute(fmt_query("ALTER TABLE appointments ADD COLUMN IF NOT EXISTS technician_id TEXT"))
    cursor.execute(fmt_query("ALTER TABLE appointments ADD COLUMN IF NOT EXISTS start_time TEXT"))
    cursor.execute(fmt_query("ALTER TABLE appointments ADD COLUMN IF NOT EXISTS end_time TEXT"))
    cursor.execute(fmt_query("ALTER TABLE appointments ADD COLUMN IF NOT EXISTS source TEXT"))  # 'web' | 'ivr' | 'kiosk' | 'admin'

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

    # Create business_hours table 
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

    # ---- Schema migrations for central scheduling engine (idempotent) ----
    # Services: ensure duration_minutes exists to support variable durations
    cursor.execute(fmt_query("ALTER TABLE services ADD COLUMN IF NOT EXISTS duration_minutes INTEGER"))

    # Staff: ensure role and active flags exist (for legacy DBs that predate staff table evolution)
    cursor.execute(fmt_query("ALTER TABLE staff ADD COLUMN IF NOT EXISTS role TEXT DEFAULT 'mechanic'"))
    cursor.execute(fmt_query("ALTER TABLE staff ADD COLUMN IF NOT EXISTS active INTEGER DEFAULT 1"))

    # Appointments: enrich with scheduling engine + vehicle fields
    cursor.execute(fmt_query("ALTER TABLE appointments ADD COLUMN IF NOT EXISTS service_id TEXT"))
    cursor.execute(fmt_query("ALTER TABLE appointments ADD COLUMN IF NOT EXISTS technician_id TEXT"))
    cursor.execute(fmt_query("ALTER TABLE appointments ADD COLUMN IF NOT EXISTS start_time TEXT"))
    cursor.execute(fmt_query("ALTER TABLE appointments ADD COLUMN IF NOT EXISTS end_time TEXT"))
    cursor.execute(fmt_query("ALTER TABLE appointments ADD COLUMN IF NOT EXISTS source TEXT"))
    cursor.execute(fmt_query("ALTER TABLE appointments ADD COLUMN IF NOT EXISTS vehicle_make TEXT"))
    cursor.execute(fmt_query("ALTER TABLE appointments ADD COLUMN IF NOT EXISTS vehicle_model TEXT"))
    cursor.execute(fmt_query("ALTER TABLE appointments ADD COLUMN IF NOT EXISTS vehicle_color TEXT"))
    cursor.execute(fmt_query("ALTER TABLE appointments ADD COLUMN IF NOT EXISTS vehicle_year INTEGER"))

    conn.commit()

    conn.commit()
    conn.close()
    print("Database initialized successfully!")


def seed_data():
    """Seed the database with initial data (uses postgres/DATABASE_URL, not app RLS role)."""
    conn = get_db_connection(use_app_role=False)
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
    for col in ("vehicle_make", "vehicle_model", "vehicle_color"):
        cursor.execute(fmt_query(f"ALTER TABLE customers ADD COLUMN IF NOT EXISTS {col} TEXT"))
    cursor.execute(fmt_query("ALTER TABLE customers ADD COLUMN IF NOT EXISTS vehicle_year INTEGER"))

    # Ensure blackouts table exists for environments that only run seed_data()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS blackouts (
            id TEXT PRIMARY KEY,
            reason TEXT,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            scope TEXT DEFAULT 'shop',
            technician_id TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (technician_id) REFERENCES staff (id)
        )
    """)

    # ---- Data backfill for central scheduling engine (idempotent) ----
    # 1) Services: copy duration into duration_minutes if empty
    try:
        cursor.execute(fmt_query("UPDATE services SET duration_minutes = duration WHERE duration_minutes IS NULL"))
    except Exception:
        # Column might not exist yet on very old SQLite; safe to ignore
        pass

    # 2) Appointments: populate start_time and source where missing
    try:
        cursor.execute(fmt_query("""
            UPDATE appointments
            SET start_time = appointment_time
            WHERE start_time IS NULL
        """))
    except Exception:
        pass

    try:
        cursor.execute(fmt_query("""
            UPDATE appointments
            SET source = COALESCE(source, 'web')
        """))
    except Exception:
        pass

    # Check if services already exist
    cursor.execute("SELECT COUNT(*) as count FROM services")
    row = cursor.fetchone()
    count = row['count'] if isinstance(row, dict) else row[0]
    if count == 0:
        # Insert sample services
        services = [
            ('srv_oil_change', 'Oil Change', 'Standard oil change and filter replacement', 60, 49.99, 0, 'Maintenance'),
            ('srv_tire_rotation', 'Tire Rotation', 'Rotate all four tires to ensure even wear', 30, 29.99, 0, 'Maintenance'),
            ('srv_brake_inspection', 'Brake Inspection', 'Comprehensive brake system inspection', 45, 39.99, 0, 'Safety'),
            ('srv_emergency_roadside', 'Emergency Roadside Assistance', '24/7 roadside assistance', 15, 99.99, 1, 'Emergency'),
            ('srv_flat_tire', 'Flat Tire Repair', 'Flat tire repair or replacement', 30, 49.99, 1, 'Emergency'),
            ('srv_battery', 'Battery Replacement', 'Car battery replacement', 45, 79.99, 1, 'Emergency'),
        ]

        for s in services:
            if DB_TYPE == "postgresql":
                cursor.execute("""
                    INSERT INTO services (id, name, description, duration, price, is_emergency, category)
                    VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING
                """, s)
            else:
                cursor.execute("""
                    INSERT OR IGNORE INTO services (id, name, description, duration, price, is_emergency, category)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, s)

    # Seed initial staff if empty
    cursor.execute("SELECT COUNT(*) as count FROM staff")
    row = cursor.fetchone()
    count = row['count'] if isinstance(row, dict) else row[0]
    if count == 0:
        import uuid
        staff_members = [
            (str(uuid.uuid4()), 'John Mechanic', 'mechanic', 1),
            (str(uuid.uuid4()), 'Sarah Advisor', 'advisor', 1),
            (str(uuid.uuid4()), 'Mike Tech', 'mechanic', 1)
        ]
        if DB_TYPE == "postgresql":
            cursor.executemany("INSERT INTO staff (id, name, role, active) VALUES (%s, %s, %s, %s)", staff_members)
        else:
            cursor.executemany("INSERT INTO staff (id, name, role, active) VALUES (?, ?, ?, ?)", staff_members)

    # Check if admin user exists
    cursor.execute("SELECT COUNT(*) as count FROM users WHERE username = 'admin'")
    row = cursor.fetchone()
    count = row['count'] if isinstance(row, dict) else row[0]
    if count == 0:
        # Insert default admin user (password: admin123)
        # WARNING: This is a weak default password. User should change it immediately.
        # In production, consider generating a random password or requiring setup.
        from passlib.context import CryptContext
        import uuid
        import warnings
        
        warnings.warn(
            "Default admin user created with weak password 'admin123'. "
            "Change this password immediately in production!",
            UserWarning
        )
        
        pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")
        admin_id = str(uuid.uuid4())
        admin_password = pwd_context.hash("admin123")
        
        if DB_TYPE == "postgresql":
            cursor.execute("""
                INSERT INTO users (id, username, email, hashed_password, is_admin)
                VALUES (%s, %s, %s, %s, %s)
            """, (admin_id, "admin", "admin@lbautomotive.com", admin_password, 1))
        else:
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
        ('ivr_voice', '', 'Override TTS voice; blank = male by language (Polly.Matthew en, Polly.Miguel es)'),
        ('ivr_language', 'en-US', 'Language for text-to-speech'),
        ('staff_count', '5', 'Number of staff members available per day'),
        ('timezone', 'America/New_York', 'Business timezone'),
        ('ivr_latency_masking_enabled', 'true', 'Enable latency masking for IVR (true/false)'),
        ('ivr_filler_mode', 'hybrid', 'Filler mode (voice_only, sound_only, hybrid)'),
        ('ivr_filler_phrases', '["One moment...", "Let me check that for you...", "Got it, one second...", "Understood, just a moment.", "Checking our system, one second please."]', 'JSON list of filler phrases'),
        ('ivr_thinking_sound_url', 'https://twilio.kozytherocket.space/audio/thinking.mp3', 'URL for background thinking sound'),
        ('ivr_processing_timeout', '10', 'Max seconds to wait for AI response before fallback'),
        ('ivr_speech_timeout', 'auto', 'Twilio speechTimeout: auto or seconds (e.g. 3)'),
        ('ivr_repair_max_retries', '2', 'Max timeouts before offering transfer'),
        ('ivr_transfer_number', '', 'E.164 number for representative transfer (Dial)'),
        ('ivr_transfer_timeout', '30', 'Seconds to ring before transfer no-answer (10-60)'),
        ('ivr_language_prompt_enabled', 'false', 'Play language selection at start (true/false)'),
        ('ivr_recording_disclaimer_en', 'This call may be recorded for quality purposes.', 'Recording disclaimer (English)'),
        ('ivr_recording_disclaimer_es', 'Esta llamada puede ser grabada para fines de calidad.', 'Recording disclaimer (Spanish)'),
        # IVR TTS: Twilio Polly (default) vs ElevenLabs + <Play> — see docs/architecture/voice-flow.md
        ('ivr_tts_provider', 'twilio', 'twilio | elevenlabs — default twilio (Polly) until validated'),
        ('ivr_tts_canary_prompts', 'welcome', 'Comma-separated prompt keys for ElevenLabs (e.g. welcome); use * for all'),
        ('elevenlabs_voice_id_en', '', 'ElevenLabs voice ID for English (required for elevenlabs on EN prompts)'),
        ('elevenlabs_voice_id_es', '', 'ElevenLabs voice ID for Spanish'),
        ('elevenlabs_model_id', 'eleven_multilingual_v2', 'ElevenLabs model_id for TTS'),
        ('ivr_tts_audio_ttl_seconds', '600', 'TTL seconds for MP3 at /api/twilio/tts-audio/{id} (Twilio fetch window)'),
        ('ivr_tts_static_url_welcome_en', '', 'Optional HTTPS URL to pre-generated welcome MP3 (skips API; English)'),
        ('ivr_tts_static_url_welcome_es', '', 'Optional HTTPS URL to pre-generated welcome MP3 (Spanish)'),
    ]

    for key, value, desc in default_settings:
        if DB_TYPE == "postgresql":
            cursor.execute("""
                INSERT INTO settings (key, value, description) 
                VALUES (%s, %s, %s) ON CONFLICT DO NOTHING
            """, (key, value, desc))
        else:
            cursor.execute("INSERT OR IGNORE INTO settings (key, value, description) VALUES (?, ?, ?)", (key, value, desc))

    # Seed default business hours (Monday-Friday: 8 AM - 6 PM, Saturday-Sunday: Closed)
    default_business_hours = [
        (0, '08:00', '18:00', 0),  # Monday
        (1, '08:00', '18:00', 0),  # Tuesday
        (2, '08:00', '18:00', 0),  # Wednesday
        (3, '08:00', '18:00', 0),  # Thursday
        (4, '08:00', '18:00', 0),  # Friday
        (5, None, None, 1),         # Saturday - Closed
        (6, None, None, 1),         # Sunday - Closed
    ]
    
    for day, open_time, close_time, is_closed in default_business_hours:
        if DB_TYPE == "postgresql":
            cursor.execute("""
                INSERT INTO business_hours (day_of_week, opening_time, closing_time, is_closed)
                VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING
            """, (day, open_time, close_time, is_closed))
        else:
            cursor.execute("""
                INSERT OR IGNORE INTO business_hours (day_of_week, opening_time, closing_time, is_closed)
                VALUES (?, ?, ?, ?)
            """, (day, open_time, close_time, is_closed))

    conn.commit()
    conn.close()
    print("Database seeded successfully!")





def get_call_state(call_sid: str) -> Optional[dict]:
    """Get call state from database using Read Replica if available."""
    with DatabaseContextManager(read_only=True) as conn:
        cursor = conn.cursor()
        cursor.execute(fmt_query("""
            SELECT id, call_sid, current_step, language, metadata, appointment_id, 
                   last_response_time, created_at, updated_at
            FROM call_states WHERE call_sid = ?
        """), (call_sid,))
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
            "updated_at": row["updated_at"]
        }
    return None


def upsert_call_state(call_sid: str, current_step: str, language: str = "en", 
                      metadata: dict = None, appointment_id: str = None):
    """Create or update call state on the Primary DB."""
    with DatabaseContextManager(read_only=False) as conn:
        cursor = conn.cursor()
        
        # Check existing (Small optimization: we can do this on primary since we're about to write)
        cursor.execute(fmt_query("SELECT id FROM call_states WHERE call_sid = ?"), (call_sid,))
        existing = cursor.fetchone()
        
        metadata_json = json.dumps(metadata or {})
    
        import uuid
        if existing:
            cursor.execute(fmt_query("""
                UPDATE call_states 
                SET current_step = ?, language = ?, metadata = ?, appointment_id = ?,
                    last_response_time = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE call_sid = ?
            """), (current_step, language, metadata_json, appointment_id, call_sid))
        else:
            state_id = str(uuid.uuid4())
            cursor.execute(fmt_query("""
                INSERT INTO call_states (id, call_sid, current_step, language, metadata, appointment_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """), (state_id, call_sid, current_step, language, metadata_json, appointment_id))
        
        conn.commit()


def get_setting(key: str, default: str = None) -> str:
    """Retrieve a setting value from the database using Read Replica."""
    with DatabaseContextManager(read_only=True) as conn:
        cursor = conn.cursor()
        cursor.execute(fmt_query("SELECT value FROM settings WHERE key = ?"), (key,))
        row = cursor.fetchone()
        return row["value"] if row else default


def update_appointment_status(appointment_id: str, status: str):
    """Update appointment status on the Primary DB."""
    with DatabaseContextManager(read_only=False) as conn:
        cursor = conn.cursor()
        cursor.execute(fmt_query("UPDATE appointments SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?"), (status, appointment_id))
        conn.commit()




def migrate_schema():
    """Apply schema migrations for new IVR features."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Migration 1: Add decision_path to call_states
    try:
        cursor.execute("ALTER TABLE call_states ADD COLUMN decision_path TEXT DEFAULT '[]'")
        print("- Added decision_path column to call_states")
        conn.commit()
    except Exception as e:
        conn.rollback()
        if "already exists" not in str(e).lower() and "duplicate column" not in str(e).lower():
            print(f"  Note: decision_path column issue: {e}")
    
    # Migration 2: Add time slot columns to appointments
    try:
        cursor.execute("ALTER TABLE appointments ADD COLUMN time_slot_start TEXT")
        print("- Added time_slot_start column to appointments")
        conn.commit()
    except Exception as e:
        conn.rollback()
        if "already exists" not in str(e).lower() and "duplicate column" not in str(e).lower():
            print(f"  Note: time_slot_start column issue: {e}")
    
    try:
        cursor.execute("ALTER TABLE appointments ADD COLUMN time_slot_end TEXT")
        print("- Added time_slot_end column to appointments")
        conn.commit()
    except Exception as e:
        conn.rollback()
        if "already exists" not in str(e).lower() and "duplicate column" not in str(e).lower():
            print(f"  Note: time_slot_end column issue: {e}")
    
    try:
        cursor.execute("ALTER TABLE appointments ADD COLUMN slot_duration_minutes INTEGER DEFAULT 30")
        print("- Added slot_duration_minutes column to appointments")
        conn.commit()
    except Exception as e:
        conn.rollback()
        if "already exists" not in str(e).lower() and "duplicate column" not in str(e).lower():
            print(f"  Note: slot_duration_minutes column issue: {e}")
    
    # Migration 3: Create ivr_analytics table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ivr_analytics (
            id TEXT PRIMARY KEY,
            call_sid TEXT NOT NULL,
            node_name TEXT NOT NULL,
            decision_taken TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            duration_seconds INTEGER,
            FOREIGN KEY (call_sid) REFERENCES call_states (call_sid)
        )
    """)
    print("- Created ivr_analytics table")
    
    # Create indexes for IVR analytics
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ivr_analytics_call_sid ON ivr_analytics(call_sid)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ivr_analytics_node ON ivr_analytics(node_name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ivr_analytics_timestamp ON ivr_analytics(timestamp)")
    print("- Created indexes for ivr_analytics")
    
    conn.commit()
    conn.close()
    print("Schema migrations completed!")


if __name__ == "__main__":
    print("Initializing database...")
    init_db()
    print("Running schema migrations...")
    migrate_schema()
    seed_data()
