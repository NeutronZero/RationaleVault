"""RationaleVault Base Transport Adapter — ABC interface for all transports.

Every transport implements this interface. Vendors select which transport to use.

Design rules:
  - ABC defines the contract; implementations provide behavior.
  - All methods are deterministic (no I/O in the interface).
  - Actual I/O happens in concrete implementations (outside this layer).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from rationalevault.transport.models import (
    TransportCapabilities,
    TransportManifest,
)


class BaseTransportAdapter(ABC):
    """Interface that every transport must implement."""

    @abstractmethod
    def manifest(self) -> TransportManifest:
        """Return the transport's manifest."""
        ...

    @abstractmethod
    def capabilities(self) -> TransportCapabilities:
        """Return the transport's capabilities."""
        ...

    @abstractmethod
    def serialize(self, package_dict: dict[str, Any]) -> bytes:
        """Serialize a WorkspacePackage dict for this transport."""
        ...

    @abstractmethod
    def content_type(self) -> str:
        """Return the MIME content type of serialized output."""
        ...

    @abstractmethod
    def format_name(self) -> str:
        """Return a human-readable name for this serialization format."""
        ...
