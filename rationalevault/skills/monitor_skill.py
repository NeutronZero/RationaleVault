"""
RationaleVault Skills — MonitorSkill.

Handles MONITOR category decisions. Sets up monitoring criteria for
beliefs in the intermediate confidence zone.
"""
from __future__ import annotations

from typing import ClassVar

from rationalevault.skill_platform.manifest import SkillManifest
from rationalevault.skill_platform.skill_input import SkillInput
from rationalevault.skill_platform.skill_output import SkillOutput
from rationalevault.skills.base import BaseSkill


class MonitorSkill(BaseSkill):
    """Sets up monitoring for beliefs in the intermediate confidence zone."""

    deterministic: ClassVar[bool] = True
    side_effect_free: ClassVar[bool] = True
    idempotent: ClassVar[bool] = True
    requires_network: ClassVar[bool] = False

    def manifest(self) -> SkillManifest:
        return SkillManifest(
            skill_id=SkillManifest.generate_skill_id("monitor-skill", "1.0.0"),
            name="monitor-skill",
            version="1.0.0",
            description="Sets up monitoring for beliefs in the intermediate confidence zone",
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
            accepted_categories=["MONITOR"],
            timeout_seconds=30,
            idempotent=True,
        )

    def __call__(self, skill_input: SkillInput) -> SkillOutput:
        recommendations = [
            f"Watch '{skill_input.belief_title}' for confidence changes",
            "Re-evaluate when new evidence arrives",
            "Set alert threshold at confidence ±0.1",
        ]
        summary = (
            f"Belief '{skill_input.belief_title}' placed in monitoring. "
            f"Current confidence {skill_input.confidence:.2f} is in intermediate zone. "
            "Will re-evaluate when new evidence arrives."
        )
        return SkillOutput(
            status="completed",
            confirmed_items=[],
            challenged_items=[],
            recommendations=recommendations,
            summary=summary,
            metrics={"confidence": skill_input.confidence},
        )
