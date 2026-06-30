"""Tests for I11.1 — Organization Models."""
from __future__ import annotations

import json

import pytest

from rationalevault.organization.models import (
    CrossProjectConflict,
    KnowledgeLineage,
    OrganizationHealth,
    OrganizationState,
    SharedKnowledge,
    TransferabilityTelemetry,
)


class TestTransferabilityTelemetry:
    def test_default_values(self) -> None:
        t = TransferabilityTelemetry()
        assert t.local_only_count == 0
        assert t.reusable_count == 0
        assert t.organizational_count == 0
        assert t.transfer_attempts == 0
        assert t.transfer_matches == 0
        assert t.acceptance_rate == 0.0

    def test_to_dict(self) -> None:
        t = TransferabilityTelemetry(
            local_only_count=10, reusable_count=5, organizational_count=2,
            transfer_attempts=17, transfer_matches=7, acceptance_rate=7 / 17,
        )
        d = t.to_dict()
        assert d["local_only_count"] == 10
        assert d["acceptance_rate"] == round(7 / 17, 4)

    def test_serializable(self) -> None:
        t = TransferabilityTelemetry(
            local_only_count=3, reusable_count=2, organizational_count=1,
            transfer_attempts=6, transfer_matches=3, acceptance_rate=0.5,
        )
        serialized = json.dumps(t.to_dict())
        assert isinstance(serialized, str)


class TestKnowledgeLineage:
    def test_basic_lineage(self) -> None:
        l = KnowledgeLineage(
            knowledge_id="k1", origin_project="proj_a",
            current_projects=["proj_b", "proj_c"],
            transfer_path=["proj_a", "proj_b", "proj_c"],
            depth=2,
        )
        assert l.origin_project == "proj_a"
        assert l.depth == 2
        assert len(l.transfer_path) == 3

    def test_to_dict(self) -> None:
        l = KnowledgeLineage(
            knowledge_id="k1", origin_project="proj_a",
            current_projects=["proj_b"],
            transfer_path=["proj_a", "proj_b"],
            depth=1,
        )
        d = l.to_dict()
        assert d["knowledge_id"] == "k1"
        assert d["depth"] == 1

    def test_empty_defaults(self) -> None:
        l = KnowledgeLineage(knowledge_id="k1", origin_project="proj_a")
        assert l.current_projects == []
        assert l.transfer_path == []
        assert l.depth == 0


class TestSharedKnowledge:
    def test_basic(self) -> None:
        s = SharedKnowledge(
            knowledge_id="k1", title="Use PostgreSQL",
            knowledge_type="ARCHITECTURE_PRINCIPLE",
            present_in_projects=["proj_a", "proj_b"],
            transfer_count=1,
        )
        assert len(s.present_in_projects) == 2
        assert s.transfer_count == 1

    def test_independent_from_lineage(self) -> None:
        s = SharedKnowledge(
            knowledge_id="k1", title="Use PostgreSQL",
            knowledge_type="ARCHITECTURE_PRINCIPLE",
            present_in_projects=["proj_a", "proj_b"],
            transfer_count=0,  # independent creation, no transfer
        )
        assert s.transfer_count == 0
        assert len(s.present_in_projects) == 2

    def test_to_dict(self) -> None:
        s = SharedKnowledge(
            knowledge_id="k1", title="Use PostgreSQL",
            knowledge_type="ARCHITECTURE_PRINCIPLE",
            present_in_projects=["proj_a"],
        )
        d = s.to_dict()
        assert d["knowledge_id"] == "k1"


class TestCrossProjectConflict:
    def test_with_reasons(self) -> None:
        c = CrossProjectConflict(
            conflict_id="conflict-1",
            knowledge_a_id="k1", knowledge_b_id="k2",
            project_a="proj_a", project_b="proj_b",
            knowledge_a_title="Auth", knowledge_b_title="Auth",
            confidence=0.8,
            reasons=["same_title", "same_type", "content_divergence"],
        )
        assert len(c.reasons) == 3
        assert c.confidence == 0.8

    def test_to_dict(self) -> None:
        c = CrossProjectConflict(
            conflict_id="c1", knowledge_a_id="k1", knowledge_b_id="k2",
            project_a="a", project_b="b",
            knowledge_a_title="T1", knowledge_b_title="T2",
        )
        d = c.to_dict()
        assert "reasons" in d
        assert d["conflict_id"] == "c1"


class TestOrganizationHealth:
    def test_adoption_rate(self) -> None:
        h = OrganizationHealth(
            total_projects=3, total_knowledge=100,
            transferable_knowledge=60, shared_knowledge_count=20,
            knowledge_adoption_rate=20 / 60,
        )
        assert h.knowledge_adoption_rate == pytest.approx(1 / 3)

    def test_to_dict(self) -> None:
        h = OrganizationHealth(
            total_projects=2, total_knowledge=50,
            transferable_knowledge=30, shared_knowledge_count=10,
            knowledge_adoption_rate=10 / 30,
        )
        d = h.to_dict()
        assert d["total_projects"] == 2
        assert "knowledge_adoption_rate" in d


class TestOrganizationState:
    def test_empty_state(self) -> None:
        s = OrganizationState(compiled_at="2026-01-01T00:00:00+00:00")
        assert s.project_ids == []
        assert s.active_lineages == {}
        assert s.shared_knowledge == []
        assert s.cross_project_conflicts == []
        assert s.invariants_across_projects == []
        assert s.project_clusters == []

    def test_to_dict_serializable(self) -> None:
        s = OrganizationState(
            compiled_at="2026-01-01T00:00:00+00:00",
            project_ids=["a", "b"],
            active_lineages={
                "k1": KnowledgeLineage(
                    knowledge_id="k1", origin_project="a",
                    current_projects=["b"], transfer_path=["a", "b"], depth=1,
                ),
            },
            shared_knowledge=[
                SharedKnowledge("k1", "Use PG", "ARCHITECTURE_PRINCIPLE", ["a", "b"], 1),
            ],
            cross_project_conflicts=[],
            invariants_across_projects=[],
            project_clusters=[["a", "b"]],
            transferability_telemetry=TransferabilityTelemetry(
                local_only_count=5, reusable_count=3, organizational_count=2,
                transfer_attempts=10, transfer_matches=5, acceptance_rate=0.5,
            ),
            health=OrganizationHealth(
                total_projects=2, total_knowledge=10,
                transferable_knowledge=5, shared_knowledge_count=1,
                knowledge_adoption_rate=0.2,
            ),
        )
        d = s.to_dict()
        serialized = json.dumps(d)
        assert isinstance(serialized, str)
        assert d["active_lineage_count"] == 1
        assert d["shared_knowledge_count"] == 1

    def test_version_default(self) -> None:
        s = OrganizationState(compiled_at="2026-01-01T00:00:00+00:00")
        assert s.projection_version == "1.0"
