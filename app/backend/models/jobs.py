"""Response models for the jobs router."""

from typing import Optional
from pydantic import BaseModel


class JobInfo(BaseModel):
    """Status of a single LakebaseOps job."""

    key: str
    job_id: int
    name: str
    status: str


class JobListResponse(BaseModel):
    """Response for GET /api/jobs/list."""

    jobs: list[JobInfo]
    error: Optional[str] = None


class TriggeredJob(BaseModel):
    """A successfully triggered job run."""

    key: str
    name: str
    job_id: int
    run_id: int


class JobError(BaseModel):
    """A job that failed to trigger."""

    key: str
    name: str
    error: str


class TriggerSyncResponse(BaseModel):
    """Response for POST /api/jobs/sync."""

    status: str
    total: int
    triggered_count: int
    error_count: int
    triggered: list[TriggeredJob]
    errors: list[JobError]


class RunStatus(BaseModel):
    """Status of a single job run."""

    run_id: int
    job_id: Optional[int] = None
    name: Optional[str] = None
    status: str
    life_cycle_state: Optional[str] = None
    result_state: Optional[str] = None
    message: str = ""


class PollSyncStatusResponse(BaseModel):
    """Response for GET /api/jobs/sync/status."""

    runs: list[RunStatus]
    overall: str
    error: Optional[str] = None
