"""Response models for the operations router."""

from typing import Optional
from pydantic import BaseModel


class VacuumDaySummary(BaseModel):
    """Vacuum operations summary for a single day and operation type."""

    vacuum_date: str
    operation_type: str
    operations: str
    successful: str
    failed: str
    avg_duration_s: str


VacuumHistoryResponse = list[VacuumDaySummary]


class SyncTableStatus(BaseModel):
    """Sync validation status for a table pair."""

    source_table: str
    target_table: str
    source_count: str
    target_count: str
    count_drift: str
    lag_minutes: str
    checksum_match: str
    status: str
    validated_at: str


SyncStatusResponse = list[SyncTableStatus]


class BranchActivityDay(BaseModel):
    """Branch lifecycle events for a single day and event type."""

    event_date: str
    event_type: str
    events: str
    unique_branches: str


BranchActivityResponse = list[BranchActivityDay]


class ArchivalDaySummary(BaseModel):
    """Archival operations summary for a single day and source table."""

    archive_date: str
    source_table: str
    total_rows_archived: str
    total_bytes_reclaimed: str
    mb_reclaimed: str
    operations: str


ArchivalSummaryResponse = list[ArchivalDaySummary]
