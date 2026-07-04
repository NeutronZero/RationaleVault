"""
RationaleVault Skill Platform — SkillResolver.

Resolves a SkillManifest to a SkillDescriptor. Separation from
activation allows C3/C4 to introduce plugins, version selection,
signatures, lazy loading, and remote skills.

Design rules:
  - Resolver is metadata-only — it produces descriptors, not callables.
  - Activation (descriptor → callable) belongs to SkillActivator.
  - Descriptor wraps activation target (module path, class name, etc.)
    without the resolver knowing what an activation target IS.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rationalevault.skill_platform.manifest import SkillManifest, SkillManifestRegistry


@dataclass(frozen=True)
class ActivationTarget:
    """
    Encapsulates how to activate a skill. Supports multiple runtimes.
    """
    kind: str = "python"                   # "python" | "wasm" | "subprocess" | "rpc" | "remote"
    module_path: str = ""                  # Python module path or plugin file
    class_name: str = ""                   # Class name or skill activator class
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "module_path": self.module_path,
            "class_name": self.class_name,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ActivationTarget:
        return cls(
            kind=d.get("kind", "python"),
            module_path=d.get("module_path", ""),
            class_name=d.get("class_name", ""),
            metadata=d.get("metadata", {}),
        )



@dataclass(frozen=True)
class SkillDescriptor:
    """
    Immutable description of a resolved skill.

    Produced by SkillResolver. Consumed by SkillActivator.
    The descriptor carries identity and activation metadata
    without the resolver knowing how activation works.
    """
    skill_id: str
    name: str
    version: str
    activation_target: ActivationTarget
    required_permissions: list[str]
    accepted_categories: list[str]
    deterministic: bool = True
    side_effect_free: bool = True
    idempotent: bool = True
    requires_network: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "version": self.version,
            "activation_target": self.activation_target.to_dict(),
            "required_permissions": self.required_permissions,
            "accepted_categories": self.accepted_categories,
            "deterministic": self.deterministic,
            "side_effect_free": self.side_effect_free,
            "idempotent": self.idempotent,
            "requires_network": self.requires_network,
        }


class SkillResolver:
    """
    Resolves a SkillManifest to a SkillDescriptor.

    The resolver is metadata-only — it produces descriptors,
    not callables. Activation belongs to SkillActivator.
    """

    # Built-in skill registry: name → (module_path, class_name)
    _BUILTIN_SKILLS: dict[str, tuple[str, str]] = {
        "affirm-skill": ("rationalevault.skills.affirm_skill", "AffirmSkill"),
        "challenge-skill": ("rationalevault.skills.challenge_skill", "ChallengeSkill"),
        "resolve-skill": ("rationalevault.skills.resolve_skill", "ResolveSkill"),
        "monitor-skill": ("rationalevault.skills.monitor_skill", "MonitorSkill"),
    }

    # External skill registry: name → ActivationTarget
    _EXTERNAL_SKILLS: dict[str, ActivationTarget] = {}

    @staticmethod
    def resolve(
        manifest: SkillManifest,
        registry: SkillManifestRegistry | None = None,
    ) -> SkillDescriptor:
        """
        Resolve a manifest to a descriptor.

        Checks built-in registry first, then falls back to
        module_path/class_name from manifest metadata.
        """
        # Check built-in registry
        if manifest.name in SkillResolver._BUILTIN_SKILLS:
            module_path, class_name = SkillResolver._BUILTIN_SKILLS[manifest.name]
            target = ActivationTarget(kind="python", module_path=module_path, class_name=class_name)
        elif manifest.name in SkillResolver._EXTERNAL_SKILLS:
            target = SkillResolver._EXTERNAL_SKILLS[manifest.name]
        else:
            # External skill — use manifest metadata if available
            target = ActivationTarget(
                kind="python",
                module_path=manifest.name,  # placeholder
                class_name="ExternalSkill",
            )

        return SkillDescriptor(
            skill_id=manifest.skill_id,
            name=manifest.name,
            version=manifest.version,
            activation_target=target,
            required_permissions=manifest.required_permissions,
            accepted_categories=manifest.accepted_categories,
        )

    @staticmethod
    def register_builtin(
        name: str,
        module_path: str,
        class_name: str,
    ) -> None:
        """Register a built-in skill for resolution."""
        SkillResolver._BUILTIN_SKILLS[name] = (module_path, class_name)

    @staticmethod
    def register_external(
        name: str,
        target: ActivationTarget,
    ) -> None:
        """Register an external plugin-provided skill for resolution."""
        SkillResolver._EXTERNAL_SKILLS[name] = target

