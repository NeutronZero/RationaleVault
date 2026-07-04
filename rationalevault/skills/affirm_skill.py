"""
RationaleVault Skills — AffirmSkill.

Handles AFFIRM category decisions. Confirms beliefs with high confidence
and no active contradictions. Produces structured affirmation output.
"""
from __future__ import annotations

from typing import ClassVar

from rationalevault.skill_platform.manifest import SkillManifest
from rationalevault.skill_platform.skill_input import SkillInput
from rationalevault.skill_platform.skill_output import SkillOutput
from rationalevault.skills.base import BaseSkill


class AffirmSkill(BaseSkill):
    """Affirms beliefs with high confidence and no active contradictions."""

    deterministic: ClassVar[bool] = True
    side_effect_free: ClassVar[bool] = True
    idempotent: ClassVar[bool] = True
    requires_network: ClassVar[bool] = False

    def manifest(self) -> SkillManifest:
        return SkillManifest(
            skill_id=SkillManifest.generate_skill_id("affirm-skill", "1.0.0"),
            name="affirm-skill",
            version="1.0.0",
            description="Confirms beliefs with high confidence and no active contradictions",
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
                "required": ["status", "confirmed_items", "recommendations", "summary"],
                "properties": {
                    "status": {"type": "string"},
                    "confirmed_items": {"type": "array"},
                    "recommendations": {"type": "array"},
                    "summary": {"type": "string"},
                },
            },
            required_permissions=["projection:memory"],
            accepted_categories=["AFFIRM"],
            timeout_seconds=30,
            idempotent=True,
        )

    def __call__(self, skill_input: SkillInput) -> SkillOutput:
        confirmed = [skill_input.belief_title]
        recommendations = [
            f"Document '{skill_input.belief_title}' as validated (confidence: {skill_input.confidence:.2f})"
        ]
        summary = (
            f"Belief '{skill_input.belief_title}' affirmed with confidence "
            f"{skill_input.confidence:.2f}. No active contradictions detected."
        )
        return SkillOutput(
            status="completed",
            confirmed_items=confirmed,
            challenged_items=[],
            recommendations=recommendations,
            summary=summary,
            metrics={"confidence": skill_input.confidence},
        )
