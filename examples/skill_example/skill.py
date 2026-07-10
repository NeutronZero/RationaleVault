"""Example Skill for writing files."""
from __future__ import annotations

import os
from typing import Any, ClassVar

from rationalevault.skills import BaseSkill, SkillManifest, SkillInput, SkillOutput


# Decision:
# Skills are the ONLY place in RationaleVault where I/O and side effects
# are permitted.
#
# Why:
# Since they do not run during projection replay, they don't break determinism.
# They execute once, and emit immutable events recording what they did.

class WriteFileSkill(BaseSkill):
    """Writes content to a file safely."""
    
    deterministic: ClassVar[bool] = False
    side_effect_free: ClassVar[bool] = False
    idempotent: ClassVar[bool] = False
    requires_network: ClassVar[bool] = False

    def manifest(self) -> SkillManifest:
        return SkillManifest(
            skill_id=SkillManifest.generate_skill_id("WriteFileSkill", "1.0.0"),
            name="WriteFileSkill",
            version="1.0.0",
            description="Writes content to a file safely.",
            input_schema={
                "type": "object",
                "properties": {
                    "filepath": {"type": "string"},
                    "content": {"type": "string"}
                }
            },
            output_schema={
                "type": "object"
            },
            required_permissions=["skill:execute"],
            accepted_categories=["RESOLVE"],
            timeout_seconds=5,
            idempotent=False
        )

    def __call__(self, skill_input: SkillInput) -> SkillOutput:
        """Writes content to a file."""
        # Inputs are typically provided in the metadata dict
        filepath = skill_input.metadata.get("filepath")
        content = skill_input.metadata.get("content")
        
        if not filepath or not content:
            return SkillOutput(
                status="failed",
                summary="Missing 'filepath' or 'content' in input."
            )

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            
            return SkillOutput(
                status="completed",
                summary=f"Wrote {len(content)} bytes to {filepath}",
                metrics={"bytes_written": len(content)}
            )
        except Exception as e:
            return SkillOutput(
                status="failed",
                summary=f"Error writing file: {str(e)}"
            )
