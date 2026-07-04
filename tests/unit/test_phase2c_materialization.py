"""
Tests for RationaleVault Knowledge Materialization.

Covers KnowledgeCandidate → KnowledgeObject conversion, provenance chain
construction, confidence computation, and initial epistemic status classification.
"""
from __future__ import annotations

import pytest

from rationalevault.knowledge.models import (
    KnowledgeObject,
    KnowledgeType,
    KnowledgeDomain,
    KnowledgeTransferability,
    KnowledgeLifecycle,
    KnowledgeConfidence,
    ProvenanceChain,
    EpistemicStatus,
)
from rationalevault.knowledge.promotion_models import (
    KnowledgeCandidate,
    KnowledgePromotionDecision,
    PromotionDecisionType,
)
from rationalevault.knowledge.promotion_materializer import (
    KnowledgeMaterializer,
    _determine_initial_status,
)


# =====================================================================
# Fixtures
# =====================================================================

def _make_candidate(
    confidence: float = 0.8,
    supporting: list[str] | None = None,
    contradicting: list[str] | None = None,
) -> KnowledgeCandidate:
    return KnowledgeCandidate(
        candidate_id="KCAN-TEST001",
        source_decision_id="PD-TEST001",
        knowledge_type=KnowledgeType.LESSON,
        knowledge_domain=KnowledgeDomain.PROCESS,
        title="Test Knowledge",
        content="Important lesson learned from reflection",
        confidence=confidence,
        importance="medium",
        transferability=KnowledgeTransferability.ORGANIZATIONAL,
        supporting_memory_ids=supporting if supporting is not None else ["LEARN-001", "LEARN-002"],
        contradicting_memory_ids=contradicting if contradicting is not None else [],
        source_reflection_ids=["REFL-001", "REFL-002"],
        source_learning_record_ids=["LEARN-001", "LEARN-002"],
        created_at="2026-06-26T12:00:00Z",
    )


def _make_decision(
    decision: PromotionDecisionType = PromotionDecisionType.APPROVE,
) -> KnowledgePromotionDecision:
    return KnowledgePromotionDecision(
        decision_id="PD-TEST001",
        candidate_id="PROMO-TEST001",
        gate_result_version="1.0",
        decision=decision,
        knowledge_candidate_id="KCAN-TEST001",
        reasons=["All gate checks passed"],
        created_at="2026-06-26T12:00:00Z",
    )


# =====================================================================
# Materialization
# =====================================================================

class TestKnowledgeMaterializer:
    def test_basic_materialization(self):
        candidate = _make_candidate()
        decision = _make_decision()

        knowledge = KnowledgeMaterializer.materialize(candidate, decision)

        assert knowledge.id is not None
        assert knowledge.version == 1
        assert knowledge.title == "Test Knowledge"
        assert knowledge.content == "Important lesson learned from reflection"
        assert knowledge.knowledge_type == KnowledgeType.LESSON
        assert knowledge.knowledge_domain == KnowledgeDomain.PROCESS
        assert knowledge.importance == "medium"
        assert knowledge.lifecycle_status == KnowledgeLifecycle.ACTIVE.value
        assert knowledge.superseded_by is None

    def test_provenance_built(self):
        candidate = _make_candidate(supporting=["L1", "L2", "L3"])
        decision = _make_decision()

        knowledge = KnowledgeMaterializer.materialize(candidate, decision)

        assert knowledge.provenance.knowledge_id == knowledge.id
        assert knowledge.provenance.source_memory_ids == ["L1", "L2", "L3"]
        assert knowledge.provenance.source_event_ids == ["REFL-001", "REFL-002"]
        assert knowledge.provenance.synthesis_event_id == "PD-TEST001"
        assert knowledge.provenance.evidence_count == 3

    def test_confidence_computed(self):
        candidate = _make_candidate(confidence=0.85, supporting=["L1", "L2", "L3"])
        decision = _make_decision()

        knowledge = KnowledgeMaterializer.materialize(candidate, decision)

        assert isinstance(knowledge.confidence, KnowledgeConfidence)
        assert knowledge.confidence.memory_count == 3
        assert knowledge.confidence.source_event_count == 4  # 2 reflection + 2 learning
        assert knowledge.confidence.contradiction_count == 0
        assert knowledge.confidence.score > 0.0

    def test_epistemic_status_validated(self):
        """High confidence + no contradictions + 3+ supporting → VALIDATED."""
        candidate = _make_candidate(confidence=0.9, supporting=["L1", "L2", "L3"])
        decision = _make_decision()

        knowledge = KnowledgeMaterializer.materialize(candidate, decision)

        assert knowledge.epistemic_status == EpistemicStatus.VALIDATED

    def test_epistemic_status_proposed(self):
        """Medium confidence + no contradictions → PROPOSED."""
        candidate = _make_candidate(confidence=0.6, supporting=["L1"])
        decision = _make_decision()

        knowledge = KnowledgeMaterializer.materialize(candidate, decision)

        assert knowledge.epistemic_status == EpistemicStatus.PROPOSED

    def test_epistemic_status_conflicted(self):
        """Has contradictions → CONFLICTED."""
        candidate = _make_candidate(
            confidence=0.8,
            supporting=["L1", "L2", "L3"],
            contradicting=["L4"],
        )
        decision = _make_decision()

        knowledge = KnowledgeMaterializer.materialize(candidate, decision)

        assert knowledge.epistemic_status == EpistemicStatus.CONFLICTED

    def test_transferability_preserved(self):
        candidate = _make_candidate()
        decision = _make_decision()

        knowledge = KnowledgeMaterializer.materialize(candidate, decision)

        assert knowledge.transferability == KnowledgeTransferability.ORGANIZATIONAL.value

    def test_supporting_contradicting_ids_preserved(self):
        candidate = _make_candidate(
            supporting=["L1", "L2"],
            contradicting=["L3"],
        )
        decision = _make_decision()

        knowledge = KnowledgeMaterializer.materialize(candidate, decision)

        assert knowledge.supporting_memory_ids == ["L1", "L2"]
        assert knowledge.contradicting_memory_ids == ["L3"]

    def test_deterministic_id(self):
        candidate = _make_candidate()
        decision = _make_decision()

        k1 = KnowledgeMaterializer.materialize(candidate, decision)
        k2 = KnowledgeMaterializer.materialize(candidate, decision)

        assert k1.id == k2.id

    def test_serialization_roundtrip(self):
        candidate = _make_candidate()
        decision = _make_decision()

        knowledge = KnowledgeMaterializer.materialize(candidate, decision)
        d = knowledge.to_dict()
        restored = KnowledgeObject.from_dict(d)

        assert restored.id == knowledge.id
        assert restored.title == knowledge.title
        assert restored.knowledge_type == knowledge.knowledge_type
        assert restored.epistemic_status == knowledge.epistemic_status


# =====================================================================
# Initial Status Classification
# =====================================================================

class TestDetermineInitialStatus:
    def test_validated_high_confidence(self):
        assert _determine_initial_status(0.9, 3, 0) == EpistemicStatus.VALIDATED

    def test_proposed_medium_confidence(self):
        assert _determine_initial_status(0.6, 2, 0) == EpistemicStatus.PROPOSED

    def test_conflicted_with_contradictions(self):
        assert _determine_initial_status(0.9, 3, 1) == EpistemicStatus.CONFLICTED

    def test_proposed_low_support(self):
        assert _determine_initial_status(0.85, 1, 0) == EpistemicStatus.PROPOSED

    def test_conflicted_takes_precedence(self):
        """Even high confidence is CONFLICTED if there are contradictions."""
        assert _determine_initial_status(0.95, 5, 1) == EpistemicStatus.CONFLICTED
