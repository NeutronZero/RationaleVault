"""
RationaleVault Skill Platform — SkillActivator.

Activates a SkillDescriptor into a callable skill instance.
Separation from resolution allows C3/C4 to introduce lazy loading,
remote skills, and WASM modules.

Design rules:
  - Activator imports modules and instantiates classes.
  - It never resolves (that's SkillResolver's job).
  - It never execute (that's SkillRuntime's job).
  - Activation is deterministic: same descriptor → same callable.
"""
from __future__ import annotations

import importlib
import sys
from typing import Any, Callable

from rationalevault.skill_platform.resolver import SkillDescriptor
from rationalevault.skills.base import BaseSkill


class SkillActivationError(Exception):
    """Raised when skill activation fails."""
    pass


class SkillActivator:
    """
    Activates a SkillDescriptor into a callable skill instance.

    The activator imports the module and instantiates the class.
    It never resolves or executes — only activates.
    """

    @staticmethod
    def activate(descriptor: SkillDescriptor) -> Callable[[dict[str, Any]], dict[str, Any]]:
        """
        Activate a skill descriptor into a callable.

        Returns a callable that takes a dict and returns a dict.
        The callable is an instance of the skill class.
        """
        target = descriptor.activation_target
        plugin_id = target.metadata.get("plugin_id")

        if plugin_id:
            from rationalevault.skill_platform.plugin import PluginRegistry, PluginContext
            from rationalevault.skill_platform.permissions import CapabilityModel

            plugin = PluginRegistry.get_instance(plugin_id)
            if plugin is None:
                raise SkillActivationError(
                    f"Plugin '{plugin_id}' not found in registry"
                )

            # Construct PluginContext
            context = PluginContext(
                sdk_version=plugin.sdk_version,
                api_version="1.0",
                runtime_version=sys.version.split()[0],
                capabilities=CapabilityModel(descriptor.required_permissions),
            )

            skill_id = target.metadata.get("skill_id") or descriptor.name
            try:
                instance = plugin.create(skill_id, context)
            except Exception as e:
                raise SkillActivationError(
                    f"Failed to instantiate skill '{skill_id}' from plugin '{plugin_id}': {e}"
                ) from e
        else:
            try:
                module = importlib.import_module(target.module_path)
            except ImportError as e:
                raise SkillActivationError(
                    f"Cannot import module '{target.module_path}' for skill '{descriptor.name}': {e}"
                ) from e

            skill_class = getattr(module, target.class_name, None)
            if skill_class is None:
                raise SkillActivationError(
                    f"Module '{target.module_path}' has no class '{target.class_name}'"
                )

            try:
                instance = skill_class()
            except Exception as e:
                raise SkillActivationError(
                    f"Cannot instantiate '{target.class_name}' for skill '{descriptor.name}': {e}"
                ) from e

        if not callable(instance):
            raise SkillActivationError(
                f"Skill '{descriptor.name}' instance is not callable"
            )

        if isinstance(instance, BaseSkill):
            # Wrap BaseSkill to map dict inputs/outputs to SkillInput/SkillOutput
            from rationalevault.skill_platform.skill_input import SkillInput, ProjectionSnapshot

            def wrapped_skill(inputs_dict: dict[str, Any]) -> dict[str, Any]:
                proj_dict = inputs_dict.get("projections", {})
                projections = ProjectionSnapshot(
                    memory=proj_dict.get("memory", {}),
                    knowledge=proj_dict.get("knowledge", {}),
                    execution_state=proj_dict.get("execution_state", {}),
                    graph=proj_dict.get("graph", {}),
                    context=proj_dict.get("context", {}),
                )
                skill_input = SkillInput(
                    version=inputs_dict.get("version", "1.0"),
                    decision_id=inputs_dict.get("decision_id", ""),
                    belief_id=inputs_dict.get("belief_id", ""),
                    belief_title=inputs_dict.get("belief_title", ""),
                    belief_content=inputs_dict.get("belief_content", ""),
                    confidence=inputs_dict.get("confidence", 0.0),
                    category=inputs_dict.get("category", ""),
                    projections=projections,
                    metadata=inputs_dict.get("metadata", {}),
                )
                try:
                    output = instance(skill_input)
                    return output.to_dict()
                except Exception as exc:
                    raise exc

            return wrapped_skill

        return instance  # type: ignore[return-value]

