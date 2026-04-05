"""Pydantic response models for LakebaseOps API endpoints."""

from .agents import AgentsSummaryResponse, AgentSummary, AgentTool
from .health import HealthResponse
from .indexes import (
    IndexRecommendationsResponse,
    IndexRecommendationSummary,
)
from .jobs import (
    JobError,
    JobInfo,
    JobListResponse,
    PollSyncStatusResponse,
    RunStatus,
    TriggeredJob,
    TriggerSyncResponse,
)
from .lakebase import RealtimeStatsResponse
from .metrics import (
    MetricSnapshot,
    MetricsOverviewResponse,
    MetricsTrendsResponse,
    MetricTrendPoint,
)
from .operations import (
    ArchivalDaySummary,
    ArchivalSummaryResponse,
    BranchActivityDay,
    BranchActivityResponse,
    SyncStatusResponse,
    SyncTableStatus,
    VacuumDaySummary,
    VacuumHistoryResponse,
)
from .performance import (
    RegressionEntry,
    RegressionsResponse,
    SlowQueriesResponse,
    SlowQuery,
)

__all__ = [
    "AgentSummary",
    "AgentTool",
    "AgentsSummaryResponse",
    "ArchivalDaySummary",
    "ArchivalSummaryResponse",
    "BranchActivityDay",
    "BranchActivityResponse",
    "HealthResponse",
    "IndexRecommendationSummary",
    "IndexRecommendationsResponse",
    "JobError",
    "JobInfo",
    "JobListResponse",
    "MetricSnapshot",
    "MetricTrendPoint",
    "MetricsOverviewResponse",
    "MetricsTrendsResponse",
    "PollSyncStatusResponse",
    "RealtimeStatsResponse",
    "RegressionEntry",
    "RegressionsResponse",
    "RunStatus",
    "SlowQueriesResponse",
    "SlowQuery",
    "SyncStatusResponse",
    "SyncTableStatus",
    "TriggerSyncResponse",
    "TriggeredJob",
    "VacuumDaySummary",
    "VacuumHistoryResponse",
]
