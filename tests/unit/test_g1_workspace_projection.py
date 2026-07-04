"""
G1 — Workspace Projection Tests.

WorkspaceState = WorkspaceStateProjection.project(workspace, ...)

Deterministic snapshot of what is happening in a workspace right now.
"""
from __future__ import annotations

import hashlib
import pytest
from datetime import datetime, timezone

from rationalevault.workspace.models import Workspace, WorkspaceStatus
from rationalevault.projections.workspace import (
    WorkspaceState,
    WorkspaceStateProjection,
)


# ── Helpers ──────────────────────────────────────────────────────────────

def _make_workspace(
    name: str = "Test Workspace",
    status: WorkspaceStatus = WorkspaceStatus.ACTIVE,
    agent_ids: list[str] | None = None,
    project_ids: list[str] | None = None,
    created_at: str = "2026-06-26T12:00:00Z",
    updated_at: str = "2026-06-26T12:30:00Z",
) -> Workspace:
    ws_id = Workspace.generate_workspace_id(name, created_at)
    return Workspace(
        workspace_id=ws_id,
        name=name,
        description="Test workspace for projection",
        status=status,
        agent_ids=agent_ids or ["agent-a", "agent-b"],
        project_ids=project_ids or ["proj-1"],
        created_at=created_at,
        updated_at=updated_at,
    )


# ── WorkspaceState Model Tests ──────────────────────────────────────────

class TestWorkspaceStateModel:
    def test_frozen(self):
        ws = _make_workspace()
        state = WorkspaceState(
            workspace_id=ws.workspace_id,
            workspace_name=ws.name,
            workspace_status=ws.status.value,
            compiled_at="2026-06-26T12:00:00Z",
        )
        with pytest.raises(AttributeError):
            state.workspace_id = "WS-HACKED"

    def test_to_dict_minimal(self):
        ws = _make_workspace()
        state = WorkspaceState(
            workspace_id=ws.workspace_id,
            workspace_name=ws.name,
            workspace_status=ws.status.value,
            compiled_at="2026-06-26T12:00:00Z",
        )
        d = state.to_dict()
        assert d["workspace_id"] == ws.workspace_id
        assert d["workspace_name"] == "Test Workspace"
        assert d["workspace_status"] == "ACTIVE"
        assert d["compiled_at"] == "2026-06-26T12:00:00Z"
        assert d["projection_version"] == "1.0"
        assert d["active_decisions"] == []
        assert d["running_executions"] == []
        assert d["pending_reflections"] == []
        assert d["active_knowledge"] == []
        assert d["open_promotions"] == []
        assert d["planner_policy_id"] is None
        assert d["scheduler_jobs"] == []
        assert d["decision_count"] == 0
        assert d["execution_count"] == 0
        assert d["reflection_count"] == 0
        assert d["knowledge_count"] == 0
        assert d["promotion_count"] == 0
        assert d["job_count"] == 0
        assert d["last_activity_at"] is None
        assert d["activity_summary"] == ""
        assert d["total_active_items"] == 0

    def test_to_dict_full(self):
        ws = _make_workspace()
        state = WorkspaceState(
            workspace_id=ws.workspace_id,
            workspace_name=ws.name,
            workspace_status=ws.status.value,
            compiled_at="2026-06-26T12:00:00Z",
            active_decisions=["DEC-001", "DEC-002"],
            running_executions=["SKE-001"],
            pending_reflections=["RCAND-001"],
            active_knowledge=["KNOW-001", "KNOW-002", "KNOW-003"],
            open_promotions=["PROMO-001"],
            planner_policy_id="PPOL-001",
            scheduler_jobs=["CJOB-001", "CJOB-002"],
            decision_count=2,
            execution_count=1,
            reflection_count=1,
            knowledge_count=3,
            promotion_count=1,
            job_count=2,
            last_activity_at="2026-06-26T12:30:00Z",
            activity_summary="Workspace active: 2 open decisions",
            total_active_items=10,
        )
        d = state.to_dict()
        assert len(d["active_decisions"]) == 2
        assert d["planner_policy_id"] == "PPOL-001"
        assert d["total_active_items"] == 10

    def test_counts_match_lists(self):
        ws = _make_workspace()
        state = WorkspaceState(
            workspace_id=ws.workspace_id,
            workspace_name=ws.name,
            workspace_status=ws.status.value,
            compiled_at="2026-06-26T12:00:00Z",
            active_decisions=["DEC-001", "DEC-002", "DEC-003"],
            execution_count=3,
            decision_count=3,
        )
        assert state.decision_count == len(state.active_decisions)

    def test_immutable_lists(self):
        """Lists in frozen dataclass are still mutable (frozen prevents attribute reassignment)."""
        ws = _make_workspace()
        state = WorkspaceState(
            workspace_id=ws.workspace_id,
            workspace_name=ws.name,
            workspace_status=ws.status.value,
            compiled_at="2026-06-26T12:00:00Z",
            active_decisions=["DEC-001"],
        )
        # Lists are not deeply frozen, but the dataclass attribute is
        state.active_decisions.append("DEC-002")
        assert len(state.active_decisions) == 2


# ── Projection Tests ────────────────────────────────────────────────────

class TestWorkspaceStateProjection:
    def test_empty_workspace(self):
        ws = _make_workspace()
        state = WorkspaceStateProjection.project(workspace=ws)
        assert state.workspace_id == ws.workspace_id
        assert state.workspace_name == ws.name
        assert state.workspace_status == "ACTIVE"
        assert state.decision_count == 0
        assert state.execution_count == 0
        assert state.reflection_count == 0
        assert state.knowledge_count == 0
        assert state.promotion_count == 0
        assert state.job_count == 0
        assert state.total_active_items == 0
        assert state.planner_policy_id is None
        assert "quiet" in state.activity_summary.lower()

    def test_deterministic_output(self):
        ws = _make_workspace()
        ref_time = datetime(2026, 6, 26, 12, 0, 0, tzinfo=timezone.utc)
        s1 = WorkspaceStateProjection.project(
            workspace=ws,
            active_decisions=["DEC-001"],
            reference_time=ref_time,
        )
        s2 = WorkspaceStateProjection.project(
            workspace=ws,
            active_decisions=["DEC-001"],
            reference_time=ref_time,
        )
        assert s1.to_dict() == s2.to_dict()

    def test_sorted_ids(self):
        ws = _make_workspace()
        state = WorkspaceStateProjection.project(
            workspace=ws,
            active_decisions=["DEC-003", "DEC-001", "DEC-002"],
            running_executions=["SKE-002", "SKE-001"],
            pending_reflections=["RCAND-001"],
            active_knowledge=["KNOW-003", "KNOW-001", "KNOW-002"],
            open_promotions=["PROMO-001"],
            scheduler_jobs=["CJOB-002", "CJOB-001"],
        )
        assert state.active_decisions == ["DEC-001", "DEC-002", "DEC-003"]
        assert state.running_executions == ["SKE-001", "SKE-002"]
        assert state.active_knowledge == ["KNOW-001", "KNOW-002", "KNOW-003"]
        assert state.scheduler_jobs == ["CJOB-001", "CJOB-002"]

    def test_counts_match(self):
        ws = _make_workspace()
        state = WorkspaceStateProjection.project(
            workspace=ws,
            active_decisions=["DEC-001", "DEC-002"],
            running_executions=["SKE-001"],
            pending_reflections=["RCAND-001", "RCAND-002", "RCAND-003"],
            active_knowledge=["KNOW-001"],
            open_promotions=["PROMO-001", "PROMO-002"],
            scheduler_jobs=["CJOB-001"],
        )
        assert state.decision_count == 2
        assert state.execution_count == 1
        assert state.reflection_count == 3
        assert state.knowledge_count == 1
        assert state.promotion_count == 2
        assert state.job_count == 1
        assert state.total_active_items == 10

    def test_planner_policy(self):
        ws = _make_workspace()
        state_with = WorkspaceStateProjection.project(
            workspace=ws, planner_policy_id="PPOL-001"
        )
        state_without = WorkspaceStateProjection.project(workspace=ws)
        assert state_with.planner_policy_id == "PPOL-001"
        assert state_without.planner_policy_id is None

    def test_activity_summary_empty(self):
        ws = _make_workspace()
        state = WorkspaceStateProjection.project(workspace=ws)
        assert "quiet" in state.activity_summary.lower()

    def test_activity_summary_single_type(self):
        ws = _make_workspace()
        state = WorkspaceStateProjection.project(
            workspace=ws, active_decisions=["DEC-001"]
        )
        assert "1 open decision" in state.activity_summary
        assert "s " not in state.activity_summary  # no plural 's'

    def test_activity_summary_plural(self):
        ws = _make_workspace()
        state = WorkspaceStateProjection.project(
            workspace=ws, active_decisions=["DEC-001", "DEC-002"]
        )
        assert "2 open decisions" in state.activity_summary

    def test_activity_summary_multiple_types(self):
        ws = _make_workspace()
        state = WorkspaceStateProjection.project(
            workspace=ws,
            active_decisions=["DEC-001"],
            running_executions=["SKE-001"],
            active_knowledge=["KNOW-001"],
        )
        assert "1 open decision" in state.activity_summary
        assert "1 running execution" in state.activity_summary
        assert "1 active knowledge item" in state.activity_summary

    def test_activity_summary_planner(self):
        ws = _make_workspace()
        state = WorkspaceStateProjection.project(
            workspace=ws, planner_policy_id="PPOL-001"
        )
        assert "planner active" in state.activity_summary

    def test_activity_summary_jobs(self):
        ws = _make_workspace()
        state = WorkspaceStateProjection.project(
            workspace=ws, scheduler_jobs=["CJOB-001", "CJOB-002"]
        )
        assert "2 scheduled jobs" in state.activity_summary

    def test_workspace_status_preserved(self):
        for status in WorkspaceStatus:
            ws = _make_workspace(status=status)
            state = WorkspaceStateProjection.project(workspace=ws)
            assert state.workspace_status == status.value

    def test_last_activity_at_from_workspace(self):
        ws = _make_workspace(updated_at="2026-06-26T15:45:00Z")
        state = WorkspaceStateProjection.project(workspace=ws)
        assert state.last_activity_at == "2026-06-26T15:45:00Z"

    def test_reference_time_override(self):
        ws = _make_workspace()
        ref_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
        state = WorkspaceStateProjection.project(
            workspace=ws, reference_time=ref_time
        )
        assert state.compiled_at == "2026-01-01T00:00:00+00:00"

    def test_all_subsystems_active(self):
        ws = _make_workspace()
        state = WorkspaceStateProjection.project(
            workspace=ws,
            active_decisions=["DEC-001", "DEC-002"],
            running_executions=["SKE-001", "SKE-002"],
            pending_reflections=["RCAND-001"],
            active_knowledge=["KNOW-001", "KNOW-002"],
            open_promotions=["PROMO-001"],
            planner_policy_id="PPOL-001",
            scheduler_jobs=["CJOB-001", "CJOB-002", "CJOB-003"],
        )
        assert state.decision_count == 2
        assert state.execution_count == 2
        assert state.reflection_count == 1
        assert state.knowledge_count == 2
        assert state.promotion_count == 1
        assert state.job_count == 3
        assert state.planner_policy_id == "PPOL-001"
        assert state.total_active_items == 11
        # Activity summary mentions all types
        assert "decision" in state.activity_summary
        assert "execution" in state.activity_summary
        assert "reflection" in state.activity_summary
        assert "knowledge" in state.activity_summary
        assert "promotion" in state.activity_summary
        assert "planner" in state.activity_summary
        assert "job" in state.activity_summary

    def test_to_dict_roundtrip_data(self):
        ws = _make_workspace()
        state = WorkspaceStateProjection.project(
            workspace=ws,
            active_decisions=["DEC-001"],
            running_executions=["SKE-001"],
            pending_reflections=["RCAND-001"],
            active_knowledge=["KNOW-001"],
            open_promotions=["PROMO-001"],
            planner_policy_id="PPOL-001",
            scheduler_jobs=["CJOB-001"],
        )
        d = state.to_dict()
        # Verify all fields present and correct
        assert d["workspace_id"] == ws.workspace_id
        assert d["active_decisions"] == ["DEC-001"]
        assert d["running_executions"] == ["SKE-001"]
        assert d["pending_reflections"] == ["RCAND-001"]
        assert d["active_knowledge"] == ["KNOW-001"]
        assert d["open_promotions"] == ["PROMO-001"]
        assert d["planner_policy_id"] == "PPOL-001"
        assert d["scheduler_jobs"] == ["CJOB-001"]
        assert d["total_active_items"] == 6

    def test_projection_version(self):
        ws = _make_workspace()
        state = WorkspaceStateProjection.project(workspace=ws)
        assert state.projection_version == "1.0"
        assert WorkspaceStateProjection.version.major == 1
        assert WorkspaceStateProjection.version.minor == 0
        assert WorkspaceStateProjection.version.patch == 0

    def test_projection_is_composite(self):
        from rationalevault.projections.base import ProjectionKind
        assert WorkspaceStateProjection.projection_kind == ProjectionKind.COMPOSITE

    def test_empty_lists_not_none(self):
        ws = _make_workspace()
        state = WorkspaceStateProjection.project(workspace=ws)
        assert state.active_decisions == []
        assert state.running_executions == []
        assert state.pending_reflections == []
        assert state.active_knowledge == []
        assert state.open_promotions == []
        assert state.scheduler_jobs == []

    def test_workspace_id_propagated(self):
        ws = _make_workspace(name="My Special Workspace")
        state = WorkspaceStateProjection.project(workspace=ws)
        assert state.workspace_id == ws.workspace_id
        assert state.workspace_name == "My Special Workspace"

    def test_archived_workspace(self):
        ws = _make_workspace(status=WorkspaceStatus.ARCHIVED)
        state = WorkspaceStateProjection.project(workspace=ws)
        assert state.workspace_status == "ARCHIVED"

    def test_paused_workspace(self):
        ws = _make_workspace(status=WorkspaceStatus.PAUSED)
        state = WorkspaceStateProjection.project(workspace=ws)
        assert state.workspace_status == "PAUSED"
