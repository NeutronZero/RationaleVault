"""Recommendation Projection — deterministic analytical facts from events."""

from rationalevault.recommendation.projection import RecommendationProjection
from rationalevault.recommendation.runtime import RecommendationRuntime
from rationalevault.recommendation.rules import RecommendationRuleRegistry
from rationalevault.recommendation.state import (
    Recommendation,
    RecommendationCategory,
    RecommendationState,
)

__all__ = [
    "Recommendation",
    "RecommendationCategory",
    "RecommendationProjection",
    "RecommendationRuntime",
    "RecommendationRuleRegistry",
    "RecommendationState",
]
