"""
RationaleVault AI Advisory — Optional AI advisory layer producing immutable AdvisoryReport objects.

Design rules:
  - AI never writes to the ledger — advisory only.
  - AdvisoryReport is an immutable, append-only object.
  - AdvisoryReport can influence but never deterministically control decisions.
  - Advisory reports are identified by ADVCS-[hash].
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum
from typing import Any


# =====================================================================
# Enums
# =====================================================================

class AdvisoryType(str, Enum):
    """Types of AI advisory reports."""
    REFLECTION_SUMMARY = "REFLECTION_SUMMARY"
    PROMOTION_SUGGESTION = "PROMOTION_SUGGESTION"
    CONFLICT_ANALYSIS = "CONFLICT_ANALYSIS"
    KNOWLEDGE_ASSESSMENT = "KNOWLEDGE_ASSESSMENT"
    PLANNER_RECOMMENDATION = "PLANNER_RECOMMENDATION"


class AdvisoryConfidence(str, Enum):
    """Confidence level of the advisory report."""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


# =====================================================================
# Domain Models
# =====================================================================

@dataclass(frozen=True)
class AdvisoryReport:
    """
    Immutable AI advisory report.

    AI produces this object but never writes to the ledger.
    AdvisoryReport can influence decisions but never deterministically control them.
    """
    report_id: str                  # ADVCS-[hash]
    advisory_type: AdvisoryType
    confidence: AdvisoryConfidence
    summary: str
    details: str
    source_ids: list[str]           # IDs of objects this advisory references
    recommendations: list[str]
    warnings: list[str]
    created_at: str
    model_version: str = ""

    @staticmethod
    def generate_report_id(advisory_type: str, summary: str, created_at: str) -> str:
        data = f"advisory:{advisory_type}:{summary}:{created_at}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"ADVCS-{h}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "advisory_type": self.advisory_type.value,
            "confidence": self.confidence.value,
            "summary": self.summary,
            "details": self.details,
            "source_ids": self.source_ids,
            "recommendations": self.recommendations,
            "warnings": self.warnings,
            "created_at": self.created_at,
            "model_version": self.model_version,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> AdvisoryReport:
        return cls(
            report_id=d["report_id"],
            advisory_type=AdvisoryType(d["advisory_type"]),
            confidence=AdvisoryConfidence(d["confidence"]),
            summary=d["summary"],
            details=d["details"],
            source_ids=d.get("source_ids", []),
            recommendations=d.get("recommendations", []),
            warnings=d.get("warnings", []),
            created_at=d["created_at"],
            model_version=d.get("model_version", ""),
        )


@dataclass(frozen=True)
class AdvisoryRequest:
    """
    Request for AI advisory analysis.

    This is what the system sends to the AI layer.
    The AI responds with an AdvisoryReport.
    """
    request_id: str
    advisory_type: AdvisoryType
    context_ids: list[str]          # IDs of objects to analyze
    question: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "advisory_type": self.advisory_type.value,
            "context_ids": self.context_ids,
            "question": self.question,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> AdvisoryRequest:
        return cls(
            request_id=d["request_id"],
            advisory_type=AdvisoryType(d["advisory_type"]),
            context_ids=d.get("context_ids", []),
            question=d["question"],
            created_at=d["created_at"],
        )
