"""
RationaleVault Knowledge Promotion Pipeline — Deterministic logic for knowledge promotion.

Mirrors the execution pipeline:

    Execution:
        ExecutionEvaluation → GateResult → PromotionDecision → ArtifactCandidate → Artifact

    Knowledge:
        PromotionAssessment → PromotionGateResult → KnowledgePromotionDecision → KnowledgeCandidate

Pipeline stages:
  1. Assess  — compute facts from PromotionCandidate
  2. Gate    — apply PromotionGatePolicy to assessment
  3. Decide  — record business decision (approve/reject/defer)
  4. Build   — if approved, create KnowledgeCandidate

Design rules:
  - All logic is deterministic (no randomness, no I/O, no AI calls).
  - Each stage returns an immutable frozen dataclass.
  - AI never writes to the pipeline — advisory only.
"""
from __future__ import annotations

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
    generate_assessment_id,
    generate_gate_result_id,
)
from rationalevault.knowledge.models import (
    KnowledgeType,
    KnowledgeDomain,
    KnowledgeTransferability,
)


# =====================================================================
# Stage 1: Assessment
# =====================================================================

class PromotionAssessor:
    """
    Computes facts and scores from a PromotionCandidate.

    Answers: what happened?
    No policy decisions — pure measurement.
    """

    @staticmethod
    def assess(candidate: PromotionCandidate) -> PromotionAssessment:
        supporting = len(candidate.supporting_evidence)
        contradicting = len(candidate.contradicting_evidence)
        total = supporting + contradicting

        evidence_ratio = supporting / total if total > 0 else 0.0
        has_contradictions = contradicting > 0

        # Validate promotion type
        promotion_type_valid = candidate.promotion_type in PromotionType

        # Validate knowledge type
        knowledge_type_valid = candidate.knowledge_type in KnowledgeType

        findings: list[str] = []
        warnings: list[str] = []

        findings.append(f"Candidate has {supporting} supporting and {contradicting} contradicting evidence")
        findings.append(f"Evidence ratio: {evidence_ratio:.4f}")
        findings.append(f"Confidence: {candidate.confidence:.4f}")

        if has_contradictions:
            warnings.append(f"Candidate has {contradicting} contradicting evidence items")
        if candidate.confidence < 0.5:
            warnings.append(f"Low confidence: {candidate.confidence:.4f}")
        if not promotion_type_valid:
            warnings.append(f"Invalid promotion type: {candidate.promotion_type}")
        if not knowledge_type_valid:
            warnings.append(f"Invalid knowledge type: {candidate.knowledge_type}")

        return PromotionAssessment(
            candidate_id=candidate.candidate_id,
            confidence_score=candidate.confidence,
            evidence_ratio=evidence_ratio,
            supporting_count=supporting,
            contradicting_count=contradicting,
            has_contradictions=has_contradictions,
            promotion_type_valid=promotion_type_valid,
            knowledge_type_valid=knowledge_type_valid,
            findings=findings,
            warnings=warnings,
        )


# =====================================================================
# Stage 2: Gate
# =====================================================================

class PromotionGate:
    """
    Applies PromotionGatePolicy to a PromotionAssessment.

    Answers: is this acceptable under the policy?
    """

    @staticmethod
    def apply(
        assessment: PromotionAssessment,
        policy: PromotionGatePolicy,
    ) -> PromotionGateResult:
        violations: list[str] = []
        warnings: list[str] = list(assessment.warnings)

        # Confidence threshold
        if assessment.confidence_score < policy.min_confidence:
            violations.append(
                f"Confidence {assessment.confidence_score:.4f} below minimum {policy.min_confidence:.4f}"
            )

        # Supporting evidence minimum
        if assessment.supporting_count < policy.min_supporting_evidence:
            violations.append(
                f"Supporting evidence {assessment.supporting_count} below minimum {policy.min_supporting_evidence}"
            )

        # Contradicting evidence maximum
        if assessment.contradicting_count > policy.max_contradicting_evidence:
            violations.append(
                f"Contradicting evidence {assessment.contradicting_count} exceeds maximum {policy.max_contradicting_evidence}"
            )

        # No contradictions required
        if policy.require_no_contradictions and assessment.has_contradictions:
            violations.append(
                f"Policy requires no contradictions, but {assessment.contradicting_count} found"
            )

        # Valid promotion type required
        if policy.require_valid_promotion_type and not assessment.promotion_type_valid:
            violations.append("Invalid promotion type")

        # Valid knowledge type required
        if policy.require_valid_knowledge_type and not assessment.knowledge_type_valid:
            violations.append("Invalid knowledge type")

        # Determine decision
        if violations:
            decision = PromotionDecisionType.REJECT
        else:
            decision = PromotionDecisionType.APPROVE

        return PromotionGateResult(
            decision=decision,
            violations=violations,
            warnings=warnings,
            evaluated_policy_version=policy.version,
        )


# =====================================================================
# Stage 3: Decision
# =====================================================================

class PromotionDecider:
    """
    Records the business decision for a knowledge promotion.

    Answers: what exactly should be promoted?
    If approved, creates a KnowledgeCandidate.
    """

    @staticmethod
    def decide(
        candidate: PromotionCandidate,
        assessment: PromotionAssessment,
        gate_result: PromotionGateResult,
        created_at: str,
    ) -> tuple[KnowledgePromotionDecision, KnowledgeCandidate | None]:
        reasons: list[str] = []
        kc: KnowledgeCandidate | None = None

        if gate_result.decision == PromotionDecisionType.REJECT:
            reasons.extend(gate_result.violations)
            decision_id = KnowledgePromotionDecision.generate_decision_id(
                candidate.candidate_id, "REJECT", created_at
            )
            decision = KnowledgePromotionDecision(
                decision_id=decision_id,
                candidate_id=candidate.candidate_id,
                gate_result_version=gate_result.version,
                decision=PromotionDecisionType.REJECT,
                knowledge_candidate_id=None,
                reasons=reasons,
                created_at=created_at,
            )
        elif gate_result.decision == PromotionDecisionType.DEFER:
            reasons.append("Deferred pending further evidence")
            decision_id = KnowledgePromotionDecision.generate_decision_id(
                candidate.candidate_id, "DEFER", created_at
            )
            decision = KnowledgePromotionDecision(
                decision_id=decision_id,
                candidate_id=candidate.candidate_id,
                gate_result_version=gate_result.version,
                decision=PromotionDecisionType.DEFER,
                knowledge_candidate_id=None,
                reasons=reasons,
                created_at=created_at,
            )
        else:
            # APPROVE — create KnowledgeCandidate
            reasons.append("All gate checks passed")
            decision_id = KnowledgePromotionDecision.generate_decision_id(
                candidate.candidate_id, "APPROVE", created_at
            )
            kc_id = KnowledgeCandidate.generate_candidate_id(
                decision_id, candidate.knowledge_type, created_at
            )
            kc = KnowledgeCandidate(
                candidate_id=kc_id,
                source_decision_id=decision_id,
                knowledge_type=candidate.knowledge_type,
                knowledge_domain=candidate.knowledge_domain,
                title=candidate.title,
                content=candidate.content,
                confidence=candidate.confidence,
                importance=_classify_importance(candidate.confidence, assessment.evidence_ratio),
                transferability=_classify_transferability(candidate.knowledge_domain),
                supporting_memory_ids=list(candidate.supporting_evidence),
                contradicting_memory_ids=list(candidate.contradicting_evidence),
                source_reflection_ids=list(candidate.source_reflection_ids),
                source_learning_record_ids=[],
                created_at=created_at,
            )
            decision = KnowledgePromotionDecision(
                decision_id=decision_id,
                candidate_id=candidate.candidate_id,
                gate_result_version=gate_result.version,
                decision=PromotionDecisionType.APPROVE,
                knowledge_candidate_id=kc_id,
                reasons=reasons,
                created_at=created_at,
            )

        return decision, kc


def _classify_importance(confidence: float, evidence_ratio: float) -> str:
    """Deterministic importance classification based on confidence and evidence."""
    composite = (confidence + evidence_ratio) / 2.0
    if composite >= 0.85:
        return "high"
    elif composite >= 0.65:
        return "medium"
    else:
        return "low"


def _classify_transferability(domain: KnowledgeDomain) -> KnowledgeTransferability:
    """Deterministic transferability based on knowledge domain."""
    if domain == KnowledgeDomain.ARCHITECTURE:
        return KnowledgeTransferability.REUSABLE
    elif domain == KnowledgeDomain.PROCESS:
        return KnowledgeTransferability.ORGANIZATIONAL
    else:
        return KnowledgeTransferability.LOCAL_ONLY


# =====================================================================
# Pipeline Orchestrator
# =====================================================================

class PromotionPipeline:
    """
    Orchestrates the full knowledge promotion pipeline.

    PromotionCandidate → Assessment → Gate → Decision → (KnowledgeCandidate | None)

    Returns a PromotionReport containing all intermediate results.
    """

    @staticmethod
    def run(
        candidate: PromotionCandidate,
        policy: PromotionGatePolicy,
        created_at: str,
    ) -> PromotionReport:
        # Stage 1: Assess
        assessment = PromotionAssessor.assess(candidate)

        # Stage 2: Gate
        gate_result = PromotionGate.apply(assessment, policy)

        # Stage 3: Decide
        decision, kc = PromotionDecider.decide(candidate, assessment, gate_result, created_at)

        # Build report
        report_id = PromotionReport.generate_report_id(decision.decision_id, created_at)
        return PromotionReport(
            report_id=report_id,
            candidate=candidate,
            assessment=assessment,
            gate_result=gate_result,
            decision=decision,
            knowledge_candidate=kc,
            created_at=created_at,
        )

    @staticmethod
    def to_event_payloads(report: PromotionReport) -> list:
        """
        Convert a PromotionReport into a list of event payloads for the event ledger.

        Returns:
            [PromotionCandidateCreatedPayload, PromotionAssessedPayload,
             PromotionGatedPayload, PromotionDecisionPayload]
        """
        candidate_payload = PromotionCandidateCreatedPayload(
            candidate_id=report.candidate.candidate_id,
            source_reflection_ids=report.candidate.source_reflection_ids,
            promotion_type=report.candidate.promotion_type.value,
            knowledge_type=report.candidate.knowledge_type.value,
            knowledge_domain=report.candidate.knowledge_domain.value,
            title=report.candidate.title,
            content=report.candidate.content,
            confidence=report.candidate.confidence,
            supporting_evidence=report.candidate.supporting_evidence,
            contradicting_evidence=report.candidate.contradicting_evidence,
            created_at=report.candidate.created_at,
        )

        assessment_id = generate_assessment_id(
            report.candidate.candidate_id, report.created_at
        )
        assessment_payload = PromotionAssessedPayload(
            assessment_id=assessment_id,
            candidate_id=report.assessment.candidate_id,
            confidence_score=report.assessment.confidence_score,
            evidence_ratio=report.assessment.evidence_ratio,
            supporting_count=report.assessment.supporting_count,
            contradicting_count=report.assessment.contradicting_count,
            has_contradictions=report.assessment.has_contradictions,
            promotion_type_valid=report.assessment.promotion_type_valid,
            knowledge_type_valid=report.assessment.knowledge_type_valid,
            findings=report.assessment.findings,
            warnings=report.assessment.warnings,
            created_at=report.created_at,
        )

        gate_result_id = generate_gate_result_id(
            assessment_id, report.gate_result.decision.value, report.created_at
        )
        gate_payload = PromotionGatedPayload(
            gate_result_id=gate_result_id,
            assessment_id=assessment_id,
            candidate_id=report.candidate.candidate_id,
            decision=report.gate_result.decision.value,
            policy_version=report.gate_result.evaluated_policy_version,
            violations=report.gate_result.violations,
            warnings=report.gate_result.warnings,
            created_at=report.created_at,
        )

        decision_payload = PromotionDecisionPayload(
            decision_id=report.decision.decision_id,
            candidate_id=report.decision.candidate_id,
            gate_result_id=gate_result_id,
            decision=report.decision.decision.value,
            knowledge_candidate_id=report.decision.knowledge_candidate_id,
            reasons=report.decision.reasons,
            created_at=report.created_at,
        )

        return [candidate_payload, assessment_payload, gate_payload, decision_payload]
