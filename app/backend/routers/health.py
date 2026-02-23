"""Health check router."""

from fastapi import APIRouter
from ..services.sql_service import execute_query

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health_check():
    """Basic health check — verifies SQL warehouse connectivity."""
    try:
        rows = execute_query("SELECT 1 AS ok")
        if rows and rows[0].get("ok") == "1":
            return {"status": "healthy", "sql_warehouse": "connected"}
    except Exception:
        pass
    return {"status": "degraded", "sql_warehouse": "unreachable"}
