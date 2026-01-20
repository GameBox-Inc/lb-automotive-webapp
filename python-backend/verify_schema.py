
import sqlite3
import os

DB_PATH = "data/lb_automotive.db"
if not os.path.exists(DB_PATH):
    print(f"Database not found at {DB_PATH}")
    exit(1)

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

try:
    cursor.execute("PRAGMA table_info(services)")
    columns = cursor.fetchall()
    print("Columns in services table:")
    for col in columns:
        print(f"  {col[1]} ({col[2]})")
except Exception as e:
    print(f"Error: {e}")
finally:
    conn.close()
