"""RationaleVault Recommendation Engine — Deterministic decision synthesis.

RecommendationEngine generates RecommendationSet from projected organizational state.
Engine layer, not projection layer. No persistence. No new source of truth.
"""
from rationalevault.organization.recommendations.models import (
    CATEGORY_PRIORITY,
    EvidenceType,
    Recommendation,
    RecommendationCategory,
    RecommendationSet,
)
from rationalevault.organization.recommendations.engine import RecommendationEngine

__all__ = [
    "CATEGORY_PRIORITY",
    "EvidenceType",
    "Recommendation",
    "RecommendationCategory",
    "RecommendationEngine",
    "RecommendationSet",
]
