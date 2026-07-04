"""
RationaleVault Knowledge Promotion Models — Immutable contracts for the knowledge promotion pipeline.

Mirrors the execution pipeline pattern:

    Execution:
        ExecutionReport → ExecutionEvaluation → GateResult → PromotionDecision → Artifact

    Knowledge:
        ReflectionReport → PromotionAssessment → PromotionGateResult → PromotionDecision → KnowledgeCandidate → KnowledgeObject

Design rules:
  - All models are FROZEN dataclasses.
  - Domain models ≠ Event payloads (separation of concerns).
  - Each stage has a distinct responsibility:
    * PromotionAssessment — computes facts and scores.
    * PromotionGateResult — applies policy to those facts.
    * PromotionDecision — records the business decision.
  - KnowledgeObject is intentionally lightweight; lineage is reconstructed from projections.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum
from typing import Any

from rationalevault.knowledge.models import (
    KnowledgeType,
    KnowledgeDomain,
    KnowledgeTransferability,
)


# =====================================================================
# Enums
# =====================================================================

class PromotionType(str, Enum):
    """Types of knowledge promotion from reflection to knowledge."""
    LESSON_TO_INVARIANT = "LESSON_TO_INVARIANT"
    PATTERN_TO_PRINCIPLE = "PATTERN_TO_PRINCIPLE"
    FAILURE_TO_PATTERN = "FAILURE_TO_PATTERN"
    OBSERVATION_TO_FACT = "OBSERVATION_TO_FACT"
    WORKFLOW_TO_INVARIANT = "WORKFLOW_TO_INVARIANT"


class PromotionDecisionType(str, Enum):
    """Possible outcomes of a knowledge promotion decision."""
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    DEFER = "DEFER"


# =====================================================================
# Domain Models (ephemeral, implementation details)
# =====================================================================

@dataclass(frozen=True)
class PromotionCandidate:
    """
    A candidate for promotion from reflection to knowledge.

    Ephemeral — the persisted contract is PromotionCandidateCreatedPayload.
    """
    candidate_id: str               # PROMO-[hash]
    source_reflection_ids: list[str]
    promotion_type: PromotionType
    knowledge_type: KnowledgeType
    knowledge_domain: KnowledgeDomain
    title: str
    content: str
    confidence: float
    supporting_evidence: list[str]   # LEARN-[hash] or REFL-[hash]
    contradicting_evidence: list[str]
    created_at: str

    @staticmethod
    def generate_candidate_id(
        source_reflection_ids: list[str],
        knowledge_type: KnowledgeType,
        created_at: str,
    ) -> str:
        sorted_ids = ",".join(sorted(source_reflection_ids))
        data = f"promotion:{sorted_ids}:{knowledge_type.value}:{created_at}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"PROMO-{h}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "source_reflection_ids": self.source_reflection_ids,
            "promotion_type": self.promotion_type.value,
            "knowledge_type": self.knowledge_type.value,
            "knowledge_domain": self.knowledge_domain.value,
            "title": self.title,
            "content": self.content,
            "confidence": round(self.confidence, 4),
            "supporting_evidence": self.supporting_evidence,
            "contradicting_evidence": self.contradicting_evidence,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PromotionCandidate:
        return cls(
            candidate_id=d["candidate_id"],
            source_reflection_ids=d.get("source_reflection_ids", []),
            promotion_type=PromotionType(d["promotion_type"]),
            knowledge_type=KnowledgeType(d["knowledge_type"]),
            knowledge_domain=KnowledgeDomain(d.get("knowledge_domain", KnowledgeDomain.ARCHITECTURE.value)),
            title=d["title"],
            content=d["content"],
            confidence=d["confidence"],
            supporting_evidence=d.get("supporting_evidence", []),
            contradicting_evidence=d.get("contradicting_evidence", []),
            created_at=d["created_at"],
        )


@dataclass(frozen=True)
class PromotionAssessment:
    """
    Facts and scores computed from a PromotionCandidate.

    Computes what happened — does not apply policy.
    Mirrors ExecutionEvaluation.
    """
    candidate_id: str
    confidence_score: float
    evidence_ratio: float            # supporting / (supporting + contradicting)
    supporting_count: int
    contradicting_count: int
    has_contradictions: bool
    promotion_type_valid: bool
    knowledge_type_valid: bool
    findings: list[str]
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "confidence_score": round(self.confidence_score, 4),
            "evidence_ratio": round(self.evidence_ratio, 4),
            "supporting_count": self.supporting_count,
            "contradicting_count": self.contradicting_count,
            "has_contradictions": self.has_contradictions,
            "promotion_type_valid": self.promotion_type_valid,
            "knowledge_type_valid": self.knowledge_type_valid,
            "findings": self.findings,
            "warnings": self.warnings,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PromotionAssessment:
        return cls(
            candidate_id=d["candidate_id"],
            confidence_score=d["confidence_score"],
            evidence_ratio=d["evidence_ratio"],
            supporting_count=d["supporting_count"],
            contradicting_count=d["contradicting_count"],
            has_contradictions=d["has_contradictions"],
            promotion_type_valid=d["promotion_type_valid"],
            knowledge_type_valid=d["knowledge_type_valid"],
            findings=d.get("findings", []),
            warnings=d.get("warnings", []),
        )


@dataclass(frozen=True)
class PromotionGatePolicy:
    """Configurable threshold rules for knowledge promotion gates."""
    version: str = "1.0"
    min_confidence: float = 0.60
    min_supporting_evidence: int = 2
    max_contradicting_evidence: int = 0
    require_no_contradictions: bool = True
    require_valid_promotion_type: bool = True
    require_valid_knowledge_type: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "min_confidence": self.min_confidence,
            "min_supporting_evidence": self.min_supporting_evidence,
            "max_contradicting_evidence": self.max_contradicting_evidence,
            "require_no_contradictions": self.require_no_contradictions,
            "require_valid_promotion_type": self.require_valid_promotion_type,
            "require_valid_knowledge_type": self.require_valid_knowledge_type,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PromotionGatePolicy:
        return cls(
            version=d.get("version", "1.0"),
            min_confidence=d.get("min_confidence", 0.60),
            min_supporting_evidence=d.get("min_supporting_evidence", 2),
            max_contradicting_evidence=d.get("max_contradicting_evidence", 0),
            require_no_contradictions=d.get("require_no_contradictions", True),
            require_valid_promotion_type=d.get("require_valid_promotion_type", True),
            require_valid_knowledge_type=d.get("require_valid_knowledge_type", True),
        )


@dataclass(frozen=True)
class PromotionGateResult:
    """
    Result of applying promotion gate policy to an assessment.

    Applies policy to facts — does not record business decision.
    Mirrors GateResult in execution pipeline.
    """
    decision: PromotionDecisionType
    violations: list[str]
    warnings: list[str]
    evaluated_policy_version: str
    version: str = "1.0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "decision": self.decision.value,
            "violations": self.violations,
            "warnings": self.warnings,
            "evaluated_policy_version": self.evaluated_policy_version,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PromotionGateResult:
        return cls(
            decision=PromotionDecisionType(d["decision"]),
            violations=d.get("violations", []),
            warnings=d.get("warnings", []),
            evaluated_policy_version=d["evaluated_policy_version"],
            version=d.get("version", "1.0"),
        )


@dataclass(frozen=True)
class KnowledgePromotionDecision:
    """
    Immutable promotion decision record.

    Records the business decision (approve, reject, defer).
    Mirrors PromotionDecision in execution pipeline.
    """
    decision_id: str                    # PD-[hash]
    candidate_id: str                   # PROMO-[hash]
    gate_result_version: str
    decision: PromotionDecisionType
    knowledge_candidate_id: str | None  # KCAN-[hash] if approved
    reasons: list[str]
    created_at: str

    @staticmethod
    def generate_decision_id(candidate_id: str, gate_decision: str, created_at: str) -> str:
        data = f"promotion_decision:{candidate_id}:{gate_decision}:{created_at}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"PD-{h}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "candidate_id": self.candidate_id,
            "gate_result_version": self.gate_result_version,
            "decision": self.decision.value,
            "knowledge_candidate_id": self.knowledge_candidate_id,
            "reasons": self.reasons,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> KnowledgePromotionDecision:
        return cls(
            decision_id=d["decision_id"],
            candidate_id=d["candidate_id"],
            gate_result_version=d["gate_result_version"],
            decision=PromotionDecisionType(d["decision"]),
            knowledge_candidate_id=d.get("knowledge_candidate_id"),
            reasons=d.get("reasons", []),
            created_at=d["created_at"],
        )


@dataclass(frozen=True)
class KnowledgeCandidate:
    """
    Ephemeral knowledge object before materialization into KnowledgeObject.

    Mirrors ArtifactCandidate in execution pipeline.
    """
    candidate_id: str                   # KCAN-[hash]
    source_decision_id: str             # PD-[hash]
    knowledge_type: KnowledgeType
    knowledge_domain: KnowledgeDomain
    title: str
    content: str
    confidence: float
    importance: str
    transferability: KnowledgeTransferability
    supporting_memory_ids: list[str]
    contradicting_memory_ids: list[str]
    source_reflection_ids: list[str]
    source_learning_record_ids: list[str]
    created_at: str

    @staticmethod
    def generate_candidate_id(
        source_decision_id: str,
        knowledge_type: KnowledgeType,
        created_at: str,
    ) -> str:
        data = f"knowledge_candidate:{source_decision_id}:{knowledge_type.value}:{created_at}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"KCAN-{h}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "source_decision_id": self.source_decision_id,
            "knowledge_type": self.knowledge_type.value,
            "knowledge_domain": self.knowledge_domain.value,
            "title": self.title,
            "content": self.content,
            "confidence": round(self.confidence, 4),
            "importance": self.importance,
            "transferability": self.transferability.value,
            "supporting_memory_ids": self.supporting_memory_ids,
            "contradicting_memory_ids": self.contradicting_memory_ids,
            "source_reflection_ids": self.source_reflection_ids,
            "source_learning_record_ids": self.source_learning_record_ids,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> KnowledgeCandidate:
        return cls(
            candidate_id=d["candidate_id"],
            source_decision_id=d["source_decision_id"],
            knowledge_type=KnowledgeType(d["knowledge_type"]),
            knowledge_domain=KnowledgeDomain(d.get("knowledge_domain", KnowledgeDomain.ARCHITECTURE.value)),
            title=d["title"],
            content=d["content"],
            confidence=d["confidence"],
            importance=d.get("importance", "medium"),
            transferability=KnowledgeTransferability(d.get("transferability", KnowledgeTransferability.LOCAL_ONLY.value)),
            supporting_memory_ids=d.get("supporting_memory_ids", []),
            contradicting_memory_ids=d.get("contradicting_memory_ids", []),
            source_reflection_ids=d.get("source_reflection_ids", []),
            source_learning_record_ids=d.get("source_learning_record_ids", []),
            created_at=d["created_at"],
        )


@dataclass(frozen=True)
class PromotionReport:
    """
    Aggregated report of a promotion cycle.

    Mirrors ArtifactPromotionReport in execution pipeline.
    """
    report_id: str                      # PREP-[hash]
    candidate: PromotionCandidate
    assessment: PromotionAssessment
    gate_result: PromotionGateResult
    decision: KnowledgePromotionDecision
    knowledge_candidate: KnowledgeCandidate | None
    created_at: str

    @staticmethod
    def generate_report_id(decision_id: str, created_at: str) -> str:
        data = f"promotion_report:{decision_id}:{created_at}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"PREP-{h}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "candidate": self.candidate.to_dict(),
            "assessment": self.assessment.to_dict(),
            "gate_result": self.gate_result.to_dict(),
            "decision": self.decision.to_dict(),
            "knowledge_candidate": self.knowledge_candidate.to_dict() if self.knowledge_candidate else None,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PromotionReport:
        kc_data = d.get("knowledge_candidate")
        return cls(
            report_id=d["report_id"],
            candidate=PromotionCandidate.from_dict(d["candidate"]),
            assessment=PromotionAssessment.from_dict(d["assessment"]),
            gate_result=PromotionGateResult.from_dict(d["gate_result"]),
            decision=KnowledgePromotionDecision.from_dict(d["decision"]),
            knowledge_candidate=KnowledgeCandidate.from_dict(kc_data) if kc_data else None,
            created_at=d["created_at"],
        )
