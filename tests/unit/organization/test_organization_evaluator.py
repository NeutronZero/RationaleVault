"""Tests for I11.3 — Organization Evaluator."""
from __future__ import annotations

import pytest

from rationalevault.evaluation.organization_evaluator import (
    OrganizationEvaluator,
    check_organization_gates,
)
from rationalevault.organization.models import (
    CrossProjectConflict,
    KnowledgeLineage,
    OrganizationHealth,
    OrganizationState,
    SharedKnowledge,
    TransferabilityTelemetry,
)


def _state(**kwargs) -> OrganizationState:
    defaults = dict(
        compiled_at="2026-01-01T00:00:00+00:00",
        active_lineages={},
        shared_knowledge=[],
        cross_project_conflicts=[],
        invariants_across_projects=[],
        project_clusters=[],
        transferability_telemetry=TransferabilityTelemetry(),
        health=OrganizationHealth(),
    )
    defaults.update(kwargs)
    return OrganizationState(**defaults)


class TestLineageCompleteness:
    def test_no_lineages(self) -> None:
        s = _state()
        e = OrganizationEvaluator()
        r = e.evaluate(s)
        assert r.lineage_completeness == 1.0

    def test_complete_lineages(self) -> None:
        s = _state(active_lineages={
            "k1": KnowledgeLineage("k1", "proj_a", ["proj_b"], ["proj_a", "proj_b"], 1),
        })
        e = OrganizationEvaluator()
        r = e.evaluate(s)
        assert r.lineage_completeness == 1.0

    def test_incomplete_lineage(self) -> None:
        s = _state(active_lineages={
            "k1": KnowledgeLineage("k1", "", ["proj_b"], [], 0),
        })
        e = OrganizationEvaluator()
        r = e.evaluate(s)
        assert r.lineage_completeness == 0.0


class TestProvenanceChain:
    def test_no_lineages(self) -> None:
        s = _state()
        e = OrganizationEvaluator()
        r = e.evaluate(s)
        assert r.provenance_chain == 1.0

    def test_valid_chain(self) -> None:
        s = _state(active_lineages={
            "k1": KnowledgeLineage("k1", "proj_a", ["proj_b"], ["proj_a", "proj_b"], 1),
        })
        e = OrganizationEvaluator()
        r = e.evaluate(s)
        assert r.provenance_chain == 1.0

    def test_missing_transfer_path(self) -> None:
        s = _state(active_lineages={
            "k1": KnowledgeLineage("k1", "proj_a", ["proj_b"], [], 0),
        })
        e = OrganizationEvaluator()
        r = e.evaluate(s)
        assert r.provenance_chain == 0.0


class TestContradictionDetection:
    def test_no_conflicts(self) -> None:
        s = _state()
        e = OrganizationEvaluator()
        r = e.evaluate(s)
        assert r.contradiction_detection == 1.0

    def test_conflicts_with_reasons(self) -> None:
        s = _state(cross_project_conflicts=[
            CrossProjectConflict("c1", "k1", "k2", "a", "b", "T", "T", 0.8, ["same_title"]),
        ])
        e = OrganizationEvaluator()
        r = e.evaluate(s)
        assert r.contradiction_detection == 1.0

    def test_conflicts_without_reasons(self) -> None:
        s = _state(cross_project_conflicts=[
            CrossProjectConflict("c1", "k1", "k2", "a", "b", "T", "T"),
        ])
        e = OrganizationEvaluator()
        r = e.evaluate(s)
        assert r.contradiction_detection == 0.0


class TestTelemetryAccuracy:
    def test_no_raw_data(self) -> None:
        s = _state()
        e = OrganizationEvaluator()
        r = e.evaluate(s)
        assert r.telemetry_accuracy == 1.0

    def test_matching_counts(self) -> None:
        from rationalevault.knowledge.models import KnowledgeObject, KnowledgeType, KnowledgeDomain, KnowledgeLifecycle, KnowledgeConfidence, ProvenanceChain
        conf = KnowledgeConfidence(1, 1, 0, 0.9, 0.9)
        prov = ProvenanceChain("k1", [], [], "", conf, 1)
        k = KnowledgeObject(
            id="k1", version=1, title="T", content="C",
            knowledge_type=KnowledgeType.ARCHITECTURE_PRINCIPLE,
            knowledge_domain=KnowledgeDomain.ARCHITECTURE,
            confidence=conf, importance="high", provenance=prov,
            supporting_memory_ids=[], lifecycle_status=KnowledgeLifecycle.ACTIVE.value,
            project_id="a", transferability="REUSABLE",
        )
        s = _state(transferability_telemetry=TransferabilityTelemetry(
            local_only_count=0, reusable_count=1, organizational_count=0,
            transfer_attempts=1, transfer_matches=1, acceptance_rate=1.0,
        ))
        e = OrganizationEvaluator()
        r = e.evaluate(s, raw_knowledge_by_project={"a": [k]})
        assert r.telemetry_accuracy == 1.0

    def test_mismatched_counts(self) -> None:
        from rationalevault.knowledge.models import KnowledgeObject, KnowledgeType, KnowledgeDomain, KnowledgeLifecycle, KnowledgeConfidence, ProvenanceChain
        conf = KnowledgeConfidence(1, 1, 0, 0.9, 0.9)
        prov = ProvenanceChain("k1", [], [], "", conf, 1)
        k = KnowledgeObject(
            id="k1", version=1, title="T", content="C",
            knowledge_type=KnowledgeType.ARCHITECTURE_PRINCIPLE,
            knowledge_domain=KnowledgeDomain.ARCHITECTURE,
            confidence=conf, importance="high", provenance=prov,
            supporting_memory_ids=[], lifecycle_status=KnowledgeLifecycle.ACTIVE.value,
            project_id="a", transferability="LOCAL_ONLY",
        )
        s = _state(transferability_telemetry=TransferabilityTelemetry(
            local_only_count=0, reusable_count=1, organizational_count=0,
            transfer_attempts=1, transfer_matches=1, acceptance_rate=1.0,
        ))
        e = OrganizationEvaluator()
        r = e.evaluate(s, raw_knowledge_by_project={"a": [k]})
        assert r.telemetry_accuracy == 0.0


class TestIsolation:
    def test_no_lineages(self) -> None:
        s = _state()
        e = OrganizationEvaluator()
        r = e.evaluate(s)
        assert r.isolation == 1.0

    def test_clean_origins(self) -> None:
        s = _state(active_lineages={
            "k1": KnowledgeLineage("k1", "proj_a", ["proj_b"], ["proj_a", "proj_b"], 1),
        })
        e = OrganizationEvaluator()
        r = e.evaluate(s)
        assert r.isolation == 1.0

    def test_missing_origin(self) -> None:
        s = _state(active_lineages={
            "k1": KnowledgeLineage("k1", "", ["proj_b"], [], 0),
        })
        e = OrganizationEvaluator()
        r = e.evaluate(s)
        assert r.isolation == 0.0


class TestDeterminism:
    def test_no_previous(self) -> None:
        s = _state()
        e = OrganizationEvaluator()
        r = e.evaluate(s)
        assert r.determinism == 1.0

    def test_identical_states(self) -> None:
        s1 = _state(active_lineages={
            "k1": KnowledgeLineage("k1", "a", ["b"], ["a", "b"], 1),
        }, shared_knowledge=[
            SharedKnowledge("k1", "T", "ARCHITECTURE_PRINCIPLE", ["a", "b"], 1),
        ])
        s2 = _state(active_lineages={
            "k1": KnowledgeLineage("k1", "a", ["b"], ["a", "b"], 1),
        }, shared_knowledge=[
            SharedKnowledge("k1", "T", "ARCHITECTURE_PRINCIPLE", ["a", "b"], 1),
        ])
        e = OrganizationEvaluator()
        r = e.evaluate(s1, previous_state=s2)
        assert r.determinism == 1.0

    def test_different_lineages(self) -> None:
        s1 = _state(active_lineages={
            "k1": KnowledgeLineage("k1", "a", ["b"], ["a", "b"], 1),
        })
        s2 = _state(active_lineages={
            "k1": KnowledgeLineage("k1", "c", ["d"], ["c", "d"], 1),
        })
        e = OrganizationEvaluator()
        r = e.evaluate(s1, previous_state=s2)
        assert r.determinism == 0.0


class TestLineageReplayability:
    def test_no_previous(self) -> None:
        s = _state()
        e = OrganizationEvaluator()
        r = e.evaluate(s)
        assert r.lineage_replayability == 1.0

    def test_identical(self) -> None:
        s1 = _state(active_lineages={
            "k1": KnowledgeLineage("k1", "a", ["b"], ["a", "b"], 1),
        }, shared_knowledge=[
            SharedKnowledge("k1", "T", "ARCHITECTURE_PRINCIPLE", ["a", "b"], 1),
        ])
        s2 = _state(active_lineages={
            "k1": KnowledgeLineage("k1", "a", ["b"], ["a", "b"], 1),
        }, shared_knowledge=[
            SharedKnowledge("k1", "T", "ARCHITECTURE_PRINCIPLE", ["a", "b"], 1),
        ])
        e = OrganizationEvaluator()
        r = e.evaluate(s1, previous_state=s2)
        assert r.lineage_replayability == 1.0

    def test_different_lineages(self) -> None:
        s1 = _state(active_lineages={
            "k1": KnowledgeLineage("k1", "a", ["b"], ["a", "b"], 1),
        })
        s2 = _state(active_lineages={})
        e = OrganizationEvaluator()
        r = e.evaluate(s1, previous_state=s2)
        assert r.lineage_replayability == 0.0


class TestGates:
    def test_pass(self) -> None:
        s = _state(
            active_lineages={
                "k1": KnowledgeLineage("k1", "a", ["b"], ["a", "b"], 1),
            },
            shared_knowledge=[
                SharedKnowledge("k1", "T", "ARCHITECTURE_PRINCIPLE", ["a", "b"], 1),
            ],
        )
        e = OrganizationEvaluator()
        r = e.evaluate(s, previous_state=s)
        passed, failures = check_organization_gates(r)
        assert passed

    def test_fail_isolation(self) -> None:
        s = _state(active_lineages={
            "k1": KnowledgeLineage("k1", "", ["b"], [], 0),
        })
        e = OrganizationEvaluator()
        r = e.evaluate(s)
        passed, failures = check_organization_gates(r)
        assert not passed
        assert "isolation" in failures

    def test_to_dict(self) -> None:
        s = _state()
        e = OrganizationEvaluator()
        r = e.evaluate(s)
        d = r.to_dict()
        assert "org_projection_success_rate" in d
        assert "passed" in d
