"""RationaleVault Serialization Pipeline — Converts WorkspacePackage to vendor-native format.

SerializationPipeline routes packages through the appropriate serializer.

Design rules:
  - Pure functions, no I/O.
  - Deterministic: same package + serializer → identical output.
  - Serializers are transport-level concerns, not vendor concerns.
"""
from __future__ import annotations

from typing import Any

from rationalevault.transport.models import WorkspacePackageSerializer


class SerializationPipeline:
    """Routes and executes serialization for transport packages."""

    _serializers: dict[str, WorkspacePackageSerializer] = {}

    @classmethod
    def register(cls, name: str, serializer: WorkspacePackageSerializer) -> None:
        """Register a serializer by name."""
        cls._serializers[name] = serializer

    @classmethod
    def get(cls, name: str) -> WorkspacePackageSerializer | None:
        """Get a registered serializer by name."""
        return cls._serializers.get(name)

    @classmethod
    def list_serializers(cls) -> list[str]:
        """List all registered serializer names."""
        return sorted(cls._serializers.keys())

    @classmethod
    def serialize(
        cls,
        package_dict: dict[str, Any],
        format_name: str,
    ) -> tuple[bytes, str]:
        """Serialize a package dict using the named format.

        Args:
            package_dict: WorkspacePackage as dict.
            format_name: Serializer name (e.g., "JSON", "msgpack").

        Returns:
            (serialized bytes, content type).

        Raises:
            ValueError: If format_name is not registered.
        """
        serializer = cls._serializers.get(format_name)
        if serializer is None:
            raise ValueError(
                f"Unknown serialization format: {format_name}. "
                f"Registered: {cls.list_serializers()}"
            )
        return serializer.serialize(package_dict), serializer.content_type()

    @classmethod
    def clear(cls) -> None:
        """Clear all registered serializers (for testing)."""
        cls._serializers.clear()
