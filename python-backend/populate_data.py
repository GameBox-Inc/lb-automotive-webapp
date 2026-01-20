
import sqlite3
import uuid
import os

DB_PATH = "data/lb_automotive.db"

COMMON_SERVICES = [
    # General Maintenance
    {"name": "Synthetic Oil Change", "category": "Maintenance", "description": "Full synthetic oil change up to 5 quarts, includes filter.", "duration": 45, "price": 89.99},
    {"name": "Standard Oil Change", "category": "Maintenance", "description": "Conventional oil change up to 5 quarts, includes filter.", "duration": 30, "price": 49.99},
    {"name": "Tire Rotation", "category": "Maintenance", "description": "Rotate tires to ensure even wear.", "duration": 30, "price": 29.99},
    {"name": "Wheel Alignment", "category": "Maintenance", "description": "Computerized wheel alignment.", "duration": 60, "price": 129.99},
    {"name": "Battery Replacement", "category": "Maintenance", "description": "Install new battery and check charging system.", "duration": 30, "price": 49.99},
    
    # Brakes
    {"name": "Brake Pad Replacement (Front)", "category": "Braking", "description": "Replace front brake pads and inspect rotors.", "duration": 90, "price": 189.99},
    {"name": "Brake Pad Replacement (Rear)", "category": "Braking", "description": "Replace rear brake pads and inspect rotors.", "duration": 90, "price": 189.99},
    {"name": "Brake Fluid Flush", "category": "Braking", "description": "Flush old brake fluid and replace with new.", "duration": 60, "price": 99.99},

    # Engine
    {"name": "Spark Plug Replacement", "category": "Engine", "description": "Replace spark plugs (4 cyl).", "duration": 60, "price": 149.99},
    {"name": "Coolant Flush", "category": "Engine", "description": "Drain and refill cooling system.", "duration": 60, "price": 119.99},
    {"name": "Check Engine Light Diagnostic", "category": "Diagnostic", "description": "Scan and diagnose check engine codes.", "duration": 45, "price": 89.99},

    # Suspension
    {"name": "Shock/Strut Replacement", "category": "Suspension", "description": "Replace worn shocks or struts (per axle).", "duration": 120, "price": 350.00},
]

def populate():
    if not os.path.exists(DB_PATH):
        print("Database not found!")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("Checking existing services...")
    cursor.execute("SELECT name FROM services")
    existing_names = {row[0] for row in cursor.fetchall()}

    added = 0
    for s in COMMON_SERVICES:
        if s["name"] not in existing_names:
            service_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO services (id, name, description, duration, price, is_emergency, category, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 0, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (service_id, s["name"], s["description"], s["duration"], s["price"], s["category"]))
            added += 1
            print(f"Added: {s['name']}")
    
    conn.commit()
    conn.close()
    print(f"\nDone! Added {added} new services.")

if __name__ == "__main__":
    populate()
