"""RationaleVault Cross-Project Evaluator — Evaluates cross-project knowledge transfer quality."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rationalevault.evaluation.thresholds import EvaluationThresholds
from rationalevault.projections.cross_project import CrossProjectState


@dataclass
class CrossProjectEvalResult:
    """Evaluation result for cross-project projection."""
    transfer_coverage: float
    provenance_integrity: float
    relevance_precision: float
    isolation_score: float
    determinism: float
    transferability_enforcement: float

    def passes_exit_gate(self) -> tuple[bool, list[str]]:
        """Check if all checks pass against thresholds."""
        t = EvaluationThresholds()
        failures: list[str] = []

        checks = {
            "transfer_coverage": (self.transfer_coverage, t.MIN_CROSS_PROJECT_TRANSFER_COVERAGE),
            "provenance_integrity": (self.provenance_integrity, t.MIN_CROSS_PROJECT_PROVENANCE_INTEGRITY),
            "relevance_precision": (self.relevance_precision, t.MIN_CROSS_PROJECT_RELEVANCE_PRECISION),
            "isolation_score": (self.isolation_score, t.MIN_CROSS_PROJECT_ISOLATION),
            "determinism": (self.determinism, t.MIN_CROSS_PROJECT_DETERMINISM),
            "transferability_enforcement": (self.transferability_enforcement, t.MIN_CROSS_PROJECT_TRANSFERABILITY_ENFORCEMENT),
        }

        for name, (value, threshold) in checks.items():
            if value < threshold:
                failures.append(name)

        return len(failures) == 0, failures

    def to_dict(self) -> dict[str, Any]:
        passed, failures = self.passes_exit_gate()
        t = EvaluationThresholds()
        checks = {
            "transfer_coverage": self.transfer_coverage,
            "provenance_integrity": self.provenance_integrity,
            "relevance_precision": self.relevance_precision,
            "isolation_score": self.isolation_score,
            "determinism": self.determinism,
            "transferability_enforcement": self.transferability_enforcement,
        }
        total = len(checks)
        threshold_map = {
            "transfer_coverage": t.MIN_CROSS_PROJECT_TRANSFER_COVERAGE,
            "provenance_integrity": t.MIN_CROSS_PROJECT_PROVENANCE_INTEGRITY,
            "relevance_precision": t.MIN_CROSS_PROJECT_RELEVANCE_PRECISION,
            "isolation_score": t.MIN_CROSS_PROJECT_ISOLATION,
            "determinism": t.MIN_CROSS_PROJECT_DETERMINISM,
            "transferability_enforcement": t.MIN_CROSS_PROJECT_TRANSFERABILITY_ENFORCEMENT,
        }
        passing_count = sum(
            1 for name, value in checks.items()
            if value >= threshold_map[name]
        )
        return {
            **checks,
            "cross_project_success_rate": passing_count / total if total > 0 else 1.0,
            "passed": passed,
            "failures": failures,
        }


class CrossProjectEvaluator:
    """Evaluates cross-project knowledge transfer quality."""

    def evaluate(
        self,
        state: CrossProjectState,
        previous_state: CrossProjectState | None = None,
        total_knowledge_in_targets: int = 0,
    ) -> CrossProjectEvalResult:
        """Evaluate cross-project projection.

        Args:
            state: The cross-project state to evaluate.
            previous_state: Optional duplicate build for determinism check.
            total_knowledge_in_targets: Total knowledge objects across all target projects.
        """
        return CrossProjectEvalResult(
            transfer_coverage=self._check_transfer_coverage(state, total_knowledge_in_targets),
            provenance_integrity=self._check_provenance_integrity(state),
            relevance_precision=self._check_relevance_precision(state),
            isolation_score=self._check_isolation(state),
            determinism=self._check_determinism(state, previous_state),
            transferability_enforcement=self._check_transferability_enforcement(state),
        )

    def _check_transfer_coverage(
        self,
        state: CrossProjectState,
        total_knowledge_in_targets: int,
    ) -> float:
        """% of target knowledge that was transferable and discovered."""
        if total_knowledge_in_targets == 0:
            return 1.0
        if state.health is None:
            return 0.0
        return state.health.total_transferable / total_knowledge_in_targets

    def _check_provenance_integrity(self, state: CrossProjectState) -> float:
        """% of transferred items with valid provenance mapping."""
        if not state.transferable_knowledge:
            return 1.0
        valid = sum(
            1 for k in state.transferable_knowledge
            if k.knowledge_id in state.provenance_map
            and state.provenance_map[k.knowledge_id] in state.knowledge_by_project
        )
        return valid / len(state.transferable_knowledge)

    def _check_relevance_precision(self, state: CrossProjectState) -> float:
        """Average relevance score across transferred items."""
        if not state.transferable_knowledge:
            return 1.0
        total = sum(k.relevance_score for k in state.transferable_knowledge)
        return total / len(state.transferable_knowledge)

    def _check_isolation(self, state: CrossProjectState) -> float:
        """No cross-contamination: each item maps to exactly one source project."""
        if not state.transferable_knowledge:
            return 1.0
        # Each knowledge_id should map to exactly one project
        multi_source = 0
        for k in state.transferable_knowledge:
            sources = [
                proj_id for proj_id, kids in state.knowledge_by_project.items()
                if k.knowledge_id in kids
            ]
            if len(sources) != 1:
                multi_source += 1
        clean = len(state.transferable_knowledge) - multi_source
        return clean / len(state.transferable_knowledge)

    def _check_determinism(
        self,
        state: CrossProjectState,
        previous_state: CrossProjectState | None,
    ) -> float:
        """1.0 if duplicate projection produces identical transfer set."""
        if previous_state is None:
            return 1.0
        # Compare knowledge IDs transferred
        ids1 = sorted(k.knowledge_id for k in state.transferable_knowledge)
        ids2 = sorted(k.knowledge_id for k in previous_state.transferable_knowledge)
        if ids1 != ids2:
            return 0.0
        # Compare provenance maps
        if state.provenance_map != previous_state.provenance_map:
            return 0.0
        # Compare knowledge_by_project
        if state.knowledge_by_project != previous_state.knowledge_by_project:
            return 0.0
        return 1.0

    def _check_transferability_enforcement(self, state: CrossProjectState) -> float:
        """1.0 if no LOCAL_ONLY items were transferred."""
        if not state.transferable_knowledge:
            return 1.0
        local_only_leaked = sum(
            1 for k in state.transferable_knowledge
            if k.transferability == "LOCAL_ONLY"
        )
        return 1.0 if local_only_leaked == 0 else 0.0


def check_cross_project_gates(
    result: CrossProjectEvalResult,
    thresholds: EvaluationThresholds | None = None,
) -> tuple[bool, list[str]]:
    """Check if cross-project evaluation passes exit gates."""
    if thresholds is None:
        thresholds = EvaluationThresholds()
    return result.passes_exit_gate()
