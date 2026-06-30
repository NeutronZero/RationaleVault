from __future__ import annotations

import pytest
from rationalevault.projections.knowledge import KnowledgeState, ConflictRecord
from rationalevault.knowledge.models import (
    KnowledgeObject,
    KnowledgeType,
    KnowledgeDomain,
    KnowledgeConfidence,
    ProvenanceChain
)
from rationalevault.cognitive_head.cognitive_reducer import CognitiveStateReducer


def _create_knowledge_state(project_id: str, invariants: list[KnowledgeObject], conflicts: list[ConflictRecord]) -> KnowledgeState:
    return KnowledgeState(
        project_id=project_id,
        compiled_at="2026-06-26T12:00:00Z",
        active_knowledge=invariants,
        invariants=invariants,
        conflict_queue=conflicts
    )


def _create_invariant(title: str, sup_ids: list[str], conf_ids: list[str], score: float) -> KnowledgeObject:
    k_conf = KnowledgeConfidence(len(sup_ids), 1, len(conf_ids), score)
    prov = ProvenanceChain("k-1", sup_ids, ["1"], "syn-1", k_conf, len(sup_ids))
    return KnowledgeObject(
        id=title.lower().replace(" ", "-"),
        version=1,
        title=title,
        content="Invariance content",
        knowledge_type=KnowledgeType.PROJECT_INVARIANT,
        knowledge_domain=KnowledgeDomain.ARCHITECTURE,
        confidence=k_conf,
        importance="high",
        provenance=prov,
        supporting_memory_ids=sup_ids,
        contradicting_memory_ids=conf_ids
    )


def test_reducer_structured_reduction() -> None:
    inv1 = _create_invariant("Always postgres", ["mem-1", "mem-2"], ["mem-3"], 0.9)
    inv2 = _create_invariant("Standards check", ["mem-4"], [], 0.8)
    
    conflict = ConflictRecord("conf-1", "k-a", "k-b", "Always postgres", "Never postgres", 1.0, "2026-06-26T12:00:00Z")

    state1 = _create_knowledge_state("project-a", [inv1], [conflict])
    state2 = _create_knowledge_state("project-b", [inv2], [])

    reduction = CognitiveStateReducer.reduce([state1, state2])
    
    assert "Always postgres" in reduction.invariants
    assert "Standards check" in reduction.invariants
    assert "mem-1" in reduction.supporting_evidence
    assert "mem-3" in reduction.conflicting_evidence
    assert reduction.confidence == pytest.approx(0.85)
    assert len(reduction.unresolved_questions) == 1
    assert "Always postgres vs Never postgres" in reduction.unresolved_questions[0]


def test_reducer_order_determinism() -> None:
    inv1 = _create_invariant("Always postgres", ["mem-1"], [], 0.9)
    inv2 = _create_invariant("Standards check", ["mem-2"], [], 0.8)

    state1 = _create_knowledge_state("project-a", [inv1], [])
    state2 = _create_knowledge_state("project-b", [inv2], [])

    # Order of inputs: state1 then state2
    reduction1 = CognitiveStateReducer.reduce([state1, state2])
    # Order of inputs: state2 then state1
    reduction2 = CognitiveStateReducer.reduce([state2, state1])

    # Both must produce identical results due to internal sorting by project_id
    assert reduction1.invariants == reduction2.invariants
    assert reduction1.supporting_evidence == reduction2.supporting_evidence
    assert reduction1.confidence == reduction2.confidence
