
import sys
import os

# Add python-backend to path
sys.path.append(os.getcwd())

from auth import verify_password, create_access_token
from database import get_db_connection
from datetime import timedelta

def check_admin_login():
    print("\n--- Checking Admin Login ---")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT hashed_password FROM users WHERE username='admin'")
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        print("❌ Admin user not found!")
        return False
        
    hashed = row[0]
    is_valid = verify_password('admin123', hashed)
    print(f"Password 'admin123' valid: {is_valid}")
    return is_valid

def check_services_endpoint():
    print("\n--- Checking Services Endpoint ---")
    # Simulate service retrieval logic from routes/services.py
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT count(*) FROM services")
    count = cursor.fetchone()[0]
    conn.close()
    print(f"Services in DB: {count}")
    return count > 0

if __name__ == "__main__":
    check_admin_login()
    check_services_endpoint()
