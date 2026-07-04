"""
RationaleVault Skills — BuiltinSkillRegistry.

Metadata-only registry of built-in skills. Does not instantiate or
activate skills — that belongs to SkillResolver and SkillActivator.

Design rules:
  - Registry is declarative — stores descriptors, not instances.
  - Activation belongs exclusively to SkillActivator.
  - Registry metadata is used for discovery and validation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rationalevault.skill_platform.manifest import SkillManifest
from rationalevault.skill_platform.resolver import SkillDescriptor, ActivationTarget


@dataclass(frozen=True)
class BuiltinSkillEntry:
    """Metadata entry for a built-in skill."""
    descriptor: SkillDescriptor
    manifest: SkillManifest

    def to_dict(self) -> dict[str, Any]:
        return {
            "descriptor": self.descriptor.to_dict(),
            "manifest": self.manifest.to_dict(),
        }


class BuiltinSkillRegistry:
    """
    Metadata-only registry of built-in skills.

    Stores SkillDescriptor + SkillManifest pairs. Does not instantiate
    or activate skills — that belongs to SkillActivator.
    """

    def __init__(self) -> None:
        self._entries: dict[str, BuiltinSkillEntry] = {}

    def register(self, manifest: SkillManifest, descriptor: SkillDescriptor) -> None:
        if manifest.name in self._entries:
            raise ValueError(f"Skill already registered: {manifest.name}")
        self._entries[manifest.name] = BuiltinSkillEntry(
            descriptor=descriptor,
            manifest=manifest,
        )

    def get(self, name: str) -> BuiltinSkillEntry | None:
        return self._entries.get(name)

    def list_all(self) -> list[BuiltinSkillEntry]:
        return list(self._entries.values())

    def find_by_category(self, category: str) -> list[BuiltinSkillEntry]:
        return [
            entry for entry in self._entries.values()
            if category in entry.manifest.accepted_categories
        ]

    def __len__(self) -> int:
        return len(self._entries)

    def __contains__(self, name: str) -> bool:
        return name in self._entries


def create_builtin_registry() -> BuiltinSkillRegistry:
    """Create and populate the built-in skill registry."""
    from rationalevault.skills.affirm_skill import AffirmSkill
    from rationalevault.skills.challenge_skill import ChallengeSkill
    from rationalevault.skills.resolve_skill import ResolveSkill
    from rationalevault.skills.monitor_skill import MonitorSkill

    registry = BuiltinSkillRegistry()

    for skill_cls in [AffirmSkill, ChallengeSkill, ResolveSkill, MonitorSkill]:
        instance = skill_cls()
        manifest = instance.manifest()
        descriptor = SkillDescriptor(
            skill_id=manifest.skill_id,
            name=manifest.name,
            version=manifest.version,
            activation_target=ActivationTarget(
                module_path=skill_cls.__module__,
                class_name=skill_cls.__name__,
            ),
            required_permissions=manifest.required_permissions,
            accepted_categories=manifest.accepted_categories,
            deterministic=skill_cls.deterministic,
            side_effect_free=skill_cls.side_effect_free,
            idempotent=skill_cls.idempotent,
            requires_network=skill_cls.requires_network,
        )
        registry.register(manifest, descriptor)

    return registry
