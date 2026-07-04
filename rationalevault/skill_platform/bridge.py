"""
RationaleVault Skill Platform — Decision→Skill Bridge.

The bridge maps DecisionItem entries from DecisionSet to skill
invocations via SkillCandidate and ExecutionPlan objects. It is a pure
mapping function — no reasoning, no re-scoring.

Design rules:
  - SkillCandidate is an immutable intermediate between DecisionItem
    and SkillManifest, carrying match metadata.
  - ExecutionPlan carries candidate + context + execution constraints.
  - Category matching is exact: item.category ∈ skill.accepted_categories.
  - Specificity: fewer accepted_categories = more specific = preferred.
  - No matching skill → blocked with reason "no_matching_skill".
  - The bridge never mutates DecisionItem or SkillManifest.
  - The bridge's responsibility is planning execution, not merely
    selecting skills.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rationalevault.cognitive_head.decision import DecisionItem, DecisionSet
from rationalevault.skill_platform.manifest import SkillManifest, SkillManifestRegistry


@dataclass(frozen=True)
class SkillCandidate:
    """
    Immutable intermediate between DecisionItem and SkillManifest.

    Carries match metadata that will be useful for C2/C3:
    match_score, blocked_reason, policy_override, estimated_cost,
    estimated_duration, requires_confirmation.
    """
    decision: DecisionItem
    manifest: SkillManifest
    match_score: float                    # 1.0 for exact match; lower for partial
    blocked: bool                         # True if skill cannot execute
    blocked_reason: str                   # empty if not blocked
    specificity: int                      # number of accepted_categories (lower = more specific)

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision.decision_id,
            "skill_id": self.manifest.skill_id,
            "skill_name": self.manifest.name,
            "category": self.decision.category.value,
            "match_score": round(self.match_score, 4),
            "blocked": self.blocked,
            "blocked_reason": self.blocked_reason,
            "specificity": self.specificity,
        }


class DecisionSkillBridge:
    """
    Maps DecisionItem entries to SkillCandidates via category matching.

    The bridge is a pure function: DecisionSet + Registry → list[SkillCandidate].
    It never mutates the DecisionSet or the Registry.
    """

    @staticmethod
    def _select_best(
        decision: DecisionItem,
        candidates: list[SkillManifest],
    ) -> SkillManifest | None:
        """
        Select the most specific skill for a decision.

        Specificity = number of accepted_categories (fewer = more specific).
        Ties are broken by skill_id (deterministic).
        """
        if not candidates:
            return None
        return min(
            candidates,
            key=lambda m: (len(m.accepted_categories), m.skill_id),
        )

    @staticmethod
    def map_decision(
        decision: DecisionItem,
        registry: SkillManifestRegistry,
    ) -> SkillCandidate:
        """
        Map a single DecisionItem to a SkillCandidate.

        Returns a SkillCandidate that is either matched or blocked.
        """
        matching = registry.find_by_category(decision.category.value)

        if not matching:
            return SkillCandidate(
                decision=decision,
                manifest=SkillManifest(
                    skill_id="",
                    name="",
                    version="",
                    description="No matching skill",
                    input_schema={},
                    output_schema={},
                    required_permissions=[],
                    accepted_categories=[],
                    timeout_seconds=0,
                    idempotent=False,
                ),
                match_score=0.0,
                blocked=True,
                blocked_reason="no_matching_skill",
                specificity=0,
            )

        best = DecisionSkillBridge._select_best(decision, matching)
        assert best is not None  # guaranteed by non-empty matching

        return SkillCandidate(
            decision=decision,
            manifest=best,
            match_score=1.0,
            blocked=False,
            blocked_reason="",
            specificity=len(best.accepted_categories),
        )

    @staticmethod
    def map_decision_set(
        decision_set: DecisionSet,
        registry: SkillManifestRegistry,
    ) -> list[SkillCandidate]:
        """
        Map all decisions in a DecisionSet to SkillCandidates.

        Returns one SkillCandidate per DecisionItem, preserving
        the original decision order.
        """
        return [
            DecisionSkillBridge.map_decision(d, registry)
            for d in decision_set.decisions
        ]

    @staticmethod
    def create_execution_plans(
        decision_set: DecisionSet,
        registry: SkillManifestRegistry,
    ) -> list["ExecutionPlan"]:
        """
        Create ExecutionPlans for all decisions in a DecisionSet.

        This is the bridge's primary output — planning execution,
        not merely selecting skills. Each plan carries the candidate,
        context, and execution constraints.
        """
        from rationalevault.skill_platform.context import ExecutionContext
        from rationalevault.skill_platform.execution_plan import ExecutionPlan
        from rationalevault.skill_platform.permissions import CapabilityModel
        from rationalevault.skill_platform.provenance import Provenance

        candidates = DecisionSkillBridge.map_decision_set(decision_set, registry)
        plans: list[ExecutionPlan] = []

        for candidate in candidates:
            if candidate.blocked:
                # Blocked candidates still get a plan (for audit trail)
                # but with a minimal context
                continue

            provenance = Provenance(
                execution_id="",
                decision_id=candidate.decision.decision_id,
                synthesis_id=candidate.decision.synthesis_id,
                belief_id=candidate.decision.belief_id,
                source_event_ids=[],
                skill_version=candidate.manifest.version,
                gate_policy_version=candidate.decision.gate_policy_version,
                input_snapshot_hash="",
                timestamp="",
            )

            capabilities = CapabilityModel(
                list(set(["projection:memory", "ledger:read"]))
            )

            context = ExecutionContext(
                decision_id=candidate.decision.decision_id,
                synthesis_id=candidate.decision.synthesis_id,
                belief_id=candidate.decision.belief_id,
                source_event_ids=[],
                manifest=candidate.manifest,
                candidate=candidate,
                input_snapshot={},
                provenance=provenance,
                capabilities=capabilities,
                gate_policy_version=candidate.decision.gate_policy_version,
            )

            plan = ExecutionPlan(
                candidate=candidate,
                context=context,
                timeout_seconds=candidate.manifest.timeout_seconds,
            )
            plans.append(plan)

        return plans
