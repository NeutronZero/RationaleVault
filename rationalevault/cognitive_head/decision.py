"""
RationaleVault Cognitive Head — Decision Gate.

Phase 3: Applies a DecisionGatePolicy to a SynthesisReport to produce a
DecisionSet.

Design rules:
  - The gate NEVER re-scores. It only evaluates policy (allow / block).
  - Confidence, priority, and category are frozen after synthesis.
  - DEC-[hash] is derived from (policy.version + synthesis_id) so that
    changing the gate policy version produces new IDs for identical synthesis
    artifacts — different policies → different decision identities.
  - DecisionSet is a *diagnostic* artifact. It states which items satisfy
    the current policy. It does NOT instruct execution. Execution belongs to
    the layer above (Skills / Epic C).
  - All gate decisions are derived exclusively from DecisionGatePolicy.
    No hidden constants exist inside DecisionGate.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from rationalevault.cognitive_head.synthesis import (
    SynthesisCategory,
    SynthesisItem,
    SynthesisPriority,
    SynthesisReport,
)


# ── Configuration ──────────────────────────────────────────────────────────────

@dataclass
class DecisionGatePolicy:
    """
    All gate decisions are derived exclusively from this policy.

    version  — changing this produces new DEC-[hash] IDs for identical
               synthesis artifacts, making policy changes fully traceable.
    """
    version: str = "1.0"
    minimum_confidence: float = 0.60      # items below this floor are blocked
    block_if_contradicted: bool = True    # items with active contradictions are blocked
    max_decisions: int = 0                # 0 = unlimited; applies after ordering


# ── Data structures ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class DecisionItem:
    """
    A synthesis item that passed the gate.

    decision_id is derived from (policy.version, synthesis_id) so that
    identical synthesis artifacts evaluated under different policy versions
    produce different, distinguishable decision IDs.

    Confidence, priority, and category are copied verbatim from the
    SynthesisItem — the gate does NOT re-score any field.
    """
    decision_id: str              # DEC-[hash] from (policy.version, synthesis_id)
    synthesis_id: str
    belief_id: str
    category: SynthesisCategory
    priority: SynthesisPriority
    confidence: float             # frozen from SynthesisItem — NOT re-scored
    impact: float                 # frozen from SynthesisItem — NOT re-scored
    contradiction_ids: list[str]
    belief_title: str
    belief_content: str
    gate_policy_version: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "synthesis_id": self.synthesis_id,
            "belief_id": self.belief_id,
            "category": self.category.value,
            "priority": self.priority.value,
            "confidence": round(self.confidence, 4),
            "impact": round(self.impact, 4),
            "contradiction_ids": self.contradiction_ids,
            "belief_title": self.belief_title,
            "belief_content": self.belief_content,
            "gate_policy_version": self.gate_policy_version,
        }


@dataclass(frozen=True)
class DecisionSet:
    """
    Immutable diagnostic artifact produced by the Decision Gate.

    decisions — items that passed the gate, ordered CRITICAL → LOW then
                confidence descending within each band.
    blocked   — items that did not pass (DEFER category, below confidence
                floor, contradicted per policy, or over max_decisions cap).
    gate_policy — full snapshot of the applied policy, for auditability.

    This is a *diagnostic* artifact. It states "these items satisfy the
    current policy." Execution belongs to the layer above (Skills / Epic C).
    """
    decisions: list[DecisionItem]   # approved, ordered
    blocked: list[SynthesisItem]    # rejected by any gate rule
    gate_policy: dict[str, Any]     # immutable snapshot of the applied policy
    summary: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "decisions": [d.to_dict() for d in self.decisions],
            "blocked": [b.to_dict() for b in self.blocked],
            "gate_policy": self.gate_policy,
            "summary": self.summary,
        }


# ── Phase 3: Decision Gate ─────────────────────────────────────────────────────

class DecisionGate:
    """
    Phase 3: Applies DecisionGatePolicy to a SynthesisReport.

    Responsibilities:
      - Evaluate policy (allow or block). Nothing more.
      - Never mutate confidence, priority, or category from synthesis.
      - Derive DEC-[hash] IDs from (policy.version, synthesis_id).
    """

    @staticmethod
    def _generate_decision_id(policy_version: str, synthesis_id: str) -> str:
        data = f"decision:{policy_version}:{synthesis_id}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"DEC-{h}"

    @staticmethod
    def _passes_gate(item: SynthesisItem, policy: DecisionGatePolicy) -> bool:
        """
        Policy evaluation — the sole gate decision point.

        Rules (all derived from policy, no hidden constants):
          1. DEFER category is always blocked.
          2. Confidence must meet the minimum floor.
          3. If block_if_contradicted, items with active contradictions are blocked.
        """
        if item.category == SynthesisCategory.DEFER:
            return False
        if item.confidence < policy.minimum_confidence:
            return False
        if policy.block_if_contradicted and item.contradiction_ids:
            return False
        return True

    @staticmethod
    def gate(
        synthesis: SynthesisReport,
        policy: DecisionGatePolicy = DecisionGatePolicy(),
    ) -> DecisionSet:
        """
        Apply the gate policy to a SynthesisReport.

        Items are processed in synthesis order (already sorted by priority
        then confidence).  The max_decisions cap is applied last so that
        the highest-priority items are always preferred.
        """
        # Collect pass/block decisions, preserving synthesis order
        passed_pairs: list[tuple[SynthesisItem, DecisionItem]] = []
        blocked: list[SynthesisItem] = []

        for item in synthesis.items:
            if DecisionGate._passes_gate(item, policy):
                decision_id = DecisionGate._generate_decision_id(
                    policy.version, item.synthesis_id
                )
                decision = DecisionItem(
                    decision_id=decision_id,
                    synthesis_id=item.synthesis_id,
                    belief_id=item.belief_id,
                    category=item.category,
                    priority=item.priority,
                    confidence=item.confidence,
                    impact=item.impact,
                    contradiction_ids=item.contradiction_ids,
                    belief_title=item.belief_title,
                    belief_content=item.candidate.belief_content,
                    gate_policy_version=policy.version,
                )
                passed_pairs.append((item, decision))
            else:
                blocked.append(item)

        # Apply max_decisions cap: overflow items go to blocked
        if policy.max_decisions > 0 and len(passed_pairs) > policy.max_decisions:
            overflow = passed_pairs[policy.max_decisions:]
            blocked.extend(syn_item for syn_item, _ in overflow)
            passed_pairs = passed_pairs[:policy.max_decisions]

        decisions = [d for _, d in passed_pairs]

        gate_policy_snapshot: dict[str, Any] = {
            "version": policy.version,
            "minimum_confidence": policy.minimum_confidence,
            "block_if_contradicted": policy.block_if_contradicted,
            "max_decisions": policy.max_decisions,
        }

        summary: dict[str, Any] = {
            "total_candidates": len(synthesis.items),
            "approved": len(decisions),
            "blocked": len(blocked),
        }

        return DecisionSet(
            decisions=decisions,
            blocked=blocked,
            gate_policy=gate_policy_snapshot,
            summary=summary,
        )
