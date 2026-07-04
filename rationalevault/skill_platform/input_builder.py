"""
RationaleVault Skill Platform — SkillInputBuilder.

Constructs SkillInput from DecisionItem fields and projection snapshots.
Replaces raw dict construction with a typed, immutable value object.

Design rules:
  - SkillInputBuilder is a pure function — no I/O, no side effects.
  - ProjectionSnapshot carries typed projection data.
  - SkillInput is immutable and versioned.
"""
from __future__ import annotations

from typing import Any

from rationalevault.cognitive_head.decision import DecisionItem
from rationalevault.skill_platform.skill_input import ProjectionSnapshot, SkillInput


class SkillInputBuilder:
    """
    Constructs SkillInput from DecisionItem and projection data.

    The builder is a pure function — it never mutates projections
    or decision items.
    """

    @staticmethod
    def build(
        decision: DecisionItem,
        projections: ProjectionSnapshot | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SkillInput:
        """
        Build a SkillInput from a DecisionItem and optional projections.

        Parameters:
            decision: The DecisionItem to build input for.
            projections: Typed projection snapshots (memory, knowledge, etc.)
            metadata: Additional metadata for the skill.
        """
        return SkillInput(
            decision_id=decision.decision_id,
            belief_id=decision.belief_id,
            belief_title=decision.belief_title,
            belief_content=decision.belief_content,
            confidence=decision.confidence,
            category=decision.category.value,
            projections=projections or ProjectionSnapshot(),
            metadata=metadata or {},
        )

    @staticmethod
    def build_with_snapshots(
        decision: DecisionItem,
        memory: dict[str, Any] | None = None,
        knowledge: dict[str, Any] | None = None,
        execution_state: dict[str, Any] | None = None,
        graph: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SkillInput:
        """
        Build a SkillInput with explicit projection snapshots.

        This is a convenience method for cases where projections
        are provided as individual dicts rather than a ProjectionSnapshot.
        """
        projections = ProjectionSnapshot(
            memory=memory or {},
            knowledge=knowledge or {},
            execution_state=execution_state or {},
            graph=graph or {},
            context=context or {},
        )
        return SkillInputBuilder.build(decision, projections, metadata)
