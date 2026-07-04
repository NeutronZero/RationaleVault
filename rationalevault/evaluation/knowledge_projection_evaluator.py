"""RationaleVault Knowledge Projection Evaluator — Evaluates KnowledgeState quality.

Checks:
  - Active knowledge traceable (all active items have provenance)
  - Contradictions detected (conflict queue populated when contradictions exist)
  - Invariants preserved (all PROJECT_INVARIANT items identified)
  - Supersession chains complete (SUPERSEDED items have superseded_by)
  - Epistemic status correct (derivation rules applied properly)
  - Lifecycle filtering works (stale/superseded excluded from active)
  - Health computed (all metrics populated)
"""
from __future__ import annotations

from dataclasses import dataclass

from rationalevault.knowledge.models import KnowledgeLifecycle, KnowledgeType
from rationalevault.projections.knowledge import KnowledgeState


@dataclass
class KnowledgeProjectionEvalResult:
    """Evaluation result for KnowledgeProjection quality."""
    active_knowledge_traceable: bool
    contradictions_detected: bool
    invariants_preserved: bool
    supersession_chains_complete: bool
    epistemic_status_correct: bool
    lifecycle_filtering_works: bool
    health_computed: bool

    @property
    def knowledge_projection_success_rate(self) -> float:
        """Fraction of checks that passed. Sprint I8 gate: >= 0.95."""
        checks = [
            self.active_knowledge_traceable,
            self.contradictions_detected,
            self.invariants_preserved,
            self.supersession_chains_complete,
            self.epistemic_status_correct,
            self.lifecycle_filtering_works,
            self.health_computed,
        ]
        return sum(checks) / len(checks)

    def passes_exit_gate(self) -> tuple[bool, list[str]]:
        """Sprint I8 exit gate: knowledge_projection_success_rate >= 0.95."""
        failures = []
        if self.knowledge_projection_success_rate < 0.95:
            failures.append(
                f"knowledge_projection_success_rate="
                f"{self.knowledge_projection_success_rate:.2%} < 95%"
            )
        return len(failures) == 0, failures


class KnowledgeProjectionEvaluator:
    """Evaluates KnowledgeState quality against Sprint I8 criteria."""

    def evaluate(self, state: KnowledgeState) -> KnowledgeProjectionEvalResult:
        """Run all evaluation checks against a KnowledgeState."""
        return KnowledgeProjectionEvalResult(
            active_knowledge_traceable=self._check_traceability(state),
            contradictions_detected=self._check_contradictions(state),
            invariants_preserved=self._check_invariants(state),
            supersession_chains_complete=self._check_supersession(state),
            epistemic_status_correct=self._check_epistemic(state),
            lifecycle_filtering_works=self._check_lifecycle_filtering(state),
            health_computed=self._check_health(state),
        )

    def _check_traceability(self, state: KnowledgeState) -> bool:
        """All active knowledge must have non-empty provenance."""
        if not state.active_knowledge:
            return True
        return all(
            k.provenance and k.provenance.source_event_ids
            for k in state.active_knowledge
        )

    def _check_contradictions(self, state: KnowledgeState) -> bool:
        """If conflicted knowledge exists, conflict queue must be populated."""
        if state.conflicted and not state.conflict_queue:
            return False
        return True

    def _check_invariants(self, state: KnowledgeState) -> bool:
        """All PROJECT_INVARIANT knowledge must be in invariants list."""

        for k in state.active_knowledge:
            if k.knowledge_type == KnowledgeType.PROJECT_INVARIANT:
                if k.id not in [inv.id for inv in state.invariants]:
                    return False
        return True

    def _check_supersession(self, state: KnowledgeState) -> bool:
        """All SUPERSEDED knowledge should have superseded_by pointer."""
        for k in state.stale_knowledge:
            if k.lifecycle_status == KnowledgeLifecycle.SUPERSEDED.value:
                if not k.superseded_by:
                    return False
        return True

    def _check_epistemic(self, state: KnowledgeState) -> bool:
        """Verify epistemic classification consistency."""
        # All items should be in exactly one epistemic bucket
        all_classified = (
            len(state.proposed)
            + len(state.validated)
            + len(state.invariants)
            + len(state.conflicted)
            + len(state.tombstoned)
        )
        total = len(state.active_knowledge) + len(state.stale_knowledge) + len(state.superseded_knowledge)
        return all_classified == total

    def _check_lifecycle_filtering(self, state: KnowledgeState) -> bool:
        """Active knowledge should only contain ACTIVE lifecycle items."""
        return all(
            k.lifecycle_status == KnowledgeLifecycle.ACTIVE.value
            for k in state.active_knowledge
        )

    def _check_health(self, state: KnowledgeState) -> bool:
        """Health must be computed with valid ranges."""
        if state.health is None:
            return False
        h = state.health
        return (
            0.0 <= h.confidence <= 1.0
            and 0.0 <= h.contradiction_rate <= 1.0
            and 0.0 <= h.invariant_ratio <= 1.0
            and 0.0 <= h.stale_ratio <= 1.0
            and h.active_count >= 0
            and h.total_count >= 0
        )
