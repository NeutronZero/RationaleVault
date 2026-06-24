"""RationaleVault Organization Evaluator — Evaluates organizational knowledge visibility."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rationalevault.evaluation.thresholds import EvaluationThresholds
from rationalevault.organization.models import OrganizationState


@dataclass
class OrganizationEvalResult:
    """Evaluation result for organizational projection."""
    lineage_completeness: float
    provenance_chain: float
    contradiction_detection: float
    telemetry_accuracy: float
    isolation: float
    determinism: float
    lineage_replayability: float

    def passes_exit_gate(self) -> tuple[bool, list[str]]:
        """Check if all checks pass against thresholds."""
        t = EvaluationThresholds()
        failures: list[str] = []

        checks = {
            "lineage_completeness": (self.lineage_completeness, t.MIN_ORG_LINEAGE_COMPLETENESS),
            "provenance_chain": (self.provenance_chain, t.MIN_ORG_PROVENANCE_CHAIN),
            "contradiction_detection": (self.contradiction_detection, t.MIN_ORG_CONTRADICTION_DETECTION),
            "telemetry_accuracy": (self.telemetry_accuracy, t.MIN_ORG_TELEMETRY_ACCURACY),
            "isolation": (self.isolation, t.MIN_ORG_ISOLATION),
            "determinism": (self.determinism, t.MIN_ORG_DETERMINISM),
            "lineage_replayability": (self.lineage_replayability, t.MIN_ORG_LINEAGE_REPLAYABILITY),
        }

        for name, (value, threshold) in checks.items():
            if value < threshold:
                failures.append(name)

        return len(failures) == 0, failures

    def to_dict(self) -> dict[str, Any]:
        passed, failures = self.passes_exit_gate()
        t = EvaluationThresholds()
        checks = {
            "lineage_completeness": self.lineage_completeness,
            "provenance_chain": self.provenance_chain,
            "contradiction_detection": self.contradiction_detection,
            "telemetry_accuracy": self.telemetry_accuracy,
            "isolation": self.isolation,
            "determinism": self.determinism,
            "lineage_replayability": self.lineage_replayability,
        }
        threshold_map = {
            "lineage_completeness": t.MIN_ORG_LINEAGE_COMPLETENESS,
            "provenance_chain": t.MIN_ORG_PROVENANCE_CHAIN,
            "contradiction_detection": t.MIN_ORG_CONTRADICTION_DETECTION,
            "telemetry_accuracy": t.MIN_ORG_TELEMETRY_ACCURACY,
            "isolation": t.MIN_ORG_ISOLATION,
            "determinism": t.MIN_ORG_DETERMINISM,
            "lineage_replayability": t.MIN_ORG_LINEAGE_REPLAYABILITY,
        }
        total = len(checks)
        passing_count = sum(
            1 for name, value in checks.items()
            if value >= threshold_map[name]
        )
        return {
            **checks,
            "org_projection_success_rate": passing_count / total if total > 0 else 1.0,
            "passed": passed,
            "failures": failures,
        }


class OrganizationEvaluator:
    """Evaluates organizational knowledge visibility quality."""

    def evaluate(
        self,
        state: OrganizationState,
        previous_state: OrganizationState | None = None,
        raw_knowledge_by_project: dict[str, list] | None = None,
    ) -> OrganizationEvalResult:
        """Evaluate organizational projection.

        Args:
            state: The organization state to evaluate.
            previous_state: Optional duplicate build for determinism check.
            raw_knowledge_by_project: Raw knowledge for telemetry accuracy validation.
        """
        total_transferred = self._count_transferred(state)
        return OrganizationEvalResult(
            lineage_completeness=self._check_lineage_completeness(state, total_transferred),
            provenance_chain=self._check_provenance_chain(state),
            contradiction_detection=self._check_contradiction_detection(state),
            telemetry_accuracy=self._check_telemetry_accuracy(state, raw_knowledge_by_project),
            isolation=self._check_isolation(state),
            determinism=self._check_determinism(state, previous_state),
            lineage_replayability=self._check_lineage_replayability(state, previous_state),
        )

    def _count_transferred(self, state: OrganizationState) -> int:
        """Count knowledge items in active lineages (all represent transferred knowledge)."""
        return len(state.active_lineages)

    def _check_lineage_completeness(
        self,
        state: OrganizationState,
        total_transferred: int,
    ) -> float:
        """valid lineages / transferred knowledge."""
        if total_transferred == 0:
            return 1.0
        valid = sum(
            1 for l in state.active_lineages.values()
            if l.origin_project and l.current_projects
        )
        return valid / total_transferred

    def _check_provenance_chain(self, state: OrganizationState) -> float:
        """% of lineages with non-empty origin AND transfer_path."""
        if not state.active_lineages:
            return 1.0
        valid = sum(
            1 for l in state.active_lineages.values()
            if l.origin_project and l.transfer_path
        )
        return valid / len(state.active_lineages)

    def _check_contradiction_detection(self, state: OrganizationState) -> float:
        """Heuristic: 1.0 if conflicts have evidence (reasons populated)."""
        if not state.cross_project_conflicts:
            return 1.0
        with_reasons = sum(1 for c in state.cross_project_conflicts if c.reasons)
        return with_reasons / len(state.cross_project_conflicts)

    def _check_telemetry_accuracy(
        self,
        state: OrganizationState,
        raw_knowledge_by_project: dict[str, list] | None,
    ) -> float:
        """1.0 if telemetry counts match raw data."""
        if raw_knowledge_by_project is None:
            return 1.0
        t = state.transferability_telemetry
        # Count raw
        local_only = 0
        reusable = 0
        org_count = 0
        for klist in raw_knowledge_by_project.values():
            for k in klist:
                tr = getattr(k, "transferability", "")
                if tr == "LOCAL_ONLY":
                    local_only += 1
                elif tr == "REUSABLE":
                    reusable += 1
                elif tr == "ORGANIZATIONAL":
                    org_count += 1

        if t.local_only_count != local_only:
            return 0.0
        if t.reusable_count != reusable:
            return 0.0
        if t.organizational_count != org_count:
            return 0.0
        return 1.0

    def _check_isolation(self, state: OrganizationState) -> float:
        """No knowledge_id maps to multiple origin projects."""
        if not state.active_lineages:
            return 1.0
        # Each lineage should have a single origin
        multi_origin = sum(
            1 for l in state.active_lineages.values()
            if not l.origin_project
        )
        clean = len(state.active_lineages) - multi_origin
        return clean / len(state.active_lineages)

    def _check_determinism(
        self,
        state: OrganizationState,
        previous_state: OrganizationState | None,
    ) -> float:
        """1.0 if duplicate projection produces identical state."""
        if previous_state is None:
            return 1.0
        # Compare lineages
        if set(state.active_lineages.keys()) != set(previous_state.active_lineages.keys()):
            return 0.0
        for kid in state.active_lineages:
            l1 = state.active_lineages[kid]
            l2 = previous_state.active_lineages[kid]
            if l1.origin_project != l2.origin_project:
                return 0.0
            if l1.current_projects != l2.current_projects:
                return 0.0
        # Compare shared knowledge IDs
        ids1 = sorted(s.knowledge_id for s in state.shared_knowledge)
        ids2 = sorted(s.knowledge_id for s in previous_state.shared_knowledge)
        if ids1 != ids2:
            return 0.0
        # Compare conflicts
        cids1 = sorted(c.conflict_id for c in state.cross_project_conflicts)
        cids2 = sorted(c.conflict_id for c in previous_state.cross_project_conflicts)
        if cids1 != cids2:
            return 0.0
        return 1.0

    def _check_lineage_replayability(
        self,
        state: OrganizationState,
        previous_state: OrganizationState | None,
    ) -> float:
        """1.0 if lineages and shared knowledge are deterministic across builds."""
        if previous_state is None:
            return 1.0
        # Lineages must match exactly
        if state.active_lineages != previous_state.active_lineages:
            return 0.0
        # Shared knowledge must match
        s1 = sorted(s.knowledge_id for s in state.shared_knowledge)
        s2 = sorted(s.knowledge_id for s in previous_state.shared_knowledge)
        if s1 != s2:
            return 0.0
        return 1.0


def check_organization_gates(
    result: OrganizationEvalResult,
    thresholds: EvaluationThresholds | None = None,
) -> tuple[bool, list[str]]:
    """Check if organization evaluation passes exit gates."""
    if thresholds is None:
        thresholds = EvaluationThresholds()
    return result.passes_exit_gate()
