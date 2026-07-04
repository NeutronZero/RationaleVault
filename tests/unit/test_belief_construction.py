from __future__ import annotations

import pytest
from datetime import datetime, timezone
from rationalevault.cognitive_head.evidence import EvidenceBundle, EvidenceAggregator
from rationalevault.cognitive_head.assessment import AssessmentEngine, EvidenceAssessment
from rationalevault.cognitive_head.belief import BeliefEngine, Belief
from rationalevault.cognitive_head.propagation import PropagationEngine
from rationalevault.cognitive_head.reasoning_report import ReasoningReport, ReasoningReportBuilder
from rationalevault.cognitive_head.engine import ReasoningEngine
from rationalevault.projections.knowledge import KnowledgeState, ConflictRecord
from rationalevault.knowledge.models import (
    KnowledgeObject,
    KnowledgeType,
    KnowledgeDomain,
    KnowledgeConfidence,
    ProvenanceChain
)


def _create_knowledge_state(project_id: str, invariants: list[KnowledgeObject], conflicts: list[ConflictRecord], support_graph: dict[str, list[str]] = None) -> KnowledgeState:
    return KnowledgeState(
        project_id=project_id,
        compiled_at="2026-06-26T12:00:00Z",
        active_knowledge=invariants,
        invariants=invariants,
        conflict_queue=conflicts,
        support_graph=support_graph or {}
    )


def _create_invariant(title: str, content: str, sup_ids: list[str], conf_ids: list[str], score: float) -> KnowledgeObject:
    k_conf = KnowledgeConfidence(len(sup_ids), 1, len(conf_ids), score)
    prov = ProvenanceChain("k-1", sup_ids, ["1"], "syn-1", k_conf, len(sup_ids))
    return KnowledgeObject(
        id=title.lower().replace(" ", "-"),
        version=1,
        title=title,
        content=content,
        knowledge_type=KnowledgeType.PROJECT_INVARIANT,
        knowledge_domain=KnowledgeDomain.ARCHITECTURE,
        confidence=k_conf,
        importance="high",
        provenance=prov,
        supporting_memory_ids=sup_ids,
        contradicting_memory_ids=conf_ids,
        created_at="2026-06-26T12:00:00Z",
        updated_at="2026-06-26T12:00:00Z"
    )


def test_confidence_determinism_and_explainability() -> None:
    # Build bundle
    bundle = EvidenceBundle(
        concept_id="test-rule",
        title="Test Rule",
        content="Always follow X",
        supporting_evidence=["mem-1", "mem-2"],
        contradicting_evidence=["mem-3"],
        provenance=["ev-1"],
        freshness=10.0,
        source_diversity=3,
        base_confidence=0.8
    )

    assessment1 = AssessmentEngine.assess(bundle)
    assessment2 = AssessmentEngine.assess(bundle)

    # Determinism
    assert assessment1 == assessment2
    assert assessment1.base_confidence == 0.8
    # Agreement: min(0.2, (3 - 1) * 0.1) = 0.2
    assert assessment1.agreement_score == pytest.approx(0.2)
    # Corroboration: min(0.2, 2 * 0.05) = 0.1
    assert assessment1.corroboration_score == pytest.approx(0.1)
    # Contradiction penalty: min(1.0, 1 * 0.3) = 0.3
    assert assessment1.contradiction_penalty == pytest.approx(0.3)
    # Staleness: min(0.5, 10.0 * 0.01) = 0.1
    assert assessment1.staleness_penalty == pytest.approx(0.1)
    
    # Expected local confidence: 0.8 + 0.2 + 0.1 - 0.3 - 0.1 = 0.7
    assert assessment1.local_confidence == pytest.approx(0.7)
    assert assessment1.final_confidence == pytest.approx(0.7)


def test_belief_id_determinism() -> None:
    bundle = EvidenceBundle(
        concept_id="test-rule",
        title="Unique Rule Title",
        content="Content rule X",
        supporting_evidence=[],
        contradicting_evidence=[],
        provenance=[],
        freshness=0.0,
        source_diversity=1,
        base_confidence=1.0
    )
    assessment = AssessmentEngine.assess(bundle)
    belief1 = BeliefEngine.construct(bundle.title, bundle.content, assessment, bundle.supporting_evidence)
    belief2 = BeliefEngine.construct(bundle.title, bundle.content, assessment, bundle.supporting_evidence)

    assert belief1.belief_id == belief2.belief_id
    assert belief1.belief_id.startswith("BEL-")


def test_assessment_independence() -> None:
    bundle1 = EvidenceBundle(
        concept_id="rule",
        title="Rule",
        content="Content",
        supporting_evidence=["mem-1"],
        contradicting_evidence=[],
        provenance=[],
        freshness=0.0,
        source_diversity=1,
        base_confidence=0.9
    )
    # Bundle 2 has different ID/title but identical evidence stats
    bundle2 = EvidenceBundle(
        concept_id="rule-diff",
        title="Rule Different",
        content="Content",
        supporting_evidence=["mem-1"],
        contradicting_evidence=[],
        provenance=[],
        freshness=0.0,
        source_diversity=1,
        base_confidence=0.9
    )

    assessment1 = AssessmentEngine.assess(bundle1)
    assessment2 = AssessmentEngine.assess(bundle2)

    # Changing non-evidence details should not alter confidence scores
    assert assessment1.local_confidence == assessment2.local_confidence


def test_attenuated_propagation() -> None:
    # Rule A supports Rule B
    # Rule A has a low confidence (0.4)
    # Rule B has a high local confidence (0.9)
    # Attenuated penalty from Rule A is (0.4 - 1.0) * 0.8 = -0.48
    # Rule B's final confidence should be 0.9 - 0.48 = 0.42
    
    assessment_a = EvidenceAssessment(0.4, 0.0, 0.0, 0.0, 0.0, 0.0, 0.4, 0.4)
    assessment_b = EvidenceAssessment(0.9, 0.0, 0.0, 0.0, 0.0, 0.0, 0.9, 0.9)

    belief_a = Belief("BEL-A", "Rule A", "Content A", 0.4, 0.0, 0.4, assessment_a, ["synth-a"], [])
    belief_b = Belief("BEL-B", "Rule B", "Content B", 0.9, 0.0, 0.9, assessment_b, ["synth-b"], [])

    concept_id_to_belief_id = {
        "synth-a": "BEL-A",
        "synth-b": "BEL-B"
    }
    support_graph = {
        "synth-a": ["synth-b"]
    }

    updated = PropagationEngine.propagate_beliefs([belief_a, belief_b], concept_id_to_belief_id, support_graph)
    
    belief_b_updated = next(b for b in updated if b.belief_id == "BEL-B")
    assert belief_b_updated.propagated_adjustment == pytest.approx(-0.48)
    assert belief_b_updated.final_confidence == pytest.approx(0.42)


def test_propagation_order_independence() -> None:
    # A -> B -> C
    # Changing walking/declaration order of beliefs does not alter final confidences.
    
    assessment_a = EvidenceAssessment(0.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.5, 0.5)
    assessment_b = EvidenceAssessment(0.9, 0.0, 0.0, 0.0, 0.0, 0.0, 0.9, 0.9)
    assessment_c = EvidenceAssessment(1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0)

    concept_id_to_belief_id = {
        "a": "BEL-A",
        "b": "BEL-B",
        "c": "BEL-C"
    }
    support_graph = {
        "a": ["b"],
        "b": ["c"]
    }

    # Order 1: A, B, C
    b_a1 = Belief("BEL-A", "A", "Content", 0.5, 0.0, 0.5, assessment_a, ["a"], [])
    b_b1 = Belief("BEL-B", "B", "Content", 0.9, 0.0, 0.9, assessment_b, ["b"], [])
    b_c1 = Belief("BEL-C", "C", "Content", 1.0, 0.0, 1.0, assessment_c, ["c"], [])
    res1 = PropagationEngine.propagate_beliefs([b_a1, b_b1, b_c1], concept_id_to_belief_id, support_graph)

    # Order 2: C, B, A
    b_a2 = Belief("BEL-A", "A", "Content", 0.5, 0.0, 0.5, assessment_a, ["a"], [])
    b_b2 = Belief("BEL-B", "B", "Content", 0.9, 0.0, 0.9, assessment_b, ["b"], [])
    b_c2 = Belief("BEL-C", "C", "Content", 1.0, 0.0, 1.0, assessment_c, ["c"], [])
    res2 = PropagationEngine.propagate_beliefs([b_c2, b_b2, b_a2], concept_id_to_belief_id, support_graph)

    map1 = {b.belief_id: b.final_confidence for b in res1}
    map2 = {b.belief_id: b.final_confidence for b in res2}

    assert map1 == map2


def test_cyclic_reasoning_prevention() -> None:
    # A supports B, B supports A (cycle)
    # The cycle should be detected and propagation skipped (terminating the loop)
    
    assessment_a = EvidenceAssessment(0.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.5, 0.5)
    assessment_b = EvidenceAssessment(0.9, 0.0, 0.0, 0.0, 0.0, 0.0, 0.9, 0.9)

    b_a = Belief("BEL-A", "A", "Content", 0.5, 0.0, 0.5, assessment_a, ["a"], [])
    b_b = Belief("BEL-B", "B", "Content", 0.9, 0.0, 0.9, assessment_b, ["b"], [])

    concept_id_to_belief_id = {"a": "BEL-A", "b": "BEL-B"}
    support_graph = {
        "a": ["b"],
        "b": ["a"]
    }

    res = PropagationEngine.propagate_beliefs([b_a, b_b], concept_id_to_belief_id, support_graph)
    
    # Final confidence remains unchanged because cycle causes cycle bypass
    map_res = {b.belief_id: b.final_confidence for b in res}
    assert map_res["BEL-A"] == 0.5
    assert map_res["BEL-B"] == 0.9


def test_non_mutating_suppression() -> None:
    k1 = _create_invariant("Database postgres", "db_engine = postgres", ["mem-1"], [], 0.9)
    k2 = _create_invariant("Database sqlite", "db_engine = sqlite", ["mem-2"], [], 0.9)

    # This creates a conflict on kw 'postgres' or 'sqlite'
    state = _create_knowledge_state("project-a", [k1, k2], [])
    
    # Run reasoning report with NO suppression
    report = ReasoningEngine.reason([state])
    assert report.summary["contradictions_count"] > 0
    assert report.summary["active_contradictions_count"] > 0
    
    # Suppress the contradiction ID
    contr_id = report.contradictions[0].finding_id
    report_suppressed = ReasoningEngine.reason([state], suppressed_ids={contr_id})
    
    # Underlying finding is preserved in the list
    assert len(report_suppressed.contradictions) == 1
    assert report_suppressed.contradictions[0].suppressed is True
    
    # Active contradictions count should drop
    assert report_suppressed.summary["active_contradictions_count"] == 0
    assert report_suppressed.summary["contradictions_count"] == 1
    
    # Confidence metrics must remain identical (suppression is non-mutating)
    assert report.overall_confidence == pytest.approx(report_suppressed.overall_confidence)
