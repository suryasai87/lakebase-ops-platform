"""Tests for AgentFramework: event bus, subscribe/dispatch, tool registration, cycle orchestration."""

import pytest

from framework.agent_framework import (
    AgentTool,
    BaseAgent,
    Event,
    EventType,
    TaskResult,
    TaskStatus,
)

# ---------------------------------------------------------------------------
# Minimal concrete agent for testing
# ---------------------------------------------------------------------------


class _StubAgent(BaseAgent):
    """Minimal agent that registers a single echo tool."""

    def __init__(self, name: str = "StubAgent"):
        super().__init__(name=name, description="test stub")
        self.cycle_called = False

    def register_tools(self) -> None:
        self.register_tool("echo", self._echo, description="return input")
        self.register_tool("fail", self._fail, description="always fails", risk_level="high")
        self.register_tool("approval", self._echo, description="needs approval", requires_approval=True)

    @staticmethod
    def _echo(**kwargs) -> dict:
        return kwargs

    @staticmethod
    def _fail(**kwargs):
        raise RuntimeError("intentional failure")

    async def run_cycle(self, context=None):
        self.cycle_called = True
        r = await self.execute_tool("echo", msg="cycle")
        return [r]


# ---------------------------------------------------------------------------
# BaseAgent basics
# ---------------------------------------------------------------------------


class TestBaseAgent:
    def test_register_tool_adds_to_dict(self):
        agent = _StubAgent()
        agent.register_tools()
        assert "echo" in agent.tools
        assert "fail" in agent.tools
        assert isinstance(agent.tools["echo"], AgentTool)

    def test_tool_metadata(self):
        agent = _StubAgent()
        agent.register_tools()
        assert agent.tools["fail"].risk_level == "high"
        assert agent.tools["approval"].requires_approval is True

    @pytest.mark.asyncio
    async def test_execute_tool_success(self):
        agent = _StubAgent()
        agent.register_tools()
        result = await agent.execute_tool("echo", msg="hello")
        assert result.status == TaskStatus.SUCCESS
        assert result.data == {"msg": "hello"}
        assert result.agent_name == "StubAgent"

    @pytest.mark.asyncio
    async def test_execute_tool_failure(self):
        agent = _StubAgent()
        agent.register_tools()
        result = await agent.execute_tool("fail")
        assert result.status == TaskStatus.FAILED
        assert "intentional failure" in result.message

    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self):
        agent = _StubAgent()
        agent.register_tools()
        result = await agent.execute_tool("nonexistent")
        assert result.status == TaskStatus.FAILED
        assert "not found" in result.message

    def test_results_summary_empty(self):
        agent = _StubAgent()
        summary = agent.get_results_summary()
        assert summary["total_tasks"] == 0
        assert summary["success_rate"] == "N/A"

    @pytest.mark.asyncio
    async def test_results_summary_after_executions(self):
        agent = _StubAgent()
        agent.register_tools()
        await agent.execute_tool("echo", x=1)
        await agent.execute_tool("fail")
        summary = agent.get_results_summary()
        assert summary["total_tasks"] == 2
        assert summary["successful"] == 1
        assert summary["failed"] == 1

    @pytest.mark.asyncio
    async def test_duration_is_tracked(self):
        agent = _StubAgent()
        agent.register_tools()
        result = await agent.execute_tool("echo")
        assert result.duration_seconds >= 0


# ---------------------------------------------------------------------------
# Event bus: subscribe / dispatch
# ---------------------------------------------------------------------------


class TestEventBus:
    def test_subscribe_and_dispatch(self, framework):
        received = []
        framework.subscribe(EventType.BRANCH_CREATED, lambda e: received.append(e))
        event = Event(
            event_type=EventType.BRANCH_CREATED,
            source_agent="test",
            data={"branch": "ci-pr-1"},
        )
        framework.dispatch_event(event)
        assert len(received) == 1
        assert received[0].data["branch"] == "ci-pr-1"

    def test_multiple_subscribers(self, framework):
        count = {"a": 0, "b": 0}
        framework.subscribe(EventType.THRESHOLD_BREACHED, lambda e: count.__setitem__("a", count["a"] + 1))
        framework.subscribe(EventType.THRESHOLD_BREACHED, lambda e: count.__setitem__("b", count["b"] + 1))
        framework.dispatch_event(Event(event_type=EventType.THRESHOLD_BREACHED, source_agent="test"))
        assert count["a"] == 1
        assert count["b"] == 1

    def test_dispatch_unsubscribed_event(self, framework):
        # Should not raise
        framework.dispatch_event(Event(event_type=EventType.VACUUM_COMPLETED, source_agent="test"))

    def test_handler_error_does_not_block_others(self, framework):
        results = []

        def bad_handler(e):
            raise ValueError("boom")

        def good_handler(e):
            results.append(e)

        framework.subscribe(EventType.BRANCH_DELETED, bad_handler)
        framework.subscribe(EventType.BRANCH_DELETED, good_handler)
        framework.dispatch_event(Event(event_type=EventType.BRANCH_DELETED, source_agent="test"))
        assert len(results) == 1  # good_handler still ran

    def test_event_log_tracking(self, framework):
        assert len(framework._event_log) == 0
        framework.dispatch_event(Event(event_type=EventType.BRANCH_CREATED, source_agent="x"))
        framework.dispatch_event(Event(event_type=EventType.BRANCH_DELETED, source_agent="x"))
        assert len(framework._event_log) == 2

    def test_agent_emit_event(self, framework):
        received = []
        framework.subscribe(EventType.BRANCH_CREATED, lambda e: received.append(e))
        agent = _StubAgent()
        framework.register_agent(agent)
        agent.emit_event(EventType.BRANCH_CREATED, {"test": True})
        assert len(received) == 1
        assert received[0].source_agent == "StubAgent"


# ---------------------------------------------------------------------------
# Agent registration
# ---------------------------------------------------------------------------


class TestAgentRegistration:
    def test_register_agent(self, framework):
        agent = _StubAgent()
        framework.register_agent(agent)
        assert "StubAgent" in framework.agents
        assert agent._framework is framework
        # register_tools should have been called
        assert len(agent.tools) > 0

    def test_register_multiple_agents(self, framework):
        a1 = _StubAgent("Agent1")
        a2 = _StubAgent("Agent2")
        framework.register_agent(a1)
        framework.register_agent(a2)
        assert len(framework.agents) == 2


# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------


class TestSharedState:
    def test_get_set(self, framework):
        framework.set_shared_state("key1", [1, 2, 3])
        assert framework.get_shared_state("key1") == [1, 2, 3]

    def test_get_missing_key(self, framework):
        assert framework.get_shared_state("nonexistent") is None

    def test_default_shared_state_keys(self, framework):
        assert framework.get_shared_state("active_projects") == []
        assert framework.get_shared_state("pending_approvals") == []


# ---------------------------------------------------------------------------
# Full cycle orchestration
# ---------------------------------------------------------------------------


class TestFullCycle:
    @pytest.mark.asyncio
    async def test_run_full_cycle_with_stub_agents(self, framework):
        prov = _StubAgent("ProvisioningAgent")
        perf = _StubAgent("PerformanceAgent")
        health = _StubAgent("HealthAgent")
        framework.register_agent(prov)
        framework.register_agent(perf)
        framework.register_agent(health)

        result = await framework.run_full_cycle()
        assert "results" in result
        assert "duration_seconds" in result
        assert result["duration_seconds"] >= 0
        assert prov.cycle_called
        assert perf.cycle_called
        assert health.cycle_called

    @pytest.mark.asyncio
    async def test_run_full_cycle_partial_agents(self, framework):
        perf = _StubAgent("PerformanceAgent")
        framework.register_agent(perf)
        result = await framework.run_full_cycle()
        assert "results" in result
        assert perf.cycle_called

    @pytest.mark.asyncio
    async def test_run_full_cycle_no_agents(self, framework):
        result = await framework.run_full_cycle()
        assert result["events"] == 0


# ---------------------------------------------------------------------------
# TaskResult
# ---------------------------------------------------------------------------


class TestTaskResult:
    def test_str_representation(self):
        r = TaskResult(
            task_id="abc",
            agent_name="TestAgent",
            tool_name="do_thing",
            status=TaskStatus.SUCCESS,
            message="ok",
        )
        s = str(r)
        assert "success" in s.lower()
        assert "TestAgent" in s
        assert "do_thing" in s
