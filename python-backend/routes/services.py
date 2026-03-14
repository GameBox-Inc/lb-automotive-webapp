from typing import List, Optional
from fastapi import APIRouter, HTTPException
from database import get_db_connection, fmt_query
from models import Service, ServiceCreate
from cache import get_cached, set_cached, TTL_SERVICES, TTL_CATEGORIES, cache_key
from observability.monitoring import db_query_duration_seconds
from time import time

router = APIRouter(prefix="/api/services", tags=["services"])


@router.get("", response_model=List[Service])
def list_services(category: str = None, is_emergency: bool = None):
    """List all services with optional filters."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM services"
    params = []
    filters = []
    
    if category:
        filters.append("category = ?")
        params.append(category)
    
    if is_emergency is not None:
        filters.append("is_emergency = ?")
        params.append(int(is_emergency))
    
    if filters:
        query += " WHERE " + " AND ".join(filters)
    
    query += " ORDER BY category, name"
    
    cursor.execute(fmt_query(query), params)
    rows = cursor.fetchall()
    conn.close()

    services = []
    for row in rows:
        # Use .get() so missing columns (e.g. category, updated_at in some migrations) don't break the response
        r = dict(row) if not isinstance(row, dict) else row
        duration_val = r.get("duration_minutes") or r.get("duration")
        if duration_val is None:
            duration_val = 60
        try:
            duration_val = int(duration_val)
        except (TypeError, ValueError):
            duration_val = 60
        services.append(Service(
            id=r.get("id"),
            name=r.get("name") or "",
            description=r.get("description"),
            duration=duration_val,
            price=float(r.get("price") or 0),
            is_emergency=bool(r.get("is_emergency")),
            category=r.get("category") or "general",
            created_at=r.get("created_at"),
            updated_at=r.get("updated_at"),
        ))
    return services


@router.get("/categories")
async def get_service_categories():
    """Get unique service categories, cached for 24 hours"""
    key = "services:categories"
    
    # Try cache
    cached = await get_cached(key)
    if cached is not None:
        return cached
    
    # Query database in thread pool to avoid blocking async loop
    start_time = time()
    
    def fetch_categories():
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(fmt_query("SELECT DISTINCT category FROM services ORDER BY category"))
            rows = cursor.fetchall()
            conn.close()
            out = []
            for row in rows:
                r = dict(row) if not isinstance(row, dict) else row
                c = r.get("category")
                if c is not None:
                    out.append(str(c))
            return out if out else ["general"]
        except Exception:
            return ["general"]
    
    from starlette.concurrency import run_in_threadpool
    categories = await run_in_threadpool(fetch_categories)
    
    db_query_duration_seconds.labels(table='services', operation='select_distinct').observe(time() - start_time)
    
    # Cache for 24 hours
    await set_cached(key, categories, TTL_CATEGORIES)
    
    return categories


@router.get("/emergency", response_model=List[Service])
def list_emergency_services():
    """Get list of emergency services."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(fmt_query("SELECT * FROM services WHERE is_emergency = 1 ORDER BY name"))
    rows = cursor.fetchall()
    conn.close()

    services = []
    for row in rows:
        r = dict(row) if not isinstance(row, dict) else row
        duration_val = r.get("duration_minutes") or r.get("duration") or 60
        try:
            duration_val = int(duration_val)
        except (TypeError, ValueError):
            duration_val = 60
        services.append(Service(
            id=r.get("id"),
            name=r.get("name") or "",
            description=r.get("description"),
            duration=duration_val,
            price=float(r.get("price") or 0),
            is_emergency=bool(r.get("is_emergency")),
            category=r.get("category") or "general",
            created_at=r.get("created_at"),
            updated_at=r.get("updated_at"),
        ))
    return services


@router.get("/{service_id}", response_model=Service)
def get_service(service_id: str):
    """Get a specific service by ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(fmt_query("SELECT * FROM services WHERE id = ?"), (service_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Service not found")

    r = dict(row) if not isinstance(row, dict) else row
    duration_val = r.get("duration_minutes") or r.get("duration") or 60
    try:
        duration_val = int(duration_val)
    except (TypeError, ValueError):
        duration_val = 60
    return Service(
        id=r.get("id"),
        name=r.get("name") or "",
        description=r.get("description"),
        duration=duration_val,
        price=float(r.get("price") or 0),
        is_emergency=bool(r.get("is_emergency")),
        category=r.get("category") or "general",
        created_at=r.get("created_at"),
        updated_at=r.get("updated_at"),
    )


from auth import get_current_active_user, get_optional_user
from fastapi import Depends, status
from typing import Dict, Any

@router.post("", response_model=Service, status_code=status.HTTP_201_CREATED)
def create_service(
    service: ServiceCreate,
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Create a new service (Admin only)."""
    import logging
    from security import sanitize_input
    logger = logging.getLogger(__name__)

    if not current_user.get("is_admin"):
        logger.warning(f"Unauthorized service creation attempt by user: {current_user.get('username')}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to create services"
        )
    
    # Sanitize inputs
    service.name = sanitize_input(service.name, "text")
    if service.description:
        service.description = sanitize_input(service.description, "text")
    service.category = sanitize_input(service.category, "text")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    import uuid
    service_id = str(uuid.uuid4())
    
    cursor.execute(fmt_query("""
        INSERT INTO services (id, name, description, duration, price, is_emergency, category)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """), (
        service_id,
        service.name,
        service.description,
        service.duration,
        service.price,
        int(service.is_emergency),
        service.category
    ))
    
    conn.commit()
    
    cursor.execute(fmt_query("SELECT * FROM services WHERE id = ?"), (service_id,))
    row = cursor.fetchone()
    conn.close()

    logger.info(f"Service created by {current_user['username']}: {service.name}")

    r = dict(row) if row and not isinstance(row, dict) else (row or {})
    duration_val = int(r.get("duration_minutes") or r.get("duration") or 60)
    return Service(
        id=r.get("id"),
        name=r.get("name") or "",
        description=r.get("description"),
        duration=duration_val,
        price=float(r.get("price") or 0),
        is_emergency=bool(r.get("is_emergency")),
        category=r.get("category") or "general",
        created_at=r.get("created_at"),
        updated_at=r.get("updated_at"),
    )


from models import ServiceUpdate

@router.put("/{service_id}", response_model=Service)
def update_service(
    service_id: str,
    service_update: ServiceUpdate,
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Update a service (Admin only)."""
    import logging
    from security import sanitize_input
    logger = logging.getLogger(__name__)

    if not current_user.get("is_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update services"
        )
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check existence
    cursor.execute(fmt_query("SELECT * FROM services WHERE id = ?"), (service_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Service not found")
    
    # Build update query
    updates = []
    params = []
    
    if service_update.name is not None:
        updates.append("name = ?")
        params.append(sanitize_input(service_update.name, "text"))
    if service_update.description is not None:
        updates.append("description = ?")
        params.append(sanitize_input(service_update.description, "text"))
    if service_update.duration is not None:
        updates.append("duration = ?")
        params.append(service_update.duration)
    if service_update.price is not None:
        updates.append("price = ?")
        params.append(service_update.price)
    if service_update.is_emergency is not None:
        updates.append("is_emergency = ?")
        params.append(int(service_update.is_emergency))
    if service_update.category is not None:
        updates.append("category = ?")
        params.append(sanitize_input(service_update.category, "text"))
        
    if not updates:
        conn.close()
        raise HTTPException(status_code=400, detail="No updates provided")
        
    updates.append("updated_at = CURRENT_TIMESTAMP")
    params.append(service_id)
    
    query = f"UPDATE services SET {', '.join(updates)} WHERE id = ?"  # nosec B608
    cursor.execute(fmt_query(query), params)
    
    conn.commit()
    
    # Fetch updated
    cursor.execute(fmt_query("SELECT * FROM services WHERE id = ?"), (service_id,))
    row = cursor.fetchone()
    conn.close()
    
    logger.info(f"Service {service_id} updated by {current_user['username']}")

    r = dict(row) if row and not isinstance(row, dict) else (row or {})
    duration_val = int(r.get("duration_minutes") or r.get("duration") or 60)
    return Service(
        id=r.get("id"),
        name=r.get("name") or "",
        description=r.get("description"),
        duration=duration_val,
        price=float(r.get("price") or 0),
        is_emergency=bool(r.get("is_emergency")),
        category=r.get("category") or "general",
        created_at=r.get("created_at"),
        updated_at=r.get("updated_at"),
    )


@router.delete("/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_service(
    service_id: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Delete a service (Admin only)."""
    if not current_user.get("is_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete services"
        )
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check existence
    cursor.execute(fmt_query("SELECT id FROM services WHERE id = ?"), (service_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Service not found")
    
    cursor.execute(fmt_query("DELETE FROM services WHERE id = ?"), (service_id,))
    conn.commit()
    conn.close()
