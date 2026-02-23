"""Agents router — static agent metadata."""

from fastapi import APIRouter
from ..services.agent_service import get_agents_summary

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("/summary")
def agents_summary():
    """Return metadata for the 3 LakebaseOps agents."""
    return get_agents_summary()
