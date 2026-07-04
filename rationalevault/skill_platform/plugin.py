"""
RationaleVault Skill Platform — Plugin SDK.

Defines the Plugin status lifecycle, capabilities, context, descriptors, BasePlugin
contracts, and the Scanner/Validator/Loader/Registry pipeline.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any

from rationalevault.skill_platform.resolver import ActivationTarget
from rationalevault.skill_platform.manifest import SkillManifest
from rationalevault.skills.base import BaseSkill
from rationalevault.skill_platform.permissions import CapabilityModel


class PluginStatus(str, Enum):
    """Lifecycle status of a plugin."""
    DISCOVERED = "DISCOVERED"
    VALIDATED = "VALIDATED"
    LOADED = "LOADED"
    ENABLED = "ENABLED"
    DISABLED = "DISABLED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class PluginCapabilities:
    """Configurable system access capabilities declared by a plugin."""
    requires_network: bool = False
    requires_filesystem: bool = False
    requires_subprocess: bool = False
    experimental: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "requires_network": self.requires_network,
            "requires_filesystem": self.requires_filesystem,
            "requires_subprocess": self.requires_subprocess,
            "experimental": self.experimental,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PluginCapabilities:
        return cls(
            requires_network=d.get("requires_network", False),
            requires_filesystem=d.get("requires_filesystem", False),
            requires_subprocess=d.get("requires_subprocess", False),
            experimental=d.get("experimental", False),
        )


@dataclass(frozen=True)
class PluginContext:
    """Secure runtime context passed to plugins during skill creation."""
    sdk_version: str
    api_version: str
    runtime_version: str
    capabilities: CapabilityModel

    def to_dict(self) -> dict[str, Any]:
        return {
            "sdk_version": self.sdk_version,
            "api_version": self.api_version,
            "runtime_version": self.runtime_version,
            "capabilities": self.capabilities.to_dict(),
        }


@dataclass(frozen=True)
class PluginDescriptor:
    """Declarative, immutable metadata representing a scanned plugin."""
    plugin_id: str
    name: str
    version: str
    author: str
    sdk_version: str
    entrypoint: ActivationTarget
    capabilities: PluginCapabilities
    signature: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "plugin_id": self.plugin_id,
            "name": self.name,
            "version": self.version,
            "author": self.author,
            "sdk_version": self.sdk_version,
            "entrypoint": self.entrypoint.to_dict(),
            "capabilities": self.capabilities.to_dict(),
            "signature": self.signature,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PluginDescriptor:
        return cls(
            plugin_id=d["plugin_id"],
            name=d["name"],
            version=d["version"],
            author=d["author"],
            sdk_version=d["sdk_version"],
            entrypoint=ActivationTarget.from_dict(d["entrypoint"]),
            capabilities=PluginCapabilities.from_dict(d["capabilities"]),
            signature=d.get("signature"),
        )


class BasePlugin(ABC):
    """
    Abstract base class for all RationaleVault plugins.

    The first public API layer for skill extensions.
    """
    sdk_version: str = "1.0"

    @abstractmethod
    def manifests(self) -> list[SkillManifest]:
        """
        Returns manifests for all skills provided by the plugin.
        
        Must never instantiate the skill class directly.
        """
        pass

    @abstractmethod
    def create(self, skill_id: str, context: PluginContext) -> BaseSkill:
        """
        Lazy-instantiates the skill associated with the given ID.
        
        This is where skill class instantiation occurs.
        """
        pass


class PluginScanner:
    """Scans filesystem directories to discover plugin descriptors without executing plugin code."""

    @staticmethod
    def scan(plugins_dir: str) -> list[PluginDescriptor]:
        import json
        from pathlib import Path

        descriptors = []
        p_dir = Path(plugins_dir)
        if not p_dir.exists() or not p_dir.is_dir():
            return descriptors

        for child in p_dir.iterdir():
            if child.is_dir():
                json_file = child / "plugin.json"
                if json_file.exists():
                    try:
                        with open(json_file, "r", encoding="utf-8") as f:
                            data = json.load(f)

                        # Enforce declarative structure
                        entry_data = data.get("entrypoint", {})
                        target = ActivationTarget(
                            kind=entry_data.get("kind", "python"),
                            module_path=entry_data.get("module_path", ""),
                            class_name=entry_data.get("class_name", ""),
                            metadata=entry_data.get("metadata", {}),
                        )

                        caps_data = data.get("capabilities", {})
                        caps = PluginCapabilities(
                            requires_network=caps_data.get("requires_network", False),
                            requires_filesystem=caps_data.get("requires_filesystem", False),
                            requires_subprocess=caps_data.get("requires_subprocess", False),
                            experimental=caps_data.get("experimental", False),
                        )

                        descriptor = PluginDescriptor(
                            plugin_id=data.get("plugin_id", ""),
                            name=data.get("name", ""),
                            version=data.get("version", ""),
                            author=data.get("author", ""),
                            sdk_version=data.get("sdk_version", ""),
                            entrypoint=target,
                            capabilities=caps,
                            signature=data.get("signature"),
                        )
                        descriptors.append(descriptor)
                    except Exception:
                        pass
        return descriptors


class PluginValidator:
    """Enforces safety rules and compatibility gates on discovered plugin descriptors."""

    SUPPORTED_SDK_VERSIONS = {"1.0"}

    @staticmethod
    def validate(
        descriptor: PluginDescriptor, loaded_plugins: list[PluginDescriptor]
    ) -> tuple[bool, list[str]]:
        import re

        errors = []

        if descriptor.sdk_version not in PluginValidator.SUPPORTED_SDK_VERSIONS:
            errors.append(
                f"Unsupported SDK version: {descriptor.sdk_version}. "
                f"Supported: {PluginValidator.SUPPORTED_SDK_VERSIONS}"
            )

        if not descriptor.plugin_id or not descriptor.name:
            errors.append("Plugin ID and name must be specified and non-empty")

        # Duplicate ID check
        for lp in loaded_plugins:
            if lp.plugin_id == descriptor.plugin_id:
                errors.append(f"Duplicate plugin ID: {descriptor.plugin_id}")

        # Semver check
        if not re.match(r"^\d+\.\d+\.\d+$", descriptor.version):
            errors.append(f"Invalid semver version format: {descriptor.version}")

        return len(errors) == 0, errors


class PluginLoader:
    """Imports python modules dynamically and instantiates BasePlugin subclasses."""

    @staticmethod
    def load(descriptor: PluginDescriptor, plugins_dir: str) -> BasePlugin:
        import importlib
        import sys
        from pathlib import Path

        # Add plugins directory to sys.path if not present
        abs_plugins_dir = str(Path(plugins_dir).resolve())
        if abs_plugins_dir not in sys.path:
            sys.path.insert(0, abs_plugins_dir)

        target = descriptor.entrypoint
        try:
            module = importlib.import_module(target.module_path)
        except Exception as e:
            raise ImportError(f"Failed to import plugin module '{target.module_path}': {e}")

        plugin_class = getattr(module, target.class_name, None)
        if plugin_class is None:
            raise AttributeError(
                f"Module '{target.module_path}' does not define plugin class '{target.class_name}'"
            )

        if not issubclass(plugin_class, BasePlugin):
            raise TypeError(f"Class '{target.class_name}' must inherit from BasePlugin")

        try:
            instance = plugin_class()
        except Exception as e:
            raise RuntimeError(f"Failed to instantiate plugin class '{target.class_name}': {e}")

        return instance


class PluginRegistry:
    """Manages active descriptors, loaded BasePlugin instances, and status lifecycles."""

    _instances: dict[str, BasePlugin] = {}
    _descriptors: dict[str, PluginDescriptor] = {}
    _statuses: dict[str, PluginStatus] = {}

    @classmethod
    def register(cls, descriptor: PluginDescriptor, instance: BasePlugin) -> None:
        cls._descriptors[descriptor.plugin_id] = descriptor
        cls._instances[descriptor.plugin_id] = instance
        cls._statuses[descriptor.plugin_id] = PluginStatus.ENABLED

    @classmethod
    def get_instance(cls, plugin_id: str) -> BasePlugin | None:
        return cls._instances.get(plugin_id)

    @classmethod
    def get_descriptor(cls, plugin_id: str) -> PluginDescriptor | None:
        return cls._descriptors.get(plugin_id)

    @classmethod
    def set_status(cls, plugin_id: str, status: PluginStatus) -> None:
        cls._statuses[plugin_id] = status

    @classmethod
    def get_status(cls, plugin_id: str) -> PluginStatus:
        return cls._statuses.get(plugin_id, PluginStatus.DISCOVERED)

    @classmethod
    def get_all_descriptors(cls) -> list[PluginDescriptor]:
        return list(cls._descriptors.values())

    @classmethod
    def clear(cls) -> None:
        """Clears all registered plugins (primarily for test isolation)."""
        cls._instances.clear()
        cls._descriptors.clear()
        cls._statuses.clear()
