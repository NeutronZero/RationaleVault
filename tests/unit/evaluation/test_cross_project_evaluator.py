"""Tests for I10.6 — Cross-Project Evaluator."""
from __future__ import annotations

import pytest

from rationalevault.evaluation.cross_project_evaluator import (
    CrossProjectEvaluator,
    check_cross_project_gates,
)
from rationalevault.evaluation.cross_project_benchmark import build_benchmark_corpus
from rationalevault.evaluation.thresholds import EvaluationThresholds
from rationalevault.knowledge.models import (
    KnowledgeConfidence,
    KnowledgeDomain,
    KnowledgeLifecycle,
    KnowledgeObject,
    KnowledgeTransferability,
    KnowledgeType,
    ProvenanceChain,
)
from rationalevault.projections.cross_project import (
    CrossProjectHealth,
    CrossProjectKnowledge,
    CrossProjectProjection,
    CrossProjectState,
)


def _conf() -> KnowledgeConfidence:
    return KnowledgeConfidence(
        memory_count=3, source_event_count=2, contradiction_count=0,
        average_memory_confidence=0.9, score=0.9,
    )


def _prov(kid: str) -> ProvenanceChain:
    return ProvenanceChain(
        knowledge_id=kid, source_memory_ids=["m1"],
        source_event_ids=["100"], synthesis_event_id="syn-1",
        confidence=_conf(), evidence_count=1,
    )


def _k(
    kid: str,
    title: str,
    project_id: str = "",
    transferability: str = KnowledgeTransferability.REUSABLE.value,
) -> KnowledgeObject:
    return KnowledgeObject(
        id=kid, version=1, title=title, content=f"content for {title}",
        knowledge_type=KnowledgeType.ARCHITECTURE_PRINCIPLE,
        knowledge_domain=KnowledgeDomain.ARCHITECTURE,
        confidence=_conf(), importance="high", provenance=_prov(kid),
        supporting_memory_ids=[f"m-{kid}"],
        lifecycle_status=KnowledgeLifecycle.ACTIVE.value,
        project_id=project_id,
        transferability=transferability,
    )


def _build_state(**kwargs) -> CrossProjectState:
    """Build a CrossProjectState with defaults for testing."""
    defaults = dict(
        project_id="proj_a",
        compiled_at="2026-01-01T00:00:00+00:00",
        projection_version="1.0",
        source_projects=[],
        transferable_knowledge=[],
        knowledge_by_project={},
        provenance_map={},
        related_projects={},
        health=CrossProjectHealth(
            total_projects=1, total_transferable=0,
            reusable_count=0, organizational_count=0, coverage=0.0,
        ),
    )
    defaults.update(kwargs)
    return CrossProjectState(**defaults)


class TestCrossProjectEvaluator:
    """Tests for CrossProjectEvaluator metrics."""

    def test_perfect_state(self) -> None:
        k = CrossProjectKnowledge(
            knowledge_id="k1", source_project_id="proj_b",
            title="Use Redis", content="content", knowledge_type="ARCHITECTURE_PRINCIPLE",
            transferability="REUSABLE", confidence=0.9, relevance_score=0.8,
            matched_terms=["redis"], reasons=["reusable_knowledge"],
        )
        state = _build_state(
            source_projects=["proj_b"],
            transferable_knowledge=[k],
            knowledge_by_project={"proj_b": ["k1"]},
            provenance_map={"k1": "proj_b"},
            health=CrossProjectHealth(
                total_projects=1, total_transferable=1,
                reusable_count=1, organizational_count=0, coverage=1.0,
            ),
        )
        evaluator = CrossProjectEvaluator()
        result = evaluator.evaluate(state, total_knowledge_in_targets=1)

        assert result.transfer_coverage == 1.0
        assert result.provenance_integrity == 1.0
        assert result.relevance_precision == 0.8
        assert result.isolation_score == 1.0
        assert result.determinism == 1.0
        assert result.transferability_enforcement == 1.0
        passed, failures = result.passes_exit_gate()
        assert passed
        assert failures == []

    def test_transfer_coverage_partial(self) -> None:
        state = _build_state(
            health=CrossProjectHealth(
                total_projects=1, total_transferable=1,
                reusable_count=1, organizational_count=0, coverage=0.5,
            ),
        )
        evaluator = CrossProjectEvaluator()
        result = evaluator.evaluate(state, total_knowledge_in_targets=2)
        assert result.transfer_coverage == 0.5

    def test_transfer_coverage_empty_targets(self) -> None:
        state = _build_state()
        evaluator = CrossProjectEvaluator()
        result = evaluator.evaluate(state, total_knowledge_in_targets=0)
        assert result.transfer_coverage == 1.0

    def test_provenance_integrity_missing_provenance(self) -> None:
        k = CrossProjectKnowledge(
            knowledge_id="k1", source_project_id="proj_b",
            title="Use Redis", content="content", knowledge_type="ARCHITECTURE_PRINCIPLE",
            transferability="REUSABLE", confidence=0.9, relevance_score=0.8,
        )
        state = _build_state(
            transferable_knowledge=[k],
            provenance_map={},  # missing
            knowledge_by_project={"proj_b": ["k1"]},
        )
        evaluator = CrossProjectEvaluator()
        result = evaluator.evaluate(state)
        assert result.provenance_integrity == 0.0

    def test_relevance_precision_empty(self) -> None:
        state = _build_state()
        evaluator = CrossProjectEvaluator()
        result = evaluator.evaluate(state)
        assert result.relevance_precision == 1.0

    def test_relevance_precision_average(self) -> None:
        k1 = CrossProjectKnowledge(
            knowledge_id="k1", source_project_id="proj_b",
            title="A", content="c", knowledge_type="ARCHITECTURE_PRINCIPLE",
            transferability="REUSABLE", confidence=0.9, relevance_score=0.6,
        )
        k2 = CrossProjectKnowledge(
            knowledge_id="k2", source_project_id="proj_b",
            title="B", content="c", knowledge_type="ARCHITECTURE_PRINCIPLE",
            transferability="REUSABLE", confidence=0.9, relevance_score=0.8,
        )
        state = _build_state(
            transferable_knowledge=[k1, k2],
            knowledge_by_project={"proj_b": ["k1", "k2"]},
            provenance_map={"k1": "proj_b", "k2": "proj_b"},
        )
        evaluator = CrossProjectEvaluator()
        result = evaluator.evaluate(state)
        assert result.relevance_precision == pytest.approx(0.7)

    def test_isolation_score_clean(self) -> None:
        k = CrossProjectKnowledge(
            knowledge_id="k1", source_project_id="proj_b",
            title="A", content="c", knowledge_type="ARCHITECTURE_PRINCIPLE",
            transferability="REUSABLE", confidence=0.9, relevance_score=0.8,
        )
        state = _build_state(
            transferable_knowledge=[k],
            knowledge_by_project={"proj_b": ["k1"]},
            provenance_map={"k1": "proj_b"},
        )
        evaluator = CrossProjectEvaluator()
        result = evaluator.evaluate(state)
        assert result.isolation_score == 1.0

    def test_determinism_same_inputs(self) -> None:
        k = CrossProjectKnowledge(
            knowledge_id="k1", source_project_id="proj_b",
            title="A", content="c", knowledge_type="ARCHITECTURE_PRINCIPLE",
            transferability="REUSABLE", confidence=0.9, relevance_score=0.8,
        )
        state1 = _build_state(
            transferable_knowledge=[k],
            knowledge_by_project={"proj_b": ["k1"]},
            provenance_map={"k1": "proj_b"},
        )
        state2 = _build_state(
            transferable_knowledge=[k],
            knowledge_by_project={"proj_b": ["k1"]},
            provenance_map={"k1": "proj_b"},
        )
        evaluator = CrossProjectEvaluator()
        result = evaluator.evaluate(state1, previous_state=state2)
        assert result.determinism == 1.0

    def test_determinism_different_inputs(self) -> None:
        k1 = CrossProjectKnowledge(
            knowledge_id="k1", source_project_id="proj_b",
            title="A", content="c", knowledge_type="ARCHITECTURE_PRINCIPLE",
            transferability="REUSABLE", confidence=0.9, relevance_score=0.8,
        )
        k2 = CrossProjectKnowledge(
            knowledge_id="k2", source_project_id="proj_b",
            title="B", content="c", knowledge_type="ARCHITECTURE_PRINCIPLE",
            transferability="REUSABLE", confidence=0.9, relevance_score=0.8,
        )
        state1 = _build_state(
            transferable_knowledge=[k1],
            knowledge_by_project={"proj_b": ["k1"]},
            provenance_map={"k1": "proj_b"},
        )
        state2 = _build_state(
            transferable_knowledge=[k2],
            knowledge_by_project={"proj_b": ["k2"]},
            provenance_map={"k2": "proj_b"},
        )
        evaluator = CrossProjectEvaluator()
        result = evaluator.evaluate(state1, previous_state=state2)
        assert result.determinism == 0.0

    def test_transferability_enforcement_clean(self) -> None:
        k = CrossProjectKnowledge(
            knowledge_id="k1", source_project_id="proj_b",
            title="A", content="c", knowledge_type="ARCHITECTURE_PRINCIPLE",
            transferability="REUSABLE", confidence=0.9, relevance_score=0.8,
        )
        state = _build_state(
            transferable_knowledge=[k],
            knowledge_by_project={"proj_b": ["k1"]},
            provenance_map={"k1": "proj_b"},
        )
        evaluator = CrossProjectEvaluator()
        result = evaluator.evaluate(state)
        assert result.transferability_enforcement == 1.0

    def test_transferability_enforcement_violation(self) -> None:
        k = CrossProjectKnowledge(
            knowledge_id="k1", source_project_id="proj_b",
            title="A", content="c", knowledge_type="ARCHITECTURE_PRINCIPLE",
            transferability="LOCAL_ONLY", confidence=0.9, relevance_score=0.8,
        )
        state = _build_state(
            transferable_knowledge=[k],
            knowledge_by_project={"proj_b": ["k1"]},
            provenance_map={"k1": "proj_b"},
        )
        evaluator = CrossProjectEvaluator()
        result = evaluator.evaluate(state)
        assert result.transferability_enforcement == 0.0

    def test_to_dict_serialization(self) -> None:
        state = _build_state()
        evaluator = CrossProjectEvaluator()
        result = evaluator.evaluate(state)
        d = result.to_dict()
        assert "cross_project_success_rate" in d
        assert "passed" in d
        assert "failures" in d

    def test_gate_pass(self) -> None:
        state = _build_state(
            health=CrossProjectHealth(
                total_projects=1, total_transferable=1,
                reusable_count=1, organizational_count=0, coverage=1.0,
            ),
        )
        k = CrossProjectKnowledge(
            knowledge_id="k1", source_project_id="proj_b",
            title="A", content="c", knowledge_type="ARCHITECTURE_PRINCIPLE",
            transferability="REUSABLE", confidence=0.9, relevance_score=0.8,
        )
        state = _build_state(
            transferable_knowledge=[k],
            knowledge_by_project={"proj_b": ["k1"]},
            provenance_map={"k1": "proj_b"},
            health=CrossProjectHealth(
                total_projects=1, total_transferable=1,
                reusable_count=1, organizational_count=0, coverage=1.0,
            ),
        )
        evaluator = CrossProjectEvaluator()
        result = evaluator.evaluate(state, total_knowledge_in_targets=1)
        passed, failures = check_cross_project_gates(result)
        assert passed

    def test_gate_fail_isolation(self) -> None:
        k = CrossProjectKnowledge(
            knowledge_id="k1", source_project_id="proj_b",
            title="A", content="c", knowledge_type="ARCHITECTURE_PRINCIPLE",
            transferability="LOCAL_ONLY", confidence=0.9, relevance_score=0.8,
        )
        state = _build_state(
            transferable_knowledge=[k],
            knowledge_by_project={"proj_b": ["k1"]},
            provenance_map={"k1": "proj_b"},
        )
        evaluator = CrossProjectEvaluator()
        result = evaluator.evaluate(state)
        passed, failures = check_cross_project_gates(result)
        assert not passed
        assert "transferability_enforcement" in failures

    def test_evaluator_with_benchmark_corpus(self) -> None:
        """Evaluate against the benchmark corpus scenarios."""
        corpus = build_benchmark_corpus()
        evaluator = CrossProjectEvaluator()

        for scenario in corpus.scenarios:
            current = scenario.projects.get("proj_a", [])
            targets = {pid: klist for pid, klist in scenario.projects.items() if pid != "proj_a"}

            state = CrossProjectProjection.project(
                current_project_id="proj_a",
                current_knowledge=current,
                target_knowledge=targets,
                query=scenario.query,
                transferability_filter=scenario.transferability_filter,
            )

            total_knowledge = sum(len(klist) for klist in targets.values())
            result = evaluator.evaluate(state, total_knowledge_in_targets=total_knowledge)

            # All metrics should be between 0 and 1
            assert 0.0 <= result.transfer_coverage <= 1.0
            assert 0.0 <= result.provenance_integrity <= 1.0
            assert 0.0 <= result.relevance_precision <= 1.0
            assert 0.0 <= result.isolation_score <= 1.0
            assert 0.0 <= result.determinism <= 1.0
            assert 0.0 <= result.transferability_enforcement <= 1.0
