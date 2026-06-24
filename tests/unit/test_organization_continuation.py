"""Tests for I14.1 + I14.2 — Activity and Continuation projections."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pytest

from rationalevault.organization.activity import (
    OrganizationActivityProjection,
    OrganizationActivityState,
    ProjectActivity,
    OrgTransferEvent,
    OrgConflictEvent,
    KnowledgeSummary,
)
from rationalevault.organization.continuation import (
    OrganizationContinuationProjection,
    OrganizationContinuationState,
    OrganizationContinuationHealth,
)
from rationalevault.organization.graph import (
    OrganizationGraphProjection,
    OrganizationGraphState,
    OrganizationNode,
    OrganizationEdge,
    OrganizationGraphHealth,
)
from rationalevault.organization.models import (
    CrossProjectConflict,
    KnowledgeLineage,
    OrganizationHealth,
    OrganizationState,
    SharedKnowledge,
    TransferabilityTelemetry,
)
from rationalevault.organization.relation_types import OrganizationRelationType


# ── Helpers ──────────────────────────────────────────────────────────────────

@dataclass
class FakeEvent:
    recorded_at: str

@dataclass
class FakeKnowledge:
    id: str
    title: str
    created_at: str
    updated_at: str = ""
    knowledge_type: str = "principle"

@dataclass
class FakeMemory:
    id: str
    created_at: str


def _lineage(kid, origin, current):
    return KnowledgeLineage(
        knowledge_id=kid, origin_project=origin,
        current_projects=current, transfer_path=[origin] + current, depth=len(current),
    )


def _shared(kid, title, projects):
    return SharedKnowledge(
        knowledge_id=kid, title=title, knowledge_type="principle",
        present_in_projects=projects, transfer_count=len(projects) - 1,
    )


def _conflict(a_id, b_id, pa, pb, conf=0.8):
    return CrossProjectConflict(
        conflict_id=f"{pa}_{pb}", knowledge_a_id=a_id, knowledge_b_id=b_id,
        project_a=pa, project_b=pb, knowledge_a_title="A", knowledge_b_title="B",
        confidence=conf, reasons=["lexical_similarity"],
    )


# ── OrganizationActivityState ────────────────────────────────────────────────

class TestOrganizationActivityState:
    def test_to_dict(self) -> None:
        state = OrganizationActivityState(compiled_at="2025-01-01", project_count=1)
        d = state.to_dict()
        assert d["compiled_at"] == "2025-01-01"
        assert d["project_count"] == 1
        assert d["overall_activity_level"] == 0.0
        import json
        serialized = json.dumps(d)
        assert isinstance(serialized, str)

    def test_to_dict_with_data(self) -> None:
        state = OrganizationActivityState(
            compiled_at="2025-01-01",
            project_count=3,
            active_projects=[
                ProjectActivity(project_id="a", recent_event_count=5, last_event_at="2025-01-01T12:00:00"),
            ],
            inactive_projects=["b", "c"],
            recent_transfers=[
                OrgTransferEvent("k1", "Knowledge 1", "a", "b", "2025-01-01T12:00:00"),
            ],
        )
        d = state.to_dict()
        assert len(d["active_projects"]) == 1
        assert len(d["inactive_projects"]) == 2
        assert len(d["recent_transfers"]) == 1


class TestProjectActivity:
    def test_defaults(self) -> None:
        pa = ProjectActivity(project_id="a")
        assert pa.recent_event_count == 0
        assert pa.recent_knowledge_count == 0
        assert pa.recent_memory_count == 0


class TestActivityProjectionBasic:
    def test_no_projects(self) -> None:
        org = OrganizationState(compiled_at="2025-01-01")
        state = OrganizationActivityProjection.project(
            project_ids=[],
            recent_events_by_project={},
            recent_knowledge_by_project={},
            recent_memories_by_project={},
            org_state=org,
        )
        assert state.project_count == 0
        assert state.overall_activity_level == 0.0

    def test_all_inactive(self) -> None:
        org = OrganizationState(compiled_at="2025-01-01", project_ids=["a", "b"])
        state = OrganizationActivityProjection.project(
            project_ids=["a", "b"],
            recent_events_by_project={},
            recent_knowledge_by_project={},
            recent_memories_by_project={},
            org_state=org,
        )
        assert len(state.active_projects) == 0
        assert sorted(state.inactive_projects) == ["a", "b"]
        assert state.overall_activity_level == 0.0


class TestActivityProjectionActiveDetection:
    def test_events_make_active(self) -> None:
        org = OrganizationState(compiled_at="2025-01-01", project_ids=["a", "b"])
        state = OrganizationActivityProjection.project(
            project_ids=["a", "b"],
            recent_events_by_project={
                "a": [FakeEvent(recorded_at="2025-01-01T12:00:00")],
            },
            recent_knowledge_by_project={},
            recent_memories_by_project={},
            org_state=org,
        )
        assert len(state.active_projects) == 1
        assert state.active_projects[0].project_id == "a"
        assert state.active_projects[0].recent_event_count == 1
        assert "b" in state.inactive_projects

    def test_knowledge_makes_active(self) -> None:
        org = OrganizationState(compiled_at="2025-01-01", project_ids=["a"])
        state = OrganizationActivityProjection.project(
            project_ids=["a"],
            recent_events_by_project={},
            recent_knowledge_by_project={
                "a": [FakeKnowledge(id="k1", title="K1", created_at="2025-01-01T12:00:00")],
            },
            recent_memories_by_project={},
            org_state=org,
        )
        assert len(state.active_projects) == 1
        assert state.active_projects[0].recent_knowledge_count == 1


class TestActivityProjectionTransfers:
    def test_recent_transfer_detected(self) -> None:
        org = OrganizationState(
            compiled_at="2025-01-01",
            project_ids=["a", "b"],
            active_lineages={
                "k1": _lineage("k1", "a", ["b"]),
            },
        )
        state = OrganizationActivityProjection.project(
            project_ids=["a", "b"],
            recent_events_by_project={},
            recent_knowledge_by_project={
                "b": [FakeKnowledge(id="k1", title="Transferred K", created_at="2025-01-01T12:00:00")],
            },
            recent_memories_by_project={},
            org_state=org,
        )
        assert len(state.recent_transfers) == 1
        t = state.recent_transfers[0]
        assert t.source_project == "a"
        assert t.target_project == "b"
        assert t.knowledge_id == "k1"


class TestActivityProjectionConflicts:
    def test_recent_conflict_detected(self) -> None:
        org = OrganizationState(
            compiled_at="2025-01-01",
            project_ids=["a", "b"],
            cross_project_conflicts=[
                _conflict("k_a", "k_b", "a", "b"),
            ],
        )
        state = OrganizationActivityProjection.project(
            project_ids=["a", "b"],
            recent_events_by_project={},
            recent_knowledge_by_project={
                "a": [FakeKnowledge(id="k_a", title="A", created_at="2025-01-01T12:00:00")],
            },
            recent_memories_by_project={},
            org_state=org,
        )
        assert len(state.recent_conflicts) == 1


class TestActivityProjectionDeterminism:
    def test_deterministic_ordering(self) -> None:
        org = OrganizationState(compiled_at="2025-01-01", project_ids=["a", "b"])
        s1 = OrganizationActivityProjection.project(
            project_ids=["a", "b"],
            recent_events_by_project={
                "a": [FakeEvent(recorded_at="2025-01-01T12:00:00")],
            },
            recent_knowledge_by_project={},
            recent_memories_by_project={},
            org_state=org,
        )
        s2 = OrganizationActivityProjection.project(
            project_ids=["a", "b"],
            recent_events_by_project={
                "a": [FakeEvent(recorded_at="2025-01-01T12:00:00")],
            },
            recent_knowledge_by_project={},
            recent_memories_by_project={},
            org_state=org,
        )
        assert len(s1.active_projects) == len(s2.active_projects)
        assert s1.active_projects[0].project_id == s2.active_projects[0].project_id
        assert s1.inactive_projects == s2.inactive_projects

    def test_activity_replayability(self) -> None:
        org = OrganizationState(compiled_at="2025-01-01", project_ids=["a", "b", "c"])
        s1 = OrganizationActivityProjection.project(
            project_ids=["a", "b", "c"],
            recent_events_by_project={
                "a": [FakeEvent(recorded_at="2025-01-01T10:00:00")],
                "b": [FakeEvent(recorded_at="2025-01-01T12:00:00")],
            },
            recent_knowledge_by_project={},
            recent_memories_by_project={},
            org_state=org,
        )
        s2 = OrganizationActivityProjection.project(
            project_ids=["a", "b", "c"],
            recent_events_by_project={
                "a": [FakeEvent(recorded_at="2025-01-01T10:00:00")],
                "b": [FakeEvent(recorded_at="2025-01-01T12:00:00")],
            },
            recent_knowledge_by_project={},
            recent_memories_by_project={},
            org_state=org,
        )
        d1 = s1.to_dict()
        d2 = s2.to_dict()
        d1.pop("compiled_at")
        d2.pop("compiled_at")
        assert d1 == d2


# ── OrganizationContinuationState ──────────────────────────────────────────

class TestOrganizationContinuationState:
    def test_to_dict(self) -> None:
        state = OrganizationContinuationState(compiled_at="2025-01-01")
        d = state.to_dict()
        assert d["compiled_at"] == "2025-01-01"
        assert "health" in d
        assert "projects_needing_attention" in d
        import json
        serialized = json.dumps(d)
        assert isinstance(serialized, str)


class TestContinuationAttention:
    def test_inactive_projects_need_attention(self) -> None:
        org = OrganizationState(compiled_at="2025-01-01", project_ids=["a", "b"])
        activity = OrganizationActivityProjection.project(
            project_ids=["a", "b"],
            recent_events_by_project={},
            recent_knowledge_by_project={},
            recent_memories_by_project={},
            org_state=org,
        )
        graph = OrganizationGraphProjection.project(org)
        cont = OrganizationContinuationProjection.project(org, graph, activity)
        assert "a" in cont.projects_needing_attention
        assert "b" in cont.projects_needing_attention


class TestContinuationNextActions:
    def test_actions_for_inactive_projects(self) -> None:
        org = OrganizationState(compiled_at="2025-01-01", project_ids=["a"])
        activity = OrganizationActivityProjection.project(
            project_ids=["a"],
            recent_events_by_project={},
            recent_knowledge_by_project={},
            recent_memories_by_project={},
            org_state=org,
        )
        graph = OrganizationGraphProjection.project(org)
        cont = OrganizationContinuationProjection.project(org, graph, activity)
        assert any("inactive" in a for a in cont.organizational_next_actions)

    def test_actions_for_conflict_hotspots(self) -> None:
        org = OrganizationState(
            compiled_at="2025-01-01",
            project_ids=["a", "b"],
            cross_project_conflicts=[
                _conflict("k1", "k2", "a", "b"),
            ],
        )
        activity = OrganizationActivityProjection.project(
            project_ids=["a", "b"],
            recent_events_by_project={
                "a": [FakeEvent(recorded_at="2025-01-01T12:00:00")],
                "b": [FakeEvent(recorded_at="2025-01-01T12:00:00")],
            },
            recent_knowledge_by_project={},
            recent_memories_by_project={},
            org_state=org,
        )
        graph = OrganizationGraphProjection.project(org)
        cont = OrganizationContinuationProjection.project(org, graph, activity)
        assert any("contradiction" in a.lower() or "conflict" in a.lower() for a in cont.organizational_next_actions)


class TestContinuationSummary:
    def test_summary_bounded(self) -> None:
        org = OrganizationState(compiled_at="2025-01-01", project_ids=["a"])
        activity = OrganizationActivityProjection.project(
            project_ids=["a"],
            recent_events_by_project={},
            recent_knowledge_by_project={},
            recent_memories_by_project={},
            org_state=org,
        )
        graph = OrganizationGraphProjection.project(org)
        cont = OrganizationContinuationProjection.project(org, graph, activity)
        assert len(cont.continuation_summary) <= cont.MAX_SUMMARY_ITEMS

    def test_summary_contains_counts(self) -> None:
        org = OrganizationState(compiled_at="2025-01-01", project_ids=["a", "b"])
        activity = OrganizationActivityProjection.project(
            project_ids=["a", "b"],
            recent_events_by_project={
                "a": [FakeEvent(recorded_at="2025-01-01T12:00:00")],
            },
            recent_knowledge_by_project={},
            recent_memories_by_project={},
            org_state=org,
        )
        graph = OrganizationGraphProjection.project(org)
        cont = OrganizationContinuationProjection.project(org, graph, activity)
        assert any("active" in s and "projects" in s for s in cont.continuation_summary)


class TestContinuationHealth:
    def test_health_computed(self) -> None:
        org = OrganizationState(compiled_at="2025-01-01", project_ids=["a", "b"])
        activity = OrganizationActivityProjection.project(
            project_ids=["a", "b"],
            recent_events_by_project={
                "a": [FakeEvent(recorded_at="2025-01-01T12:00:00")],
            },
            recent_knowledge_by_project={},
            recent_memories_by_project={},
            org_state=org,
        )
        graph = OrganizationGraphProjection.project(org)
        cont = OrganizationContinuationProjection.project(org, graph, activity)
        assert cont.health.activity_coverage == 0.5
        assert 0 <= cont.health.overall <= 1.0


class TestContinuationProvenance:
    def test_activity_compiled_at_stored(self) -> None:
        org = OrganizationState(compiled_at="2025-01-01", project_ids=["a"])
        activity = OrganizationActivityProjection.project(
            project_ids=["a"],
            recent_events_by_project={},
            recent_knowledge_by_project={},
            recent_memories_by_project={},
            org_state=org,
        )
        graph = OrganizationGraphProjection.project(org)
        cont = OrganizationContinuationProjection.project(org, graph, activity)
        assert cont.activity_compiled_at == activity.compiled_at


class TestContinuationDeterminism:
    def test_deterministic(self) -> None:
        org = OrganizationState(compiled_at="2025-01-01", project_ids=["a", "b", "c"])
        activity = OrganizationActivityProjection.project(
            project_ids=["a", "b", "c"],
            recent_events_by_project={
                "a": [FakeEvent(recorded_at="2025-01-01T10:00:00")],
            },
            recent_knowledge_by_project={},
            recent_memories_by_project={},
            org_state=org,
        )
        graph = OrganizationGraphProjection.project(org)
        c1 = OrganizationContinuationProjection.project(org, graph, activity)
        c2 = OrganizationContinuationProjection.project(org, graph, activity)
        d1 = c1.to_dict()
        d2 = c2.to_dict()
        d1.pop("compiled_at")
        d2.pop("compiled_at")
        assert d1 == d2
