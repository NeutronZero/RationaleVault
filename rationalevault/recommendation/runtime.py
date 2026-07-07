"""Recommendation runtime — query, filter, enrich, and rank recommendations.

This is the only component that uses DependencyReader to access
other projection state. The runtime never mutates recommendations.
It is a pure query layer over immutable projection state.

Graceful degradation:
- Embedding unavailable → skip semantic similarity (use 1.0)
- Knowledge unavailable → skip knowledge context (use None)
- Both unavailable → use priority ordering only

Determinism guarantee:
Same RecommendationState + same RecommendationQueryContext → same answer.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from rationalevault.recommendation.state import (
    Recommendation,
    RecommendationCategory,
    RecommendationQueryContext,
    RecommendationState,
    RankedRecommendation,
)


class RecommendationRuntime:
    """Query layer for recommendations.

    Provides filter, enrich, rank, and search over RecommendationState.
    Never mutates recommendations. Degrades gracefully if
    optional dependencies (Embedding, Knowledge) are unavailable.
    """

    def filter(
        self,
        state: RecommendationState,
        entity: str | None = None,
        category: RecommendationCategory | None = None,
    ) -> list[Recommendation]:
        """Filter recommendations by entity and/or category.

        Returns a new list; does not mutate state.
        """
        results = state.recommendations

        if entity is not None:
            results = [
                r for r in results
                if r.target_entity == entity
            ]

        if category is not None:
            results = [
                r for r in results
                if r.category == category
            ]

        return results

    def enrich(
        self,
        recommendations: list[Recommendation],
        dependency_reader: Any | None = None,
    ) -> list[RankedRecommendation]:
        """Add runtime context (knowledge, embeddings) — optional.

        Gracefully degrades if dependencies are unavailable.
        Returns RankedRecommendation objects preserving enrichment.
        """
        enriched = []
        for r in recommendations:
            knowledge_context = None
            semantic_similarity = 1.0

            if dependency_reader is not None:
                try:
                    from rationalevault.projection_platform.models import (
                        DependencyKind,
                    )
                    knowledge_state = dependency_reader.read(
                        "knowledge", DependencyKind.STATE,
                    )
                    knowledge_context = knowledge_state
                except Exception:
                    pass

                try:
                    from rationalevault.projection_platform.models import (
                        DependencyKind,
                    )
                    embedding = dependency_reader.read(
                        "embedding", DependencyKind.SEARCH,
                    )
                    semantic_similarity = embedding
                except Exception:
                    pass

            enriched.append(RankedRecommendation(
                recommendation=r,
                final_score=r.priority * semantic_similarity,
                semantic_similarity=semantic_similarity,
                knowledge_context=knowledge_context,
            ))

        return enriched

    def rank(
        self,
        enriched: list[RankedRecommendation],
        context: RecommendationQueryContext | None = None,
    ) -> list[RankedRecommendation]:
        """Rank by combined score using query context.

        Deterministic: same enriched list + same context → same result.
        """
        if context is None:
            context = RecommendationQueryContext(
                query_time=datetime.now(),
            )

        def _combined_score(e: RankedRecommendation) -> float:
            age_days = (
                context.query_time - e.recommendation.created_at
            ).days if e.recommendation.created_at else 0
            freshness = 1.0 / (1.0 + age_days * 0.1)
            return e.final_score * freshness

        return sorted(
            enriched,
            key=_combined_score,
            reverse=True,
        )

    def search(
        self,
        state: RecommendationState,
        query: str | None = None,
        entity: str | None = None,
        category: RecommendationCategory | None = None,
        k: int = 10,
        dependency_reader: Any | None = None,
        context: RecommendationQueryContext | None = None,
    ) -> list[RankedRecommendation]:
        """Full pipeline: filter → enrich → rank → top k.

        If dependencies are unavailable, degrades gracefully
        to priority-based ranking.
        """
        filtered = self.filter(state, entity=entity, category=category)
        enriched = self.enrich(filtered, dependency_reader)
        ranked = self.rank(enriched, context)
        return ranked[:k]
