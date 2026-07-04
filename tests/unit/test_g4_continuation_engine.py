"""
G4 — Continuation Engine Tests.

ContinuationEngine.resume() orchestrates workspace resumption.
"""
from __future__ import annotations

import pytest
from datetime import datetime, timezone

from rationalevault.workspace.continuation import ContinuationEngine
from rationalevault.workspace.models import Workspace, WorkspaceStatus


REF_TIME = datetime(2026, 6, 26, 12, 0, 0, tzinfo=timezone.utc)


def _make_workspace(
    name: str = "Test Workspace",
    status: WorkspaceStatus = WorkspaceStatus.ACTIVE,
) -> Workspace:
    ws_id = Workspace.generate_workspace_id(name, REF_TIME.isoformat())
    return Workspace(
        workspace_id=ws_id,
        name=name,
        description="Test workspace for continuation",
        status=status,
        agent_ids=["agent-a", "agent-b"],
        project_ids=["proj-1"],
        created_at=REF_TIME.isoformat(),
        updated_at=REF_TIME.isoformat(),
    )


# ── ContinuationEngine Tests ────────────────────────────────────────────

class TestContinuationEngine:
    def test_resume_produces_package(self):
        ws = _make_workspace()
        pkg, payload = ContinuationEngine.resume(
            workspace=ws,
            agent_id="agent-a",
            reference_time=REF_TIME,
        )
        assert pkg.workspace_id == ws.workspace_id
        assert pkg.agent_id == "agent-a"
        assert pkg.package_id.startswith("WSPKG-")

    def test_resume_deterministic(self):
        ws = _make_workspace()
        p1, _ = ContinuationEngine.resume(
            workspace=ws,
            agent_id="agent-a",
            goals=["goal-1"],
            active_decisions=["DEC-001"],
            reference_time=REF_TIME,
        )
        p2, _ = ContinuationEngine.resume(
            workspace=ws,
            agent_id="agent-a",
            goals=["goal-1"],
            active_decisions=["DEC-001"],
            reference_time=REF_TIME,
        )
        assert p1.to_dict() == p2.to_dict()

    def test_resume_inherits_decisions(self):
        ws = _make_workspace()
        pkg, _ = ContinuationEngine.resume(
            workspace=ws,
            agent_id="a",
            active_decisions=["DEC-001", "DEC-002"],
            reference_time=REF_TIME,
        )
        assert pkg.open_decisions == ["DEC-001", "DEC-002"]

    def test_resume_inherits_executions(self):
        ws = _make_workspace()
        pkg, _ = ContinuationEngine.resume(
            workspace=ws,
            agent_id="a",
            running_executions=["SKE-001"],
            reference_time=REF_TIME,
        )
        assert pkg.running_executions == ["SKE-001"]

    def test_resume_inherits_reflections(self):
        ws = _make_workspace()
        pkg, _ = ContinuationEngine.resume(
            workspace=ws,
            agent_id="a",
            pending_reflections=["RCAND-001"],
            reference_time=REF_TIME,
        )
        assert pkg.pending_reflections == ["RCAND-001"]

    def test_resume_inherits_knowledge(self):
        ws = _make_workspace()
        pkg, _ = ContinuationEngine.resume(
            workspace=ws,
            agent_id="a",
            active_knowledge=["KNOW-001", "KNOW-002"],
            reference_time=REF_TIME,
        )
        assert pkg.recent_knowledge == ["KNOW-001", "KNOW-002"]

    def test_resume_goals_sorted(self):
        ws = _make_workspace()
        pkg, _ = ContinuationEngine.resume(
            workspace=ws,
            agent_id="a",
            goals=["z", "a", "m"],
            reference_time=REF_TIME,
        )
        assert pkg.goals == ["a", "m", "z"]

    def test_resume_lineage_paths(self):
        ws = _make_workspace()
        pkg, _ = ContinuationEngine.resume(
            workspace=ws,
            agent_id="a",
            lineage_paths=["DEC-001 → KNOW-001"],
            reference_time=REF_TIME,
        )
        assert pkg.lineage_paths == ["DEC-001 → KNOW-001"]

    def test_resume_empty_workspace(self):
        ws = _make_workspace()
        pkg, _ = ContinuationEngine.resume(
            workspace=ws, agent_id="a", reference_time=REF_TIME
        )
        assert pkg.open_decisions == []
        assert pkg.running_executions == []
        assert pkg.pending_reflections == []
        assert pkg.recent_knowledge == []

    def test_resume_full_state(self):
        ws = _make_workspace()
        pkg, _ = ContinuationEngine.resume(
            workspace=ws,
            agent_id="a",
            goals=["g1"],
            active_decisions=["DEC-001"],
            running_executions=["SKE-001"],
            pending_reflections=["RCAND-001"],
            active_knowledge=["KNOW-001"],
            open_promotions=["PROMO-001"],
            planner_policy_id="PPOL-001",
            scheduler_jobs=["CJOB-001"],
            lineage_paths=["path-1"],
            reference_time=REF_TIME,
        )
        assert len(pkg.open_decisions) == 1
        assert len(pkg.running_executions) == 1
        assert len(pkg.pending_reflections) == 1
        assert len(pkg.recent_knowledge) == 1
        assert "PPOL-001" in pkg.planner_policy_summary

    def test_payload_matches_package(self):
        ws = _make_workspace()
        pkg, payload = ContinuationEngine.resume(
            workspace=ws,
            agent_id="a",
            reference_time=REF_TIME,
        )
        assert payload.package_id == pkg.package_id
        assert payload.workspace_id == pkg.workspace_id
        assert payload.agent_id == pkg.agent_id

    def test_package_frozen(self):
        ws = _make_workspace()
        pkg, _ = ContinuationEngine.resume(
            workspace=ws, agent_id="a", reference_time=REF_TIME
        )
        with pytest.raises(AttributeError):
            pkg.agent_id = "hacked"

    def test_package_has_snapshot_id(self):
        ws = _make_workspace()
        pkg, _ = ContinuationEngine.resume(
            workspace=ws, agent_id="a", reference_time=REF_TIME
        )
        assert pkg.snapshot_id.startswith("WSSNP-")

    def test_package_has_context_id(self):
        ws = _make_workspace()
        pkg, _ = ContinuationEngine.resume(
            workspace=ws, agent_id="a", reference_time=REF_TIME
        )
        assert pkg.context_id.startswith("WSCTX-")

    def test_exported_at_set(self):
        ws = _make_workspace()
        pkg, _ = ContinuationEngine.resume(
            workspace=ws, agent_id="a", reference_time=REF_TIME
        )
        assert pkg.exported_at == REF_TIME.isoformat()

    def test_to_dict_roundtrip(self):
        ws = _make_workspace()
        pkg, _ = ContinuationEngine.resume(
            workspace=ws,
            agent_id="a",
            goals=["g1"],
            active_decisions=["DEC-001"],
            reference_time=REF_TIME,
        )
        d = pkg.to_dict()
        assert d["agent_id"] == "a"
        assert d["goals"] == ["g1"]
        assert d["open_decisions"] == ["DEC-001"]
        assert d["workspace_id"] == ws.workspace_id
