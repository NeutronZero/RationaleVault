"""
Tests for RationaleVault Knowledge Promotion Pipeline.

Covers all four stages (Assess, Gate, Decide, Build) plus the orchestrator
and event payload conversion.
"""
from __future__ import annotations

import pytest

from rationalevault.knowledge.promotion_models import (
    PromotionCandidate,
    PromotionAssessment,
    PromotionGatePolicy,
    PromotionGateResult,
    KnowledgePromotionDecision,
    KnowledgeCandidate,
    PromotionReport,
    PromotionType,
    PromotionDecisionType,
)
from rationalevault.knowledge.promotion_events import (
    PromotionCandidateCreatedPayload,
    PromotionAssessedPayload,
    PromotionGatedPayload,
    PromotionDecisionPayload,
)
from rationalevault.knowledge.promotion_pipeline import (
    PromotionAssessor,
    PromotionGate,
    PromotionDecider,
    PromotionPipeline,
    _classify_importance,
    _classify_transferability,
)
from rationalevault.knowledge.models import (
    KnowledgeType,
    KnowledgeDomain,
    KnowledgeTransferability,
)


# =====================================================================
# Fixtures
# =====================================================================

def _make_candidate(
    confidence: float = 0.8,
    supporting: list[str] | None = None,
    contradicting: list[str] | None = None,
    promotion_type: PromotionType = PromotionType.LESSON_TO_INVARIANT,
    knowledge_type: KnowledgeType = KnowledgeType.LESSON,
) -> PromotionCandidate:
    return PromotionCandidate(
        candidate_id="PROMO-TEST001",
        source_reflection_ids=["REFL-001", "REFL-002"],
        promotion_type=promotion_type,
        knowledge_type=knowledge_type,
        knowledge_domain=KnowledgeDomain.PROCESS,
        title="Test Knowledge",
        content="Important lesson learned",
        confidence=confidence,
        supporting_evidence=supporting if supporting is not None else ["LEARN-001", "LEARN-002"],
        contradicting_evidence=contradicting if contradicting is not None else [],
        created_at="2026-06-26T12:00:00Z",
    )


def _make_policy(**kwargs) -> PromotionGatePolicy:
    return PromotionGatePolicy(**kwargs)


# =====================================================================
# Stage 1: PromotionAssessor
# =====================================================================

class TestPromotionAssessor:
    def test_basic_assessment(self):
        candidate = _make_candidate(confidence=0.8, supporting=["L1", "L2", "L3"], contradicting=[])
        assessment = PromotionAssessor.assess(candidate)

        assert assessment.candidate_id == "PROMO-TEST001"
        assert assessment.confidence_score == 0.8
        assert assessment.supporting_count == 3
        assert assessment.contradicting_count == 0
        assert assessment.evidence_ratio == 1.0
        assert assessment.has_contradictions is False
        assert assessment.promotion_type_valid is True
        assert assessment.knowledge_type_valid is True

    def test_with_contradictions(self):
        candidate = _make_candidate(supporting=["L1", "L2"], contradicting=["L3"])
        assessment = PromotionAssessor.assess(candidate)

        assert assessment.has_contradictions is True
        assert assessment.contradicting_count == 1
        assert assessment.evidence_ratio == pytest.approx(2 / 3)
        assert any("contradicting" in w for w in assessment.warnings)

    def test_no_evidence(self):
        candidate = _make_candidate(supporting=[], contradicting=[])
        assessment = PromotionAssessor.assess(candidate)

        assert assessment.evidence_ratio == 0.0
        assert assessment.supporting_count == 0
        assert assessment.contradicting_count == 0

    def test_low_confidence_warning(self):
        candidate = _make_candidate(confidence=0.3)
        assessment = PromotionAssessor.assess(candidate)

        assert any("Low confidence" in w for w in assessment.warnings)

    def test_finds_findings(self):
        candidate = _make_candidate(confidence=0.9, supporting=["L1", "L2"])
        assessment = PromotionAssessor.assess(candidate)

        assert len(assessment.findings) >= 3
        assert any("supporting" in f for f in assessment.findings)


# =====================================================================
# Stage 2: PromotionGate
# =====================================================================

class TestPromotionGate:
    def test_approve_when_policy_met(self):
        assessment = PromotionAssessment(
            candidate_id="PROMO-TEST",
            confidence_score=0.8,
            evidence_ratio=1.0,
            supporting_count=3,
            contradicting_count=0,
            has_contradictions=False,
            promotion_type_valid=True,
            knowledge_type_valid=True,
            findings=[],
            warnings=[],
        )
        policy = _make_policy()
        gate = PromotionGate.apply(assessment, policy)

        assert gate.decision == PromotionDecisionType.APPROVE
        assert gate.violations == []

    def test_reject_low_confidence(self):
        assessment = PromotionAssessment(
            candidate_id="PROMO-TEST",
            confidence_score=0.4,
            evidence_ratio=1.0,
            supporting_count=3,
            contradicting_count=0,
            has_contradictions=False,
            promotion_type_valid=True,
            knowledge_type_valid=True,
            findings=[],
            warnings=[],
        )
        policy = _make_policy(min_confidence=0.6)
        gate = PromotionGate.apply(assessment, policy)

        assert gate.decision == PromotionDecisionType.REJECT
        assert any("Confidence" in v for v in gate.violations)

    def test_reject_insufficient_evidence(self):
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
        policy = _make_policy(min_supporting_evidence=2)
        gate = PromotionGate.apply(assessment, policy)

        assert gate.decision == PromotionDecisionType.REJECT
        assert any("Supporting evidence" in v for v in gate.violations)

    def test_reject_contradictions(self):
        assessment = PromotionAssessment(
            candidate_id="PROMO-TEST",
            confidence_score=0.8,
            evidence_ratio=0.5,
            supporting_count=2,
            contradicting_count=2,
            has_contradictions=True,
            promotion_type_valid=True,
            knowledge_type_valid=True,
            findings=[],
            warnings=[],
        )
        policy = _make_policy(require_no_contradictions=True, max_contradicting_evidence=0)
        gate = PromotionGate.apply(assessment, policy)

        assert gate.decision == PromotionDecisionType.REJECT
        assert any("contradictions" in v for v in gate.violations)

    def test_multiple_violations(self):
        assessment = PromotionAssessment(
            candidate_id="PROMO-TEST",
            confidence_score=0.3,
            evidence_ratio=0.0,
            supporting_count=0,
            contradicting_count=0,
            has_contradictions=False,
            promotion_type_valid=False,
            knowledge_type_valid=True,
            findings=[],
            warnings=[],
        )
        policy = _make_policy(min_confidence=0.6, min_supporting_evidence=2, require_valid_promotion_type=True)
        gate = PromotionGate.apply(assessment, policy)

        assert gate.decision == PromotionDecisionType.REJECT
        assert len(gate.violations) >= 2

    def test_warnings_propagated(self):
        assessment = PromotionAssessment(
            candidate_id="PROMO-TEST",
            confidence_score=0.8,
            evidence_ratio=1.0,
            supporting_count=3,
            contradicting_count=0,
            has_contradictions=False,
            promotion_type_valid=True,
            knowledge_type_valid=True,
            findings=[],
            warnings=["Some warning"],
        )
        policy = _make_policy()
        gate = PromotionGate.apply(assessment, policy)

        assert "Some warning" in gate.warnings


# =====================================================================
# Stage 3: PromotionDecider
# =====================================================================

class TestPromotionDecider:
    def test_approve_creates_knowledge_candidate(self):
        candidate = _make_candidate()
        assessment = PromotionAssessor.assess(candidate)
        gate_result = PromotionGateResult(
            decision=PromotionDecisionType.APPROVE,
            violations=[],
            warnings=[],
            evaluated_policy_version="1.0",
        )

        decision, kc = PromotionDecider.decide(candidate, assessment, gate_result, "2026-06-26T12:00:00Z")

        assert decision.decision == PromotionDecisionType.APPROVE
        assert kc is not None
        assert kc.candidate_id.startswith("KCAN-")
        assert decision.knowledge_candidate_id == kc.candidate_id
        assert kc.knowledge_type == KnowledgeType.LESSON
        assert kc.knowledge_domain == KnowledgeDomain.PROCESS

    def test_reject_no_knowledge_candidate(self):
        candidate = _make_candidate()
        assessment = PromotionAssessor.assess(candidate)
        gate_result = PromotionGateResult(
            decision=PromotionDecisionType.REJECT,
            violations=["Too few evidence"],
            warnings=[],
            evaluated_policy_version="1.0",
        )

        decision, kc = PromotionDecider.decide(candidate, assessment, gate_result, "2026-06-26T12:00:00Z")

        assert decision.decision == PromotionDecisionType.REJECT
        assert kc is None
        assert decision.knowledge_candidate_id is None
        assert "Too few evidence" in decision.reasons

    def test_defer_no_knowledge_candidate(self):
        candidate = _make_candidate()
        assessment = PromotionAssessor.assess(candidate)
        gate_result = PromotionGateResult(
            decision=PromotionDecisionType.DEFER,
            violations=[],
            warnings=[],
            evaluated_policy_version="1.0",
        )

        decision, kc = PromotionDecider.decide(candidate, assessment, gate_result, "2026-06-26T12:00:00Z")

        assert decision.decision == PromotionDecisionType.DEFER
        assert kc is None

    def test_importance_classification(self):
        assert _classify_importance(0.95, 1.0) == "high"
        assert _classify_importance(0.7, 0.7) == "medium"
        assert _classify_importance(0.3, 0.2) == "low"

    def test_transferability_classification(self):
        assert _classify_transferability(KnowledgeDomain.ARCHITECTURE) == KnowledgeTransferability.REUSABLE
        assert _classify_transferability(KnowledgeDomain.PROCESS) == KnowledgeTransferability.ORGANIZATIONAL
        assert _classify_transferability(KnowledgeDomain.OPERATIONS) == KnowledgeTransferability.LOCAL_ONLY


# =====================================================================
# Pipeline Orchestrator
# =====================================================================

class TestPromotionPipeline:
    def test_full_approval_pipeline(self):
        candidate = _make_candidate(confidence=0.85, supporting=["L1", "L2", "L3"])
        policy = _make_policy()

        report = PromotionPipeline.run(candidate, policy, "2026-06-26T12:00:00Z")

        assert report.report_id.startswith("PREP-")
        assert report.candidate == candidate
        assert report.assessment.confidence_score == 0.85
        assert report.gate_result.decision == PromotionDecisionType.APPROVE
        assert report.decision.decision == PromotionDecisionType.APPROVE
        assert report.knowledge_candidate is not None
        assert report.knowledge_candidate.candidate_id.startswith("KCAN-")

    def test_full_rejection_pipeline(self):
        candidate = _make_candidate(confidence=0.3, supporting=["L1"])
        policy = _make_policy(min_confidence=0.6, min_supporting_evidence=2)

        report = PromotionPipeline.run(candidate, policy, "2026-06-26T12:00:00Z")

        assert report.gate_result.decision == PromotionDecisionType.REJECT
        assert report.decision.decision == PromotionDecisionType.REJECT
        assert report.knowledge_candidate is None

    def test_pipeline_deterministic(self):
        candidate = _make_candidate()
        policy = _make_policy()

        r1 = PromotionPipeline.run(candidate, policy, "2026-06-26T12:00:00Z")
        r2 = PromotionPipeline.run(candidate, policy, "2026-06-26T12:00:00Z")

        assert r1.to_dict() == r2.to_dict()


# =====================================================================
# Event Payload Conversion
# =====================================================================

class TestPromotionEventConversion:
    def test_to_event_payloads_approved(self):
        candidate = _make_candidate(confidence=0.85, supporting=["L1", "L2", "L3"])
        policy = _make_policy()
        report = PromotionPipeline.run(candidate, policy, "2026-06-26T12:00:00Z")

        payloads = PromotionPipeline.to_event_payloads(report)

        assert len(payloads) == 4
        assert isinstance(payloads[0], PromotionCandidateCreatedPayload)
        assert isinstance(payloads[1], PromotionAssessedPayload)
        assert isinstance(payloads[2], PromotionGatedPayload)
        assert isinstance(payloads[3], PromotionDecisionPayload)

        # Verify chain of IDs
        candidate_payload = payloads[0]
        assessment_payload = payloads[1]
        gate_payload = payloads[2]
        decision_payload = payloads[3]

        assert candidate_payload.candidate_id == "PROMO-TEST001"
        assert assessment_payload.candidate_id == "PROMO-TEST001"
        assert gate_payload.candidate_id == "PROMO-TEST001"
        assert gate_payload.assessment_id == assessment_payload.assessment_id
        assert decision_payload.candidate_id == "PROMO-TEST001"
        assert decision_payload.gate_result_id == gate_payload.gate_result_id
        assert decision_payload.decision == "APPROVE"

    def test_to_event_payloads_rejected(self):
        candidate = _make_candidate(confidence=0.3, supporting=["L1"])
        policy = _make_policy(min_confidence=0.6, min_supporting_evidence=2)
        report = PromotionPipeline.run(candidate, policy, "2026-06-26T12:00:00Z")

        payloads = PromotionPipeline.to_event_payloads(report)

        assert len(payloads) == 4
        decision_payload = payloads[3]
        assert decision_payload.decision == "REJECT"
        assert decision_payload.knowledge_candidate_id is None

    def test_payloads_serializable(self):
        candidate = _make_candidate()
        policy = _make_policy()
        report = PromotionPipeline.run(candidate, policy, "2026-06-26T12:00:00Z")

        payloads = PromotionPipeline.to_event_payloads(report)
        for p in payloads:
            d = p.to_dict()
            assert isinstance(d, dict)
            assert "schema_version" in d

    def test_payload_roundtrip(self):
        candidate = _make_candidate()
        policy = _make_policy()
        report = PromotionPipeline.run(candidate, policy, "2026-06-26T12:00:00Z")

        payloads = PromotionPipeline.to_event_payloads(report)
        for p in payloads:
            d = p.to_dict()
            cls = type(p)
            restored = cls.from_dict(d)
            assert restored.to_dict() == d
