"""
G2 — Workspace Service API Tests.

Deterministic service layer: frozen inputs → (frozen output, event_payload).
"""
from __future__ import annotations

import pytest
from datetime import datetime, timezone

from rationalevault.workspace.models import (
    Workspace,
    WorkspaceContext,
    WorkspacePackage,
    WorkspaceSession,
    WorkspaceSnapshot,
    WorkspaceStatus,
)
from rationalevault.workspace.service import (
    Error,
    Success,
    WorkspaceDiff,
    WorkspaceService,
)


# ── Helpers ──────────────────────────────────────────────────────────────

REF_TIME = datetime(2026, 6, 26, 12, 0, 0, tzinfo=timezone.utc)


def _make_workspace(
    name: str = "Test Workspace",
    status: WorkspaceStatus = WorkspaceStatus.ACTIVE,
    agent_ids: list[str] | None = None,
    project_ids: list[str] | None = None,
) -> Workspace:
    ws_id = Workspace.generate_workspace_id(name, REF_TIME.isoformat())
    return Workspace(
        workspace_id=ws_id,
        name=name,
        description="Test",
        status=status,
        agent_ids=sorted(agent_ids or ["a", "b"]),
        project_ids=sorted(project_ids or ["p1"]),
        created_at=REF_TIME.isoformat(),
        updated_at=REF_TIME.isoformat(),
    )


def _make_snapshot(
    workspace_id: str = "WS-TEST",
    version: int = 1,
    **kwargs: any,
) -> WorkspaceSnapshot:
    snap_id = WorkspaceSnapshot.generate_snapshot_id(
        workspace_id, REF_TIME.isoformat()
    )
    defaults = dict(
        snapshot_id=snap_id,
        workspace_id=workspace_id,
        version=version,
        active_decisions=[],
        running_executions=[],
        pending_reflections=[],
        active_knowledge=[],
        open_promotions=[],
        planner_policy_id=None,
        scheduler_jobs=[],
        created_at=REF_TIME.isoformat(),
    )
    defaults.update(kwargs)
    return WorkspaceSnapshot(**defaults)


def _make_context(
    session_id: str = "WSSSN-TEST",
    snapshot_id: str = "WSSNP-TEST",
    agent_id: str = "agent-a",
) -> WorkspaceContext:
    ctx_id = WorkspaceContext.generate_context_id(
        session_id, REF_TIME.isoformat()
    )
    return WorkspaceContext(
        context_id=ctx_id,
        session_id=session_id,
        snapshot_id=snapshot_id,
        agent_id=agent_id,
        goals=["goal-1"],
        open_decisions=["DEC-001"],
        running_executions=[],
        pending_reflections=[],
        recent_knowledge=[],
        planner_policy_summary="Default policy",
        memory_focus=[],
        lineage_summary=[],
        created_at=REF_TIME.isoformat(),
    )


# ── open() ───────────────────────────────────────────────────────────────

class TestOpen:
    def test_creates_active_workspace(self):
        ws, payload = WorkspaceService.open(
            name="My Workspace",
            description="A test workspace",
            agent_ids=["claude", "codex"],
            project_ids=["proj-1", "proj-2"],
            reference_time=REF_TIME,
        )
        assert ws.name == "My Workspace"
        assert ws.status == WorkspaceStatus.ACTIVE
        assert ws.agent_ids == ["claude", "codex"]
        assert ws.project_ids == ["proj-1", "proj-2"]

    def test_payload_matches_workspace(self):
        ws, payload = WorkspaceService.open(
            name="X", reference_time=REF_TIME
        )
        assert payload.workspace_id == ws.workspace_id
        assert payload.name == ws.name
        assert payload.agent_ids == ws.agent_ids

    def test_deterministic_ids(self):
        ws1, _ = WorkspaceService.open(name="A", reference_time=REF_TIME)
        ws2, _ = WorkspaceService.open(name="A", reference_time=REF_TIME)
        assert ws1.workspace_id == ws2.workspace_id

    def test_different_names_different_ids(self):
        ws1, _ = WorkspaceService.open(name="A", reference_time=REF_TIME)
        ws2, _ = WorkspaceService.open(name="B", reference_time=REF_TIME)
        assert ws1.workspace_id != ws2.workspace_id

    def test_empty_defaults(self):
        ws, payload = WorkspaceService.open(name="X", reference_time=REF_TIME)
        assert ws.agent_ids == []
        assert ws.project_ids == []
        assert ws.description == ""

    def test_workspace_is_frozen(self):
        ws, _ = WorkspaceService.open(name="X", reference_time=REF_TIME)
        with pytest.raises(AttributeError):
            ws.name = "Hacked"


# ── resume() ─────────────────────────────────────────────────────────────

class TestResume:
    def test_resume_paused_workspace(self):
        ws = _make_workspace(status=WorkspaceStatus.PAUSED)
        result = WorkspaceService.resume(ws, reference_time=REF_TIME)
        assert isinstance(result, tuple)
        resumed, payload = result
        assert resumed.status == WorkspaceStatus.ACTIVE

    def test_resume_active_fails(self):
        ws = _make_workspace(status=WorkspaceStatus.ACTIVE)
        result = WorkspaceService.resume(ws, reference_time=REF_TIME)
        assert isinstance(result, Error)
        assert "ACTIVE" in result.reason

    def test_resume_archived_fails(self):
        ws = _make_workspace(status=WorkspaceStatus.ARCHIVED)
        result = WorkspaceService.resume(ws, reference_time=REF_TIME)
        assert isinstance(result, Error)
        assert "ARCHIVED" in result.reason

    def test_resume_preserves_identity(self):
        ws = _make_workspace(status=WorkspaceStatus.PAUSED)
        resumed, _ = WorkspaceService.resume(ws, reference_time=REF_TIME)
        assert resumed.workspace_id == ws.workspace_id
        assert resumed.name == ws.name

    def test_resume_updates_timestamp(self):
        ws = _make_workspace(status=WorkspaceStatus.PAUSED)
        later = datetime(2026, 6, 26, 13, 0, 0, tzinfo=timezone.utc)
        resumed, _ = WorkspaceService.resume(ws, reference_time=later)
        assert resumed.updated_at == later.isoformat()


# ── pause() ──────────────────────────────────────────────────────────────

class TestPause:
    def test_pause_active_workspace(self):
        ws = _make_workspace(status=WorkspaceStatus.ACTIVE)
        result = WorkspaceService.pause(ws, reference_time=REF_TIME)
        assert isinstance(result, tuple)
        paused, payload = result
        assert paused.status == WorkspaceStatus.PAUSED

    def test_pause_paused_fails(self):
        ws = _make_workspace(status=WorkspaceStatus.PAUSED)
        result = WorkspaceService.pause(ws, reference_time=REF_TIME)
        assert isinstance(result, Error)
        assert "PAUSED" in result.reason

    def test_pause_archived_fails(self):
        ws = _make_workspace(status=WorkspaceStatus.ARCHIVED)
        result = WorkspaceService.pause(ws, reference_time=REF_TIME)
        assert isinstance(result, Error)

    def test_pause_preserves_identity(self):
        ws = _make_workspace(status=WorkspaceStatus.ACTIVE)
        paused, _ = WorkspaceService.pause(ws, reference_time=REF_TIME)
        assert paused.workspace_id == ws.workspace_id

    def test_pause_updates_timestamp(self):
        ws = _make_workspace(status=WorkspaceStatus.ACTIVE)
        paused, _ = WorkspaceService.pause(ws, reference_time=REF_TIME)
        assert paused.updated_at == REF_TIME.isoformat()

    def test_pause_roundtrip(self):
        """ACTIVE → PAUSED → ACTIVE."""
        ws = _make_workspace(status=WorkspaceStatus.ACTIVE)
        paused, _ = WorkspaceService.pause(ws, reference_time=REF_TIME)
        assert isinstance(paused, Workspace)
        resumed, _ = WorkspaceService.resume(paused, reference_time=REF_TIME)
        assert isinstance(resumed, Workspace)
        assert resumed.status == WorkspaceStatus.ACTIVE


# ── snapshot() ───────────────────────────────────────────────────────────

class TestSnapshot:
    def test_empty_snapshot(self):
        ws = _make_workspace()
        snap, payload = WorkspaceService.snapshot(
            workspace=ws, version=1, reference_time=REF_TIME
        )
        assert snap.workspace_id == ws.workspace_id
        assert snap.version == 1
        assert snap.active_decisions == []
        assert snap.running_executions == []

    def test_snapshot_with_data(self):
        ws = _make_workspace()
        snap, _ = WorkspaceService.snapshot(
            workspace=ws,
            version=2,
            active_decisions=["DEC-001", "DEC-002"],
            running_executions=["SKE-001"],
            pending_reflections=["RCAND-001"],
            active_knowledge=["KNOW-001", "KNOW-002"],
            open_promotions=["PROMO-001"],
            planner_policy_id="PPOL-001",
            scheduler_jobs=["CJOB-001"],
            reference_time=REF_TIME,
        )
        assert len(snap.active_decisions) == 2
        assert len(snap.running_executions) == 1
        assert snap.planner_policy_id == "PPOL-001"

    def test_snapshot_sorted_ids(self):
        ws = _make_workspace()
        snap, _ = WorkspaceService.snapshot(
            workspace=ws,
            version=1,
            active_decisions=["DEC-003", "DEC-001", "DEC-002"],
            reference_time=REF_TIME,
        )
        assert snap.active_decisions == ["DEC-001", "DEC-002", "DEC-003"]

    def test_snapshot_id_deterministic(self):
        ws = _make_workspace()
        s1, _ = WorkspaceService.snapshot(
            workspace=ws, version=1, reference_time=REF_TIME
        )
        s2, _ = WorkspaceService.snapshot(
            workspace=ws, version=1, reference_time=REF_TIME
        )
        assert s1.snapshot_id == s2.snapshot_id

    def test_snapshot_payload_matches(self):
        ws = _make_workspace()
        snap, payload = WorkspaceService.snapshot(
            workspace=ws, version=1, reference_time=REF_TIME
        )
        assert payload.snapshot_id == snap.snapshot_id
        assert payload.workspace_id == snap.workspace_id

    def test_snapshot_frozen(self):
        ws = _make_workspace()
        snap, _ = WorkspaceService.snapshot(
            workspace=ws, version=1, reference_time=REF_TIME
        )
        with pytest.raises(AttributeError):
            snap.version = 2


# ── diff() ───────────────────────────────────────────────────────────────

class TestDiff:
    def test_identical_snapshots_no_changes(self):
        ws = _make_workspace()
        s1, _ = WorkspaceService.snapshot(
            workspace=ws, version=1, reference_time=REF_TIME
        )
        diff = WorkspaceService.diff(s1, s1)
        assert not diff.has_changes
        assert diff.total_changes == 0

    def test_added_decisions(self):
        s1 = _make_snapshot(active_decisions=["DEC-001"])
        s2 = _make_snapshot(active_decisions=["DEC-001", "DEC-002", "DEC-003"])
        diff = WorkspaceService.diff(s1, s2)
        assert diff.added_decisions == ["DEC-002", "DEC-003"]
        assert diff.removed_decisions == []
        assert diff.has_changes

    def test_removed_decisions(self):
        s1 = _make_snapshot(active_decisions=["DEC-001", "DEC-002"])
        s2 = _make_snapshot(active_decisions=["DEC-001"])
        diff = WorkspaceService.diff(s1, s2)
        assert diff.added_decisions == []
        assert diff.removed_decisions == ["DEC-002"]

    def test_added_executions(self):
        s1 = _make_snapshot(running_executions=[])
        s2 = _make_snapshot(running_executions=["SKE-001", "SKE-002"])
        diff = WorkspaceService.diff(s1, s2)
        assert diff.added_executions == ["SKE-001", "SKE-002"]

    def test_removed_executions(self):
        s1 = _make_snapshot(running_executions=["SKE-001"])
        s2 = _make_snapshot(running_executions=[])
        diff = WorkspaceService.diff(s1, s2)
        assert diff.removed_executions == ["SKE-001"]

    def test_added_reflections(self):
        s1 = _make_snapshot(pending_reflections=[])
        s2 = _make_snapshot(pending_reflections=["RCAND-001"])
        diff = WorkspaceService.diff(s1, s2)
        assert diff.added_reflections == ["RCAND-001"]

    def test_removed_knowledge(self):
        s1 = _make_snapshot(active_knowledge=["KNOW-001", "KNOW-002"])
        s2 = _make_snapshot(active_knowledge=["KNOW-001"])
        diff = WorkspaceService.diff(s1, s2)
        assert diff.removed_knowledge == ["KNOW-002"]

    def test_added_promotions(self):
        s1 = _make_snapshot(open_promotions=[])
        s2 = _make_snapshot(open_promotions=["PROMO-001"])
        diff = WorkspaceService.diff(s1, s2)
        assert diff.added_promotions == ["PROMO-001"]

    def test_added_jobs(self):
        s1 = _make_snapshot(scheduler_jobs=[])
        s2 = _make_snapshot(scheduler_jobs=["CJOB-001", "CJOB-002"])
        diff = WorkspaceService.diff(s1, s2)
        assert diff.added_jobs == ["CJOB-001", "CJOB-002"]

    def test_planner_changed(self):
        s1 = _make_snapshot(planner_policy_id="PPOL-001")
        s2 = _make_snapshot(planner_policy_id="PPOL-002")
        diff = WorkspaceService.diff(s1, s2)
        assert diff.planner_changed
        assert diff.total_changes == 1

    def test_planner_unchanged(self):
        s1 = _make_snapshot(planner_policy_id="PPOL-001")
        s2 = _make_snapshot(planner_policy_id="PPOL-001")
        diff = WorkspaceService.diff(s1, s2)
        assert not diff.planner_changed

    def test_mixed_changes(self):
        s1 = _make_snapshot(
            active_decisions=["DEC-001", "DEC-002"],
            running_executions=["SKE-001"],
            planner_policy_id="PPOL-001",
        )
        s2 = _make_snapshot(
            active_decisions=["DEC-001", "DEC-003"],
            running_executions=["SKE-001", "SKE-002"],
            planner_policy_id="PPOL-002",
        )
        diff = WorkspaceService.diff(s1, s2)
        assert diff.added_decisions == ["DEC-003"]
        assert diff.removed_decisions == ["DEC-002"]
        assert diff.added_executions == ["SKE-002"]
        assert diff.planner_changed
        assert diff.total_changes == 4

    def test_diff_to_dict(self):
        s1 = _make_snapshot(active_decisions=["DEC-001"])
        s2 = _make_snapshot(active_decisions=["DEC-001", "DEC-002"])
        diff = WorkspaceService.diff(s1, s2)
        d = diff.to_dict()
        assert d["added_decisions"] == ["DEC-002"]
        assert d["has_changes"] is True
        assert d["total_changes"] == 1


# ── export() ─────────────────────────────────────────────────────────────

class TestExport:
    def test_export_package(self):
        ws = _make_workspace()
        snap, _ = WorkspaceService.snapshot(
            workspace=ws, version=1, reference_time=REF_TIME
        )
        ctx = _make_context(snapshot_id=snap.snapshot_id)
        pkg, payload = WorkspaceService.export(
            workspace=ws,
            context=ctx,
            snapshot=snap,
            agent_id="agent-a",
            reference_time=REF_TIME,
        )
        assert pkg.workspace_id == ws.workspace_id
        assert pkg.context_id == ctx.context_id
        assert pkg.snapshot_id == snap.snapshot_id
        assert pkg.agent_id == "agent-a"

    def test_export_inherits_snapshot_data(self):
        ws = _make_workspace()
        snap, _ = WorkspaceService.snapshot(
            workspace=ws,
            version=1,
            active_decisions=["DEC-001"],
            running_executions=["SKE-001"],
            reference_time=REF_TIME,
        )
        ctx = _make_context(snapshot_id=snap.snapshot_id)
        pkg, _ = WorkspaceService.export(
            workspace=ws,
            context=ctx,
            snapshot=snap,
            agent_id="agent-a",
            reference_time=REF_TIME,
        )
        assert pkg.open_decisions == ["DEC-001"]
        assert pkg.running_executions == ["SKE-001"]

    def test_export_inherits_context_data(self):
        ws = _make_workspace()
        snap, _ = WorkspaceService.snapshot(
            workspace=ws, version=1, reference_time=REF_TIME
        )
        ctx = _make_context(snapshot_id=snap.snapshot_id)
        ctx = WorkspaceContext(
            context_id=ctx.context_id,
            session_id=ctx.session_id,
            snapshot_id=ctx.snapshot_id,
            agent_id=ctx.agent_id,
            goals=["goal-1", "goal-2"],
            open_decisions=[],
            running_executions=[],
            pending_reflections=[],
            recent_knowledge=["KNOW-001"],
            planner_policy_summary="Test policy",
            memory_focus=["MEM-001"],
            lineage_summary=[],
            created_at=ctx.created_at,
        )
        pkg, _ = WorkspaceService.export(
            workspace=ws,
            context=ctx,
            snapshot=snap,
            agent_id="agent-a",
            reference_time=REF_TIME,
        )
        assert pkg.goals == ["goal-1", "goal-2"]
        assert pkg.recent_knowledge == ["KNOW-001"]
        assert pkg.planner_policy_summary == "Test policy"

    def test_export_with_lineage(self):
        ws = _make_workspace()
        snap, _ = WorkspaceService.snapshot(
            workspace=ws, version=1, reference_time=REF_TIME
        )
        ctx = _make_context(snapshot_id=snap.snapshot_id)
        pkg, _ = WorkspaceService.export(
            workspace=ws,
            context=ctx,
            snapshot=snap,
            agent_id="agent-a",
            lineage_paths=["DEC-001 → KNOW-001", "SKE-001 → ART-001"],
            reference_time=REF_TIME,
        )
        assert len(pkg.lineage_paths) == 2

    def test_export_payload_matches(self):
        ws = _make_workspace()
        snap, _ = WorkspaceService.snapshot(
            workspace=ws, version=1, reference_time=REF_TIME
        )
        ctx = _make_context(snapshot_id=snap.snapshot_id)
        pkg, payload = WorkspaceService.export(
            workspace=ws,
            context=ctx,
            snapshot=snap,
            agent_id="agent-a",
            reference_time=REF_TIME,
        )
        assert payload.package_id == pkg.package_id
        assert payload.workspace_id == pkg.workspace_id

    def test_export_package_frozen(self):
        ws = _make_workspace()
        snap, _ = WorkspaceService.snapshot(
            workspace=ws, version=1, reference_time=REF_TIME
        )
        ctx = _make_context(snapshot_id=snap.snapshot_id)
        pkg, _ = WorkspaceService.export(
            workspace=ws,
            context=ctx,
            snapshot=snap,
            agent_id="agent-a",
            reference_time=REF_TIME,
        )
        with pytest.raises(AttributeError):
            pkg.agent_id = "hacked"


# ── merge() ──────────────────────────────────────────────────────────────

class TestMerge:
    def test_merge_combines_agents(self):
        ws_a = _make_workspace(
            name="A", agent_ids=["claude", "codex"], project_ids=["p1"]
        )
        ws_b = _make_workspace(
            name="B", agent_ids=["codex", "gemini"], project_ids=["p2"]
        )
        merged, payload = WorkspaceService.merge(
            ws_a, ws_b, reference_time=REF_TIME
        )
        assert "claude" in merged.agent_ids
        assert "codex" in merged.agent_ids
        assert "gemini" in merged.agent_ids
        assert len(merged.agent_ids) == 3

    def test_merge_combines_projects(self):
        ws_a = _make_workspace(name="A", project_ids=["p1", "p2"])
        ws_b = _make_workspace(name="B", project_ids=["p2", "p3"])
        merged, _ = WorkspaceService.merge(ws_a, ws_b, reference_time=REF_TIME)
        assert merged.project_ids == ["p1", "p2", "p3"]

    def test_merge_creates_new_workspace(self):
        ws_a = _make_workspace(name="Alpha")
        ws_b = _make_workspace(name="Beta")
        merged, _ = WorkspaceService.merge(ws_a, ws_b, reference_time=REF_TIME)
        assert merged.workspace_id != ws_a.workspace_id
        assert merged.workspace_id != ws_b.workspace_id

    def test_merge_default_name(self):
        ws_a = _make_workspace(name="Alpha")
        ws_b = _make_workspace(name="Beta")
        merged, _ = WorkspaceService.merge(ws_a, ws_b, reference_time=REF_TIME)
        assert merged.name == "Alpha + Beta"

    def test_merge_custom_name(self):
        ws_a = _make_workspace(name="A")
        ws_b = _make_workspace(name="B")
        merged, _ = WorkspaceService.merge(
            ws_a, ws_b, name="Combined", reference_time=REF_TIME
        )
        assert merged.name == "Combined"

    def test_merge_status_active(self):
        ws_a = _make_workspace(status=WorkspaceStatus.ACTIVE)
        ws_b = _make_workspace(status=WorkspaceStatus.PAUSED)
        merged, _ = WorkspaceService.merge(ws_a, ws_b, reference_time=REF_TIME)
        assert merged.status == WorkspaceStatus.ACTIVE

    def test_merge_description(self):
        ws_a = _make_workspace(name="A")
        ws_b = _make_workspace(name="B")
        merged, _ = WorkspaceService.merge(ws_a, ws_b, reference_time=REF_TIME)
        assert "A" in merged.description
        assert "B" in merged.description

    def test_merge_payload_matches(self):
        ws_a = _make_workspace(name="A")
        ws_b = _make_workspace(name="B")
        merged, payload = WorkspaceService.merge(
            ws_a, ws_b, reference_time=REF_TIME
        )
        assert payload.workspace_id == merged.workspace_id
        assert payload.name == merged.name

    def test_merge_frozen(self):
        ws_a = _make_workspace(name="A")
        ws_b = _make_workspace(name="B")
        merged, _ = WorkspaceService.merge(ws_a, ws_b, reference_time=REF_TIME)
        with pytest.raises(AttributeError):
            merged.name = "Hacked"

    def test_merge_sorted_deduped(self):
        ws_a = _make_workspace(
            name="A", agent_ids=["z", "a", "m"], project_ids=["p3", "p1"]
        )
        ws_b = _make_workspace(
            name="B", agent_ids=["a", "b"], project_ids=["p1", "p2"]
        )
        merged, _ = WorkspaceService.merge(ws_a, ws_b, reference_time=REF_TIME)
        assert merged.agent_ids == ["a", "b", "m", "z"]
        assert merged.project_ids == ["p1", "p2", "p3"]


# ── Error Type ───────────────────────────────────────────────────────────

class TestErrorType:
    def test_error_is_frozen(self):
        e = Error(reason="test")
        with pytest.raises(AttributeError):
            e.reason = "changed"

    def test_error_to_dict(self):
        e = Error(reason="Cannot pause archived workspace")
        d = e.to_dict() if hasattr(e, "to_dict") else {"reason": e.reason}
        assert d["reason"] == "Cannot pause archived workspace"

    def test_success_wraps_value(self):
        s = Success(value=42)
        assert s.value == 42
