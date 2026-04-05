"""Response models for the agents router."""

from typing import Optional
from pydantic import BaseModel


class AgentTool(BaseModel):
    """Metadata for a single agent tool."""

    name: str
    module: str
    schedule: Optional[str] = None
    risk: str


class AgentSummary(BaseModel):
    """Summary metadata for one LakebaseOps agent."""

    name: str
    description: str
    tool_count: int
    icon: str
    color: str
    tools: list[AgentTool]


AgentsSummaryResponse = list[AgentSummary]
