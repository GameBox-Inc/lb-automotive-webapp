
import sys
import os
import json
from fastapi import HTTPException
from starlette.datastructures import URL

# Add current directory to path
sys.path.append(os.getcwd())

from database import get_db_connection
from routes.services import list_services

print("Testing list_services()...")
try:
    services = list_services()
    print(f"Successfully retrieved {len(services)} services")
    for s in services:
        print(f" - {s.name} (${s.price})")
except Exception as e:
    print(f"Error calling list_services: {e}")
    import traceback
    traceback.print_exc()

print("\nTesting raw SQL query...")
try:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM services")
    rows = cursor.fetchall()
    print(f"Found {len(rows)} rows in DB")
    for row in rows:
        print(dict(row))
    conn.close()
except Exception as e:
    print(f"Error querying DB: {e}")
