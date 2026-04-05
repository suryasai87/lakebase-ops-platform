"""Response models for the lakebase router."""

from typing import Any
from pydantic import BaseModel


class RealtimeStatsResponse(BaseModel):
    """Real-time PostgreSQL statistics from Lakebase endpoint.

    The shape varies depending on what the lakebase_service returns,
    so we use a flexible dict model.
    """

    class Config:
        extra = "allow"
