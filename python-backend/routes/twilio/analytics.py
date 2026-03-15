from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from auth import get_current_active_user
from database import DatabaseContextManager
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/ivr/analytics", tags=["ivr_analytics"])

@router.get("/summary")
def get_analytics_summary(
    timeframe: str = Query("30d", pattern="^(24h|7d|30d|90d|all)$"),
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """
    Get aggregated IVR metrics.
    - Total Calls
    - Average Duration (if applicable from session)
    """
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

    with DatabaseContextManager(read_only=True) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) as total_calls FROM call_states WHERE created_at >= %s",
            (start_date,)
        )
        total_calls = cursor.fetchone()["total_calls"]
        cursor.execute(
            "SELECT COUNT(*) as total_steps FROM ivr_analytics WHERE timestamp >= %s",
            (start_date,)
        )
        total_steps = cursor.fetchone()["total_steps"]
    return {
        "total_calls": total_calls or 0,
        "total_steps": total_steps or 0,
        "avg_steps_per_call": round(total_steps / total_calls, 1) if total_calls > 0 else 0
    }

@router.get("/nodes")
def get_node_analytics(
    timeframe: str = Query("30d", pattern="^(24h|7d|30d|90d|all)$"),
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """
    Get visit counts for each IVR node/step.
    """
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

    with DatabaseContextManager(read_only=True) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT node_name, COUNT(*) as visits
            FROM ivr_analytics
            WHERE timestamp >= %s
            GROUP BY node_name
            ORDER BY visits DESC
            """,
            (start_date,)
        )
        rows = cursor.fetchall()
    return [dict(row) for row in rows]
