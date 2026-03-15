
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, Query
from auth import get_current_active_user
from database import get_db_connection
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/reports", tags=["reports"])

@router.get("/summary")
def get_report_summary(
    timeframe: str = Query("30d", pattern="^(7d|30d|90d|all)$"),
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """
    Get aggregated repair metrics.
    Returns:
    - Total Revenue (sum of service prices)
    - Total Repairs (count of completed cases)
    - Average Duration (minutes)
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Calculate start date based on timeframe
    if timeframe == "7d":
        start_date = (datetime.now() - timedelta(days=7)).isoformat()
    elif timeframe == "30d":
        start_date = (datetime.now() - timedelta(days=30)).isoformat()
    elif timeframe == "90d":
        start_date = (datetime.now() - timedelta(days=90)).isoformat()
    else:
        start_date = "1970-01-01" # All time
        
    # PostgreSQL: session duration in minutes (SQLite julianday not available)
    query = """
        SELECT 
            COUNT(c.id) as total_repairs,
            SUM(s.price) as total_revenue,
            AVG(s.duration) as avg_duration,
            AVG(EXTRACT(EPOCH FROM (c.closed_at::timestamptz - (COALESCE(c.started_at, c.created_at)::timestamptz))) / 60) as avg_session_time
        FROM cases c
        JOIN appointments a ON c.appointment_id = a.id
        LEFT JOIN services s ON (a.service_id = s.id OR (a.service_id IS NULL AND a.service_type = s.name))
        WHERE c.status = 'completed'
        AND c.closed_at >= %s
    """
    cursor.execute(query, (start_date,))
    row = cursor.fetchone()
    conn.close()
    
    return {
        "total_repairs": row["total_repairs"] or 0,
        "total_revenue": row["total_revenue"] or 0,
        "avg_duration": round(row["avg_duration"] or 0),
        "avg_session_time": round(row["avg_session_time"] or 0)
    }

@router.get("/history")
def get_report_history(
    timeframe: str = Query("30d", pattern="^(7d|30d|90d|all)$"),
    limit: int = 50,
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """
    Get recent repair history for the report table.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Calculate start date based on timeframe (shared logic with /summary)
    if timeframe == "7d":
        start_date = (datetime.now() - timedelta(days=7)).isoformat()
    elif timeframe == "30d":
        start_date = (datetime.now() - timedelta(days=30)).isoformat()
    elif timeframe == "90d":
        start_date = (datetime.now() - timedelta(days=90)).isoformat()
    else:
        start_date = "1970-01-01"  # All time
    
    # PostgreSQL: actual_duration in minutes (SQLite julianday not available)
    query = """
        SELECT 
            c.case_number,
            c.closed_at,
            a.customer_name,
            COALESCE(s.name, a.service_type) as service_name,
            s.price,
            s.duration,
            (EXTRACT(EPOCH FROM (c.closed_at::timestamptz - (COALESCE(c.started_at, c.created_at)::timestamptz))) / 60)::INTEGER as actual_duration
        FROM cases c
        JOIN appointments a ON c.appointment_id = a.id
        LEFT JOIN services s ON (a.service_id = s.id OR (a.service_id IS NULL AND a.service_type = s.name))
        WHERE c.status = 'completed'
        AND c.closed_at >= %s
        ORDER BY c.closed_at DESC
        LIMIT %s
    """
    cursor.execute(query, (start_date, limit))
    rows = cursor.fetchall()
    conn.close()
    
    history = []
    for row in rows:
        history.append({
            "case_number": row["case_number"],
            "date": row["closed_at"],
            "customer": row["customer_name"],
            "service": row["service_name"] or "Unknown Service",
            "price": row["price"] or 0,
            "duration": row["duration"] or 0,
            "actual_duration": row["actual_duration"] or 0
        })
        
    return history
