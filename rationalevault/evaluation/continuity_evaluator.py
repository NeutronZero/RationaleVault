"""RationaleVault Continuity Evaluator — Context deliverability validation.

Measures whether a ContextPackage + CompilerOutput preserves the
information Agent B needs to continue Agent A's work.

Metrics:
  - goal_recall: % of expected goals found in output
  - decision_recall: % of expected decisions found in output
  - rationale_recall: % of expected rationales found in output
  - task_recall: % of expected tasks found in output
  - knowledge_recall: % of expected knowledge found in output
  - question_recall: % of expected questions found in output
  - overall_continuity: weighted average of all recalls
  - context_gain: improvement of ContextPackage over CognitiveHead

Gate thresholds (from thresholds.py):
  MIN_CONTINUITY_GOAL_RECALL = 1.00
  MIN_CONTINUITY_DECISION_RECALL = 1.00
  MIN_CONTINUITY_RATIONALE_RECALL = 0.95
  MIN_CONTINUITY_TASK_RECALL = 0.95
  MIN_CONTINUITY_KNOWLEDGE_RECALL = 0.80
  MIN_CONTINUITY_OVERALL = 0.90
  MIN_CONTEXT_GAIN = 0.10
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rationalevault.evaluation.continuity_benchmark_schema import (
        ContinuityBenchmark,
        ExpectedArtifact,
    )
    from rationalevault.compilers.compiler_output import CompilerOutput


# ── Gate Thresholds ────────────────────────────────────────────────────────

MIN_CONTINUITY_GOAL_RECALL = 1.00
MIN_CONTINUITY_DECISION_RECALL = 1.00
MIN_CONTINUITY_RATIONALE_RECALL = 0.95
MIN_CONTINUITY_TASK_RECALL = 0.95
MIN_CONTINUITY_KNOWLEDGE_RECALL = 0.80
MIN_CONTINUITY_QUESTION_RECALL = 1.00
MIN_CONTINUITY_OVERALL = 0.90
MIN_CONTEXT_GAIN = 0.10


# ── Evaluation Result ──────────────────────────────────────────────────────


@dataclass
class ContinuityResult:
    """Result of a context deliverability evaluation."""
    benchmark_id: str
    agent: str

    # Per-category recall
    goal_recall: float
    goal_expected: int
    goal_recovered: int

    decision_recall: float
    decision_expected: int
    decision_recovered: int

    rationale_recall: float
    rationale_expected: int
    rationale_recovered: int

    task_recall: float
    task_expected: int
    task_recovered: int

    knowledge_recall: float
    knowledge_expected: int
    knowledge_recovered: int

    question_recall: float
    question_expected: int
    question_recovered: int

    # Aggregate
    overall_continuity: float
    context_gain: float  # improvement over head-only baseline

    # Recovered artifact details
    recovered_artifacts: list[dict[str, str]] = field(default_factory=list)
    missed_artifacts: list[dict[str, str]] = field(default_factory=list)

    # Gate status
    passed: bool = False
    gate_failures: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, any]:
        return {
            "benchmark_id": self.benchmark_id,
            "agent": self.agent,
            "goal_recall": self.goal_recall,
            "goal_expected": self.goal_expected,
            "goal_recovered": self.goal_recovered,
            "decision_recall": self.decision_recall,
            "decision_expected": self.decision_expected,
            "decision_recovered": self.decision_recovered,
            "rationale_recall": self.rationale_recall,
            "rationale_expected": self.rationale_expected,
            "rationale_recovered": self.rationale_recovered,
            "task_recall": self.task_recall,
            "task_expected": self.task_expected,
            "task_recovered": self.task_recovered,
            "knowledge_recall": self.knowledge_recall,
            "knowledge_expected": self.knowledge_expected,
            "knowledge_recovered": self.knowledge_recovered,
            "question_recall": self.question_recall,
            "question_expected": self.question_expected,
            "question_recovered": self.question_recovered,
            "overall_continuity": self.overall_continuity,
            "context_gain": self.context_gain,
            "recovered_artifacts": self.recovered_artifacts,
            "missed_artifacts": self.missed_artifacts,
            "passed": self.passed,
            "gate_failures": self.gate_failures,
        }


# ── Evaluator ──────────────────────────────────────────────────────────────


def _compute_recall(
    expected: list[ExpectedArtifact],
    text: str,
) -> tuple[float, int, int]:
    """Compute recall for a list of expected artifacts against text.

    Returns (recall, expected_count, recovered_count).
    """
    if not expected:
        return 1.0, 0, 0

    recovered = sum(1 for a in expected if a.matches(text))
    return recovered / len(expected), len(expected), recovered


def _collect_recovered(
    expected: list[ExpectedArtifact],
    text: str,
    category: str,
) -> list[dict[str, str]]:
    """Collect details of recovered artifacts."""
    results = []
    for a in expected:
        if a.matches(text):
            results.append({
                "category": category,
                "canonical_value": a.canonical_value,
                "status": "recovered",
            })
    return results


def _collect_missed(
    expected: list[ExpectedArtifact],
    text: str,
    category: str,
) -> list[dict[str, str]]:
    """Collect details of missed artifacts."""
    results = []
    for a in expected:
        if not a.matches(text):
            results.append({
                "category": category,
                "canonical_value": a.canonical_value,
                "status": "missed",
            })
    return results


class ContinuityEvaluator:
    """Evaluates context deliverability for multi-agent handoff.

    Measures whether a CompilerOutput preserves the information
    Agent B needs to continue Agent A's work.
    """

    def __init__(self, benchmark: ContinuityBenchmark) -> None:
        self.benchmark = benchmark

    def evaluate(self, compiler_output: CompilerOutput) -> ContinuityResult:
        """Evaluate a CompilerOutput against the benchmark.

        Args:
            compiler_output: The rendered output from a ContextPackageCompiler.

        Returns:
            ContinuityResult with all metrics and gate status.
        """
        text = compiler_output.rendered_content
        b = self.benchmark

        # Compute per-category recall
        goal_recall, goal_exp, goal_rec = _compute_recall(b.expected_goals, text)
        decision_recall, dec_exp, dec_rec = _compute_recall(b.expected_decisions, text)
        rationale_recall, rat_exp, rat_rec = _compute_recall(b.expected_rationales, text)
        task_recall, task_exp, task_rec = _compute_recall(b.expected_tasks, text)
        knowledge_recall, kn_exp, kn_rec = _compute_recall(b.expected_knowledge, text)
        question_recall, q_exp, q_rec = _compute_recall(b.expected_questions, text)

        # Overall continuity (weighted average)
        total_expected = goal_exp + dec_exp + rat_exp + task_exp + kn_exp + q_exp
        total_recovered = goal_rec + dec_rec + rat_rec + task_rec + kn_rec + q_rec
        overall = total_recovered / total_expected if total_expected > 0 else 1.0

        # Context gain (placeholder — computed externally when head baseline available)
        context_gain = 0.0

        # Collect artifact details
        recovered = []
        missed = []
        for category, artifacts in [
            ("goal", b.expected_goals),
            ("decision", b.expected_decisions),
            ("rationale", b.expected_rationales),
            ("task", b.expected_tasks),
            ("knowledge", b.expected_knowledge),
            ("question", b.expected_questions),
        ]:
            recovered.extend(_collect_recovered(artifacts, text, category))
            missed.extend(_collect_missed(artifacts, text, category))

        # Gates
        failures = []
        if goal_recall < b.min_goal_recall:
            failures.append("goal_recall")
        if decision_recall < b.min_decision_recall:
            failures.append("decision_recall")
        if rationale_recall < b.min_rationale_recall:
            failures.append("rationale_recall")
        if task_recall < b.min_task_recall:
            failures.append("task_recall")
        if knowledge_recall < b.min_knowledge_recall:
            failures.append("knowledge_recall")
        if question_recall < MIN_CONTINUITY_QUESTION_RECALL:
            failures.append("question_recall")
        if overall < b.min_overall_continuity:
            failures.append("overall_continuity")

        return ContinuityResult(
            benchmark_id=b.benchmark_id,
            agent=compiler_output.agent,
            goal_recall=goal_recall,
            goal_expected=goal_exp,
            goal_recovered=goal_rec,
            decision_recall=decision_recall,
            decision_expected=dec_exp,
            decision_recovered=dec_rec,
            rationale_recall=rationale_recall,
            rationale_expected=rat_exp,
            rationale_recovered=rat_rec,
            task_recall=task_recall,
            task_expected=task_exp,
            task_recovered=task_rec,
            knowledge_recall=knowledge_recall,
            knowledge_expected=kn_exp,
            knowledge_recovered=kn_rec,
            question_recall=question_recall,
            question_expected=q_exp,
            question_recovered=q_rec,
            overall_continuity=overall,
            context_gain=context_gain,
            recovered_artifacts=recovered,
            missed_artifacts=missed,
            passed=len(failures) == 0,
            gate_failures=failures,
        )

    def evaluate_with_head_baseline(
        self,
        compiler_output: CompilerOutput,
        head_text: str,
    ) -> ContinuityResult:
        """Evaluate with CognitiveHead baseline for context gain computation.

        Args:
            compiler_output: The rendered output from a ContextPackageCompiler.
            head_text: The CognitiveHead rendered as text (for baseline comparison).

        Returns:
            ContinuityResult with context_gain computed.
        """
        result = self.evaluate(compiler_output)

        # Compute head-only baseline recall
        b = self.benchmark
        head_total = 0
        head_recovered = 0
        for artifacts in [b.expected_goals, b.expected_decisions, b.expected_rationales,
                          b.expected_tasks, b.expected_knowledge, b.expected_questions]:
            exp, rec = len(artifacts), sum(1 for a in artifacts if a.matches(head_text))
            head_total += exp
            head_recovered += rec

        head_recall = head_recovered / head_total if head_total > 0 else 1.0
        result.context_gain = result.overall_continuity - head_recall

        # Check context gain gate
        if result.context_gain < b.min_context_gain and head_total > 0:
            result.gate_failures.append("context_gain")
            result.passed = False

        return result


def check_continuity_gates(result: ContinuityResult) -> tuple[bool, list[str]]:
    """Check if a ContinuityResult passes all gates.

    Returns:
        (passed, list_of_failed_gate_names)
    """
    return result.passed, list(result.gate_failures)
