"""
RationaleVault Skills — ChallengeSkill.

Handles CHALLENGE category decisions. Flags beliefs with active
contradictions for resolution. Produces structured challenge output.
"""
from __future__ import annotations

from typing import ClassVar

from rationalevault.skill_platform.manifest import SkillManifest
from rationalevault.skill_platform.skill_input import SkillInput
from rationalevault.skill_platform.skill_output import SkillOutput
from rationalevault.skills.base import BaseSkill


class ChallengeSkill(BaseSkill):
    """Challenges beliefs with active contradictions."""

    deterministic: ClassVar[bool] = True
    side_effect_free: ClassVar[bool] = True
    idempotent: ClassVar[bool] = True
    requires_network: ClassVar[bool] = False

    def manifest(self) -> SkillManifest:
        return SkillManifest(
            skill_id=SkillManifest.generate_skill_id("challenge-skill", "1.0.0"),
            name="challenge-skill",
            version="1.0.0",
            description="Flags beliefs with active contradictions for resolution",
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
                "required": ["status", "challenged_items", "recommendations", "summary"],
                "properties": {
                    "status": {"type": "string"},
                    "challenged_items": {"type": "array"},
                    "recommendations": {"type": "array"},
                    "summary": {"type": "string"},
                },
            },
            required_permissions=["projection:memory"],
            accepted_categories=["CHALLENGE"],
            timeout_seconds=30,
            idempotent=True,
        )

    def __call__(self, skill_input: SkillInput) -> SkillOutput:
        challenged = [skill_input.belief_title]
        recommendations = [
            f"Flag '{skill_input.belief_title}' for contradiction resolution",
            "Review supporting evidence for conflicting assertions",
        ]
        summary = (
            f"Belief '{skill_input.belief_title}' challenged with confidence "
            f"{skill_input.confidence:.2f}. Active contradictions require resolution."
        )
        return SkillOutput(
            status="completed",
            confirmed_items=[],
            challenged_items=challenged,
            recommendations=recommendations,
            summary=summary,
            metrics={"confidence": skill_input.confidence},
        )
