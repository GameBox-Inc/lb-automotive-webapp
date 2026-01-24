from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from auth import get_current_active_user
from database import get_db_connection
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/ivr/analytics", tags=["ivr_analytics"])

@router.get("/summary")
def get_analytics_summary(
    timeframe: str = Query("30d", regex="^(24h|7d|30d|90d|all)$"),
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """
    Get aggregated IVR metrics.
    - Total Calls
    - Average Duration (if applicable from session)
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Calculate start date
    if timeframe == "24h":
        start_date = (datetime.now() - timedelta(hours=24)).isoformat()
    elif timeframe == "7d":
        start_date = (datetime.now() - timedelta(days=7)).isoformat()
    elif timeframe == "30d":
        start_date = (datetime.now() - timedelta(days=30)).isoformat()
    elif timeframe == "90d":
        start_date = (datetime.now() - timedelta(days=90)).isoformat()
    else:
        start_date = "1970-01-01" 

    # We can get total calls from call_states or ivr_analytics
    # Using call_states gives unique calls
    query_calls = """
        SELECT COUNT(*) as total_calls
        FROM call_states
        WHERE created_at >= ?
    """
    cursor.execute(query_calls, (start_date,))
    total_calls = cursor.fetchone()["total_calls"]
    
    # Get total interactions (steps logged)
    query_interactions = """
        SELECT COUNT(*) as total_steps
        FROM ivr_analytics
        WHERE timestamp >= ?
    """
    cursor.execute(query_interactions, (start_date,))
    total_steps = cursor.fetchone()["total_steps"]

    conn.close()
    
    return {
        "total_calls": total_calls or 0,
        "total_steps": total_steps or 0,
        "avg_steps_per_call": round(total_steps / total_calls, 1) if total_calls > 0 else 0
    }

@router.get("/nodes")
def get_node_analytics(
    timeframe: str = Query("30d", regex="^(24h|7d|30d|90d|all)$"),
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """
    Get visit counts for each IVR node/step.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Calculate start date
    if timeframe == "24h":
        start_date = (datetime.now() - timedelta(hours=24)).isoformat()
    elif timeframe == "7d":
        start_date = (datetime.now() - timedelta(days=7)).isoformat()
    elif timeframe == "30d":
        start_date = (datetime.now() - timedelta(days=30)).isoformat()
    elif timeframe == "90d":
        start_date = (datetime.now() - timedelta(days=90)).isoformat()
    else:
        start_date = "1970-01-01"
        
    query = """
        SELECT node_name, COUNT(*) as visits
        FROM ivr_analytics
        WHERE timestamp >= ?
        GROUP BY node_name
        ORDER BY visits DESC
    """
    
    cursor.execute(query, (start_date,))
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]
