"""RationaleVault Recommendation Models — Types for the recommendation engine.

RecommendationSet is a generated artifact, not a projection state.
No persistence. No replay lineage. No source-of-truth semantics.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class RecommendationCategory(str, Enum):
    """Categories of organizational recommendations. Priority-ordered below."""
    CONFLICT_RESOLUTION = "CONFLICT_RESOLUTION"
    TRANSFER_FOLLOWUP = "TRANSFER_FOLLOWUP"
    INACTIVITY_REVIEW = "INACTIVITY_REVIEW"
    FLOW_REBALANCING = "FLOW_REBALANCING"
    CLUSTER_HEALTH = "CLUSTER_HEALTH"
    INVARIANT_REVIEW = "INVARIANT_REVIEW"


CATEGORY_PRIORITY: dict[RecommendationCategory, int] = {
    RecommendationCategory.CONFLICT_RESOLUTION: 1,
    RecommendationCategory.TRANSFER_FOLLOWUP: 2,
    RecommendationCategory.INACTIVITY_REVIEW: 3,
    RecommendationCategory.FLOW_REBALANCING: 4,
    RecommendationCategory.CLUSTER_HEALTH: 5,
    RecommendationCategory.INVARIANT_REVIEW: 6,
}


class EvidenceType(str, Enum):
    """Evidence ID prefix types. Scoped, parseable, deterministic."""
    HOTSPOT = "hotspot"
    INACTIVE = "inactive"
    TRANSFER = "transfer"
    FLOW = "flow"
    CLUSTER = "cluster"
    INVARIANT = "invariant"


@dataclass(frozen=True)
class Recommendation:
    """A single deterministic recommendation derived from organizational state.

    recommendation_id is a stable hash of category + affected projects + evidence.
    No recommendation exists without supporting evidence.
    """
    recommendation_id: str
    category: RecommendationCategory
    priority: int
    title: str
    rationale: list[str] = field(default_factory=list)
    affected_projects: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    confidence: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "recommendation_id": self.recommendation_id,
            "category": self.category.value,
            "priority": self.priority,
            "title": self.title,
            "rationale": self.rationale,
            "affected_projects": self.affected_projects,
            "evidence_ids": self.evidence_ids,
            "confidence": round(self.confidence, 4),
        }

    def __post_init__(self) -> None:
        if isinstance(self.category, str):
            object.__setattr__(self, "category", RecommendationCategory(self.category))
        if not self.evidence_ids:
            raise ValueError(
                f"Recommendation {self.recommendation_id} has no evidence_ids. "
                "Every recommendation must have at least one evidence reference."
            )


def _make_recommendation_id(
    category: RecommendationCategory,
    affected_projects: list[str],
    evidence_ids: list[str],
) -> str:
    """Deterministic recommendation ID from category, projects, and evidence."""
    raw = f"{category.value}:{sorted(affected_projects)}:{sorted(evidence_ids)}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def make_recommendation(
    category: RecommendationCategory,
    title: str,
    rationale: list[str] | None = None,
    affected_projects: list[str] | None = None,
    evidence_ids: list[str] | None = None,
    confidence: float = 1.0,
) -> Recommendation:
    """Factory helper to create a Recommendation with a stable ID."""
    projects = sorted(affected_projects or [])
    evidence = sorted(evidence_ids or [])
    recommendation_id = _make_recommendation_id(category, projects, evidence)
    return Recommendation(
        recommendation_id=recommendation_id,
        category=category,
        priority=CATEGORY_PRIORITY[category],
        title=title,
        rationale=rationale or [],
        affected_projects=projects,
        evidence_ids=evidence,
        confidence=confidence,
    )


@dataclass
class RecommendationSet:
    """Generated artifact from the recommendation engine.

    Not a projection state. No version, no replay lineage.
    """
    compiled_at: str = ""
    recommendations: list[Recommendation] = field(default_factory=list)

    @property
    def recommendation_count(self) -> int:
        return len(self.recommendations)

    @property
    def attention_load(self) -> float:
        activated = len({r.category for r in self.recommendations})
        total = len(RecommendationCategory)
        return activated / total if total > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "compiled_at": self.compiled_at,
            "recommendations": [r.to_dict() for r in self.recommendations],
            "recommendation_count": self.recommendation_count,
            "attention_load": round(self.attention_load, 4),
        }
