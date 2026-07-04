"""
RationaleVault Skills — ResolveSkill.

Handles RESOLVE category decisions. Produces resolution recommendations
for beliefs with contradictions and insufficient confidence.
"""
from __future__ import annotations

from typing import ClassVar

from rationalevault.skill_platform.manifest import SkillManifest
from rationalevault.skill_platform.skill_input import SkillInput
from rationalevault.skill_platform.skill_output import SkillOutput
from rationalevault.skills.base import BaseSkill


class ResolveSkill(BaseSkill):
    """Produces resolution recommendations for contested beliefs."""

    deterministic: ClassVar[bool] = True
    side_effect_free: ClassVar[bool] = True
    idempotent: ClassVar[bool] = True
    requires_network: ClassVar[bool] = False

    def manifest(self) -> SkillManifest:
        return SkillManifest(
            skill_id=SkillManifest.generate_skill_id("resolve-skill", "1.0.0"),
            name="resolve-skill",
            version="1.0.0",
            description="Produces resolution recommendations for contested beliefs",
            input_schema={
                "type": "object",
                "required": ["decision_id", "belief_title", "confidence"],
                "properties": {
                    "decision_id": {"type": "string"},
                    "belief_title": {"type": "string"},
                    "confidence": {"type": "number"},
                },
            },
            output_schema={
                "type": "object",
                "required": ["status", "recommendations", "summary"],
                "properties": {
                    "status": {"type": "string"},
                    "recommendations": {"type": "array"},
                    "summary": {"type": "string"},
                },
            },
            required_permissions=["projection:memory"],
            accepted_categories=["RESOLVE"],
            timeout_seconds=30,
            idempotent=True,
        )

    def __call__(self, skill_input: SkillInput) -> SkillOutput:
        recommendations = [
            f"Gather additional evidence for '{skill_input.belief_title}'",
            "Evaluate source credibility and recency",
            "Consider splitting into separate beliefs if sources disagree",
        ]
        summary = (
            f"Belief '{skill_input.belief_title}' requires resolution. "
            f"Current confidence {skill_input.confidence:.2f} is below threshold. "
            "Recommend gathering additional evidence."
        )
        return SkillOutput(
            status="completed",
            confirmed_items=[],
            challenged_items=[],
            recommendations=recommendations,
            summary=summary,
            metrics={"confidence": skill_input.confidence},
        )
