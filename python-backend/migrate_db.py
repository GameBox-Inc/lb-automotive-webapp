import sqlite3
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./lb_automotive.db")
DB_PATH = DATABASE_URL.replace("sqlite:///", "").replace("sqlite://", "")

def migrate():
    print(f"Connecting to {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if staff_id column exists in users table
    cursor.execute("PRAGMA table_info(users)")
    columns = [info[1] for info in cursor.fetchall()]
    
    if 'staff_id' not in columns:
        print("Adding staff_id column to users table...")
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN staff_id TEXT")
            print("Successfully added staff_id column.")
        except Exception as e:
            print(f"Error adding column: {e}")
    else:
        print("staff_id column already exists in users table.")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    migrate()
