"""Relay Context Construction Evaluation — Sprint I5 quality metrics.

Metrics:
    - Context Completeness: % of source types represented
    - Source Traceability: % of citations with source_event_ids
    - Source Balance: min(actual/expected ratio) across sources
    - Context Precision: % of citations matching query keywords
    - Context Redundancy: duplicate content detection
    - Blending Determinism: same input → same ContextPackage
    - Timing Budget: total_ms within acceptable bounds

Sprint Exit Gates:
    MIN_CONTEXT_COMPLETENESS = 0.67  (at least 2 of 3 sources)
    MIN_SOURCE_TRACEABILITY = 1.0   (100% of citations must be traceable)
    MIN_SOURCE_BALANCE = 0.15       (no source < 15% of expected)
    MIN_BLENDING_DETERMINISM = 1.0  (100% deterministic)
    MAX_CONTEXT_COMPILE_MS = 500.0  (context must compile in < 500ms)
    MAX_CONTEXT_REDUNDANCY = 0.25   (max 25% duplicate content)
    MIN_CONTEXT_PRECISION = 0.70    (min 70% keyword match)
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

from relay.knowledge.context_compiler import (
    ContextPackage,
    PROFILE_SOURCE_WEIGHTS,
)
from relay.knowledge.context_types import ContextCitation
from relay.memory.query_analyzer import RetrievalProfile


# Sprint I5 Exit Gates
MIN_CONTEXT_COMPLETENESS: float = 0.67
MIN_SOURCE_TRACEABILITY: float = 1.0
MIN_SOURCE_BALANCE: float = 0.15
MIN_BLENDING_DETERMINISM: float = 1.0
MAX_CONTEXT_COMPILE_MS: float = 500.0
MAX_CONTEXT_REDUNDANCY: float = 0.25
MIN_CONTEXT_PRECISION: float = 0.70


@dataclass
class ContextMetrics:
    """Comprehensive context construction quality metrics."""
    # Completeness
    source_types_present: int = 0
    source_types_possible: int = 3
    context_completeness: float = 0.0

    # Traceability
    total_citations: int = 0
    citations_with_trace: int = 0
    source_traceability: float = 0.0

    # Balance
    source_balance: float = 1.0

    # Precision
    citations_with_keyword_match: int = 0
    context_precision: float = 0.0

    # Redundancy
    content_hashes: int = 0
    unique_content_hashes: int = 0
    context_redundancy: float = 0.0

    # Determinism
    run_count: int = 1
    matching_runs: int = 1
    blending_determinism: float = 1.0

    # Timing
    total_ms: float = 0.0
    within_timing_budget: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_types_present": self.source_types_present,
            "source_types_possible": self.source_types_possible,
            "context_completeness": self.context_completeness,
            "total_citations": self.total_citations,
            "citations_with_trace": self.citations_with_trace,
            "source_traceability": self.source_traceability,
            "source_balance": self.source_balance,
            "citations_with_keyword_match": self.citations_with_keyword_match,
            "context_precision": self.context_precision,
            "content_hashes": self.content_hashes,
            "unique_content_hashes": self.unique_content_hashes,
            "context_redundancy": self.context_redundancy,
            "run_count": self.run_count,
            "matching_runs": self.matching_runs,
            "blending_determinism": self.blending_determinism,
            "total_ms": self.total_ms,
            "within_timing_budget": self.within_timing_budget,
        }

    def passes_exit_gates(self) -> tuple[bool, list[str]]:
        """Check if metrics pass Sprint I5 exit gates.

        Returns:
            Tuple of (passed, list of failing gate names).
        """
        failures: list[str] = []

        if self.context_completeness < MIN_CONTEXT_COMPLETENESS:
            failures.append("context_completeness")
        if self.source_traceability < MIN_SOURCE_TRACEABILITY:
            failures.append("source_traceability")
        if self.source_balance < MIN_SOURCE_BALANCE:
            failures.append("source_balance")
        if self.blending_determinism < MIN_BLENDING_DETERMINISM:
            failures.append("blending_determinism")
        if not self.within_timing_budget:
            failures.append("timing_budget")
        if self.context_redundancy > MAX_CONTEXT_REDUNDANCY:
            failures.append("context_redundancy")
        if self.context_precision < MIN_CONTEXT_PRECISION:
            failures.append("context_precision")

        return len(failures) == 0, failures


def _compute_source_balance(package: ContextPackage) -> float:
    """Compute balance metric: min(actual/expected ratio) across sources.

    Returns 1.0 if actual ratios match expected ratios perfectly.
    Returns < 1.0 if any source is under/over-represented.
    """
    total = len(package.citations)
    if total == 0:
        return 1.0

    profile = RetrievalProfile(package.profile)
    expected = PROFILE_SOURCE_WEIGHTS.get(profile, {})
    if not expected:
        return 1.0

    actual_ratios: dict[str, float] = {}
    for source in ["event", "memory", "knowledge"]:
        count = sum(1 for c in package.citations if c.source_type == source)
        actual_ratios[source] = count / total

    deviations: list[float] = []
    for source, exp_ratio in expected.items():
        act_ratio = actual_ratios.get(source, 0.0)
        if exp_ratio > 0:
            deviations.append(act_ratio / exp_ratio)
        else:
            deviations.append(1.0 if act_ratio == 0 else 0.0)

    return min(deviations) if deviations else 1.0


def _compute_redundancy(citations: list[ContextCitation]) -> tuple[int, int, float]:
    """Detect duplicate content via normalized hash."""
    hashes: list[str] = []
    for c in citations:
        normalized = " ".join((c.title + " " + c.content).lower().strip().split())
        h = hashlib.sha256(normalized.encode()).hexdigest()[:16]
        hashes.append(h)
    unique = len(set(hashes))
    total = len(hashes)
    redundancy = 1.0 - (unique / total) if total > 0 else 0.0
    return total, unique, redundancy


def _compute_precision(
    citations: list[ContextCitation],
    keywords: list[str],
) -> tuple[int, float]:
    """How many citations contain at least one query keyword."""
    if not keywords:
        return len(citations), 1.0
    matched = 0
    for c in citations:
        content_lower = (c.title + " " + c.content).lower()
        if any(kw in content_lower for kw in keywords):
            matched += 1
    return matched, matched / len(citations) if citations else 1.0


def compute_context_metrics(
    package: ContextPackage,
    keywords: list[str] | None = None,
    run_count: int = 1,
    matching_runs: int = 1,
) -> ContextMetrics:
    """Compute all required context construction metrics.

    Args:
        package: The ContextPackage to evaluate.
        keywords: Query keywords for precision computation.
        run_count: Number of times compile_context was called with same input.
        matching_runs: Number of times the output matched exactly.

    Returns:
        ContextMetrics with all computed values.
    """
    total_citations = len(package.citations)

    # Source types present
    source_types = {c.source_type for c in package.citations}
    source_types_present = len(source_types)
    context_completeness = source_types_present / 3.0

    # Traceability
    citations_with_trace = sum(
        1 for c in package.citations if c.source_event_ids
    )
    source_traceability = (
        citations_with_trace / total_citations if total_citations else 1.0
    )

    # Balance
    source_balance = _compute_source_balance(package)

    # Precision
    if keywords is None:
        keywords = extract_keywords_from_query(package.query)
    citations_with_keyword_match, context_precision = _compute_precision(
        package.citations, keywords
    )

    # Redundancy
    content_hashes, unique_content_hashes, context_redundancy = _compute_redundancy(
        package.citations
    )

    # Determinism
    blending_determinism = (
        matching_runs / run_count if run_count > 0 else 1.0
    )

    # Timing
    total_ms = package.timing.get("total_ms", 0.0)
    within_timing_budget = total_ms <= MAX_CONTEXT_COMPILE_MS

    return ContextMetrics(
        source_types_present=source_types_present,
        context_completeness=context_completeness,
        total_citations=total_citations,
        citations_with_trace=citations_with_trace,
        source_traceability=source_traceability,
        source_balance=source_balance,
        citations_with_keyword_match=citations_with_keyword_match,
        context_precision=context_precision,
        content_hashes=content_hashes,
        unique_content_hashes=unique_content_hashes,
        context_redundancy=context_redundancy,
        run_count=run_count,
        matching_runs=matching_runs,
        blending_determinism=blending_determinism,
        total_ms=total_ms,
        within_timing_budget=within_timing_budget,
    )


def extract_keywords_from_query(query: str) -> list[str]:
    """Extract keywords from query for precision computation."""
    q_clean = query.lower().strip()
    words = [w.strip("?,.:;\"'()[]{}") for w in q_clean.split()]
    stopwords = {
        "what", "is", "a", "the", "of", "and", "in", "to", "exist",
        "are", "about", "for", "with", "on", "exists", "did", "occur", "why",
    }
    return [w for w in words if w and w not in stopwords]
