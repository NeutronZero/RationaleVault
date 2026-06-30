"""
G3 — Workspace Context Compiler Tests.

ContextCompiler.compile() bridges WorkspaceState → WorkspaceContext.
"""
from __future__ import annotations

import pytest
from datetime import datetime, timezone

from rationalevault.projections.workspace import WorkspaceState
from rationalevault.workspace.context_compiler import ContextCompiler
from rationalevault.workspace.models import WorkspaceContext


REF_TIME = datetime(2026, 6, 26, 12, 0, 0, tzinfo=timezone.utc)


def _make_state(
    workspace_id: str = "WS-TEST",
    workspace_name: str = "Test",
    workspace_status: str = "ACTIVE",
    **kwargs: any,
) -> WorkspaceState:
    defaults = dict(
        workspace_id=workspace_id,
        workspace_name=workspace_name,
        workspace_status=workspace_status,
        compiled_at=REF_TIME.isoformat(),
    )
    defaults.update(kwargs)
    return WorkspaceState(**defaults)


# ── ContextCompiler Tests ────────────────────────────────────────────────

class TestContextCompiler:
    def test_compiles_context(self):
        state = _make_state()
        ctx, payload = ContextCompiler.compile(
            workspace_state=state,
            agent_id="agent-a",
            reference_time=REF_TIME,
        )
        assert ctx.agent_id == "agent-a"
        assert ctx.context_id.startswith("WSCTX-")

    def test_deterministic_output(self):
        state = _make_state(active_decisions=["DEC-001"])
        ctx1, _ = ContextCompiler.compile(
            workspace_state=state,
            agent_id="agent-a",
            goals=["goal-1"],
            reference_time=REF_TIME,
        )
        ctx2, _ = ContextCompiler.compile(
            workspace_state=state,
            agent_id="agent-a",
            goals=["goal-1"],
            reference_time=REF_TIME,
        )
        assert ctx1.to_dict() == ctx2.to_dict()

    def test_inherits_decisions(self):
        state = _make_state(active_decisions=["DEC-001", "DEC-002", "DEC-003"])
        ctx, _ = ContextCompiler.compile(
            workspace_state=state, agent_id="a", reference_time=REF_TIME
        )
        assert ctx.open_decisions == ["DEC-001", "DEC-002", "DEC-003"]

    def test_inherits_executions(self):
        state = _make_state(running_executions=["SKE-001", "SKE-002"])
        ctx, _ = ContextCompiler.compile(
            workspace_state=state, agent_id="a", reference_time=REF_TIME
        )
        assert ctx.running_executions == ["SKE-001", "SKE-002"]

    def test_inherits_reflections(self):
        state = _make_state(pending_reflections=["RCAND-001"])
        ctx, _ = ContextCompiler.compile(
            workspace_state=state, agent_id="a", reference_time=REF_TIME
        )
        assert ctx.pending_reflections == ["RCAND-001"]

    def test_inherits_knowledge(self):
        state = _make_state(active_knowledge=["KNOW-001", "KNOW-002"])
        ctx, _ = ContextCompiler.compile(
            workspace_state=state, agent_id="a", reference_time=REF_TIME
        )
        assert ctx.recent_knowledge == ["KNOW-001", "KNOW-002"]

    def test_goals_sorted(self):
        state = _make_state()
        ctx, _ = ContextCompiler.compile(
            workspace_state=state,
            agent_id="a",
            goals=["z-goal", "a-goal", "m-goal"],
            reference_time=REF_TIME,
        )
        assert ctx.goals == ["a-goal", "m-goal", "z-goal"]

    def test_empty_goals(self):
        state = _make_state()
        ctx, _ = ContextCompiler.compile(
            workspace_state=state, agent_id="a", reference_time=REF_TIME
        )
        assert ctx.goals == []

    def test_planner_summary_active(self):
        state = _make_state(planner_policy_id="PPOL-001")
        ctx, _ = ContextCompiler.compile(
            workspace_state=state, agent_id="a", reference_time=REF_TIME
        )
        assert "PPOL-001" in ctx.planner_policy_summary

    def test_planner_summary_none(self):
        state = _make_state(planner_policy_id=None)
        ctx, _ = ContextCompiler.compile(
            workspace_state=state, agent_id="a", reference_time=REF_TIME
        )
        assert "No active" in ctx.planner_policy_summary

    def test_session_id_propagated(self):
        state = _make_state()
        ctx, _ = ContextCompiler.compile(
            workspace_state=state,
            agent_id="a",
            session_id="WSSSN-001",
            reference_time=REF_TIME,
        )
        assert ctx.session_id == "WSSSN-001"

    def test_snapshot_id_propagated(self):
        state = _make_state()
        ctx, _ = ContextCompiler.compile(
            workspace_state=state,
            agent_id="a",
            snapshot_id="WSSNP-001",
            reference_time=REF_TIME,
        )
        assert ctx.snapshot_id == "WSSNP-001"

    def test_empty_session_snapshot(self):
        state = _make_state()
        ctx, _ = ContextCompiler.compile(
            workspace_state=state, agent_id="a", reference_time=REF_TIME
        )
        assert ctx.session_id == ""
        assert ctx.snapshot_id == ""

    def test_payload_matches_context(self):
        state = _make_state(active_decisions=["DEC-001"])
        ctx, payload = ContextCompiler.compile(
            workspace_state=state,
            agent_id="agent-x",
            goals=["goal-1"],
            reference_time=REF_TIME,
        )
        assert payload.context_id == ctx.context_id
        assert payload.agent_id == ctx.agent_id
        assert payload.goals == ctx.goals
        assert payload.open_decisions == ctx.open_decisions

    def test_context_is_frozen(self):
        state = _make_state()
        ctx, _ = ContextCompiler.compile(
            workspace_state=state, agent_id="a", reference_time=REF_TIME
        )
        with pytest.raises(AttributeError):
            ctx.agent_id = "hacked"

    def test_empty_state(self):
        state = _make_state()
        ctx, _ = ContextCompiler.compile(
            workspace_state=state, agent_id="a", reference_time=REF_TIME
        )
        assert ctx.open_decisions == []
        assert ctx.running_executions == []
        assert ctx.pending_reflections == []
        assert ctx.recent_knowledge == []

    def test_full_state(self):
        state = _make_state(
            active_decisions=["DEC-001"],
            running_executions=["SKE-001"],
            pending_reflections=["RCAND-001"],
            active_knowledge=["KNOW-001"],
            planner_policy_id="PPOL-001",
        )
        ctx, _ = ContextCompiler.compile(
            workspace_state=state,
            agent_id="a",
            goals=["g1"],
            reference_time=REF_TIME,
        )
        assert len(ctx.open_decisions) == 1
        assert len(ctx.running_executions) == 1
        assert len(ctx.pending_reflections) == 1
        assert len(ctx.recent_knowledge) == 1
        assert "PPOL-001" in ctx.planner_policy_summary

    def test_to_dict_roundtrip(self):
        state = _make_state(
            active_decisions=["DEC-001"],
            running_executions=["SKE-001"],
        )
        ctx, _ = ContextCompiler.compile(
            workspace_state=state,
            agent_id="a",
            goals=["g1"],
            reference_time=REF_TIME,
        )
        d = ctx.to_dict()
        assert d["agent_id"] == "a"
        assert d["goals"] == ["g1"]
        assert d["open_decisions"] == ["DEC-001"]
        assert d["running_executions"] == ["SKE-001"]
