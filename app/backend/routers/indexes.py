"""Indexes router — recommendation scorecard."""

from fastapi import APIRouter
from ..services.sql_service import execute_query, fqn, get_cached

router = APIRouter(prefix="/api/indexes", tags=["indexes"])


def _fetch_recommendations():
    sql = f"""
    SELECT recommendation_type, confidence,
           COUNT(*) AS count,
           SUM(CASE WHEN status = 'pending_review' THEN 1 ELSE 0 END) AS pending_review,
           SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) AS approved,
           SUM(CASE WHEN status = 'executed' THEN 1 ELSE 0 END) AS executed,
           SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) AS rejected
    FROM {fqn('index_recommendations')}
    WHERE created_at > CURRENT_TIMESTAMP - INTERVAL 30 DAYS
    GROUP BY recommendation_type, confidence
    ORDER BY count DESC
    """
    return execute_query(sql)


@router.get("/recommendations")
def index_recommendations():
    """Index recommendation summary by type and confidence."""
    return get_cached("index_recommendations", _fetch_recommendations, ttl=300)
