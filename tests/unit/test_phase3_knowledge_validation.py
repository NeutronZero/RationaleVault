"""
Tests for RationaleVault Knowledge Validation (F3.5).

Covers validation status classification, evolution candidate generation,
deterministic ID generation, and the KVAL event lifecycle.
"""
from __future__ import annotations

import pytest

from rationalevault.knowledge.models import (
    KnowledgeObject,
    KnowledgeType,
    KnowledgeDomain,
    KnowledgeTransferability,
    KnowledgeConfidence,
    ProvenanceChain,
    EpistemicStatus,
)
from rationalevault.knowledge.validation import (
    KnowledgeValidator,
    KnowledgeValidationReport,
    KnowledgeEvolutionCandidate,
    ValidationStatus,
    EvidenceItem,
    _compute_evolved_confidence,
    _classify_evolution_type,
)
from rationalevault.knowledge.promotion_models import PromotionType


# =====================================================================
# Fixtures
# =====================================================================

def _make_knowledge(
    confidence_score: float = 0.8,
    content: str = "Always use type hints in Python code",
) -> KnowledgeObject:
    confidence = KnowledgeConfidence(
        memory_count=3,
        source_event_count=2,
        contradiction_count=0,
        average_memory_confidence=0.8,
        score=confidence_score,
    )
    provenance = ProvenanceChain(
        knowledge_id="KNOW-TEST001",
        source_memory_ids=["LEARN-001", "LEARN-002"],
        source_event_ids=["REFL-001"],
        synthesis_event_id="PD-001",
        confidence=confidence,
        evidence_count=3,
    )
    return KnowledgeObject(
        id="KNOW-TEST001",
        version=1,
        title="Type Hints Required",
        content=content,
        knowledge_type=KnowledgeType.LESSON,
        knowledge_domain=KnowledgeDomain.PROCESS,
        confidence=confidence,
        importance="medium",
        provenance=provenance,
        transferability=KnowledgeTransferability.ORGANIZATIONAL.value,
        epistemic_status=EpistemicStatus.VALIDATED,
    )


def _make_evidence(
    evidence_id: str = "LEARN-100",
    content: str = "Type hints improve code quality",
    confidence: float = 0.8,
    relationship: str = "supporting",
) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=evidence_id,
        content=content,
        source_type="learning_record",
        confidence=confidence,
        relationship=relationship,
        created_at="2026-06-26T12:00:00Z",
    )


# =====================================================================
# Validation Report
# =====================================================================

class TestKnowledgeValidationReport:
    def test_id_generation_deterministic(self):
        id1 = KnowledgeValidationReport.generate_report_id("KNOW-001", "2026-06-26T12:00:00Z")
        id2 = KnowledgeValidationReport.generate_report_id("KNOW-001", "2026-06-26T12:00:00Z")
        assert id1 == id2
        assert id1.startswith("KVAL-")

    def test_serialization_roundtrip(self):
        report = KnowledgeValidationReport(
            report_id="KVAL-TEST",
            knowledge_id="KNOW-TEST",
            knowledge_version=1,
            validation_status=ValidationStatus.CONFIRMED,
            evidence_count=3,
            supporting_count=3,
            contradicting_count=0,
            evidence_ratio=1.0,
            findings=["All evidence supports"],
            warnings=[],
            created_at="2026-06-26T12:00:00Z",
        )
        d = report.to_dict()
        restored = KnowledgeValidationReport.from_dict(d)
        assert restored.report_id == report.report_id
        assert restored.validation_status == report.validation_status


# =====================================================================
# Evolution Candidate
# =====================================================================

class TestKnowledgeEvolutionCandidate:
    def test_id_generation_deterministic(self):
        id1 = KnowledgeEvolutionCandidate.generate_candidate_id("KNOW-001", "KVAL-001", "2026-06-26T12:00:00Z")
        id2 = KnowledgeEvolutionCandidate.generate_candidate_id("KNOW-001", "KVAL-001", "2026-06-26T12:00:00Z")
        assert id1 == id2
        assert id1.startswith("KEVOL-")

    def test_serialization_roundtrip(self):
        candidate = KnowledgeEvolutionCandidate(
            candidate_id="KEVOL-TEST",
            source_knowledge_id="KNOW-TEST",
            source_validation_report_id="KVAL-TEST",
            promotion_type=PromotionType.LESSON_TO_INVARIANT,
            knowledge_type=KnowledgeType.LESSON,
            knowledge_domain=KnowledgeDomain.PROCESS,
            title="Updated Lesson",
            content="Updated content",
            confidence=0.75,
            supporting_evidence=["LEARN-001"],
            contradicting_evidence=[],
            created_at="2026-06-26T12:00:00Z",
        )
        d = candidate.to_dict()
        restored = KnowledgeEvolutionCandidate.from_dict(d)
        assert restored.candidate_id == candidate.candidate_id
        assert restored.promotion_type == candidate.promotion_type


# =====================================================================
# Validator
# =====================================================================

class TestKnowledgeValidator:
    def test_confirmed_when_all_support(self):
        knowledge = _make_knowledge()
        evidence = [
            _make_evidence("L1", "Type hints are important for Python", relationship="supporting"),
            _make_evidence("L2", "Type hints improve code readability", relationship="supporting"),
        ]

        report, evolution = KnowledgeValidator.validate(knowledge, evidence, "2026-06-26T12:00:00Z")

        assert report.validation_status == ValidationStatus.CONFIRMED
        assert report.supporting_count == 2
        assert report.contradicting_count == 0
        assert evolution is None

    def test_conflicted_when_contradictions_outnumber(self):
        knowledge = _make_knowledge(content="Always use type hints everywhere")
        evidence = [
            _make_evidence("L1", "Type hints slow down development significantly", relationship="contradicting"),
            _make_evidence("L2", "Type hints create unnecessary boilerplate code", relationship="contradicting"),
        ]

        report, evolution = KnowledgeValidator.validate(knowledge, evidence, "2026-06-26T12:00:00Z")

        assert report.validation_status == ValidationStatus.CONFLICTED
        assert evolution is not None
        assert evolution.source_knowledge_id == "KNOW-TEST001"

    def test_evolved_when_mixed_evidence(self):
        knowledge = _make_knowledge(content="Always use type hints in Python code")
        evidence = [
            _make_evidence("L1", "Type hints improve code quality and readability", relationship="supporting"),
            _make_evidence("L2", "Type hints slow down development significantly", relationship="contradicting"),
            _make_evidence("L3", "Type hints are essential for large projects", relationship="supporting"),
        ]

        report, evolution = KnowledgeValidator.validate(knowledge, evidence, "2026-06-26T12:00:00Z")

        # 2 supporting, 1 contradicting → EVOLVED
        assert report.validation_status == ValidationStatus.EVOLVED
        assert evolution is not None

    def test_stale_when_no_evidence(self):
        knowledge = _make_knowledge()
        report, evolution = KnowledgeValidator.validate(knowledge, [], "2026-06-26T12:00:00Z")

        assert report.validation_status == ValidationStatus.STALE
        assert evolution is None

    def test_report_deterministic(self):
        knowledge = _make_knowledge()
        evidence = [_make_evidence("L1", "Type hints are important", relationship="supporting")]

        r1, _ = KnowledgeValidator.validate(knowledge, evidence, "2026-06-26T12:00:00Z")
        r2, _ = KnowledgeValidator.validate(knowledge, evidence, "2026-06-26T12:00:00Z")

        assert r1.to_dict() == r2.to_dict()

    def test_low_confidence_evidence_neutral(self):
        """Very low confidence evidence with unknown relationship is treated as neutral."""
        knowledge = _make_knowledge(content="Always use type hints in Python code")
        evidence = [
            _make_evidence("L1", "Completely unrelated topic about coffee", confidence=0.1, relationship="unknown"),
        ]

        report, evolution = KnowledgeValidator.validate(knowledge, evidence, "2026-06-26T12:00:00Z")

        # Low confidence non-overlapping → not counted as contradicting
        assert report.contradicting_count == 0


# =====================================================================
# Helper Functions
# =====================================================================

class TestHelperFunctions:
    def test_compute_evolved_confidence(self):
        # High current, all supporting → stays high
        assert _compute_evolved_confidence(0.8, 3, 0) == pytest.approx(0.8 * 0.6 + 1.0 * 0.4)

        # High current, half contradicting → drops
        result = _compute_evolved_confidence(0.8, 1, 1)
        assert result < 0.8

    def test_classify_evolution_type(self):
        assert _classify_evolution_type(KnowledgeType.LESSON) == PromotionType.LESSON_TO_INVARIANT
        assert _classify_evolution_type(KnowledgeType.ARCHITECTURE_PRINCIPLE) == PromotionType.PATTERN_TO_PRINCIPLE
        assert _classify_evolution_type(KnowledgeType.FAILURE_PATTERN) == PromotionType.FAILURE_TO_PATTERN
