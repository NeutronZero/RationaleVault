"""
RationaleVault Vendor SDK — Extension layer for agent-specific integrations.

Vendors define WHAT data means to a specific agent:
  - Capability mapping (vendor-specific → runtime capabilities)
  - Serialization mapping (WorkspacePackage → vendor-native format)
  - Transport selection (which transports the vendor supports)

Design rules:
  - Vendor SDK is an extension layer, not a platform layer.
  - Vendors implement thin adapters over the Transport SDK.
  - Capability mapping is deterministic (same vendor → same mapping).
  - Serialization is a transport concern; vendors select the serializer.
"""
from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from rationalevault.runtime.models import Capability
from rationalevault.transport.models import TransportType


# =====================================================================
# Enums
# =====================================================================

class VendorStatus(str, Enum):
    """Lifecycle states for a vendor."""
    ACTIVE = "ACTIVE"
    DEPRECATED = "DEPRECATED"
    EXPERIMENTAL = "EXPERIMENTAL"


# =====================================================================
# Vendor Manifest
# =====================================================================

@dataclass(frozen=True)
class VendorManifest:
    """
    Immutable identity for a vendor.

    VMNF-[hash] — immutable identifier.
    """
    manifest_id: str               # VMNF-[hash]
    name: str
    vendor_id: str                 # e.g. "anthropic", "openai", "google"
    version: str                   # SemVer
    supported_transports: list[TransportType] = field(default_factory=list)
    supported_capabilities: frozenset[Capability] = field(default_factory=frozenset)
    default_serializer: str = "JSON"
    status: VendorStatus = VendorStatus.ACTIVE
    metadata: dict[str, str] = field(default_factory=dict)

    @staticmethod
    def generate_manifest_id(name: str, vendor_id: str, version: str) -> str:
        data = f"vendor_manifest:{name}:{vendor_id}:{version}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"VMNF-{h}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest_id": self.manifest_id,
            "name": self.name,
            "vendor_id": self.vendor_id,
            "version": self.version,
            "supported_transports": [t.value for t in self.supported_transports],
            "supported_capabilities": sorted(c.value for c in self.supported_capabilities),
            "default_serializer": self.default_serializer,
            "status": self.status.value,
            "metadata": self.metadata,
        }


# =====================================================================
# Capability Mapping
# =====================================================================

@dataclass(frozen=True)
class CapabilityMapping:
    """
    Maps vendor-specific capabilities to runtime capabilities.

    Deterministic: same vendor → same mapping.
    Reverse map is auto-built from vendor_to_runtime.
    """
    vendor_id: str
    vendor_to_runtime: dict[str, Capability] = field(default_factory=dict)
    _runtime_to_vendor: dict[Capability, str] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        # Build reverse map automatically
        if self.vendor_to_runtime and not self._runtime_to_vendor:
            object.__setattr__(
                self,
                "_runtime_to_vendor",
                {v: k for k, v in self.vendor_to_runtime.items()},
            )

    def vendor_to_runtime_cap(self, vendor_cap: str) -> Capability | None:
        """Map a vendor capability to a runtime capability."""
        return self.vendor_to_runtime.get(vendor_cap)

    def runtime_to_vendor_cap(self, runtime_cap: Capability) -> str | None:
        """Map a runtime capability to a vendor capability."""
        return self._runtime_to_vendor.get(runtime_cap)

    def to_dict(self) -> dict[str, Any]:
        return {
            "vendor_id": self.vendor_id,
            "vendor_to_runtime": {
                k: v.value for k, v in self.vendor_to_runtime.items()
            },
            "runtime_to_vendor": {
                v.value: k for k, v in self.vendor_to_runtime.items()
            },
        }


# =====================================================================
# Vendor Adapter (ABC)
# =====================================================================

class VendorAdapter(ABC):
    """Interface that every vendor adapter must implement."""

    @abstractmethod
    def manifest(self) -> VendorManifest:
        """Return the vendor's manifest."""
        ...

    @abstractmethod
    def capability_mapping(self) -> CapabilityMapping:
        """Return the vendor's capability mapping."""
        ...

    @abstractmethod
    def serialize(self, package_dict: dict[str, Any]) -> bytes:
        """Serialize a WorkspacePackage for this vendor."""
        ...

    @abstractmethod
    def content_type(self) -> str:
        """Return the MIME content type of vendor-native format."""
        ...

    @abstractmethod
    def format_name(self) -> str:
        """Return the serialization format name."""
        ...

    def supported_transports(self) -> list[TransportType]:
        """Return supported transports (default: all)."""
        return list(TransportType)

    def is_compatible(self, transport_type: TransportType) -> bool:
        """Check if this vendor supports a given transport."""
        return transport_type in self.supported_transports()
