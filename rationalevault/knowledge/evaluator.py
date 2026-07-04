"""RationaleVault Knowledge Evaluator — Evaluates synthesized knowledge against ground truth.

Inherits patterns from:
- continuity_metrics.py (IdentityStatus, SemanticStatus)
- evaluation.py (KnowledgeMetrics)

Key metrics:
- Identity Recall: exact title match
- Semantic Recall: content similarity match
- Determinism Score: same input → same output across runs
- Provenance Depth: evidence strength (memories + events per knowledge)
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from rationalevault.knowledge.benchmark_schema import KnowledgeBenchmark
from rationalevault.knowledge.lineage import compute_provenance_depth
from rationalevault.knowledge.models import KnowledgeObject, KnowledgeType


class KnowledgeIdentityStatus(str, Enum):
    """Identity match status for knowledge recall."""
    PRESERVED = "PRESERVED"     # Exact title match
    ALIASED = "ALIASED"         # Similar content, different title
    LOST = "LOST"               # No match found


class KnowledgeSemanticStatus(str, Enum):
    """Semantic match status for knowledge recall."""
    CONSISTENT = "CONSISTENT"   # Content semantically matches
    DRIFTED = "DRIFTED"         # Content partially matches
    CONTRADICTED = "CONTRADICTED"  # Content contradicts


@dataclass
class KnowledgeEvalResult:
    """Results from knowledge evaluation against a benchmark."""
    benchmark_id: str
    benchmark_version: int

    # Core counts
    expected_count: int
    synthesized_count: int

    # Identity Recall (exact title match)
    identity_recall: float
    identity_preserved: int
    identity_aliased: int
    identity_lost: int

    # Semantic Recall (content similarity match)
    semantic_recall: float
    semantic_consistent: int
    semantic_drifted: int
    semantic_contradicted: int

    # Precision (synthesized that match expected)
    precision: float
    false_positives: int

    # F1 (computed from precision and semantic recall)
    f1_score: float

    # Determinism (same input → same output across runs)
    determinism_score: float

    # Provenance
    provenance_pct: float
    average_provenance_depth: float

    # Contradictions
    contradictions_detected: int
    contradictions_expected: int
    true_contradictions: int
    false_contradictions: int
    contradiction_precision: float

    # Coverage (benchmark-relative)
    type_coverage: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "benchmark_id": self.benchmark_id,
            "benchmark_version": self.benchmark_version,
            "expected_count": self.expected_count,
            "synthesized_count": self.synthesized_count,
            "identity_recall": self.identity_recall,
            "identity_preserved": self.identity_preserved,
            "identity_aliased": self.identity_aliased,
            "identity_lost": self.identity_lost,
            "semantic_recall": self.semantic_recall,
            "semantic_consistent": self.semantic_consistent,
            "semantic_drifted": self.semantic_drifted,
            "semantic_contradicted": self.semantic_contradicted,
            "precision": self.precision,
            "false_positives": self.false_positives,
            "f1_score": self.f1_score,
            "determinism_score": self.determinism_score,
            "provenance_pct": self.provenance_pct,
            "average_provenance_depth": self.average_provenance_depth,
            "contradictions_detected": self.contradictions_detected,
            "contradictions_expected": self.contradictions_expected,
            "true_contradictions": self.true_contradictions,
            "false_contradictions": self.false_contradictions,
            "contradiction_precision": self.contradiction_precision,
            "type_coverage": self.type_coverage,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> KnowledgeEvalResult:
        return cls(
            benchmark_id=d["benchmark_id"],
            benchmark_version=d.get("benchmark_version", 1),
            expected_count=d.get("expected_count", 0),
            synthesized_count=d.get("synthesized_count", 0),
            identity_recall=d.get("identity_recall", 0.0),
            identity_preserved=d.get("identity_preserved", 0),
            identity_aliased=d.get("identity_aliased", 0),
            identity_lost=d.get("identity_lost", 0),
            semantic_recall=d.get("semantic_recall", 0.0),
            semantic_consistent=d.get("semantic_consistent", 0),
            semantic_drifted=d.get("semantic_drifted", 0),
            semantic_contradicted=d.get("semantic_contradicted", 0),
            precision=d.get("precision", 0.0),
            false_positives=d.get("false_positives", 0),
            f1_score=d.get("f1_score", 0.0),
            determinism_score=d.get("determinism_score", 0.0),
            provenance_pct=d.get("provenance_pct", 0.0),
            average_provenance_depth=d.get("average_provenance_depth", 0.0),
            contradictions_detected=d.get("contradictions_detected", 0),
            contradictions_expected=d.get("contradictions_expected", 0),
            true_contradictions=d.get("true_contradictions", 0),
            false_contradictions=d.get("false_contradictions", 0),
            contradiction_precision=d.get("contradiction_precision", 0.0),
            type_coverage=d.get("type_coverage", 0.0),
        )


@dataclass
class KnowledgeEvaluationThresholds:
    """Thresholds for knowledge evaluation exit gates."""
    MIN_KNOWLEDGE_PRECISION: float = 0.80
    MIN_SEMANTIC_RECALL: float = 0.80
    MIN_IDENTITY_RECALL: float = 0.50
    MIN_KNOWLEDGE_F1: float = 0.80
    MIN_KNOWLEDGE_PROVENANCE_PCT: float = 1.00
    MIN_KNOWLEDGE_DETERMINISM: float = 1.00
    MIN_CONTRADICTION_PRECISION: float = 0.90
    MAX_FALSE_CONTRADICTIONS: int = 0


def check_knowledge_gates(
    result: KnowledgeEvalResult,
    thresholds: KnowledgeEvaluationThresholds | None = None,
) -> tuple[bool, list[str]]:
    """Check if evaluation passes exit gates.

    Returns:
        Tuple of (passed, list of failing gate names).
    """
    if thresholds is None:
        thresholds = KnowledgeEvaluationThresholds()

    failures: list[str] = []

    if result.precision < thresholds.MIN_KNOWLEDGE_PRECISION:
        failures.append("precision")
    if result.semantic_recall < thresholds.MIN_SEMANTIC_RECALL:
        failures.append("semantic_recall")
    if result.identity_recall < thresholds.MIN_IDENTITY_RECALL:
        failures.append("identity_recall")
    if result.f1_score < thresholds.MIN_KNOWLEDGE_F1:
        failures.append("f1_score")
    if result.provenance_pct < thresholds.MIN_KNOWLEDGE_PROVENANCE_PCT:
        failures.append("provenance_pct")
    if result.determinism_score < thresholds.MIN_KNOWLEDGE_DETERMINISM:
        failures.append("determinism_score")
    if result.false_contradictions > thresholds.MAX_FALSE_CONTRADICTIONS:
        failures.append("false_contradictions")

    return len(failures) == 0, failures


class KnowledgeEvaluator:
    """Evaluates synthesized knowledge against ground truth benchmarks."""

    def __init__(self, benchmark: KnowledgeBenchmark):
        self.benchmark = benchmark

    def evaluate(
        self,
        synthesized: list[KnowledgeObject],
        previous_synthesis: Optional[list[KnowledgeObject]] = None,
    ) -> KnowledgeEvalResult:
        """Run full evaluation against benchmark.

        Args:
            synthesized: List of synthesized knowledge objects.
            previous_synthesis: Previous synthesis run for determinism check.
        """
        expected = self.benchmark.all_expected_knowledge

        # Identity Recall (exact title match)
        identity_preserved, identity_aliased, identity_lost = self._evaluate_identity(
            synthesized, expected
        )
        identity_recall = (
            (identity_preserved + identity_aliased) / len(expected) if expected else 1.0
        )

        # Semantic Recall (content similarity match)
        semantic_consistent, semantic_drifted, semantic_contradicted = (
            self._evaluate_semantic(synthesized, expected)
        )
        semantic_recall = (
            (semantic_consistent + semantic_drifted) / len(expected) if expected else 1.0
        )

        # Precision
        precision, false_positives = self._evaluate_precision(synthesized, expected)

        # F1 (from precision and semantic recall)
        f1_score = _compute_f1(precision, semantic_recall)

        # Determinism (same input → same output across runs)
        determinism_score = self._evaluate_determinism(synthesized, previous_synthesis)

        # Provenance
        provenance_pct, average_provenance_depth = self._evaluate_provenance(synthesized)

        # Contradictions
        (
            contradictions_detected,
            true_contradictions,
            false_contradictions,
            contradiction_precision,
        ) = self._evaluate_contradictions(synthesized)

        # Coverage (benchmark-relative)
        type_coverage = self._evaluate_coverage(synthesized)

        return KnowledgeEvalResult(
            benchmark_id=self.benchmark.benchmark_id,
            benchmark_version=self.benchmark.benchmark_version,
            expected_count=len(expected),
            synthesized_count=len(synthesized),
            identity_recall=identity_recall,
            identity_preserved=identity_preserved,
            identity_aliased=identity_aliased,
            identity_lost=identity_lost,
            semantic_recall=semantic_recall,
            semantic_consistent=semantic_consistent,
            semantic_drifted=semantic_drifted,
            semantic_contradicted=semantic_contradicted,
            precision=precision,
            false_positives=false_positives,
            f1_score=f1_score,
            determinism_score=determinism_score,
            provenance_pct=provenance_pct,
            average_provenance_depth=average_provenance_depth,
            contradictions_detected=contradictions_detected,
            contradictions_expected=len(self.benchmark.expected_contradictions),
            true_contradictions=true_contradictions,
            false_contradictions=false_contradictions,
            contradiction_precision=contradiction_precision,
            type_coverage=type_coverage,
        )

    def _evaluate_identity(
        self,
        synthesized: list[KnowledgeObject],
        expected: list[dict[str, Any]],
    ) -> tuple[int, int, int]:
        """Evaluate identity recall (exact title match).

        Returns (preserved, aliased, lost).
        """
        synthesized_titles = {k.title.lower() for k in synthesized}
        preserved = 0
        aliased = 0
        lost = 0

        for exp in expected:
            exp_title = exp.get("title", "").lower()
            if exp_title in synthesized_titles:
                preserved += 1
            elif _fuzzy_title_match(exp_title, synthesized):
                aliased += 1
            else:
                lost += 1

        return preserved, aliased, lost

    def _evaluate_semantic(
        self,
        synthesized: list[KnowledgeObject],
        expected: list[dict[str, Any]],
    ) -> tuple[int, int, int]:
        """Evaluate semantic recall (content similarity match).

        Inherits from continuity_metrics.resolve_decision_state pattern.
        Returns (consistent, drifted, contradicted).
        """
        from rationalevault.evaluation.continuity_metrics import (
            detect_contradiction,
            get_jaccard_similarity,
        )

        consistent = 0
        drifted = 0
        contradicted = 0

        for exp in expected:
            exp_content = exp.get("content", "")
            best_similarity = 0.0
            best_match: Optional[KnowledgeObject] = None

            for k in synthesized:
                sim = get_jaccard_similarity(exp_content, k.content)
                if sim > best_similarity:
                    best_similarity = sim
                    best_match = k

            if best_match and best_similarity >= 0.7:
                if detect_contradiction(exp_content, best_match.content):
                    contradicted += 1
                else:
                    consistent += 1
            elif best_match and best_similarity >= 0.4:
                if detect_contradiction(exp_content, best_match.content):
                    contradicted += 1
                else:
                    drifted += 1
            else:
                # Check for contradiction with any synthesized
                for k in synthesized:
                    if detect_contradiction(exp_content, k.content):
                        contradicted += 1
                        break

        return consistent, drifted, contradicted

    def _evaluate_precision(
        self,
        synthesized: list[KnowledgeObject],
        expected: list[dict[str, Any]],
    ) -> tuple[float, int]:
        """Evaluate precision (synthesized that match expected)."""
        expected_titles = {e.get("title", "").lower() for e in expected}
        false_positives = 0

        for k in synthesized:
            if k.title.lower() not in expected_titles:
                # Check fuzzy match
                if not _fuzzy_title_match(k.title.lower(), expected):
                    false_positives += 1

        matched = len(synthesized) - false_positives
        precision = matched / len(synthesized) if synthesized else 1.0
        return precision, false_positives

    def _evaluate_determinism(
        self,
        current: list[KnowledgeObject],
        previous: Optional[list[KnowledgeObject]],
    ) -> float:
        """Evaluate determinism: same input → same output across runs.

        Deterministic = same knowledge ID + type + provenance chain.
        """
        if not previous:
            return 1.0

        current_map = {k.id: k for k in current}
        previous_map = {k.id: k for k in previous}

        if not previous_map:
            return 1.0

        deterministic_count = 0
        for prev_id, prev_k in previous_map.items():
            if prev_id in current_map:
                curr_k = current_map[prev_id]
                # Check type and provenance chain match
                if (
                    curr_k.knowledge_type == prev_k.knowledge_type
                    and curr_k.provenance.source_memory_ids == prev_k.provenance.source_memory_ids
                ):
                    deterministic_count += 1

        return deterministic_count / len(previous_map)

    def _evaluate_provenance(
        self,
        synthesized: list[KnowledgeObject],
    ) -> tuple[float, int]:
        """Evaluate provenance quality."""
        if not synthesized:
            return 1.0, 0

        with_provenance = sum(
            1 for k in synthesized if k.provenance.source_event_ids
        )
        provenance_pct = with_provenance / len(synthesized)

        total_depth = sum(compute_provenance_depth(k) for k in synthesized)
        average_provenance_depth = total_depth / len(synthesized)

        return provenance_pct, average_provenance_depth

    def _evaluate_contradictions(
        self,
        synthesized: list[KnowledgeObject],
    ) -> tuple[int, int, int, float]:
        """Evaluate contradiction detection quality."""
        from rationalevault.knowledge.relations import find_contradictions

        detected = find_contradictions(synthesized)
        detected_count = len(detected)

        # True contradictions = detected that match expected
        expected_set = set(self.benchmark.expected_contradictions)
        expected_reversed = {(b, a) for a, b in self.benchmark.expected_contradictions}
        true_contradictions = sum(
            1 for pair in detected if pair in expected_set or pair in expected_reversed
        )

        false_contradictions = detected_count - true_contradictions
        contradiction_precision = (
            true_contradictions / detected_count if detected_count else 1.0
        )

        return detected_count, true_contradictions, false_contradictions, contradiction_precision

    def _evaluate_coverage(self, synthesized: list[KnowledgeObject]) -> float:
        """Evaluate type coverage (benchmark-relative).

        Uses expected_knowledge_types from benchmark if available,
        otherwise falls back to covered_types from synthesized.
        """
        covered_types = {k.knowledge_type.value for k in synthesized}

        # Use benchmark-relative coverage if expected types specified
        if self.benchmark.expected_knowledge_types:
            expected_set = set(self.benchmark.expected_knowledge_types)
            return len(covered_types & expected_set) / len(expected_set) if expected_set else 1.0

        # Fallback: coverage of all possible types
        return len(covered_types) / len(KnowledgeType)


def _compute_f1(precision: float, recall: float) -> float:
    """Compute F1 score."""
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _fuzzy_title_match(
    title: str,
    candidates: list[dict[str, Any]] | list[KnowledgeObject],
) -> bool:
    """Check if a title fuzzy-matches any candidate."""
    from rationalevault.evaluation.continuity_metrics import get_jaccard_similarity

    for c in candidates:
        c_title = c.get("title", "").lower() if isinstance(c, dict) else c.title.lower()
        if get_jaccard_similarity(title, c_title) >= 0.6:
            return True
    return False
