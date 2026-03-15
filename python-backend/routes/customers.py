from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel, field_validator
from database import DatabaseContextManager, fmt_query
from auth import get_current_active_user
from security import sanitize_input
import uuid
import re

router = APIRouter(prefix="/api/customers", tags=["customers"])

class CustomerBase(BaseModel):
    name: str
    phone: str
    email: Optional[str] = None
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        if not v or len(v.strip()) < 2:
            raise ValueError('Name must be at least 2 characters long')
        if len(v) > 100:
            raise ValueError('Name must not exceed 100 characters')
        # Sanitize input to prevent XSS
        return sanitize_input(v, "text")
    
    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v):
        # Remove formatting
        cleaned = re.sub(r'\D', '', v)
        if len(cleaned) < 10 or len(cleaned) > 15:
            raise ValueError('Phone number must be between 10-15 digits')
        return cleaned
    
    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        if v:
            if len(v) > 255:
                raise ValueError('Email must not exceed 255 characters')
            # Sanitize email
            return sanitize_input(v, "email")
        return v

class CustomerCreate(CustomerBase):
    vehicle_make: Optional[str] = None
    vehicle_model: Optional[str] = None
    vehicle_color: Optional[str] = None
    vehicle_year: Optional[int] = None


class Customer(CustomerBase):
    id: str
    created_at: str
    vehicle_make: Optional[str] = None
    vehicle_model: Optional[str] = None
    vehicle_color: Optional[str] = None
    vehicle_year: Optional[int] = None

def normalize_phone(phone: str) -> str:
    # Remove all non-digit characters
    return re.sub(r'\D', '', phone)

@router.get("/search", response_model=List[Customer])
def search_customers(q: str = Query(..., min_length=3, max_length=50), current_user: dict = Depends(get_current_active_user)):
    """
    Search customers by name or phone. Minimum 3 characters required.
    
    RLS: All authenticated users can search (needed for appointment creation).
    Basic customer info (name, phone) is returned, not sensitive data.
    """
    # Sanitize search query
    sanitized_query = sanitize_input(q, "text")
    normalized_query = normalize_phone(q)
    
    with DatabaseContextManager(read_only=True) as conn:
        cursor = conn.cursor()
        cursor.execute(fmt_query("""
            SELECT * FROM customers 
            WHERE name LIKE ? OR phone LIKE ? OR phone LIKE ?
            LIMIT 10
        """), (f"%{sanitized_query}%", f"%{q}%", f"%{normalized_query}%"))
        rows = cursor.fetchall()
    return [dict(row) for row in rows]

@router.post("", response_model=Customer)
def create_customer(customer: CustomerCreate, current_user: dict = Depends(get_current_active_user)):
    # Normalize phone for storage
    clean_phone = normalize_phone(customer.phone)
    if not clean_phone:
         raise HTTPException(status_code=400, detail="Invalid phone number")

    customer_id = str(uuid.uuid4())
    try:
        with DatabaseContextManager() as conn:
            cursor = conn.cursor()
            cursor.execute(fmt_query(
                "INSERT INTO customers (id, name, phone, email) VALUES (?, ?, ?, ?)"),
                (customer_id, customer.name, clean_phone, customer.email)
            )
            cursor.execute(fmt_query("SELECT * FROM customers WHERE id = ?"), (customer_id,))
            new_customer = dict(cursor.fetchone())
        return new_customer
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower() or "UNIQUE" in str(e):
            raise HTTPException(status_code=400, detail="Customer with this phone number already exists")
        raise

@router.get("", response_model=List[Customer])
def list_customers(skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500), current_user: dict = Depends(get_current_active_user)):
    """List all customers with pagination. Maximum 500 per request."""
    with DatabaseContextManager(read_only=True) as conn:
        cursor = conn.cursor()
        cursor.execute(fmt_query("SELECT * FROM customers ORDER BY created_at DESC LIMIT ? OFFSET ?"), (limit, skip))
        rows = cursor.fetchall()
    return [dict(row) for row in rows]

@router.get("/{customer_id}", response_model=Customer)
def get_customer(customer_id: str, current_user: dict = Depends(get_current_active_user)):
    """Get customer by ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(fmt_query("SELECT * FROM customers WHERE id = ?"), (customer_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="Customer not found")
        
    return dict(row)

@router.get("/{customer_id}/history")
def get_customer_history(customer_id: str, current_user: dict = Depends(get_current_active_user)):
    """Get customer's appointment history."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # First check if customer exists
    cursor.execute(fmt_query("SELECT phone FROM customers WHERE id = ?"), (customer_id,))
    customer = cursor.fetchone()
    
    if not customer:
        conn.close()
        raise HTTPException(status_code=404, detail="Customer not found")
    
    # Get appointments by phone number
    cursor.execute(fmt_query("""
        SELECT * FROM appointments 
        WHERE phone_number = ?
        ORDER BY appointment_time DESC
    """), (customer["phone"],))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

@router.put("/{customer_id}", response_model=Customer)
def update_customer(customer_id: str, customer: CustomerCreate, current_user: dict = Depends(get_current_active_user)):
    """Update customer information."""
    clean_phone = normalize_phone(customer.phone)
    if not clean_phone:
        raise HTTPException(status_code=400, detail="Invalid phone number")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if customer exists
    cursor.execute(fmt_query("SELECT * FROM customers WHERE id = ?"), (customer_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Customer not found")
    
    try:
        cursor.execute(fmt_query("""
            UPDATE customers 
            SET name = ?, phone = ?, email = ?,
                vehicle_make = COALESCE(?, vehicle_make),
                vehicle_model = COALESCE(?, vehicle_model),
                vehicle_color = COALESCE(?, vehicle_color),
                vehicle_year = COALESCE(?, vehicle_year),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """), (
            customer.name, clean_phone, customer.email,
            customer.vehicle_make,
            customer.vehicle_model,
            customer.vehicle_color,
            customer.vehicle_year,
            customer_id,
        ))
        conn.commit()
    except Exception as e:
        conn.close()
        if "UNIQUE constraint failed" in str(e):
            raise HTTPException(status_code=400, detail="Customer with this phone number already exists")
        raise e
    
    # Return updated customer
    cursor.execute(fmt_query("SELECT * FROM customers WHERE id = ?"), (customer_id,))
    updated_customer = dict(cursor.fetchone())
    conn.close()
    
    return updated_customer

@router.delete("/{customer_id}")
def delete_customer(customer_id: str, current_user: dict = Depends(get_current_active_user)):
    """Delete a customer."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if customer exists
    cursor.execute(fmt_query("SELECT * FROM customers WHERE id = ?"), (customer_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Customer not found")
    
    cursor.execute(fmt_query("DELETE FROM customers WHERE id = ?"), (customer_id,))
    conn.commit()
    conn.close()
    
    return {"message": "Customer deleted successfully"}
