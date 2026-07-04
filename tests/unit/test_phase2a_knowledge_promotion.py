"""Tests for Phase 2A: Knowledge Promotion Contracts."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from rationalevault.knowledge.models import (
    KnowledgeType,
    KnowledgeDomain,
    KnowledgeTransferability,
)
from rationalevault.knowledge.promotion_models import (
    PromotionType,
    PromotionDecisionType,
    PromotionCandidate,
    PromotionAssessment,
    PromotionGatePolicy,
    PromotionGateResult,
    KnowledgePromotionDecision,
    KnowledgeCandidate,
    PromotionReport,
)
from rationalevault.knowledge.promotion_events import (
    PromotionCandidateCreatedPayload,
    PromotionAssessedPayload,
    PromotionGatedPayload,
    PromotionDecisionPayload,
    generate_assessment_id,
    generate_gate_result_id,
    SCHEMA_VERSION,
)
from rationalevault.schema.events import EventType


# =====================================================================
# Enum Tests
# =====================================================================

class TestPromotionType:
    def test_all_values(self):
        values = [e.value for e in PromotionType]
        assert "LESSON_TO_INVARIANT" in values
        assert "PATTERN_TO_PRINCIPLE" in values
        assert "FAILURE_TO_PATTERN" in values
        assert "OBSERVATION_TO_FACT" in values
        assert "WORKFLOW_TO_INVARIANT" in values

    def test_has_five_values(self):
        assert len(PromotionType) == 5


class TestPromotionDecisionType:
    def test_all_values(self):
        values = [e.value for e in PromotionDecisionType]
        assert "APPROVE" in values
        assert "REJECT" in values
        assert "DEFER" in values


# =====================================================================
# PromotionCandidate Tests
# =====================================================================

class TestPromotionCandidate:
    def test_id_generation_deterministic(self):
        id1 = PromotionCandidate.generate_candidate_id(
            ["REFL-001", "REFL-002"], KnowledgeType.LESSON, "2026-06-26T12:00:00Z"
        )
        id2 = PromotionCandidate.generate_candidate_id(
            ["REFL-001", "REFL-002"], KnowledgeType.LESSON, "2026-06-26T12:00:00Z"
        )
        assert id1 == id2
        assert id1.startswith("PROMO-")

    def test_id_sorted_order(self):
        id1 = PromotionCandidate.generate_candidate_id(
            ["REFL-B", "REFL-A"], KnowledgeType.LESSON, "2026-06-26T12:00:00Z"
        )
        id2 = PromotionCandidate.generate_candidate_id(
            ["REFL-A", "REFL-B"], KnowledgeType.LESSON, "2026-06-26T12:00:00Z"
        )
        assert id1 == id2

    def test_id_unique_by_type(self):
        id1 = PromotionCandidate.generate_candidate_id(
            ["REFL-001"], KnowledgeType.LESSON, "2026-06-26T12:00:00Z"
        )
        id2 = PromotionCandidate.generate_candidate_id(
            ["REFL-001"], KnowledgeType.FAILURE_PATTERN, "2026-06-26T12:00:00Z"
        )
        assert id1 != id2

    def test_serialization_roundtrip(self):
        candidate = PromotionCandidate(
            candidate_id="PROMO-ABC12345",
            source_reflection_ids=["REFL-001", "REFL-002"],
            promotion_type=PromotionType.LESSON_TO_INVARIANT,
            knowledge_type=KnowledgeType.LESSON,
            knowledge_domain=KnowledgeDomain.PROCESS,
            title="Always validate inputs",
            content="Input validation prevents downstream failures.",
            confidence=0.85,
            supporting_evidence=["LEARN-001", "LEARN-002"],
            contradicting_evidence=[],
            created_at="2026-06-26T12:00:00Z",
        )
        d = candidate.to_dict()
        restored = PromotionCandidate.from_dict(d)
        assert restored == candidate

    def test_frozen(self):
        candidate = PromotionCandidate(
            candidate_id="PROMO-TEST",
            source_reflection_ids=[],
            promotion_type=PromotionType.LESSON_TO_INVARIANT,
            knowledge_type=KnowledgeType.LESSON,
            knowledge_domain=KnowledgeDomain.PROCESS,
            title="Test",
            content="Test content",
            confidence=0.5,
            supporting_evidence=[],
            contradicting_evidence=[],
            created_at="2026-06-26T12:00:00Z",
        )
        import pytest
        with pytest.raises(AttributeError):
            candidate.title = "Changed"


# =====================================================================
# PromotionAssessment Tests
# =====================================================================

class TestPromotionAssessment:
    def test_serialization_roundtrip(self):
        assessment = PromotionAssessment(
            candidate_id="PROMO-ABC12345",
            confidence_score=0.85,
            evidence_ratio=1.0,
            supporting_count=3,
            contradicting_count=0,
            has_contradictions=False,
            promotion_type_valid=True,
            knowledge_type_valid=True,
            findings=["Strong evidence base"],
            warnings=[],
        )
        d = assessment.to_dict()
        restored = PromotionAssessment.from_dict(d)
        assert restored == assessment

    def test_frozen(self):
        assessment = PromotionAssessment(
            candidate_id="PROMO-TEST",
            confidence_score=0.5,
            evidence_ratio=0.5,
            supporting_count=1,
            contradicting_count=1,
            has_contradictions=True,
            promotion_type_valid=True,
            knowledge_type_valid=True,
            findings=[],
            warnings=[],
        )
        import pytest
        with pytest.raises(AttributeError):
            assessment.confidence_score = 0.9


# =====================================================================
# PromotionGatePolicy Tests
# =====================================================================

class TestPromotionGatePolicy:
    def test_default_values(self):
        policy = PromotionGatePolicy()
        assert policy.version == "1.0"
        assert policy.min_confidence == 0.60
        assert policy.min_supporting_evidence == 2
        assert policy.max_contradicting_evidence == 0
        assert policy.require_no_contradictions is True

    def test_serialization_roundtrip(self):
        policy = PromotionGatePolicy(
            version="2.0",
            min_confidence=0.75,
            min_supporting_evidence=3,
            max_contradicting_evidence=1,
            require_no_contradictions=False,
        )
        d = policy.to_dict()
        restored = PromotionGatePolicy.from_dict(d)
        assert restored == policy


# =====================================================================
# PromotionGateResult Tests
# =====================================================================

class TestPromotionGateResult:
    def test_serialization_roundtrip(self):
        result = PromotionGateResult(
            decision=PromotionDecisionType.APPROVE,
            violations=[],
            warnings=[],
            evaluated_policy_version="1.0",
        )
        d = result.to_dict()
        restored = PromotionGateResult.from_dict(d)
        assert restored == result

    def test_with_violations(self):
        result = PromotionGateResult(
            decision=PromotionDecisionType.REJECT,
            violations=["Confidence 0.45 below minimum 0.60"],
            warnings=[],
            evaluated_policy_version="1.0",
        )
        assert result.decision == PromotionDecisionType.REJECT
        assert len(result.violations) == 1


# =====================================================================
# KnowledgePromotionDecision Tests
# =====================================================================

class TestKnowledgePromotionDecision:
    def test_id_generation_deterministic(self):
        id1 = KnowledgePromotionDecision.generate_decision_id(
            "PROMO-001", "APPROVE", "2026-06-26T12:00:00Z"
        )
        id2 = KnowledgePromotionDecision.generate_decision_id(
            "PROMO-001", "APPROVE", "2026-06-26T12:00:00Z"
        )
        assert id1 == id2
        assert id1.startswith("PD-")

    def test_serialization_roundtrip(self):
        decision = KnowledgePromotionDecision(
            decision_id="PD-ABC12345",
            candidate_id="PROMO-ABC12345",
            gate_result_version="1.0",
            decision=PromotionDecisionType.APPROVE,
            knowledge_candidate_id="KCAN-XYZ99999",
            reasons=["All gate checks passed"],
            created_at="2026-06-26T12:00:00Z",
        )
        d = decision.to_dict()
        restored = KnowledgePromotionDecision.from_dict(d)
        assert restored == decision

    def test_rejection_has_no_knowledge_candidate(self):
        decision = KnowledgePromotionDecision(
            decision_id="PD-REJECT",
            candidate_id="PROMO-REJECT",
            gate_result_version="1.0",
            decision=PromotionDecisionType.REJECT,
            knowledge_candidate_id=None,
            reasons=["Confidence below threshold"],
            created_at="2026-06-26T12:00:00Z",
        )
        assert decision.knowledge_candidate_id is None


# =====================================================================
# KnowledgeCandidate Tests
# =====================================================================

class TestKnowledgeCandidate:
    def test_id_generation_deterministic(self):
        id1 = KnowledgeCandidate.generate_candidate_id(
            "PD-001", KnowledgeType.LESSON, "2026-06-26T12:00:00Z"
        )
        id2 = KnowledgeCandidate.generate_candidate_id(
            "PD-001", KnowledgeType.LESSON, "2026-06-26T12:00:00Z"
        )
        assert id1 == id2
        assert id1.startswith("KCAN-")

    def test_serialization_roundtrip(self):
        candidate = KnowledgeCandidate(
            candidate_id="KCAN-ABC12345",
            source_decision_id="PD-ABC12345",
            knowledge_type=KnowledgeType.LESSON,
            knowledge_domain=KnowledgeDomain.PROCESS,
            title="Always validate inputs",
            content="Input validation prevents downstream failures.",
            confidence=0.85,
            importance="high",
            transferability=KnowledgeTransferability.REUSABLE,
            supporting_memory_ids=["MEM-001"],
            contradicting_memory_ids=[],
            source_reflection_ids=["REFL-001"],
            source_learning_record_ids=["LEARN-001"],
            created_at="2026-06-26T12:00:00Z",
        )
        d = candidate.to_dict()
        restored = KnowledgeCandidate.from_dict(d)
        assert restored == candidate


# =====================================================================
# PromotionReport Tests
# =====================================================================

class TestPromotionReport:
    def test_id_generation_deterministic(self):
        id1 = PromotionReport.generate_report_id("PD-001", "2026-06-26T12:00:00Z")
        id2 = PromotionReport.generate_report_id("PD-001", "2026-06-26T12:00:00Z")
        assert id1 == id2
        assert id1.startswith("PREP-")

    def test_serialization_roundtrip(self):
        candidate = PromotionCandidate(
            candidate_id="PROMO-TEST",
            source_reflection_ids=["REFL-001"],
            promotion_type=PromotionType.LESSON_TO_INVARIANT,
            knowledge_type=KnowledgeType.LESSON,
            knowledge_domain=KnowledgeDomain.PROCESS,
            title="Test",
            content="Test content",
            confidence=0.8,
            supporting_evidence=["LEARN-001"],
            contradicting_evidence=[],
            created_at="2026-06-26T12:00:00Z",
        )
        assessment = PromotionAssessment(
            candidate_id="PROMO-TEST",
            confidence_score=0.8,
            evidence_ratio=1.0,
            supporting_count=1,
            contradicting_count=0,
            has_contradictions=False,
            promotion_type_valid=True,
            knowledge_type_valid=True,
            findings=[],
            warnings=[],
        )
        gate_result = PromotionGateResult(
            decision=PromotionDecisionType.APPROVE,
            violations=[],
            warnings=[],
            evaluated_policy_version="1.0",
        )
        decision = KnowledgePromotionDecision(
            decision_id="PD-TEST",
            candidate_id="PROMO-TEST",
            gate_result_version="1.0",
            decision=PromotionDecisionType.APPROVE,
            knowledge_candidate_id="KCAN-TEST",
            reasons=["All checks passed"],
            created_at="2026-06-26T12:00:00Z",
        )
        kc = KnowledgeCandidate(
            candidate_id="KCAN-TEST",
            source_decision_id="PD-TEST",
            knowledge_type=KnowledgeType.LESSON,
            knowledge_domain=KnowledgeDomain.PROCESS,
            title="Test",
            content="Test content",
            confidence=0.8,
            importance="medium",
            transferability=KnowledgeTransferability.LOCAL_ONLY,
            supporting_memory_ids=[],
            contradicting_memory_ids=[],
            source_reflection_ids=["REFL-001"],
            source_learning_record_ids=["LEARN-001"],
            created_at="2026-06-26T12:00:00Z",
        )
        report = PromotionReport(
            report_id="PREP-TEST",
            candidate=candidate,
            assessment=assessment,
            gate_result=gate_result,
            decision=decision,
            knowledge_candidate=kc,
            created_at="2026-06-26T12:00:00Z",
        )
        d = report.to_dict()
        restored = PromotionReport.from_dict(d)
        assert restored == report
        assert restored.knowledge_candidate is not None

    def test_report_without_knowledge_candidate(self):
        """Rejection reports have no knowledge candidate."""
        candidate = PromotionCandidate(
            candidate_id="PROMO-REJECT",
            source_reflection_ids=[],
            promotion_type=PromotionType.LESSON_TO_INVARIANT,
            knowledge_type=KnowledgeType.LESSON,
            knowledge_domain=KnowledgeDomain.PROCESS,
            title="Rejected",
            content="Not enough evidence",
            confidence=0.3,
            supporting_evidence=[],
            contradicting_evidence=[],
            created_at="2026-06-26T12:00:00Z",
        )
        assessment = PromotionAssessment(
            candidate_id="PROMO-REJECT",
            confidence_score=0.3,
            evidence_ratio=0.0,
            supporting_count=0,
            contradicting_count=0,
            has_contradictions=False,
            promotion_type_valid=True,
            knowledge_type_valid=True,
            findings=[],
            warnings=[],
        )
        gate_result = PromotionGateResult(
            decision=PromotionDecisionType.REJECT,
            violations=["Confidence 0.30 below minimum 0.60"],
            warnings=[],
            evaluated_policy_version="1.0",
        )
        decision = KnowledgePromotionDecision(
            decision_id="PD-REJECT",
            candidate_id="PROMO-REJECT",
            gate_result_version="1.0",
            decision=PromotionDecisionType.REJECT,
            knowledge_candidate_id=None,
            reasons=["Confidence below threshold"],
            created_at="2026-06-26T12:00:00Z",
        )
        report = PromotionReport(
            report_id="PREP-REJECT",
            candidate=candidate,
            assessment=assessment,
            gate_result=gate_result,
            decision=decision,
            knowledge_candidate=None,
            created_at="2026-06-26T12:00:00Z",
        )
        d = report.to_dict()
        restored = PromotionReport.from_dict(d)
        assert restored.knowledge_candidate is None


# =====================================================================
# Event Payload Tests
# =====================================================================

class TestPromotionCandidateCreatedPayload:
    def test_serialization_roundtrip(self):
        payload = PromotionCandidateCreatedPayload(
            schema_version="1.0",
            candidate_id="PROMO-ABC12345",
            source_reflection_ids=["REFL-001"],
            promotion_type="LESSON_TO_INVARIANT",
            knowledge_type="LESSON",
            knowledge_domain="PROCESS",
            title="Test",
            content="Test content",
            confidence=0.8,
            supporting_evidence=["LEARN-001"],
            contradicting_evidence=[],
            created_at="2026-06-26T12:00:00Z",
        )
        d = payload.to_dict()
        restored = PromotionCandidateCreatedPayload.from_dict(d)
        assert restored == payload
        assert restored.schema_version == "1.0"


class TestPromotionAssessedPayload:
    def test_serialization_roundtrip(self):
        payload = PromotionAssessedPayload(
            schema_version="1.0",
            assessment_id="PASSMT-ABC12345",
            candidate_id="PROMO-ABC12345",
            confidence_score=0.8,
            evidence_ratio=1.0,
            supporting_count=2,
            contradicting_count=0,
            has_contradictions=False,
            promotion_type_valid=True,
            knowledge_type_valid=True,
            findings=["Strong evidence"],
            warnings=[],
            created_at="2026-06-26T12:00:00Z",
        )
        d = payload.to_dict()
        restored = PromotionAssessedPayload.from_dict(d)
        assert restored == payload


class TestPromotionGatedPayload:
    def test_serialization_roundtrip(self):
        payload = PromotionGatedPayload(
            schema_version="1.0",
            gate_result_id="PGATE-ABC12345",
            assessment_id="PASSMT-ABC12345",
            candidate_id="PROMO-ABC12345",
            decision="APPROVE",
            policy_version="1.0",
            violations=[],
            warnings=[],
            created_at="2026-06-26T12:00:00Z",
        )
        d = payload.to_dict()
        restored = PromotionGatedPayload.from_dict(d)
        assert restored == payload


class TestPromotionDecisionPayload:
    def test_serialization_roundtrip_approved(self):
        payload = PromotionDecisionPayload(
            schema_version="1.0",
            decision_id="PD-ABC12345",
            candidate_id="PROMO-ABC12345",
            gate_result_id="PGATE-ABC12345",
            decision="APPROVE",
            knowledge_candidate_id="KCAN-XYZ99999",
            reasons=["All checks passed"],
            created_at="2026-06-26T12:00:00Z",
        )
        d = payload.to_dict()
        restored = PromotionDecisionPayload.from_dict(d)
        assert restored == payload
        assert restored.knowledge_candidate_id == "KCAN-XYZ99999"

    def test_serialization_roundtrip_rejected(self):
        payload = PromotionDecisionPayload(
            schema_version="1.0",
            decision_id="PD-REJECT",
            candidate_id="PROMO-REJECT",
            gate_result_id="PGATE-REJECT",
            decision="REJECT",
            knowledge_candidate_id=None,
            reasons=["Confidence below threshold"],
            created_at="2026-06-26T12:00:00Z",
        )
        d = payload.to_dict()
        restored = PromotionDecisionPayload.from_dict(d)
        assert restored.knowledge_candidate_id is None


# =====================================================================
# ID Generation Tests
# =====================================================================

class TestPromotionIDGeneration:
    def test_assessment_id_deterministic(self):
        id1 = generate_assessment_id("PROMO-001", "2026-06-26T12:00:00Z")
        id2 = generate_assessment_id("PROMO-001", "2026-06-26T12:00:00Z")
        assert id1 == id2
        assert id1.startswith("PASSMT-")

    def test_gate_result_id_deterministic(self):
        id1 = generate_gate_result_id("PASSMT-001", "APPROVE", "2026-06-26T12:00:00Z")
        id2 = generate_gate_result_id("PASSMT-001", "APPROVE", "2026-06-26T12:00:00Z")
        assert id1 == id2
        assert id1.startswith("PGATE-")

    def test_gate_result_id_unique_by_decision(self):
        id1 = generate_gate_result_id("PASSMT-001", "APPROVE", "2026-06-26T12:00:00Z")
        id2 = generate_gate_result_id("PASSMT-001", "REJECT", "2026-06-26T12:00:00Z")
        assert id1 != id2


# =====================================================================
# Event Type Registration Tests
# =====================================================================

class TestEventTypes:
    def test_all_promotion_events_registered(self):
        expected = {
            "KNOWLEDGE_PROMOTION_CANDIDATE",
            "KNOWLEDGE_PROMOTION_ASSESSED",
            "KNOWLEDGE_PROMOTION_GATED",
            "KNOWLEDGE_PROMOTION_APPROVED",
            "KNOWLEDGE_PROMOTION_REJECTED",
        }
        actual = {e.value for e in EventType}
        assert expected.issubset(actual)
