"""
RationaleVault Transport Contracts — Immutable data structures for the Transport SDK.

The Transport SDK defines HOW data moves between the Agent Runtime and external agents.
Transports are stable platform concerns. Vendors are extension concerns.

Contract hierarchy:
    TransportManifest (identity)
        ↓
    TransportCapabilities (what the transport supports)
        ↓
    TransportNegotiation (version/capability handshake)
        ↓
    TransportSession (active connection)
        ↓
    WorkspacePackageSerializer (package → vendor-native format)

Design rules:
  - All models are FROZEN dataclasses.
  - Transports are separate from vendors (N×M → N+M).
  - Capabilities are composable (set operations).
  - Negotiation is deterministic (same inputs → same outcome).
  - Serialization is a transport-level concern.
"""
from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# =====================================================================
# Enums
# =====================================================================

class TransportType(str, Enum):
    """Supported transport protocols."""
    MCP = "MCP"
    REST = "REST"
    WEBSOCKET = "WEBSOCKET"
    CLI = "CLI"
    IPC = "IPC"
    FILESYSTEM = "FILESYSTEM"
    GRPC = "GRPC"


class TransportStatus(str, Enum):
    """Lifecycle states for a transport session."""
    CREATED = "CREATED"
    NEGOTIATING = "NEGOTIATING"
    READY = "READY"
    STREAMING = "STREAMING"
    PAUSED = "PAUSED"
    DISCONNECTED = "DISCONNECTED"
    CLOSED = "CLOSED"


class NegotiationOutcome(str, Enum):
    """Result of transport negotiation."""
    COMPATIBLE = "COMPATIBLE"
    INCOMPATIBLE = "INCOMPATIBLE"
    REQUIRES_MIGRATION = "REQUIRES_MIGRATION"
    REJECTED = "REJECTED"


# =====================================================================
# Transport Capabilities
# =====================================================================

@dataclass(frozen=True)
class TransportCapabilities:
    """
    Composable capability flags for a transport.

    Defines what a transport CAN do. Used for negotiation
    against runtime requirements.
    """
    supports_streaming: bool = False
    supports_bidirectional: bool = False
    supports_binary: bool = False
    supports_incremental_updates: bool = False
    supports_resume: bool = False
    supports_tool_calls: bool = False
    supports_large_context: bool = False
    max_payload_size_bytes: int = 0
    max_concurrent_sessions: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "supports_streaming": self.supports_streaming,
            "supports_bidirectional": self.supports_bidirectional,
            "supports_binary": self.supports_binary,
            "supports_incremental_updates": self.supports_incremental_updates,
            "supports_resume": self.supports_resume,
            "supports_tool_calls": self.supports_tool_calls,
            "supports_large_context": self.supports_large_context,
            "max_payload_size_bytes": self.max_payload_size_bytes,
            "max_concurrent_sessions": self.max_concurrent_sessions,
        }

    def satisfies(self, required: TransportCapabilities) -> bool:
        """Check if this transport satisfies required capabilities."""
        if required.supports_streaming and not self.supports_streaming:
            return False
        if required.supports_bidirectional and not self.supports_bidirectional:
            return False
        if required.supports_binary and not self.supports_binary:
            return False
        if required.supports_incremental_updates and not self.supports_incremental_updates:
            return False
        if required.supports_resume and not self.supports_resume:
            return False
        if required.supports_tool_calls and not self.supports_tool_calls:
            return False
        if required.supports_large_context and not self.supports_large_context:
            return False
        if (required.max_payload_size_bytes > 0
                and self.max_payload_size_bytes < required.max_payload_size_bytes):
            return False
        if (required.max_concurrent_sessions > 0
                and self.max_concurrent_sessions < required.max_concurrent_sessions):
            return False
        return True


# =====================================================================
# Transport Manifest
# =====================================================================

@dataclass(frozen=True)
class TransportManifest:
    """
    Immutable identity for a transport.

    TMNF-[hash] — immutable identifier.
    """
    manifest_id: str               # TMNF-[hash]
    name: str
    transport_type: TransportType
    version: str                   # SemVer
    capabilities: TransportCapabilities
    supported_runtime_versions: list[str] = field(default_factory=list)
    supported_workspace_versions: list[str] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)

    @staticmethod
    def generate_manifest_id(name: str, transport_type: TransportType, version: str) -> str:
        data = f"transport_manifest:{name}:{transport_type.value}:{version}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"TMNF-{h}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest_id": self.manifest_id,
            "name": self.name,
            "transport_type": self.transport_type.value,
            "version": self.version,
            "capabilities": self.capabilities.to_dict(),
            "supported_runtime_versions": self.supported_runtime_versions,
            "supported_workspace_versions": self.supported_workspace_versions,
            "metadata": self.metadata,
        }


# =====================================================================
# Transport Negotiation
# =====================================================================

@dataclass(frozen=True)
class TransportNegotiation:
    """
    Result of transport-runtime negotiation.

    TNAG-[hash] — immutable.
    """
    negotiation_id: str            # TNAG-[hash]
    transport_manifest_id: str     # TMNF-[hash]
    runtime_version: str
    workspace_version: str
    transport_version: str
    outcome: NegotiationOutcome
    matched_capabilities: list[str] = field(default_factory=list)
    missing_capabilities: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    required_migrations: list[str] = field(default_factory=list)
    negotiated_at: str = ""

    @staticmethod
    def generate_negotiation_id(
        transport_manifest_id: str, runtime_version: str, negotiated_at: str
    ) -> str:
        data = f"transport_negotiation:{transport_manifest_id}:{runtime_version}:{negotiated_at}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"TNAG-{h}"

    @property
    def is_compatible(self) -> bool:
        return self.outcome == NegotiationOutcome.COMPATIBLE

    def to_dict(self) -> dict[str, Any]:
        return {
            "negotiation_id": self.negotiation_id,
            "transport_manifest_id": self.transport_manifest_id,
            "runtime_version": self.runtime_version,
            "workspace_version": self.workspace_version,
            "transport_version": self.transport_version,
            "outcome": self.outcome.value,
            "matched_capabilities": self.matched_capabilities,
            "missing_capabilities": self.missing_capabilities,
            "warnings": self.warnings,
            "required_migrations": self.required_migrations,
            "negotiated_at": self.negotiated_at,
            "is_compatible": self.is_compatible,
        }


# =====================================================================
# Transport Session
# =====================================================================

@dataclass(frozen=True)
class TransportSession:
    """
    Active transport connection between runtime and agent.

    TSSN-[hash] — immutable.
    """
    session_id: str                # TSSN-[hash]
    transport_manifest_id: str     # TMNF-[hash]
    negotiation_id: str            # TNAG-[hash]
    agent_session_id: str          # AGS-[hash] (from Agent Runtime)
    workspace_id: str              # WS-[hash]
    status: TransportStatus
    packages_sent: int = 0
    bytes_transferred: int = 0
    created_at: str = ""
    last_active_at: str = ""
    closed_at: str | None = None

    @staticmethod
    def generate_session_id(
        transport_manifest_id: str, agent_session_id: str, created_at: str
    ) -> str:
        data = f"transport_session:{transport_manifest_id}:{agent_session_id}:{created_at}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"TSSN-{h}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "transport_manifest_id": self.transport_manifest_id,
            "negotiation_id": self.negotiation_id,
            "agent_session_id": self.agent_session_id,
            "workspace_id": self.workspace_id,
            "status": self.status.value,
            "packages_sent": self.packages_sent,
            "bytes_transferred": self.bytes_transferred,
            "created_at": self.created_at,
            "last_active_at": self.last_active_at,
            "closed_at": self.closed_at,
        }


# =====================================================================
# WorkspacePackageSerializer (ABC)
# =====================================================================

class WorkspacePackageSerializer(ABC):
    """
    Converts WorkspacePackage into vendor-native format.

    Every vendor speaks a different dialect. The serializer is a
    transport-level concern, not a vendor concern.
    """

    @abstractmethod
    def serialize(self, package_dict: dict[str, Any]) -> bytes:
        """Serialize a WorkspacePackage dict to bytes."""
        ...

    @abstractmethod
    def content_type(self) -> str:
        """Return the MIME content type of serialized output."""
        ...

    @abstractmethod
    def format_name(self) -> str:
        """Return a human-readable name for this serialization format."""
        ...


# =====================================================================
# Runtime Compatibility
# =====================================================================

@dataclass(frozen=True)
class RuntimeCompatibility:
    """
    Dedicated negotiation object for version compatibility.

    Replaces ad hoc version checks with a deterministic, testable object.
    """
    runtime_version: str
    workspace_version: str
    sdk_version: str
    transport_version: str
    compatible: bool
    warnings: list[str] = field(default_factory=list)
    required_migrations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "runtime_version": self.runtime_version,
            "workspace_version": self.workspace_version,
            "sdk_version": self.sdk_version,
            "transport_version": self.transport_version,
            "compatible": self.compatible,
            "warnings": self.warnings,
            "required_migrations": self.required_migrations,
        }
