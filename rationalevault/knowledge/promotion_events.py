"""
RationaleVault Knowledge Promotion Event Payloads — Immutable event-sourced contracts for the knowledge promotion pipeline.

Every knowledge promotion event follows:

    Domain Object → Event Payload → Event Ledger → Projection → State

Event hierarchy:
    KNOWLEDGE_PROMOTION_CANDIDATE
            ↓
    KNOWLEDGE_PROMOTION_ASSESSED
            ↓
    KNOWLEDGE_PROMOTION_GATED
            ↓
    KNOWLEDGE_PROMOTION_APPROVED / KNOWLEDGE_PROMOTION_REJECTED

Design rules:
  - Payloads are FROZEN dataclasses, never reused as domain objects.
  - Every payload includes schema_version for forward compatibility.
  - Domain models remain separate from event payloads.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any


SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class PromotionCandidateCreatedPayload:
    """
    Emitted when a PromotionCandidate is extracted from a ReflectionReport.

    Event: KNOWLEDGE_PROMOTION_CANDIDATE
    """
    schema_version: str = SCHEMA_VERSION
    candidate_id: str = ""           # PROMO-[hash]
    source_reflection_ids: list[str] = field(default_factory=list)
    promotion_type: str = ""
    knowledge_type: str = ""
    knowledge_domain: str = ""
    title: str = ""
    content: str = ""
    confidence: float = 0.0
    supporting_evidence: list[str] = field(default_factory=list)
    contradicting_evidence: list[str] = field(default_factory=list)
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "candidate_id": self.candidate_id,
            "source_reflection_ids": self.source_reflection_ids,
            "promotion_type": self.promotion_type,
            "knowledge_type": self.knowledge_type,
            "knowledge_domain": self.knowledge_domain,
            "title": self.title,
            "content": self.content,
            "confidence": round(self.confidence, 4),
            "supporting_evidence": self.supporting_evidence,
            "contradicting_evidence": self.contradicting_evidence,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PromotionCandidateCreatedPayload:
        return cls(
            schema_version=d.get("schema_version", SCHEMA_VERSION),
            candidate_id=d["candidate_id"],
            source_reflection_ids=d.get("source_reflection_ids", []),
            promotion_type=d["promotion_type"],
            knowledge_type=d["knowledge_type"],
            knowledge_domain=d.get("knowledge_domain", ""),
            title=d["title"],
            content=d["content"],
            confidence=d["confidence"],
            supporting_evidence=d.get("supporting_evidence", []),
            contradicting_evidence=d.get("contradicting_evidence", []),
            created_at=d["created_at"],
        )


@dataclass(frozen=True)
class PromotionAssessedPayload:
    """
    Emitted when a PromotionCandidate has been assessed.

    Event: KNOWLEDGE_PROMOTION_ASSESSED
    """
    schema_version: str = SCHEMA_VERSION
    assessment_id: str = ""
    candidate_id: str = ""           # PROMO-[hash]
    confidence_score: float = 0.0
    evidence_ratio: float = 0.0
    supporting_count: int = 0
    contradicting_count: int = 0
    has_contradictions: bool = False
    promotion_type_valid: bool = True
    knowledge_type_valid: bool = True
    findings: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "assessment_id": self.assessment_id,
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
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PromotionAssessedPayload:
        return cls(
            schema_version=d.get("schema_version", SCHEMA_VERSION),
            assessment_id=d["assessment_id"],
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
            created_at=d["created_at"],
        )


@dataclass(frozen=True)
class PromotionGatedPayload:
    """
    Emitted when promotion gate policy has been applied to an assessment.

    Event: KNOWLEDGE_PROMOTION_GATED
    """
    schema_version: str = SCHEMA_VERSION
    gate_result_id: str = ""         # PGATE-[hash]
    assessment_id: str = ""
    candidate_id: str = ""           # PROMO-[hash]
    decision: str = ""               # APPROVE, REJECT, DEFER
    policy_version: str = ""
    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "gate_result_id": self.gate_result_id,
            "assessment_id": self.assessment_id,
            "candidate_id": self.candidate_id,
            "decision": self.decision,
            "policy_version": self.policy_version,
            "violations": self.violations,
            "warnings": self.warnings,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PromotionGatedPayload:
        return cls(
            schema_version=d.get("schema_version", SCHEMA_VERSION),
            gate_result_id=d["gate_result_id"],
            assessment_id=d["assessment_id"],
            candidate_id=d["candidate_id"],
            decision=d["decision"],
            policy_version=d["policy_version"],
            violations=d.get("violations", []),
            warnings=d.get("warnings", []),
            created_at=d["created_at"],
        )


@dataclass(frozen=True)
class PromotionDecisionPayload:
    """
    Emitted when a knowledge promotion decision has been recorded.

    Event: KNOWLEDGE_PROMOTION_APPROVED or KNOWLEDGE_PROMOTION_REJECTED
    """
    schema_version: str = SCHEMA_VERSION
    decision_id: str = ""            # PD-[hash]
    candidate_id: str = ""           # PROMO-[hash]
    gate_result_id: str = ""         # PGATE-[hash]
    decision: str = ""               # APPROVE, REJECT, DEFER
    knowledge_candidate_id: str | None = None  # KCAN-[hash] if approved
    reasons: list[str] = field(default_factory=list)
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "decision_id": self.decision_id,
            "candidate_id": self.candidate_id,
            "gate_result_id": self.gate_result_id,
            "decision": self.decision,
            "knowledge_candidate_id": self.knowledge_candidate_id,
            "reasons": self.reasons,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PromotionDecisionPayload:
        return cls(
            schema_version=d.get("schema_version", SCHEMA_VERSION),
            decision_id=d["decision_id"],
            candidate_id=d["candidate_id"],
            gate_result_id=d["gate_result_id"],
            decision=d["decision"],
            knowledge_candidate_id=d.get("knowledge_candidate_id"),
            reasons=d.get("reasons", []),
            created_at=d["created_at"],
        )


# =====================================================================
# ID Generation
# =====================================================================

def generate_assessment_id(candidate_id: str, created_at: str) -> str:
    """Generate deterministic PASSMT-[hash] identifier."""
    data = f"promotion_assessment:{candidate_id}:{created_at}"
    h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
    return f"PASSMT-{h}"


def generate_gate_result_id(assessment_id: str, decision: str, created_at: str) -> str:
    """Generate deterministic PGATE-[hash] identifier."""
    data = f"promotion_gate:{assessment_id}:{decision}:{created_at}"
    h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
    return f"PGATE-{h}"
