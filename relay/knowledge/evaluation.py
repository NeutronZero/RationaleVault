"""Relay Knowledge Evaluation — Knowledge quality metrics.

Metrics:
    - Knowledge Count
    - Knowledge Density (knowledge_count / memory_count)
    - Knowledge Recall
    - Knowledge Precision
    - Knowledge Provenance %
    - Contradictions Detected
    - Knowledge Coverage
    - Determinism Score
    - Stability Score
    - Freshness Score

Sprint Exit Gates:
    MIN_KNOWLEDGE_PROVENANCE_PCT = 1.0
    MIN_KNOWLEDGE_DETERMINISM = 1.0
    MAX_ORPHAN_KNOWLEDGE = 0
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from relay.knowledge.models import KnowledgeObject, KnowledgeType


# ── Sprint Exit Gates ─────────────────────────────────────────────────────────

MIN_KNOWLEDGE_PROVENANCE_PCT = 1.0
MIN_KNOWLEDGE_DETERMINISM = 1.0
MAX_ORPHAN_KNOWLEDGE = 0


@dataclass
class KnowledgeMetrics:
    """Comprehensive knowledge quality metrics."""
    knowledge_count: int = 0
    knowledge_density: float = 0.0
    knowledge_recall: float = 0.0
    knowledge_precision: float = 0.0
    knowledge_provenance_pct: float = 0.0
    contradictions_detected: int = 0
    knowledge_coverage: float = 0.0
    determinism_score: float = 0.0
    stability_score: float = 0.0
    freshness_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "knowledge_count": self.knowledge_count,
            "knowledge_density": self.knowledge_density,
            "knowledge_recall": self.knowledge_recall,
            "knowledge_precision": self.knowledge_precision,
            "knowledge_provenance_pct": self.knowledge_provenance_pct,
            "contradictions_detected": self.contradictions_detected,
            "knowledge_coverage": self.knowledge_coverage,
            "determinism_score": self.determinism_score,
            "stability_score": self.stability_score,
            "freshness_score": self.freshness_score,
        }

    def passes_exit_gates(self) -> tuple[bool, list[str]]:
        """Check if metrics pass sprint exit gates.

        Returns:
            Tuple of (passed, list of failing gate names).
        """
        failures: list[str] = []

        if self.knowledge_provenance_pct < MIN_KNOWLEDGE_PROVENANCE_PCT:
            failures.append("knowledge_provenance_pct")
        if self.determinism_score < MIN_KNOWLEDGE_DETERMINISM:
            failures.append("determinism_score")

        return len(failures) == 0, failures


def compute_knowledge_metrics(
    synthesized: list[KnowledgeObject],
    expected: list[dict[str, Any]],
    memory_count: int = 0,
    previous_synthesis: Optional[list[KnowledgeObject]] = None,
    run_twice_same_output: bool = True,
) -> KnowledgeMetrics:
    """Compute all required knowledge metrics.

    Args:
        synthesized: List of synthesized knowledge objects.
        expected: List of expected knowledge dicts (ground truth).
        memory_count: Total number of source memories.
        previous_synthesis: Previous synthesis run for stability comparison.
        run_twice_same_output: Whether two runs produced identical output.

    Returns:
        KnowledgeMetrics with all computed values.
    """
    knowledge_count = len(synthesized)

    # Knowledge Density: knowledge_count / memory_count
    knowledge_density = knowledge_count / memory_count if memory_count > 0 else 0.0

    # Recall: % of expected knowledge found
    expected_titles = {e.get("title", "").lower() for e in expected}
    found_titles = {k.title.lower() for k in synthesized}
    matched = expected_titles & found_titles
    knowledge_recall = len(matched) / len(expected_titles) if expected_titles else 1.0

    # Precision: % of synthesized knowledge that matches expected
    knowledge_precision = len(matched) / len(found_titles) if found_titles else 1.0

    # Provenance %: % with complete provenance chain
    with_provenance = sum(
        1 for k in synthesized if k.provenance.source_event_ids
    )
    knowledge_provenance_pct = (
        with_provenance / knowledge_count if knowledge_count else 1.0
    )

    # Contradictions
    from relay.knowledge.relations import find_contradictions

    contradictions = find_contradictions(synthesized)
    contradictions_detected = len(contradictions)

    # Coverage: % of KnowledgeType enum represented
    covered_types = {k.knowledge_type for k in synthesized}
    knowledge_coverage = len(covered_types) / len(KnowledgeType)

    # Determinism: same input → same output (verified by test)
    determinism_score = 1.0 if run_twice_same_output else 0.0

    # Stability: small input change → small knowledge change
    stability_score = _compute_stability(synthesized, previous_synthesis)

    # Freshness: active knowledge / total knowledge
    from relay.knowledge.models import KnowledgeLifecycle

    active = sum(
        1
        for k in synthesized
        if k.lifecycle_status == KnowledgeLifecycle.ACTIVE.value
    )
    freshness_score = active / knowledge_count if knowledge_count else 1.0

    return KnowledgeMetrics(
        knowledge_count=knowledge_count,
        knowledge_density=knowledge_density,
        knowledge_recall=knowledge_recall,
        knowledge_precision=knowledge_precision,
        knowledge_provenance_pct=knowledge_provenance_pct,
        contradictions_detected=contradictions_detected,
        knowledge_coverage=knowledge_coverage,
        determinism_score=determinism_score,
        stability_score=stability_score,
        freshness_score=freshness_score,
    )


def _compute_stability(
    current: list[KnowledgeObject],
    previous: Optional[list[KnowledgeObject]],
) -> float:
    """Compute stability: small input change → small knowledge change.

    Stability = unchanged_knowledge / total_previous_knowledge
    """
    if not previous:
        return 1.0

    current_ids = {k.id for k in current}
    previous_ids = {k.id for k in previous}

    if not previous_ids:
        return 1.0

    unchanged = current_ids & previous_ids
    return len(unchanged) / len(previous_ids)
