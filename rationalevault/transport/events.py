"""
RationaleVault Transport Event Payloads — Immutable event-sourced contracts for the Transport SDK.

Every transport event follows:
    Domain Object → Event Payload → Event Ledger → Projection → State

Event hierarchy:
    CONNECTOR_REGISTERED
        ↓
    CONNECTOR_NEGOTIATED
        ↓
    CONNECTOR_ATTACHED
        ↓
    PACKAGE_STREAMED
        ↓
    CONNECTOR_DETACHED
        ↓
    CONNECTOR_UNREGISTERED

Design rules:
  - Payloads are FROZEN dataclasses, never reused as domain objects.
  - Every payload includes schema_version for forward compatibility.
  - Domain models remain separate from event payloads.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class ConnectorRegisteredPayload:
    """
    Emitted when a transport is registered with the runtime.

    Event: CONNECTOR_REGISTERED
    """
    schema_version: str = SCHEMA_VERSION
    manifest_id: str = ""          # TMNF-[hash]
    transport_type: str = ""
    name: str = ""
    version: str = ""
    registered_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "manifest_id": self.manifest_id,
            "transport_type": self.transport_type,
            "name": self.name,
            "version": self.version,
            "registered_at": self.registered_at,
        }


@dataclass(frozen=True)
class ConnectorNegotiatedPayload:
    """
    Emitted when transport negotiation completes.

    Event: CONNECTOR_NEGOTIATED
    """
    schema_version: str = SCHEMA_VERSION
    negotiation_id: str = ""       # TNAG-[hash]
    manifest_id: str = ""          # TMNF-[hash]
    outcome: str = ""              # COMPATIBLE, INCOMPATIBLE, etc.
    matched_capabilities: list[str] = field(default_factory=list)
    missing_capabilities: list[str] = field(default_factory=list)
    negotiated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "negotiation_id": self.negotiation_id,
            "manifest_id": self.manifest_id,
            "outcome": self.outcome,
            "matched_capabilities": self.matched_capabilities,
            "missing_capabilities": self.missing_capabilities,
            "negotiated_at": self.negotiated_at,
        }


@dataclass(frozen=True)
class ConnectorAttachedPayload:
    """
    Emitted when a transport session attaches to a workspace.

    Event: CONNECTOR_ATTACHED
    """
    schema_version: str = SCHEMA_VERSION
    session_id: str = ""           # TSSN-[hash]
    transport_manifest_id: str = "" # TMNF-[hash]
    agent_session_id: str = ""     # AGS-[hash]
    workspace_id: str = ""         # WS-[hash]
    attached_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "session_id": self.session_id,
            "transport_manifest_id": self.transport_manifest_id,
            "agent_session_id": self.agent_session_id,
            "workspace_id": self.workspace_id,
            "attached_at": self.attached_at,
        }


@dataclass(frozen=True)
class TransportPackageStreamedPayload:
    """
    Emitted when a package is streamed over a transport.

    Event: PACKAGE_STREAMED (transport-level)
    """
    schema_version: str = SCHEMA_VERSION
    session_id: str = ""           # TSSN-[hash]
    package_id: str = ""           # WSPKG-[hash]
    bytes_transferred: int = 0
    serialization_format: str = ""
    streamed_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "session_id": self.session_id,
            "package_id": self.package_id,
            "bytes_transferred": self.bytes_transferred,
            "serialization_format": self.serialization_format,
            "streamed_at": self.streamed_at,
        }


@dataclass(frozen=True)
class ConnectorDetachedPayload:
    """
    Emitted when a transport session detaches.

    Event: CONNECTOR_DETACHED
    """
    schema_version: str = SCHEMA_VERSION
    session_id: str = ""           # TSSN-[hash]
    workspace_id: str = ""         # WS-[hash]
    packages_sent: int = 0
    bytes_transferred: int = 0
    detached_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "session_id": self.session_id,
            "workspace_id": self.workspace_id,
            "packages_sent": self.packages_sent,
            "bytes_transferred": self.bytes_transferred,
            "detached_at": self.detached_at,
        }


@dataclass(frozen=True)
class ConnectorUnregisteredPayload:
    """
    Emitted when a transport is unregistered.

    Event: CONNECTOR_UNREGISTERED
    """
    schema_version: str = SCHEMA_VERSION
    manifest_id: str = ""          # TMNF-[hash]
    reason: str = ""
    unregistered_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "manifest_id": self.manifest_id,
            "reason": self.reason,
            "unregistered_at": self.unregistered_at,
        }
