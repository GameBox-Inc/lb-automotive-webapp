
import sqlite3
import os
from passlib.context import CryptContext

# Point explicitly to the correct DB used by the app
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/lb_automotive.db")
DB_PATH = DATABASE_URL.replace("sqlite:///", "").replace("sqlite://", "")

pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")

def reset_admin():
    print(f"Connecting to {DB_PATH}...")
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Check if admin exists
        cursor.execute("SELECT * FROM users WHERE username = 'admin'")
        admin = cursor.fetchone()
        
        if not admin:
            print("Admin user not found! Creating one...")
            import uuid
            admin_id = str(uuid.uuid4())
            hashed_password = pwd_context.hash("admin123")
            cursor.execute("""
                INSERT INTO users (id, username, email, hashed_password, is_admin)
                VALUES (?, ?, ?, ?, ?)
            """, (admin_id, "admin", "admin@lbautomotive.com", hashed_password, 1))
            print("Admin user created with password 'admin123'")
        else:
            print("Admin user found. Details:")
            print(dict(admin))
            
            # Reset password
            print("Resetting password to 'admin123'...")
            hashed_password = pwd_context.hash("admin123")
            cursor.execute("UPDATE users SET hashed_password = ? WHERE username = 'admin'", (hashed_password,))
            print("Password updated.")

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error accessing database at {DB_PATH}: {e}")

if __name__ == "__main__":
    reset_admin()
