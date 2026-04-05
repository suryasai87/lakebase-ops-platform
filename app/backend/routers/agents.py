"""Agents router — static agent metadata."""

from typing import List
from fastapi import APIRouter
from ..models.agents import AgentSummary
from ..services.agent_service import get_agents_summary

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("/summary", operation_id="agents_summary", response_model=List[AgentSummary])
def agents_summary():
    """Return metadata for the 3 LakebaseOps agents."""
    return get_agents_summary()
