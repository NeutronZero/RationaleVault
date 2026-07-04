"""
RationaleVault Skill Platform — Skill Manifest.

A skill manifest declares a skill's identity, capabilities, and contracts.
Manifests are immutable after registration. The registry is metadata-only:
it stores manifests but does not resolve callables or manage runtime state.

Design rules:
  - SkillManifest is frozen — immutable after creation.
  - SKL-[hash] is derived from (name, version) so identical names with
    different versions produce different IDs.
  - The registry is a metadata store. Callable resolution belongs to a
    separate RuntimeResolver (C2).
  - accepted_categories must be valid SynthesisCategory values.
  - required_permissions must be valid capability keys.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SkillManifest:
    """
    Immutable declaration of a skill's identity and contracts.

    skill_id is deterministic: SKL-[hash] from (name, version).
    """
    skill_id: str                          # SKL-[hash] from skill:{name}:{version}
    name: str                              # unique human-readable name
    version: str                           # semver
    description: str                       # one-sentence purpose
    input_schema: dict[str, Any]           # JSON Schema for required inputs
    output_schema: dict[str, Any]          # JSON Schema for produced outputs
    required_permissions: list[str]        # capability keys (see permissions.py)
    accepted_categories: list[str]         # SynthesisCategory values this skill handles
    timeout_seconds: int                   # max execution time (0 = unlimited)
    idempotent: bool                       # True = safe to re-run with same inputs

    @staticmethod
    def generate_skill_id(name: str, version: str) -> str:
        data = f"skill:{name}:{version}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"SKL-{h}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "required_permissions": self.required_permissions,
            "accepted_categories": self.accepted_categories,
            "timeout_seconds": self.timeout_seconds,
            "idempotent": self.idempotent,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "SkillManifest":
        return cls(
            skill_id=d["skill_id"],
            name=d["name"],
            version=d["version"],
            description=d.get("description", ""),
            input_schema=d.get("input_schema", {}),
            output_schema=d.get("output_schema", {}),
            required_permissions=d.get("required_permissions", []),
            accepted_categories=d.get("accepted_categories", []),
            timeout_seconds=d.get("timeout_seconds", 0),
            idempotent=d.get("idempotent", False),
        )

    def validate(self) -> list[str]:
        """
        Validate the manifest against contracts.

        Returns a list of error messages (empty if valid).
        """
        from rationalevault.skill_platform.permissions import CAPABILITY_KEYS

        errors: list[str] = []

        # Validate skill_id format
        if not self.skill_id.startswith("SKL-"):
            errors.append(f"skill_id must start with 'SKL-', got: {self.skill_id}")
        if len(self.skill_id) != 12:  # SKL- + 8 hex chars
            errors.append(f"skill_id must be 12 characters (SKL- + 8 hex), got: {len(self.skill_id)}")

        # Validate required_permissions
        for perm in self.required_permissions:
            if perm not in CAPABILITY_KEYS:
                errors.append(f"Unknown capability: {perm}")

        # Validate accepted_categories
        valid_categories = {"AFFIRM", "CHALLENGE", "RESOLVE", "DEFER", "MONITOR"}
        for cat in self.accepted_categories:
            if cat not in valid_categories:
                errors.append(f"Unknown category: {cat}")

        # Validate timeout
        if self.timeout_seconds < 0:
            errors.append(f"timeout_seconds must be >= 0, got: {self.timeout_seconds}")

        return errors


class SkillManifestRegistry:
    """
    Metadata-only registry of skill manifests.

    Stores manifests by skill_id. Does not resolve callables or manage
    runtime state. Callable resolution belongs to RuntimeResolver (C2).
    """

    def __init__(self) -> None:
        self._manifests: dict[str, SkillManifest] = {}

    def register(self, manifest: SkillManifest) -> None:
        if manifest.skill_id in self._manifests:
            raise ValueError(
                f"Skill already registered: {manifest.skill_id} ({manifest.name})"
            )
        self._manifests[manifest.skill_id] = manifest

    def get(self, skill_id: str) -> SkillManifest | None:
        return self._manifests.get(skill_id)

    def get_by_name(self, name: str) -> SkillManifest | None:
        for m in self._manifests.values():
            if m.name == name:
                return m
        return None

    def list_all(self) -> list[SkillManifest]:
        return list(self._manifests.values())

    def find_by_category(self, category: str) -> list[SkillManifest]:
        return [
            m for m in self._manifests.values()
            if category in m.accepted_categories
        ]

    def __len__(self) -> int:
        return len(self._manifests)

    def __contains__(self, skill_id: str) -> bool:
        return skill_id in self._manifests
