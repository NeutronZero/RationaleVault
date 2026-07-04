"""
Tests for RationaleVault Workspace Contracts (G0).

Covers all five contract types, ID generation, serialization, frozen semantics,
and event payload roundtrips.
"""
from __future__ import annotations

import pytest

from rationalevault.workspace.models import (
    Workspace,
    WorkspaceSnapshot,
    WorkspaceSession,
    WorkspaceContext,
    WorkspacePackage,
    WorkspaceStatus,
    AgentRole,
    SessionStatus,
)
from rationalevault.workspace.events import (
    WorkspaceCreatedPayload,
    WorkspaceSnapshotTakenPayload,
    WorkspaceSessionOpenedPayload,
    WorkspaceContextCompiledPayload,
    WorkspacePackageExportedPayload,
)


# =====================================================================
# Workspace
# =====================================================================

class TestWorkspace:
    def test_id_generation_deterministic(self):
        id1 = Workspace.generate_workspace_id("My Workspace", "2026-06-26T12:00:00Z")
        id2 = Workspace.generate_workspace_id("My Workspace", "2026-06-26T12:00:00Z")
        assert id1 == id2
        assert id1.startswith("WS-")

    def test_id_varies_by_name(self):
        id1 = Workspace.generate_workspace_id("Workspace A", "2026-06-26T12:00:00Z")
        id2 = Workspace.generate_workspace_id("Workspace B", "2026-06-26T12:00:00Z")
        assert id1 != id2

    def test_serialization_roundtrip(self):
        ws = Workspace(
            workspace_id="WS-TEST", name="Test Workspace",
            description="A test workspace", status=WorkspaceStatus.ACTIVE,
            agent_ids=["agent-1", "agent-2"], project_ids=["proj-1"],
            created_at="2026-06-26T12:00:00Z", updated_at="2026-06-26T12:00:00Z",
        )
        d = ws.to_dict()
        restored = Workspace.from_dict(d)
        assert restored.workspace_id == ws.workspace_id
        assert restored.status == ws.status
        assert restored.agent_ids == ws.agent_ids

    def test_frozen(self):
        ws = Workspace("WS-TEST", "Test", "", WorkspaceStatus.ACTIVE, [], [], "2026-06-26T12:00:00Z", "2026-06-26T12:00:00Z")
        with pytest.raises(AttributeError):
            ws.name = "Modified"


# =====================================================================
# WorkspaceSnapshot
# =====================================================================

class TestWorkspaceSnapshot:
    def test_id_generation_deterministic(self):
        id1 = WorkspaceSnapshot.generate_snapshot_id("WS-001", "2026-06-26T12:00:00Z")
        id2 = WorkspaceSnapshot.generate_snapshot_id("WS-001", "2026-06-26T12:00:00Z")
        assert id1 == id2
        assert id1.startswith("WSSNP-")

    def test_serialization_roundtrip(self):
        snap = WorkspaceSnapshot(
            snapshot_id="WSSNP-TEST", workspace_id="WS-001", version=1,
            active_decisions=["DEC-001"], running_executions=["SKE-001"],
            pending_reflections=["RCAND-001"], active_knowledge=["KNOW-001"],
            open_promotions=["PROMO-001"], planner_policy_id="PPOL-001",
            scheduler_jobs=["CJOB-001"], created_at="2026-06-26T12:00:00Z",
        )
        d = snap.to_dict()
        restored = WorkspaceSnapshot.from_dict(d)
        assert restored.snapshot_id == snap.snapshot_id
        assert restored.active_decisions == ["DEC-001"]
        assert restored.planner_policy_id == "PPOL-001"

    def test_frozen(self):
        snap = WorkspaceSnapshot("WSSNP-TEST", "WS-001", 1, [], [], [], [], [], None, [], "2026-06-26T12:00:00Z")
        with pytest.raises(AttributeError):
            snap.version = 2


# =====================================================================
# WorkspaceSession
# =====================================================================

class TestWorkspaceSession:
    def test_id_generation_deterministic(self):
        id1 = WorkspaceSession.generate_session_id("WS-001", "agent-1", "2026-06-26T12:00:00Z")
        id2 = WorkspaceSession.generate_session_id("WS-001", "agent-1", "2026-06-26T12:00:00Z")
        assert id1 == id2
        assert id1.startswith("WSSSN-")

    def test_serialization_roundtrip(self):
        session = WorkspaceSession(
            session_id="WSSSN-TEST", workspace_id="WS-001",
            agent_id="claude-1", agent_role=AgentRole.PRIMARY,
            status=SessionStatus.OPEN, started_at="2026-06-26T12:00:00Z",
            ended_at=None, snapshot_id="WSSNP-001",
        )
        d = session.to_dict()
        restored = WorkspaceSession.from_dict(d)
        assert restored.session_id == session.session_id
        assert restored.agent_role == AgentRole.PRIMARY
        assert restored.status == SessionStatus.OPEN

    def test_frozen(self):
        session = WorkspaceSession("WSSSN-TEST", "WS-001", "agent-1", AgentRole.PRIMARY, SessionStatus.OPEN, "2026-06-26T12:00:00Z", None, None)
        with pytest.raises(AttributeError):
            session.status = SessionStatus.CLOSED


# =====================================================================
# WorkspaceContext
# =====================================================================

class TestWorkspaceContext:
    def test_id_generation_deterministic(self):
        id1 = WorkspaceContext.generate_context_id("WSSSN-001", "2026-06-26T12:00:00Z")
        id2 = WorkspaceContext.generate_context_id("WSSSN-001", "2026-06-26T12:00:00Z")
        assert id1 == id2
        assert id1.startswith("WSCTX-")

    def test_serialization_roundtrip(self):
        ctx = WorkspaceContext(
            context_id="WSCTX-TEST", session_id="WSSSN-001",
            snapshot_id="WSSNP-001", agent_id="claude-1",
            goals=["Complete sprint 42"], open_decisions=["DEC-001"],
            running_executions=["SKE-001"], pending_reflections=["RCAND-001"],
            recent_knowledge=["KNOW-001"], planner_policy_summary="v1: min_confidence=0.6",
            memory_focus=["MEM-001"], lineage_summary=["KNOW-001 → REFL-001 → EVT-001"],
            created_at="2026-06-26T12:00:00Z",
        )
        d = ctx.to_dict()
        restored = WorkspaceContext.from_dict(d)
        assert restored.context_id == ctx.context_id
        assert restored.goals == ["Complete sprint 42"]
        assert restored.lineage_summary == ["KNOW-001 → REFL-001 → EVT-001"]

    def test_frozen(self):
        ctx = WorkspaceContext("WSCTX-TEST", "WSSSN-001", "WSSNP-001", "claude-1", [], [], [], [], [], "", [], [], "2026-06-26T12:00:00Z")
        with pytest.raises(AttributeError):
            ctx.goals = ["Modified"]


# =====================================================================
# WorkspacePackage
# =====================================================================

class TestWorkspacePackage:
    def test_id_generation_deterministic(self):
        id1 = WorkspacePackage.generate_package_id("WS-001", "claude-1", "2026-06-26T12:00:00Z")
        id2 = WorkspacePackage.generate_package_id("WS-001", "claude-1", "2026-06-26T12:00:00Z")
        assert id1 == id2
        assert id1.startswith("WSPKG-")

    def test_serialization_roundtrip(self):
        pkg = WorkspacePackage(
            package_id="WSPKG-TEST", workspace_id="WS-001",
            context_id="WSCTX-001", snapshot_id="WSSNP-001",
            agent_id="claude-1", goals=["Complete sprint 42"],
            open_decisions=["DEC-001"], running_executions=["SKE-001"],
            pending_reflections=["RCAND-001"],
            planner_policy_summary="v1: min_confidence=0.6",
            recent_knowledge=["KNOW-001"], memory_focus=["MEM-001"],
            lineage_paths=["KNOW-001 → REFL-001 → EVT-001"],
            exported_at="2026-06-26T12:00:00Z",
        )
        d = pkg.to_dict()
        restored = WorkspacePackage.from_dict(d)
        assert restored.package_id == pkg.package_id
        assert restored.lineage_paths == ["KNOW-001 → REFL-001 → EVT-001"]

    def test_frozen(self):
        pkg = WorkspacePackage("WSPKG-TEST", "WS-001", "WSCTX-001", "WSSNP-001", "claude-1", [], [], [], [], "", [], [], [], "2026-06-26T12:00:00Z")
        with pytest.raises(AttributeError):
            pkg.goals = ["Modified"]


# =====================================================================
# Event Payloads
# =====================================================================

class TestWorkspaceEventPayloads:
    def test_workspace_created_payload_roundtrip(self):
        p = WorkspaceCreatedPayload(
            workspace_id="WS-001", name="Test", description="Desc",
            agent_ids=["a1"], project_ids=["p1"], created_at="2026-06-26T12:00:00Z",
        )
        d = p.to_dict()
        restored = WorkspaceCreatedPayload.from_dict(d)
        assert restored.workspace_id == "WS-001"
        assert restored.name == "Test"

    def test_snapshot_taken_payload_roundtrip(self):
        p = WorkspaceSnapshotTakenPayload(
            snapshot_id="WSSNP-001", workspace_id="WS-001", version=1,
            active_decisions=["DEC-001"], created_at="2026-06-26T12:00:00Z",
        )
        d = p.to_dict()
        restored = WorkspaceSnapshotTakenPayload.from_dict(d)
        assert restored.snapshot_id == "WSSNP-001"

    def test_session_opened_payload_roundtrip(self):
        p = WorkspaceSessionOpenedPayload(
            session_id="WSSSN-001", workspace_id="WS-001",
            agent_id="claude-1", agent_role="PRIMARY",
            snapshot_id="WSSNP-001", created_at="2026-06-26T12:00:00Z",
        )
        d = p.to_dict()
        restored = WorkspaceSessionOpenedPayload.from_dict(d)
        assert restored.agent_role == "PRIMARY"

    def test_context_compiled_payload_roundtrip(self):
        p = WorkspaceContextCompiledPayload(
            context_id="WSCTX-001", session_id="WSSSN-001",
            snapshot_id="WSSNP-001", agent_id="claude-1",
            goals=["Goal 1"], created_at="2026-06-26T12:00:00Z",
        )
        d = p.to_dict()
        restored = WorkspaceContextCompiledPayload.from_dict(d)
        assert restored.goals == ["Goal 1"]

    def test_package_exported_payload_roundtrip(self):
        p = WorkspacePackageExportedPayload(
            package_id="WSPKG-001", workspace_id="WS-001",
            context_id="WSCTX-001", snapshot_id="WSSNP-001",
            agent_id="claude-1", lineage_paths=["Path 1"],
            exported_at="2026-06-26T12:00:00Z",
        )
        d = p.to_dict()
        restored = WorkspacePackageExportedPayload.from_dict(d)
        assert restored.package_id == "WSPKG-001"
        assert restored.lineage_paths == ["Path 1"]

    def test_all_payloads_have_schema_version(self):
        payloads = [
            WorkspaceCreatedPayload(workspace_id="WS-001", name="T", created_at="2026-06-26T12:00:00Z"),
            WorkspaceSnapshotTakenPayload(snapshot_id="WSSNP-001", workspace_id="WS-001", created_at="2026-06-26T12:00:00Z"),
            WorkspaceSessionOpenedPayload(session_id="WSSSN-001", workspace_id="WS-001", agent_id="a", agent_role="PRIMARY", created_at="2026-06-26T12:00:00Z"),
            WorkspaceContextCompiledPayload(context_id="WSCTX-001", session_id="WSSSN-001", snapshot_id="WSSNP-001", agent_id="a", created_at="2026-06-26T12:00:00Z"),
            WorkspacePackageExportedPayload(package_id="WSPKG-001", workspace_id="WS-001", context_id="WSCTX-001", snapshot_id="WSSNP-001", agent_id="a", exported_at="2026-06-26T12:00:00Z"),
        ]
        for p in payloads:
            d = p.to_dict()
            assert "schema_version" in d
            assert d["schema_version"] == "1.0"
