"""Response models for the health router."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Response for GET /api/health."""

    status: str
    sql_warehouse: str
