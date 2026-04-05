"""Pydantic response models for LakebaseOps API endpoints."""

from .health import HealthResponse
from .agents import AgentTool, AgentSummary, AgentsSummaryResponse
from .metrics import (
    MetricSnapshot,
    MetricsOverviewResponse,
    MetricTrendPoint,
    MetricsTrendsResponse,
)
from .performance import (
    SlowQuery,
    SlowQueriesResponse,
    RegressionEntry,
    RegressionsResponse,
)
from .indexes import (
    IndexRecommendationSummary,
    IndexRecommendationsResponse,
)
from .operations import (
    VacuumDaySummary,
    VacuumHistoryResponse,
    SyncTableStatus,
    SyncStatusResponse,
    BranchActivityDay,
    BranchActivityResponse,
    ArchivalDaySummary,
    ArchivalSummaryResponse,
)
from .lakebase import RealtimeStatsResponse
from .jobs import (
    JobInfo,
    JobListResponse,
    TriggeredJob,
    JobError,
    TriggerSyncResponse,
    RunStatus,
    PollSyncStatusResponse,
)

__all__ = [
    "HealthResponse",
    "AgentTool",
    "AgentSummary",
    "AgentsSummaryResponse",
    "MetricSnapshot",
    "MetricsOverviewResponse",
    "MetricTrendPoint",
    "MetricsTrendsResponse",
    "SlowQuery",
    "SlowQueriesResponse",
    "RegressionEntry",
    "RegressionsResponse",
    "IndexRecommendationSummary",
    "IndexRecommendationsResponse",
    "VacuumDaySummary",
    "VacuumHistoryResponse",
    "SyncTableStatus",
    "SyncStatusResponse",
    "BranchActivityDay",
    "BranchActivityResponse",
    "ArchivalDaySummary",
    "ArchivalSummaryResponse",
    "RealtimeStatsResponse",
    "JobInfo",
    "JobListResponse",
    "TriggeredJob",
    "JobError",
    "TriggerSyncResponse",
    "RunStatus",
    "PollSyncStatusResponse",
]
