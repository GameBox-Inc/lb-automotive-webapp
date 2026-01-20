from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel, validator
from database import get_db_connection
from auth import get_current_active_user
from security import sanitize_input
import uuid
import re

router = APIRouter(prefix="/api/customers", tags=["customers"])

class CustomerBase(BaseModel):
    name: str
    phone: str
    email: Optional[str] = None
    
    @validator('name')
    def validate_name(cls, v):
        if not v or len(v.strip()) < 2:
            raise ValueError('Name must be at least 2 characters long')
        if len(v) > 100:
            raise ValueError('Name must not exceed 100 characters')
        # Sanitize input to prevent XSS
        return sanitize_input(v, "text")
    
    @validator('phone')
    def validate_phone(cls, v):
        # Remove formatting
        cleaned = re.sub(r'\D', '', v)
        if len(cleaned) < 10 or len(cleaned) > 15:
            raise ValueError('Phone number must be between 10-15 digits')
        return cleaned
    
    @validator('email')
    def validate_email(cls, v):
        if v:
            if len(v) > 255:
                raise ValueError('Email must not exceed 255 characters')
            # Sanitize email
            return sanitize_input(v, "email")
        return v

class CustomerCreate(CustomerBase):
    pass

class Customer(CustomerBase):
    id: str
    created_at: str

class Customer(CustomerBase):
    id: str
    created_at: str

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
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Search by name or phone (handling partially formatted phone numbers)
    # Using parameterized queries to prevent SQL injection
    cursor.execute("""
        SELECT * FROM customers 
        WHERE name LIKE ? OR phone LIKE ? OR phone LIKE ?
        LIMIT 10
    """, (f"%{sanitized_query}%", f"%{q}%", f"%{normalized_query}%"))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

@router.post("", response_model=Customer)
def create_customer(customer: CustomerCreate, current_user: dict = Depends(get_current_active_user)):
    # Normalize phone for storage
    clean_phone = normalize_phone(customer.phone)
    if not clean_phone:
         raise HTTPException(status_code=400, detail="Invalid phone number")

    customer_id = str(uuid.uuid4())
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            "INSERT INTO customers (id, name, phone, email) VALUES (?, ?, ?, ?)",
            (customer_id, customer.name, clean_phone, customer.email)
        )
        conn.commit()
    except Exception as e:
        conn.close()
        if "UNIQUE constraint failed" in str(e):
             raise HTTPException(status_code=400, detail="Customer with this phone number already exists")
        raise e
    
    cursor.execute("SELECT * FROM customers WHERE id = ?", (customer_id,))
    new_customer = dict(cursor.fetchone())
    conn.close()
    
    return new_customer

@router.get("", response_model=List[Customer])
def list_customers(skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500), current_user: dict = Depends(get_current_active_user)):
    """List all customers with pagination. Maximum 500 per request."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM customers ORDER BY created_at DESC LIMIT ? OFFSET ?", (limit, skip))
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

@router.get("/{customer_id}", response_model=Customer)
def get_customer(customer_id: str, current_user: dict = Depends(get_current_active_user)):
    """Get customer by ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM customers WHERE id = ?", (customer_id,))
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
    cursor.execute("SELECT phone FROM customers WHERE id = ?", (customer_id,))
    customer = cursor.fetchone()
    
    if not customer:
        conn.close()
        raise HTTPException(status_code=404, detail="Customer not found")
    
    # Get appointments by phone number
    cursor.execute("""
        SELECT * FROM appointments 
        WHERE phone_number = ?
        ORDER BY appointment_time DESC
    """, (customer["phone"],))
    
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
    cursor.execute("SELECT * FROM customers WHERE id = ?", (customer_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Customer not found")
    
    try:
        cursor.execute("""
            UPDATE customers 
            SET name = ?, phone = ?, email = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (customer.name, clean_phone, customer.email, customer_id))
        conn.commit()
    except Exception as e:
        conn.close()
        if "UNIQUE constraint failed" in str(e):
            raise HTTPException(status_code=400, detail="Customer with this phone number already exists")
        raise e
    
    # Return updated customer
    cursor.execute("SELECT * FROM customers WHERE id = ?", (customer_id,))
    updated_customer = dict(cursor.fetchone())
    conn.close()
    
    return updated_customer

@router.delete("/{customer_id}")
def delete_customer(customer_id: str, current_user: dict = Depends(get_current_active_user)):
    """Delete a customer."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if customer exists
    cursor.execute("SELECT * FROM customers WHERE id = ?", (customer_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Customer not found")
    
    cursor.execute("DELETE FROM customers WHERE id = ?", (customer_id,))
    conn.commit()
    conn.close()
    
    return {"message": "Customer deleted successfully"}
