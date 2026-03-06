import sqlite3
import os

# Point to the database file in the parent directory (relative to where script is run from root)
DB_NAME = "python-backend/lb_automotive.db"

def migrate():
    if not os.path.exists(DB_NAME):
        print(f"Database {DB_NAME} not found. cwd: {os.getcwd()}")
        return

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    try:
        # Check if column exists
        cursor.execute("PRAGMA table_info(appointments)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if "notes" not in columns:
            print("Adding 'notes' column to appointments table...")
            cursor.execute("ALTER TABLE appointments ADD COLUMN notes TEXT")
            conn.commit()
            print("Column 'notes' added successfully.")
        else:
            print("Column 'notes' already exists.")
            
    except Exception as e:
        print(f"Migration failed: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
