"""RationaleVault Context Evaluator — Evaluates context packages against benchmarks.

Inherits patterns from:
- knowledge/evaluator.py (KnowledgeEvaluator, KnowledgeEvalResult)
- evaluation/continuity_metrics.py (metric computation patterns)

Key metrics:
- Completeness: Are all required sources present?
- Precision: Do citations match expected keywords?
- Source Recall: Are expected sources represented?
- Content Recall: Are expected titles/content present?
- Redundancy: Is there duplicate content?
- Source Balance: Are sources proportionally represented?
- Determinism: Same input → same ContextPackage
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

from rationalevault.evaluation.context_benchmark_schema import ContextBenchmark
from rationalevault.knowledge.context_compiler import ContextPackage, PROFILE_SOURCE_WEIGHTS
from rationalevault.knowledge.context_types import ContextCitation
from rationalevault.memory.query_analyzer import RetrievalProfile


@dataclass
class ContextEvalResult:
    """Results from context evaluation against a benchmark."""
    benchmark_id: str
    benchmark_version: int

    # Core counts
    expected_total: int
    actual_total: int

    # Completeness
    source_types_present: int
    source_types_possible: int
    completeness: float

    # Source recall
    expected_event_count: int
    actual_event_count: int
    event_recall: float

    expected_memory_count: int
    actual_memory_count: int
    memory_recall: float

    expected_knowledge_count: int
    actual_knowledge_count: int
    knowledge_recall: float

    # Content recall (titles/keywords found)
    expected_keywords: int
    matched_keywords: int
    keyword_recall: float

    # Precision
    citations_with_keyword_match: int
    precision: float

    # F1
    f1_score: float

    # Redundancy
    content_hashes: int
    unique_content_hashes: int
    redundancy: float

    # Source balance
    source_balance: float

    # Determinism
    determinism_score: float

    # Timing
    total_ms: float
    within_timing_budget: bool

    # Profile accuracy
    profile_correct: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "benchmark_id": self.benchmark_id,
            "benchmark_version": self.benchmark_version,
            "expected_total": self.expected_total,
            "actual_total": self.actual_total,
            "source_types_present": self.source_types_present,
            "source_types_possible": self.source_types_possible,
            "completeness": self.completeness,
            "expected_event_count": self.expected_event_count,
            "actual_event_count": self.actual_event_count,
            "event_recall": self.event_recall,
            "expected_memory_count": self.expected_memory_count,
            "actual_memory_count": self.actual_memory_count,
            "memory_recall": self.memory_recall,
            "expected_knowledge_count": self.expected_knowledge_count,
            "actual_knowledge_count": self.actual_knowledge_count,
            "knowledge_recall": self.knowledge_recall,
            "expected_keywords": self.expected_keywords,
            "matched_keywords": self.matched_keywords,
            "keyword_recall": self.keyword_recall,
            "citations_with_keyword_match": self.citations_with_keyword_match,
            "precision": self.precision,
            "f1_score": self.f1_score,
            "content_hashes": self.content_hashes,
            "unique_content_hashes": self.unique_content_hashes,
            "redundancy": self.redundancy,
            "source_balance": self.source_balance,
            "determinism_score": self.determinism_score,
            "total_ms": self.total_ms,
            "within_timing_budget": self.within_timing_budget,
            "profile_correct": self.profile_correct,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ContextEvalResult:
        return cls(
            benchmark_id=d["benchmark_id"],
            benchmark_version=d.get("benchmark_version", 1),
            expected_total=d.get("expected_total", 0),
            actual_total=d.get("actual_total", 0),
            source_types_present=d.get("source_types_present", 0),
            source_types_possible=d.get("source_types_possible", 3),
            completeness=d.get("completeness", 0.0),
            expected_event_count=d.get("expected_event_count", 0),
            actual_event_count=d.get("actual_event_count", 0),
            event_recall=d.get("event_recall", 0.0),
            expected_memory_count=d.get("expected_memory_count", 0),
            actual_memory_count=d.get("actual_memory_count", 0),
            memory_recall=d.get("memory_recall", 0.0),
            expected_knowledge_count=d.get("expected_knowledge_count", 0),
            actual_knowledge_count=d.get("actual_knowledge_count", 0),
            knowledge_recall=d.get("knowledge_recall", 0.0),
            expected_keywords=d.get("expected_keywords", 0),
            matched_keywords=d.get("matched_keywords", 0),
            keyword_recall=d.get("keyword_recall", 0.0),
            citations_with_keyword_match=d.get("citations_with_keyword_match", 0),
            precision=d.get("precision", 0.0),
            f1_score=d.get("f1_score", 0.0),
            content_hashes=d.get("content_hashes", 0),
            unique_content_hashes=d.get("unique_content_hashes", 0),
            redundancy=d.get("redundancy", 0.0),
            source_balance=d.get("source_balance", 0.0),
            determinism_score=d.get("determinism_score", 0.0),
            total_ms=d.get("total_ms", 0.0),
            within_timing_budget=d.get("within_timing_budget", True),
            profile_correct=d.get("profile_correct", False),
        )


@dataclass
class ContextEvaluationThresholds:
    """Thresholds for context evaluation exit gates."""
    MIN_CONTEXT_COMPLETENESS: float = 0.67
    MIN_SOURCE_TRACEABILITY: float = 1.0
    MIN_SOURCE_BALANCE: float = 0.15
    MIN_CONTEXT_PRECISION: float = 0.70
    MIN_CONTEXT_RECALL: float = 0.50
    MIN_CONTEXT_F1: float = 0.60
    MAX_CONTEXT_REDUNDANCY: float = 0.25
    MIN_BLENDING_DETERMINISM: float = 1.0
    MAX_CONTEXT_COMPILE_MS: float = 500.0


def check_context_gates(
    result: ContextEvalResult,
    thresholds: ContextEvaluationThresholds | None = None,
) -> tuple[bool, list[str]]:
    """Check if evaluation result passes exit gates.

    Returns:
        Tuple of (passed, list of failing gate names).
    """
    if thresholds is None:
        thresholds = ContextEvaluationThresholds()

    failures: list[str] = []

    if result.completeness < thresholds.MIN_CONTEXT_COMPLETENESS:
        failures.append("completeness")
    if result.source_balance < thresholds.MIN_SOURCE_BALANCE:
        failures.append("source_balance")
    if result.precision < thresholds.MIN_CONTEXT_PRECISION:
        failures.append("precision")
    avg_recall = (result.event_recall + result.memory_recall + result.knowledge_recall) / 3.0
    if avg_recall < thresholds.MIN_CONTEXT_RECALL:
        failures.append("recall")
    if result.f1_score < thresholds.MIN_CONTEXT_F1:
        failures.append("f1_score")
    if result.redundancy > thresholds.MAX_CONTEXT_REDUNDANCY:
        failures.append("redundancy")
    if result.determinism_score < thresholds.MIN_BLENDING_DETERMINISM:
        failures.append("determinism")
    if not result.within_timing_budget:
        failures.append("timing_budget")

    return len(failures) == 0, failures


class ContextEvaluator:
    """Evaluates context packages against ground truth benchmarks."""

    def __init__(self, benchmark: ContextBenchmark) -> None:
        self.benchmark = benchmark

    def evaluate(
        self,
        package: ContextPackage,
        previous_package: ContextPackage | None = None,
    ) -> ContextEvalResult:
        """Evaluate a ContextPackage against the benchmark.

        Args:
            package: The ContextPackage to evaluate.
            previous_package: Optional second run for determinism check.

        Returns:
            ContextEvalResult with all computed metrics.
        """
        b = self.benchmark

        # Source counts
        event_count = sum(1 for c in package.citations if c.source_type == "event")
        memory_count = sum(1 for c in package.citations if c.source_type == "memory")
        knowledge_count = sum(1 for c in package.citations if c.source_type == "knowledge")

        # Source recall
        event_recall = _compute_count_recall(b.expected_event_count, event_count)
        memory_recall = _compute_count_recall(b.expected_memory_count, memory_count)
        knowledge_recall = _compute_count_recall(b.expected_knowledge_count, knowledge_count)

        # Completeness
        source_types = {c.source_type for c in package.citations}
        source_types_present = len(source_types)
        completeness = source_types_present / 3.0

        # Keyword recall
        expected_keywords = [kw.lower() for kw in b.expected_keywords]
        matched_keywords = 0
        for kw in expected_keywords:
            for c in package.citations:
                content = (c.title + " " + c.content).lower()
                if kw in content:
                    matched_keywords += 1
                    break
        keyword_recall = matched_keywords / len(expected_keywords) if expected_keywords else 1.0

        # Precision
        citations_with_match = 0
        for c in package.citations:
            content = (c.title + " " + c.content).lower()
            if any(kw in content for kw in expected_keywords):
                citations_with_match += 1
        precision = citations_with_match / len(package.citations) if package.citations else 0.0

        # F1
        f1_score = _compute_f1(precision, keyword_recall)

        # Redundancy
        hashes = []
        for c in package.citations:
            normalized = " ".join((c.title + " " + c.content).lower().strip().split())
            h = hashlib.sha256(normalized.encode()).hexdigest()[:16]
            hashes.append(h)
        unique = len(set(hashes))
        total = len(hashes)
        redundancy = 1.0 - (unique / total) if total > 0 else 0.0

        # Source balance
        source_balance = _compute_source_balance(package)

        # Determinism
        determinism_score = 1.0
        if previous_package is not None:
            if _packages_equal(package, previous_package):
                determinism_score = 1.0
            else:
                determinism_score = 0.0

        # Timing
        total_ms = package.timing.get("total_ms", 0.0)
        within_timing_budget = total_ms <= 500.0

        # Profile accuracy
        profile_correct = True
        if b.expected_profile:
            profile_correct = package.profile == b.expected_profile

        # Total expected
        expected_total = b.expected_event_count + b.expected_memory_count + b.expected_knowledge_count

        return ContextEvalResult(
            benchmark_id=b.benchmark_id,
            benchmark_version=b.benchmark_version,
            expected_total=expected_total,
            actual_total=len(package.citations),
            source_types_present=source_types_present,
            source_types_possible=3,
            completeness=completeness,
            expected_event_count=b.expected_event_count,
            actual_event_count=event_count,
            event_recall=event_recall,
            expected_memory_count=b.expected_memory_count,
            actual_memory_count=memory_count,
            memory_recall=memory_recall,
            expected_knowledge_count=b.expected_knowledge_count,
            actual_knowledge_count=knowledge_count,
            knowledge_recall=knowledge_recall,
            expected_keywords=len(expected_keywords),
            matched_keywords=matched_keywords,
            keyword_recall=keyword_recall,
            citations_with_keyword_match=citations_with_match,
            precision=precision,
            f1_score=f1_score,
            content_hashes=total,
            unique_content_hashes=unique,
            redundancy=redundancy,
            source_balance=source_balance,
            determinism_score=determinism_score,
            total_ms=total_ms,
            within_timing_budget=within_timing_budget,
            profile_correct=profile_correct,
        )


def _compute_count_recall(expected: int, actual: int) -> float:
    """Compute recall for a count-based metric."""
    if expected == 0:
        return 1.0 if actual == 0 else 0.5
    return min(1.0, actual / expected)


def _compute_f1(precision: float, recall: float) -> float:
    """Compute F1 score."""
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _compute_source_balance(package: ContextPackage) -> float:
    """Compute source balance metric."""
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


def _packages_equal(a: ContextPackage, b: ContextPackage) -> bool:
    """Check if two ContextPackages are equal (for determinism check)."""
    if a.query != b.query or a.profile != b.profile:
        return False
    if len(a.citations) != len(b.citations):
        return False
    for ca, cb in zip(a.citations, b.citations):
        if ca.source_id != cb.source_id or ca.source_type != cb.source_type:
            return False
    return True
