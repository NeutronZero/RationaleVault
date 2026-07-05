"""RationaleVault Retrieval Orchestrator — Deterministic query-to-projection routing.

No LLM. No vectors. Rule-based. Deterministic.
"""
from __future__ import annotations

from typing import Optional

from rationalevault.retrieval.models import (
    INTENT_KEYWORDS,
    INTENT_PROJECTION_MAP,
    INTENT_WEIGHT_MAP,
    RetrievalIntent,
    RetrievalPlan,
)
from rationalevault.memory.query_analyzer import RetrievalProfile

# Intent → default profile mapping
_INTENT_PROFILE_MAP: dict[RetrievalIntent, RetrievalProfile] = {
    RetrievalIntent.CONTINUATION: RetrievalProfile.WORKFLOW_RETRIEVAL,
    RetrievalIntent.KNOWLEDGE_QUERY: RetrievalProfile.KNOWLEDGE_REVIEW,
    RetrievalIntent.IMPACT_ANALYSIS: RetrievalProfile.FAILURE_ANALYSIS,
    RetrievalIntent.CROSS_PROJECT: RetrievalProfile.PROJECT_OVERVIEW,
    RetrievalIntent.ORGANIZATIONAL: RetrievalProfile.ARCHITECTURE_REVIEW,
    RetrievalIntent.GENERAL: RetrievalProfile.GENERAL_SEARCH,
}

# Secondary keyword → profile refinement (overrides default mapping)
_PROFILE_REFINEMENT_KEYWORDS: dict[RetrievalProfile, frozenset[str]] = {
    RetrievalProfile.DECISION_LOOKUP: frozenset({"decision", "decide", "accepted", "choose", "chose", "select"}),
    RetrievalProfile.LESSON_DISCOVERY: frozenset({"lesson", "learned", "reflect", "reflection"}),
    RetrievalProfile.ARCHITECTURE_REVIEW: frozenset({"architecture", "goal", "design", "principle", "principles"}),
    RetrievalProfile.FAILURE_ANALYSIS: frozenset({"fail", "failure", "error", "lost", "loss", "drift"}),
    RetrievalProfile.CONTEXT_CONSTRUCTION: frozenset({"context", "construct", "blend", "unified", "combined"}),
}


class RetrievalOrchestrator:
    """Routes queries to projections and allocates context weight.

    Deterministic: same inputs → identical plan.
    Projection-agnostic: future projections require no schema change.
    """

    def build_plan(
        self,
        query: str,
        project_id: str = "",
        available_projections: Optional[dict[str, bool]] = None,
    ) -> RetrievalPlan:
        """Build a retrieval plan for the given query.

        Args:
            query: User query string
            project_id: Current project ID
            available_projections: Which projections are available (e.g. from registry)

        Returns:
            RetrievalPlan with intent, projections, weights, confidence, reasons
        """
        if available_projections is None:
            available_projections = {
                "continuation": True,
                "knowledge": True,
                "graph": True,
                "cross_project": True,
                "organization": True,
                "organization_graph": True,
            }

        # 1. Classify intents
        primary, matched = self._classify_intents(query)

        # 2. Select projections (requested vs selected after availability)
        requested, selected = self._select_projections(matched, available_projections)

        # 3. Compute weights
        weights = self._compute_weights(matched, selected)

        # 4. Compute confidence
        confidence = self._compute_confidence(matched, query)

        # 5. Build reasons
        reasons = self._build_reasons(matched, requested, selected, available_projections)

        # 6. Derive RetrievalProfile for backward compatibility
        profile = self._derive_profile(query, primary, matched)

        return RetrievalPlan(
            primary_intent=primary,
            matched_intents=matched,
            profile=profile,
            projections=selected,
            context_weights=weights,
            requested_projections=requested,
            confidence=confidence,
            reasons=reasons,
        )

    def _classify_intents(self, query: str) -> tuple[RetrievalIntent, list[RetrievalIntent]]:
        """Classify primary and all matched intents from query.

        Returns (primary, matched_all).
        """
        query_lower = query.lower()
        query_words = set(query_lower.split())

        matched: list[RetrievalIntent] = []
        for intent, keywords in INTENT_KEYWORDS.items():
            if query_words & keywords:
                matched.append(intent)

        if not matched:
            matched = [RetrievalIntent.GENERAL]

        # Primary = strongest match (priority order)
        priority = [
            RetrievalIntent.CONTINUATION,
            RetrievalIntent.IMPACT_ANALYSIS,
            RetrievalIntent.CROSS_PROJECT,
            RetrievalIntent.ORGANIZATIONAL,
            RetrievalIntent.KNOWLEDGE_QUERY,
            RetrievalIntent.GENERAL,
        ]
        primary = RetrievalIntent.GENERAL
        for intent in priority:
            if intent in matched:
                primary = intent
                break

        return primary, matched

    def _derive_profile(
        self,
        query: str,
        primary: RetrievalIntent,
        matched: list[RetrievalIntent],
    ) -> RetrievalProfile:
        """Derive a RetrievalProfile from the classified intent and query keywords.

        Uses the primary intent's default profile, then refines with secondary
        keyword signals from query_analyzer.py's trigger sets.
        """
        profile = _INTENT_PROFILE_MAP.get(primary, RetrievalProfile.GENERAL_SEARCH)

        # Secondary refinement: check if query keywords suggest a more specific profile
        query_words = set(query.lower().split())
        for refined_profile, triggers in _PROFILE_REFINEMENT_KEYWORDS.items():
            if query_words & triggers:
                # Only refine if the refined profile is more specific than GENERAL
                if refined_profile != RetrievalProfile.GENERAL_SEARCH:
                    profile = refined_profile
                    break

        return profile

    def _select_projections(
        self,
        matched_intents: list[RetrievalIntent],
        available: dict[str, bool],
    ) -> tuple[dict[str, bool], dict[str, bool]]:
        """Select projections from matched intents, filtering by availability.

        Returns (requested, selected).
        """
        # Union of projections from all matched intents
        requested: dict[str, bool] = {}
        for intent in matched_intents:
            for proj in INTENT_PROJECTION_MAP.get(intent, set()):
                requested[proj] = True

        # Apply availability
        selected: dict[str, bool] = {}
        for proj, wanted in requested.items():
            if wanted and available.get(proj, False):
                selected[proj] = True
            else:
                selected[proj] = False

        return requested, selected

    def _compute_weights(
        self,
        matched_intents: list[RetrievalIntent],
        selected: dict[str, float],
    ) -> dict[str, float]:
        """Compute context weights from matched intents.

        For single intent: use base weights.
        For HYBRID (multiple intents): average weights, renormalize.
        """
        if len(matched_intents) == 1:
            base = INTENT_WEIGHT_MAP.get(matched_intents[0], {})
            # Filter to selected projections
            return {k: v for k, v in base.items() if k in selected}

        # HYBRID: average weights across matched intents
        all_proj_keys: set[str] = set()
        for intent in matched_intents:
            all_proj_keys.update(INTENT_WEIGHT_MAP.get(intent, {}).keys())

        summed: dict[str, float] = {}
        for proj in all_proj_keys:
            values = [
                INTENT_WEIGHT_MAP[intent].get(proj, 0.0)
                for intent in matched_intents
                if intent in INTENT_WEIGHT_MAP
            ]
            if values:
                summed[proj] = sum(values) / len(values)

        # Filter to selected
        weights = {k: v for k, v in summed.items() if k in selected}

        # Renormalize
        total = sum(weights.values())
        if total > 0:
            weights = {k: v / total for k, v in weights.items()}

        return weights

    def _compute_confidence(
        self,
        matched_intents: list[RetrievalIntent],
        query: str,
    ) -> float:
        """Compute plan confidence based on keyword match quality."""
        if RetrievalIntent.GENERAL in matched_intents and len(matched_intents) == 1:
            return 0.5

        query_words = set(query.lower().split())
        matched_keyword_count = 0
        total_keyword_count = 0
        for intent in matched_intents:
            keywords = INTENT_KEYWORDS.get(intent, set())
            total_keyword_count += len(keywords)
            matched_keyword_count += len(query_words & keywords)

        if total_keyword_count == 0:
            return 0.5

        match_ratio = matched_keyword_count / min(len(query_words), total_keyword_count)
        if match_ratio >= 0.5:
            return 0.9
        elif match_ratio >= 0.2:
            return 0.7
        return 0.5

    def _build_reasons(
        self,
        matched_intents: list[RetrievalIntent],
        requested: dict[str, bool],
        selected: dict[str, bool],
        available: dict[str, bool],
    ) -> list[str]:
        """Build human-readable reasons for the plan."""
        reasons = []

        for intent in matched_intents:
            reasons.append(f"{intent.value}_keywords_detected")

        # Check for availability gaps
        for proj, wanted in requested.items():
            if wanted and not available.get(proj, False):
                reasons.append(f"{proj}_requested_but_unavailable")

        # Check efficiency
        selected_count = sum(1 for v in selected.values() if v)
        requested_count = sum(1 for v in requested.values() if v)
        if selected_count < requested_count:
            reasons.append(f"availability_filtered_{selected_count}_of_{requested_count}")

        return reasons
