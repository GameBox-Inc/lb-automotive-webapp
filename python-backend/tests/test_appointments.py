import pytest
from fastapi.testclient import TestClient
from main import app
from database import init_db
import os

client = TestClient(app)

# Helper to override auth
from auth import get_optional_user

def mock_get_optional_user():
    return {"id": "test_user_id", "phone_number": "555-1234", "is_admin": False}

app.dependency_overrides[get_optional_user] = mock_get_optional_user

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    # Ensure we use the test db defined in pytest.ini
    if os.path.exists("test.db"):
        try:
            os.remove("test.db")
        except PermissionError:
            pass
            
    init_db()
    from database import seed_data
    seed_data() # Seed to ensure services exist
    
    yield
    
    # Cleanup
    if os.path.exists("test.db"):
        try:
            os.remove("test.db")
        except PermissionError:
            print("Warning: Could not remove test.db due to file lock")
            pass

def test_create_appointment():
    response = client.post("/api/appointments", json={
        "customer_name": "Test Customer",
        "phone_number": "555-9999",
        "appointment_time": "2024-12-31T10:00:00",
        "service_type": "srv_oil_change",
        "notes": "Test Note",
        "emergency_request": False
    })
    
    # We might get 400 if service srv_oil_change is not in the seeded DB of init_db()
    # init_db seeds services, so it should exist if logic holds.
    # Otherwise we mock the validation or ensure seed_data is called.
    
    if response.status_code == 201:
        data = response.json()
        assert data["customer_name"] == "Test Customer"
        assert "id" in data
    else:
        # Debugging fallback if seed data missing
        print(response.json())
        assert response.status_code == 201

def test_get_appointments():
    # First create one
    client.post("/api/appointments", json={
        "customer_name": "Test Customer 2",
        "phone_number": "555-9999",
        "appointment_time": "2024-12-31T12:00:00",
        "service_type": "srv_oil_change",
        "emergency_request": False
    })
    
    response = client.get("/api/appointments")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
