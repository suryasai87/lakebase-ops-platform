"""Lakebase router — real-time PG stats via direct connection."""

from fastapi import APIRouter
from ..services.lakebase_service import get_realtime_stats

router = APIRouter(prefix="/api/lakebase", tags=["lakebase"])


@router.get("/realtime")
def realtime_stats():
    """Live PostgreSQL stats from the Lakebase endpoint (no cache)."""
    return get_realtime_stats()
