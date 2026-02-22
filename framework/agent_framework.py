"""
AgentFramework: Core coordination layer for the LakebaseOps multi-agent system.

Manages agent registration, scheduling, event routing, and shared state
across the Provisioning, Performance, and Health agents.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger("lakebase_ops")


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class EventType(Enum):
    BRANCH_CREATED = "branch_created"
    BRANCH_DELETED = "branch_deleted"
    BRANCH_PROTECTED = "branch_protected"
    SCHEMA_MIGRATED = "schema_migrated"
    THRESHOLD_BREACHED = "threshold_breached"
    VACUUM_COMPLETED = "vacuum_completed"
    INDEX_RECOMMENDATION = "index_recommendation"
    SYNC_DRIFT_DETECTED = "sync_drift_detected"
    COLD_DATA_ARCHIVED = "cold_data_archived"
    SELF_HEAL_EXECUTED = "self_heal_executed"
    PROVISIONING_COMPLETE = "provisioning_complete"


@dataclass
class TaskResult:
    """Result of an agent tool execution."""
    task_id: str
    agent_name: str
    tool_name: str
    status: TaskStatus
    message: str
    data: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    duration_seconds: float = 0.0

    def __str__(self):
        return f"[{self.status.value}] {self.agent_name}.{self.tool_name}: {self.message}"


@dataclass
class AgentTool:
    """Registered tool (method) within an agent."""
    name: str
    description: str
    handler: Callable
    schedule: Optional[str] = None  # Cron expression
    risk_level: str = "low"  # low, medium, high
    requires_approval: bool = False


@dataclass
class Event:
    """Inter-agent event for coordination."""
    event_type: EventType
    source_agent: str
    data: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class BaseAgent(ABC):
    """Abstract base class for all LakebaseOps agents."""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.tools: dict[str, AgentTool] = {}
        self._framework: Optional[AgentFramework] = None
        self._results: list[TaskResult] = []

    def register_tool(
        self,
        name: str,
        handler: Callable,
        description: str = "",
        schedule: Optional[str] = None,
        risk_level: str = "low",
        requires_approval: bool = False,
    ) -> None:
        """Register a tool method with this agent."""
        self.tools[name] = AgentTool(
            name=name,
            description=description,
            handler=handler,
            schedule=schedule,
            risk_level=risk_level,
            requires_approval=requires_approval,
        )

    async def execute_tool(self, tool_name: str, **kwargs) -> TaskResult:
        """Execute a registered tool and track results."""
        if tool_name not in self.tools:
            return TaskResult(
                task_id=str(uuid.uuid4())[:8],
                agent_name=self.name,
                tool_name=tool_name,
                status=TaskStatus.FAILED,
                message=f"Tool '{tool_name}' not found in {self.name}",
            )

        tool = self.tools[tool_name]
        task_id = str(uuid.uuid4())[:8]
        start = time.time()

        logger.info(f"[{self.name}] Executing: {tool_name}")

        try:
            if tool.requires_approval:
                logger.info(f"[{self.name}] Tool '{tool_name}' requires approval (risk: {tool.risk_level})")

            if asyncio.iscoroutinefunction(tool.handler):
                result_data = await tool.handler(**kwargs)
            else:
                result_data = tool.handler(**kwargs)

            duration = time.time() - start
            result = TaskResult(
                task_id=task_id,
                agent_name=self.name,
                tool_name=tool_name,
                status=TaskStatus.SUCCESS,
                message=f"Completed in {duration:.2f}s",
                data=result_data if isinstance(result_data, dict) else {"result": result_data},
                duration_seconds=duration,
            )
        except Exception as e:
            duration = time.time() - start
            result = TaskResult(
                task_id=task_id,
                agent_name=self.name,
                tool_name=tool_name,
                status=TaskStatus.FAILED,
                message=f"Failed: {str(e)}",
                duration_seconds=duration,
            )

        self._results.append(result)
        logger.info(str(result))
        return result

    def emit_event(self, event_type: EventType, data: dict = None) -> None:
        """Emit an event for other agents to consume."""
        if self._framework:
            event = Event(
                event_type=event_type,
                source_agent=self.name,
                data=data or {},
            )
            self._framework.dispatch_event(event)

    @abstractmethod
    def register_tools(self) -> None:
        """Register all tools for this agent. Must be implemented by subclasses."""
        pass

    @abstractmethod
    async def run_cycle(self, context: dict = None) -> list[TaskResult]:
        """Execute one full automation cycle. Must be implemented by subclasses."""
        pass

    def get_results_summary(self) -> dict:
        """Return summary of all task results."""
        total = len(self._results)
        success = sum(1 for r in self._results if r.status == TaskStatus.SUCCESS)
        failed = sum(1 for r in self._results if r.status == TaskStatus.FAILED)
        return {
            "agent": self.name,
            "total_tasks": total,
            "successful": success,
            "failed": failed,
            "success_rate": f"{(success / total * 100):.1f}%" if total > 0 else "N/A",
        }


class AgentFramework:
    """
    Central coordinator for the LakebaseOps multi-agent system.

    Manages:
    - Agent registration and lifecycle
    - Event routing between agents
    - Shared state (e.g., active projects, branch inventory)
    - Full automation cycle orchestration
    """

    def __init__(self, workspace_host: str = "", mock_mode: bool = True):
        self.workspace_host = workspace_host
        self.mock_mode = mock_mode
        self.agents: dict[str, BaseAgent] = {}
        self._event_handlers: dict[EventType, list[Callable]] = {}
        self._shared_state: dict[str, Any] = {
            "active_projects": [],
            "active_branches": {},
            "pending_approvals": [],
            "metrics_buffer": [],
        }
        self._event_log: list[Event] = []
        logger.info(f"AgentFramework initialized (mock_mode={mock_mode})")

    def register_agent(self, agent: BaseAgent) -> None:
        """Register an agent with the framework."""
        agent._framework = self
        agent.register_tools()
        self.agents[agent.name] = agent
        logger.info(f"Registered agent: {agent.name} ({len(agent.tools)} tools)")

    def subscribe(self, event_type: EventType, handler: Callable) -> None:
        """Subscribe to events from other agents."""
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)

    def dispatch_event(self, event: Event) -> None:
        """Dispatch an event to all subscribers."""
        self._event_log.append(event)
        logger.info(f"Event: {event.event_type.value} from {event.source_agent}")
        handlers = self._event_handlers.get(event.event_type, [])
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Event handler error: {e}")

    def get_shared_state(self, key: str) -> Any:
        """Get a value from shared state."""
        return self._shared_state.get(key)

    def set_shared_state(self, key: str, value: Any) -> None:
        """Set a value in shared state."""
        self._shared_state[key] = value

    async def run_full_cycle(self, context: dict = None) -> dict:
        """
        Execute a complete automation cycle across all agents.

        Order:
        1. Provisioning Agent (setup/maintenance)
        2. Performance Agent (metrics/analysis)
        3. Health Agent (monitoring/healing)
        """
        ctx = context or {}
        all_results = {}
        cycle_start = time.time()

        logger.info("=" * 70)
        logger.info("STARTING FULL AUTOMATION CYCLE")
        logger.info("=" * 70)

        # Phase 1: Provisioning
        if "ProvisioningAgent" in self.agents:
            logger.info("\n--- Phase 1: Provisioning & DevOps ---")
            results = await self.agents["ProvisioningAgent"].run_cycle(ctx)
            all_results["provisioning"] = results

        # Phase 2 & 3 can run in parallel: Performance + Health
        if "PerformanceAgent" in self.agents and "HealthAgent" in self.agents:
            logger.info("\n--- Phase 2+3: Performance & Health (parallel) ---")
            perf_task = self.agents["PerformanceAgent"].run_cycle(ctx)
            health_task = self.agents["HealthAgent"].run_cycle(ctx)
            perf_results, health_results = await asyncio.gather(perf_task, health_task)
            all_results["performance"] = perf_results
            all_results["health"] = health_results
        else:
            if "PerformanceAgent" in self.agents:
                logger.info("\n--- Phase 2: Performance ---")
                all_results["performance"] = await self.agents["PerformanceAgent"].run_cycle(ctx)
            if "HealthAgent" in self.agents:
                logger.info("\n--- Phase 3: Health ---")
                all_results["health"] = await self.agents["HealthAgent"].run_cycle(ctx)

        cycle_duration = time.time() - cycle_start

        # Summary
        logger.info("\n" + "=" * 70)
        logger.info("AUTOMATION CYCLE COMPLETE")
        logger.info(f"Total duration: {cycle_duration:.2f}s")
        for agent_name, agent in self.agents.items():
            summary = agent.get_results_summary()
            logger.info(f"  {agent_name}: {summary['successful']}/{summary['total_tasks']} succeeded")
        logger.info(f"  Events dispatched: {len(self._event_log)}")
        logger.info("=" * 70)

        return {
            "results": all_results,
            "duration_seconds": cycle_duration,
            "events": len(self._event_log),
            "agent_summaries": {
                name: agent.get_results_summary() for name, agent in self.agents.items()
            },
        }
