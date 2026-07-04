"""
RationaleVault Evaluation Framework — Execution Evaluator.

Consumes execution states, reports, and threshold profiles to deterministically
produce execution evaluations.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rationalevault.evaluation.thresholds import ExecutionThresholds
from rationalevault.skill_platform.execution_report import ExecutionReport
from rationalevault.skill_platform.execution_state import ExecutionState
from rationalevault.skill_platform.gate import ExecutionEvaluation, ExecutionScoreBreakdown


@dataclass(frozen=True)
class ExecutionEvaluationInput:
    """Input parameters for execution evaluation."""
    state: ExecutionState
    report: ExecutionReport
    thresholds: ExecutionThresholds

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.to_dict(),
            "report": self.report.to_dict(),
            "thresholds": {
                "profile_name": self.thresholds.profile_name,
                "min_success_rate": self.thresholds.min_success_rate,
                "max_timeout_rate": self.thresholds.max_timeout_rate,
                "max_denial_rate": self.thresholds.max_denial_rate,
                "min_overall_score": self.thresholds.min_overall_score,
            },
        }


class ExecutionEvaluator:
    """Evaluates execution states/reports against named threshold profiles."""

    def evaluate(self, inputs: ExecutionEvaluationInput) -> ExecutionEvaluation:
        state = inputs.state
        report = inputs.report
        thresholds = inputs.thresholds

        total = state.total_executions
        if total > 0:
            success_rate = state.total_completed / total
            timeout_rate = state.total_timeout / total
            denial_rate = state.total_denied / total
            failed_rate = state.total_failed / total
        else:
            success_rate = 1.0
            timeout_rate = 0.0
            denial_rate = 0.0
            failed_rate = 0.0

        # Compute factor breakdown
        success_component = success_rate
        timeout_penalty = timeout_rate * 0.5
        denial_penalty = denial_rate * 0.2
        validation_penalty = failed_rate * 0.3
        policy_bonus = 0.05 if success_rate >= 0.99 else 0.0

        score = max(
            0.0,
            min(
                1.0,
                success_component
                - timeout_penalty
                - denial_penalty
                - validation_penalty
                + policy_bonus,
            ),
        )

        breakdown = ExecutionScoreBreakdown(
            success_component=success_component,
            timeout_penalty=timeout_penalty,
            denial_penalty=denial_penalty,
            validation_penalty=validation_penalty,
            policy_bonus=policy_bonus,
        )

        findings: list[str] = []
        warnings: list[str] = []
        recommended_actions: list[str] = []

        # Gather findings
        findings.append(f"Total executions: {total}")
        findings.append(f"Successful: {state.total_completed}")
        findings.append(f"Failed: {state.total_failed}")

        # Assess thresholds
        if success_rate < thresholds.min_success_rate:
            findings.append(
                f"Success rate {success_rate:.2%} below target {thresholds.min_success_rate:.2%}"
            )
            recommended_actions.append("manual review")
            recommended_actions.append("retry")
        else:
            findings.append(
                f"Success rate {success_rate:.2%} meets target {thresholds.min_success_rate:.2%}"
            )
            recommended_actions.append("promote artifact")

        if timeout_rate > thresholds.max_timeout_rate:
            warnings.append(
                f"Timeout rate {timeout_rate:.2%} exceeds target {thresholds.max_timeout_rate:.2%}"
            )
        if denial_rate > thresholds.max_denial_rate:
            warnings.append(
                f"Denial rate {denial_rate:.2%} exceeds target {thresholds.max_denial_rate:.2%}"
            )

        passed = (
            success_rate >= thresholds.min_success_rate
            and timeout_rate <= thresholds.max_timeout_rate
            and denial_rate <= thresholds.max_denial_rate
            and score >= thresholds.min_overall_score
        )

        return ExecutionEvaluation(
            version="1.0",
            success_rate=success_rate,
            timeout_rate=timeout_rate,
            denial_rate=denial_rate,
            passed=passed,
            score=score,
            breakdown=breakdown,
            findings=findings,
            warnings=warnings,
            recommended_actions=recommended_actions,
        )
