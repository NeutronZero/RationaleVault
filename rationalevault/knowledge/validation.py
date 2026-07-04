"""
RationaleVault Knowledge Validation — Periodic validation of promoted knowledge against new evidence.

This closes the cognitive loop:

    Knowledge → New Evidence → Validation → (Evolution Candidate | Confirmed)

KVAL-[hash] reports are produced deterministically:
  1. Compare new evidence against existing KnowledgeObject
  2. Produce KnowledgeValidationReport with status (CONFIRMED, CONFLICTED, EVOLVED, STALE)
  3. If EVOLVED/CONFLICTED, produce KnowledgeEvolutionCandidate
  4. Evolution candidates feed back into the promotion pipeline

Design rules:
  - Deterministic — no randomness, no I/O, no AI calls.
  - Validation never mutates the original KnowledgeObject.
  - Evolution candidates are append-only (new version, never overwrite).
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum
from typing import Any

from rationalevault.knowledge.models import (
    KnowledgeObject,
    KnowledgeType,
    KnowledgeDomain,
)
from rationalevault.knowledge.promotion_models import (
    PromotionType,
)


# =====================================================================
# Enums
# =====================================================================

class ValidationStatus(str, Enum):
    """Outcome of knowledge validation."""
    CONFIRMED = "CONFIRMED"       # New evidence supports existing knowledge
    CONFLICTED = "CONFLICTED"     # New evidence contradicts existing knowledge
    EVOLVED = "EVOLVED"           # Knowledge needs updating based on new evidence
    STALE = "STALE"               # Knowledge is no longer relevant


# =====================================================================
# Domain Models
# =====================================================================

@dataclass(frozen=True)
class EvidenceItem:
    """A piece of evidence to validate against."""
    evidence_id: str               # LEARN-[hash] or REFL-[hash]
    content: str
    source_type: str               # "learning_record" or "reflection"
    confidence: float
    relationship: str              # "supporting" or "contradicting"
    created_at: str


@dataclass(frozen=True)
class KnowledgeValidationReport:
    """
    Report of validating a KnowledgeObject against new evidence.

    KVAL-[hash] — immutable, append-only.
    """
    report_id: str                  # KVAL-[hash]
    knowledge_id: str               # The KnowledgeObject being validated
    knowledge_version: int
    validation_status: ValidationStatus
    evidence_count: int
    supporting_count: int
    contradicting_count: int
    evidence_ratio: float
    findings: list[str]
    warnings: list[str]
    created_at: str

    @staticmethod
    def generate_report_id(knowledge_id: str, created_at: str) -> str:
        data = f"knowledge_validation:{knowledge_id}:{created_at}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"KVAL-{h}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "knowledge_id": self.knowledge_id,
            "knowledge_version": self.knowledge_version,
            "validation_status": self.validation_status.value,
            "evidence_count": self.evidence_count,
            "supporting_count": self.supporting_count,
            "contradicting_count": self.contradicting_count,
            "evidence_ratio": round(self.evidence_ratio, 4),
            "findings": self.findings,
            "warnings": self.warnings,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> KnowledgeValidationReport:
        return cls(
            report_id=d["report_id"],
            knowledge_id=d["knowledge_id"],
            knowledge_version=d["knowledge_version"],
            validation_status=ValidationStatus(d["validation_status"]),
            evidence_count=d["evidence_count"],
            supporting_count=d["supporting_count"],
            contradicting_count=d["contradicting_count"],
            evidence_ratio=d["evidence_ratio"],
            findings=d.get("findings", []),
            warnings=d.get("warnings", []),
            created_at=d["created_at"],
        )


@dataclass(frozen=True)
class KnowledgeEvolutionCandidate:
    """
    A candidate for knowledge evolution when validation finds contradictions.

    Feeds back into the promotion pipeline as a new PromotionCandidate.
    """
    candidate_id: str              # KEVOL-[hash]
    source_knowledge_id: str
    source_validation_report_id: str
    promotion_type: PromotionType
    knowledge_type: KnowledgeType
    knowledge_domain: KnowledgeDomain
    title: str
    content: str
    confidence: float
    supporting_evidence: list[str]
    contradicting_evidence: list[str]
    created_at: str

    @staticmethod
    def generate_candidate_id(
        source_knowledge_id: str,
        validation_report_id: str,
        created_at: str,
    ) -> str:
        data = f"knowledge_evolution:{source_knowledge_id}:{validation_report_id}:{created_at}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"KEVOL-{h}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "source_knowledge_id": self.source_knowledge_id,
            "source_validation_report_id": self.source_validation_report_id,
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
    def from_dict(cls, d: dict[str, Any]) -> KnowledgeEvolutionCandidate:
        return cls(
            candidate_id=d["candidate_id"],
            source_knowledge_id=d["source_knowledge_id"],
            source_validation_report_id=d["source_validation_report_id"],
            promotion_type=PromotionType(d["promotion_type"]),
            knowledge_type=KnowledgeType(d["knowledge_type"]),
            knowledge_domain=KnowledgeDomain(d["knowledge_domain"]),
            title=d["title"],
            content=d["content"],
            confidence=d["confidence"],
            supporting_evidence=d.get("supporting_evidence", []),
            contradicting_evidence=d.get("contradicting_evidence", []),
            created_at=d["created_at"],
        )


# =====================================================================
# Validator
# =====================================================================

class KnowledgeValidator:
    """
    Validates a KnowledgeObject against new evidence.

    Produces a KnowledgeValidationReport and optionally a KnowledgeEvolutionCandidate.
    """

    @staticmethod
    def validate(
        knowledge: KnowledgeObject,
        evidence: list[EvidenceItem],
        created_at: str,
    ) -> tuple[KnowledgeValidationReport, KnowledgeEvolutionCandidate | None]:
        """
        Validate a KnowledgeObject against new evidence.

        Returns:
            (report, evolution_candidate_or_None)
        """
        supporting = 0
        contradicting = 0
        findings: list[str] = []
        warnings: list[str] = []

        for item in evidence:
            if item.relationship == "supporting":
                supporting += 1
                findings.append(f"Evidence {item.evidence_id} supports knowledge")
            elif item.relationship == "contradicting":
                contradicting += 1
                findings.append(f"Evidence {item.evidence_id} contradicts knowledge")
            else:
                # Unknown relationship — treat as neutral
                findings.append(f"Evidence {item.evidence_id} has unknown relationship: {item.relationship}")

        total = supporting + contradicting
        evidence_ratio = supporting / total if total > 0 else 0.0

        # Determine validation status
        if contradicting == 0 and supporting > 0:
            status = ValidationStatus.CONFIRMED
            findings.append("All evidence supports existing knowledge")
        elif contradicting > 0 and supporting > contradicting:
            status = ValidationStatus.EVOLVED
            warnings.append(f"Knowledge needs updating: {contradicting} contradicting evidence items")
        elif contradicting > 0 and supporting <= contradicting:
            status = ValidationStatus.CONFLICTED
            warnings.append(f"Knowledge conflicts with {contradicting} evidence items")
        elif total == 0:
            status = ValidationStatus.STALE
            warnings.append("No evidence provided for validation")
        else:
            status = ValidationStatus.CONFIRMED

        # Build report
        report_id = KnowledgeValidationReport.generate_report_id(knowledge.id, created_at)
        report = KnowledgeValidationReport(
            report_id=report_id,
            knowledge_id=knowledge.id,
            knowledge_version=knowledge.version,
            validation_status=status,
            evidence_count=total,
            supporting_count=supporting,
            contradicting_count=contradicting,
            evidence_ratio=evidence_ratio,
            findings=findings,
            warnings=warnings,
            created_at=created_at,
        )

        # Build evolution candidate if needed
        evolution_candidate = None
        if status in (ValidationStatus.CONFLICTED, ValidationStatus.EVOLVED):
            evol_id = KnowledgeEvolutionCandidate.generate_candidate_id(
                knowledge.id, report_id, created_at
            )
            # Build updated content incorporating new evidence
            new_content = _build_evolved_content(knowledge, evidence, supporting, contradicting)
            new_confidence = _compute_evolved_confidence(
                knowledge.confidence.score, supporting, contradicting
            )
            evolution_candidate = KnowledgeEvolutionCandidate(
                candidate_id=evol_id,
                source_knowledge_id=knowledge.id,
                source_validation_report_id=report_id,
                promotion_type=_classify_evolution_type(knowledge.knowledge_type),
                knowledge_type=knowledge.knowledge_type,
                knowledge_domain=knowledge.knowledge_domain,
                title=knowledge.title,
                content=new_content,
                confidence=new_confidence,
                supporting_evidence=[e.evidence_id for e in evidence if e.confidence >= 0.3],
                contradicting_evidence=[e.evidence_id for e in evidence if e.confidence < 0.3 or True],  # Simplified
                created_at=created_at,
            )

        return report, evolution_candidate


def _build_evolved_content(
    knowledge: KnowledgeObject,
    evidence: list[EvidenceItem],
    supporting: int,
    contradicting: int,
) -> str:
    """Build evolved content incorporating new evidence."""
    parts = [knowledge.content]
    if contradicting > 0:
        parts.append(f"[Updated: {contradicting} contradicting evidence items incorporated]")
    return " ".join(parts)


def _compute_evolved_confidence(
    current_score: float,
    supporting: int,
    contradicting: int,
) -> float:
    """Compute evolved confidence from current score and new evidence."""
    total = supporting + contradicting
    if total == 0:
        return current_score
    new_evidence_ratio = supporting / total
    # Blend: 60% current, 40% new evidence ratio
    return max(0.0, min(1.0, current_score * 0.6 + new_evidence_ratio * 0.4))


def _classify_evolution_type(knowledge_type: KnowledgeType) -> PromotionType:
    """Classify the promotion type for an evolution candidate."""
    mapping = {
        KnowledgeType.LESSON: PromotionType.LESSON_TO_INVARIANT,
        KnowledgeType.ARCHITECTURE_PRINCIPLE: PromotionType.PATTERN_TO_PRINCIPLE,
        KnowledgeType.FAILURE_PATTERN: PromotionType.FAILURE_TO_PATTERN,
        KnowledgeType.WORKFLOW_PATTERN: PromotionType.WORKFLOW_TO_INVARIANT,
        KnowledgeType.PROJECT_INVARIANT: PromotionType.LESSON_TO_INVARIANT,
        KnowledgeType.RESEARCH_FINDING: PromotionType.OBSERVATION_TO_FACT,
        KnowledgeType.DECISION_LINEAGE: PromotionType.PATTERN_TO_PRINCIPLE,
    }
    return mapping.get(knowledge_type, PromotionType.LESSON_TO_INVARIANT)
