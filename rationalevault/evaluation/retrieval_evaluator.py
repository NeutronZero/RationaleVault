"""RationaleVault Retrieval Evaluator — Evaluates hybrid retrieval orchestrator quality.

6 metrics: intent_accuracy, projection_selection_accuracy, projection_efficiency,
context_weight_accuracy, determinism, availability_handling_accuracy.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rationalevault.evaluation.thresholds import EvaluationThresholds
from rationalevault.retrieval.models import RetrievalPlan
from rationalevault.retrieval.orchestrator import RetrievalOrchestrator


@dataclass
class RetrievalEvalResult:
    """Evaluation result for retrieval orchestration."""
    intent_accuracy: float = 0.0
    projection_selection_accuracy: float = 0.0
    projection_efficiency: float = 0.0
    context_weight_accuracy: float = 0.0
    determinism: float = 0.0
    availability_handling_accuracy: float = 0.0

    def passes_exit_gate(self) -> tuple[bool, list[str]]:
        """Check if all metrics pass thresholds."""
        t = EvaluationThresholds()
        failures: list[str] = []

        checks = {
            "intent_accuracy": (self.intent_accuracy, t.MIN_I12_INTENT_ACCURACY),
            "projection_selection_accuracy": (self.projection_selection_accuracy, t.MIN_I12_PROJECTION_SELECTION),
            "projection_efficiency": (self.projection_efficiency, t.MIN_I12_PROJECTION_EFFICIENCY),
            "context_weight_accuracy": (self.context_weight_accuracy, t.MIN_I12_CONTEXT_WEIGHT_ACCURACY),
            "determinism": (self.determinism, t.MIN_I12_DETERMINISM),
            "availability_handling_accuracy": (self.availability_handling_accuracy, t.MIN_I12_AVAILABILITY_HANDLING),
        }

        for name, (value, threshold) in checks.items():
            if value < threshold:
                failures.append(name)

        return len(failures) == 0, failures

    def to_dict(self) -> dict[str, Any]:
        passed, failures = self.passes_exit_gate()
        t = EvaluationThresholds()
        checks = {
            "intent_accuracy": self.intent_accuracy,
            "projection_selection_accuracy": self.projection_selection_accuracy,
            "projection_efficiency": self.projection_efficiency,
            "context_weight_accuracy": self.context_weight_accuracy,
            "determinism": self.determinism,
            "availability_handling_accuracy": self.availability_handling_accuracy,
        }
        threshold_map = {
            "intent_accuracy": t.MIN_I12_INTENT_ACCURACY,
            "projection_selection_accuracy": t.MIN_I12_PROJECTION_SELECTION,
            "projection_efficiency": t.MIN_I12_PROJECTION_EFFICIENCY,
            "context_weight_accuracy": t.MIN_I12_CONTEXT_WEIGHT_ACCURACY,
            "determinism": t.MIN_I12_DETERMINISM,
            "availability_handling_accuracy": t.MIN_I12_AVAILABILITY_HANDLING,
        }
        total = len(checks)
        passing = sum(1 for name, value in checks.items() if value >= threshold_map[name])
        return {
            **checks,
            "retrieval_orchestration_success_rate": passing / total if total > 0 else 1.0,
            "passed": passed,
            "failures": failures,
        }


@dataclass
class RetrievalTestCase:
    """A single retrieval test case with expected results."""
    query: str
    expected_intent: str
    expected_projections: set[str] = field(default_factory=set)
    available_projections: dict[str, bool] = field(default_factory=lambda: {
        "continuation": True, "knowledge": True, "graph": True,
        "cross_project": True, "organization": True,
    })
    expected_weight_direction: dict[str, str] = field(default_factory=dict)


# Standard test corpus
RETRIEVAL_TEST_CORPUS: list[RetrievalTestCase] = [
    RetrievalTestCase(
        query="continue sprint 34 where I left off",
        expected_intent="continuation",
        expected_projections={"continuation", "knowledge", "graph", "cross_project", "organization", "organization_graph"},
    ),
    RetrievalTestCase(
        query="what knowledge principle governs this pattern",
        expected_intent="knowledge_query",
        expected_projections={"knowledge", "graph"},
    ),
    RetrievalTestCase(
        query="what breaks if we change PostgreSQL",
        expected_intent="impact_analysis",
        expected_projections={"knowledge", "graph", "cross_project", "organization", "organization_graph"},
    ),
    RetrievalTestCase(
        query="what knowledge is shared across projects",
        expected_intent="cross_project",
        expected_projections={"cross_project", "organization", "knowledge", "graph"},
    ),
    RetrievalTestCase(
        query="show organizational lineage flow",
        expected_intent="organizational",
        expected_projections={"organization"},
    ),
    RetrievalTestCase(
        query="continue sprint 34 and show organizational flow",
        expected_intent="continuation",
        expected_projections={"continuation", "knowledge", "graph", "cross_project", "organization", "organization_graph"},
    ),
]


class RetrievalEvaluator:
    """Evaluates hybrid retrieval orchestrator quality."""

    def __init__(self) -> None:
        self.orchestrator = RetrievalOrchestrator()

    def evaluate(
        self,
        corpus: list[RetrievalTestCase] | None = None,
        previous_plans: list[RetrievalPlan] | None = None,
    ) -> RetrievalEvalResult:
        """Evaluate retrieval quality across a test corpus.

        Args:
            corpus: Test cases to evaluate against. Uses standard corpus if None.
            previous_plans: Plans from previous runs for determinism check.
        """
        if corpus is None:
            corpus = RETRIEVAL_TEST_CORPUS

        plans = [self.orchestrator.build_plan(tc.query) for tc in corpus]

        return RetrievalEvalResult(
            intent_accuracy=self._check_intent_accuracy(corpus, plans),
            projection_selection_accuracy=self._check_projection_selection(corpus, plans),
            projection_efficiency=self._check_projection_efficiency(corpus, plans),
            context_weight_accuracy=self._check_context_weight_accuracy(corpus, plans),
            determinism=self._check_determinism(corpus, plans, previous_plans),
            availability_handling_accuracy=self._check_availability_handling(),
        )

    def _check_intent_accuracy(
        self,
        corpus: list[RetrievalTestCase],
        plans: list[RetrievalPlan],
    ) -> float:
        """% of test cases where primary intent matches expected."""
        if not corpus:
            return 1.0
        correct = 0
        for tc, plan in zip(corpus, plans):
            if plan.primary_intent.value == tc.expected_intent:
                correct += 1
        return correct / len(corpus)

    def _check_projection_selection(
        self,
        corpus: list[RetrievalTestCase],
        plans: list[RetrievalPlan],
    ) -> float:
        """Jaccard similarity of selected vs expected projections."""
        if not corpus:
            return 1.0
        total_jaccard = 0.0
        for tc, plan in zip(corpus, plans):
            selected = {k for k, v in plan.projections.items() if v}
            expected = tc.expected_projections
            if not expected and not selected:
                total_jaccard += 1.0
            elif not expected or not selected:
                total_jaccard += 0.0
            else:
                intersection = len(selected & expected)
                union = len(selected | expected)
                total_jaccard += intersection / union if union > 0 else 1.0
        return total_jaccard / len(corpus)

    def _check_projection_efficiency(
        self,
        corpus: list[RetrievalTestCase],
        plans: list[RetrievalPlan],
    ) -> float:
        """selected_useful / selected_total — penalize over-selection."""
        if not corpus:
            return 1.0
        total_efficiency = 0.0
        for tc, plan in zip(corpus, plans):
            selected = {k for k, v in plan.projections.items() if v}
            expected = tc.expected_projections
            if not selected:
                total_efficiency += 1.0
                continue
            useful = len(selected & expected)
            total_efficiency += useful / len(selected)
        return total_efficiency / len(corpus)

    def _check_context_weight_accuracy(
        self,
        corpus: list[RetrievalTestCase],
        plans: list[RetrievalPlan],
    ) -> float:
        """How closely weights match the primary intent's base weights."""
        if not corpus:
            return 1.0
        total_similarity = 0.0
        from rationalevault.retrieval.models import INTENT_WEIGHT_MAP, RetrievalIntent
        for tc, plan in zip(corpus, plans):
            primary_intent = RetrievalIntent(tc.expected_intent)
            expected_weights = INTENT_WEIGHT_MAP.get(primary_intent, {})
            actual_weights = plan.context_weights
            # Compute cosine-like similarity
            all_keys = set(expected_weights.keys()) | set(actual_weights.keys())
            if not all_keys:
                total_similarity += 1.0
                continue
            dot = sum(expected_weights.get(k, 0) * actual_weights.get(k, 0) for k in all_keys)
            norm_e = sum(expected_weights.get(k, 0) ** 2 for k in all_keys) ** 0.5
            norm_a = sum(actual_weights.get(k, 0) ** 2 for k in all_keys) ** 0.5
            if norm_e > 0 and norm_a > 0:
                total_similarity += dot / (norm_e * norm_a)
            else:
                total_similarity += 0.0
        return total_similarity / len(corpus)

    def _check_determinism(
        self,
        corpus: list[RetrievalTestCase],
        plans: list[RetrievalPlan],
        previous_plans: list[RetrievalPlan] | None,
    ) -> float:
        """1.0 if re-running produces identical plans."""
        if previous_plans is None:
            return 1.0
        if len(plans) != len(previous_plans):
            return 0.0
        matches = 0
        for p1, p2 in zip(plans, previous_plans):
            if (p1.primary_intent == p2.primary_intent
                    and p1.projections == p2.projections
                    and p1.context_weights == p2.context_weights):
                matches += 1
        return matches / len(plans)

    def _check_availability_handling(self) -> float:
        """Verify plans degrade gracefully when projections unavailable."""
        test_cases = [
            {"continuation": False, "knowledge": True, "graph": True,
             "cross_project": True, "organization": True},
            {"continuation": True, "knowledge": False, "graph": False,
             "cross_project": True, "organization": True},
            {"continuation": False, "knowledge": False, "graph": False,
             "cross_project": False, "organization": False},
        ]
        passing = 0
        for avail in test_cases:
            plan = self.orchestrator.build_plan(
                "continue sprint 34 and show organizational flow",
                available_projections=avail,
            )
            # Unavailable projections should not be selected
            all_ok = True
            for proj, wanted in plan.requested_projections.items():
                if wanted and not avail.get(proj, False):
                    if plan.projections.get(proj, False) is True:
                        all_ok = False
                        break
            if all_ok:
                passing += 1
        return passing / len(test_cases)


def check_retrieval_gates(
    result: RetrievalEvalResult,
    thresholds: EvaluationThresholds | None = None,
) -> tuple[bool, list[str]]:
    """Check if retrieval evaluation passes exit gates."""
    if thresholds is None:
        thresholds = EvaluationThresholds()
    return result.passes_exit_gate()
