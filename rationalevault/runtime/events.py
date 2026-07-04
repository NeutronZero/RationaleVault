"""
RationaleVault Agent Runtime Event Payloads — Immutable event-sourced contracts for the Agent Runtime.

Every runtime event follows:
    Domain Object → Event Payload → Event Ledger → Projection → State

Event hierarchy:
    SESSION_CREATED
        ↓
    SESSION_ATTACHED
        ↓
    PACKAGE_STREAMED
        ↓
    SESSION_PAUSED
        ↓
    SESSION_RESUMED
        ↓
    SESSION_DETACHED
        ↓
    SESSION_CLOSED

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
class SessionCreatedPayload:
    """
    Emitted when a new agent session is created.

    Event: SESSION_CREATED
    """
    schema_version: str = SCHEMA_VERSION
    session_id: str = ""          # AGS-[hash]
    profile_id: str = ""          # AGNT-[hash]
    workspace_id: str = ""        # WS-[hash]
    binding_id: str = ""          # WSB-[hash]
    protocol_version: str = "1.0"
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "session_id": self.session_id,
            "profile_id": self.profile_id,
            "workspace_id": self.workspace_id,
            "binding_id": self.binding_id,
            "protocol_version": self.protocol_version,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class SessionAttachedPayload:
    """
    Emitted when an agent session attaches to a workspace.

    Event: SESSION_ATTACHED
    """
    schema_version: str = SCHEMA_VERSION
    session_id: str = ""          # AGS-[hash]
    workspace_id: str = ""        # WS-[hash]
    binding_id: str = ""          # WSB-[hash]
    capabilities: list[str] = field(default_factory=list)
    attached_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "session_id": self.session_id,
            "workspace_id": self.workspace_id,
            "binding_id": self.binding_id,
            "capabilities": self.capabilities,
            "attached_at": self.attached_at,
        }


@dataclass(frozen=True)
class PackageStreamedPayload:
    """
    Emitted when a context package is streamed to an agent.

    Event: PACKAGE_STREAMED
    """
    schema_version: str = SCHEMA_VERSION
    session_id: str = ""          # AGS-[hash]
    package_id: str = ""          # WSPKG-[hash]
    context_id: str = ""          # RTC-[hash]
    agent_id: str = ""            # AGNT-[hash]
    streamed_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "session_id": self.session_id,
            "package_id": self.package_id,
            "context_id": self.context_id,
            "agent_id": self.agent_id,
            "streamed_at": self.streamed_at,
        }


@dataclass(frozen=True)
class SessionPausedPayload:
    """
    Emitted when an agent session is paused.

    Event: SESSION_PAUSED
    """
    schema_version: str = SCHEMA_VERSION
    session_id: str = ""          # AGS-[hash]
    workspace_id: str = ""        # WS-[hash]
    paused_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "session_id": self.session_id,
            "workspace_id": self.workspace_id,
            "paused_at": self.paused_at,
        }


@dataclass(frozen=True)
class SessionResumedPayload:
    """
    Emitted when a paused agent session is resumed.

    Event: SESSION_RESUMED
    """
    schema_version: str = SCHEMA_VERSION
    session_id: str = ""          # AGS-[hash]
    workspace_id: str = ""        # WS-[hash]
    resumed_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "session_id": self.session_id,
            "workspace_id": self.workspace_id,
            "resumed_at": self.resumed_at,
        }


@dataclass(frozen=True)
class SessionDetachedPayload:
    """
    Emitted when an agent session detaches from a workspace.

    Event: SESSION_DETACHED
    """
    schema_version: str = SCHEMA_VERSION
    session_id: str = ""          # AGS-[hash]
    workspace_id: str = ""        # WS-[hash]
    binding_id: str = ""          # WSB-[hash]
    detached_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "session_id": self.session_id,
            "workspace_id": self.workspace_id,
            "binding_id": self.binding_id,
            "detached_at": self.detached_at,
        }


@dataclass(frozen=True)
class SessionClosedPayload:
    """
    Emitted when an agent session is closed.

    Event: SESSION_CLOSED
    """
    schema_version: str = SCHEMA_VERSION
    session_id: str = ""          # AGS-[hash]
    workspace_id: str = ""        # WS-[hash]
    profile_id: str = ""          # AGNT-[hash]
    packages_streamed: int = 0
    events_emitted: int = 0
    closed_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "session_id": self.session_id,
            "workspace_id": self.workspace_id,
            "profile_id": self.profile_id,
            "packages_streamed": self.packages_streamed,
            "events_emitted": self.events_emitted,
            "closed_at": self.closed_at,
        }
