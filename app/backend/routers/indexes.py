"""Indexes router — recommendation scorecard."""

from typing import List
from fastapi import APIRouter, Query
from ..models.indexes import IndexRecommendationSummary
from ..services.sql_service import execute_query, fqn, get_cached

router = APIRouter(prefix="/api/indexes", tags=["indexes"])


@router.get("/recommendations", operation_id="index_recommendations", response_model=List[IndexRecommendationSummary])
def index_recommendations(
    offset: int = Query(0, ge=0, description="Number of rows to skip"),
    limit: int = Query(100, ge=1, le=500, description="Maximum rows to return"),
):
    """Index recommendation summary by type and confidence."""
    safe_offset = int(offset)
    safe_limit = int(limit)

    def fetch():
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
        LIMIT :row_limit OFFSET :row_offset
        """
        return execute_query(sql, parameters=[
            {"name": "row_limit", "value": safe_limit, "type": "INT"},
            {"name": "row_offset", "value": safe_offset, "type": "INT"},
        ])
    return get_cached(f"index_recommendations_{safe_offset}_{safe_limit}", fetch, ttl=300)
