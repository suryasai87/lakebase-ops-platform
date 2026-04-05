"""Response models for the performance router."""

from pydantic import BaseModel


class SlowQuery(BaseModel):
    """A slow query entry from pg_stat_history."""

    query: str
    queryid: str
    total_calls: str
    avg_exec_time_ms: str
    total_time_ms: str
    total_rows: str
    total_read_mb: str
    last_seen: str


SlowQueriesResponse = list[SlowQuery]


class RegressionEntry(BaseModel):
    """A query performance regression entry."""

    queryid: str
    baseline_ms: str
    recent_ms: str
    pct_change: str | None = None
    status: str


RegressionsResponse = list[RegressionEntry]
