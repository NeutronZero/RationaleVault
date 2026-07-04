"""RationaleVault Transport Runtime — Orchestrator for transport lifecycle.

TransportRuntime orchestrates:
  NegotiationEngine → SerializationPipeline → TransportSessionManager

Design rules:
  - Pure functions: frozen inputs → (frozen output, event_payload).
  - No I/O, no mutation, no side effects.
  - Deterministic: same inputs → identical state.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from rationalevault.transport.events import (
    ConnectorAttachedPayload,
    ConnectorDetachedPayload,
    ConnectorNegotiatedPayload,
    ConnectorRegisteredPayload,
    ConnectorUnregisteredPayload,
    TransportPackageStreamedPayload,
)
from rationalevault.transport.models import (
    NegotiationOutcome,
    TransportManifest,
    TransportNegotiation,
    TransportSession,
    TransportStatus,
)
from rationalevault.transport.negotiation_engine import NegotiationEngine
from rationalevault.transport.serialization_pipeline import SerializationPipeline


# ── Result Type ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Success:
    """Successful operation result."""
    value: Any

    def to_dict(self) -> dict[str, Any]:
        return {"value": self.value}

@dataclass(frozen=True)
class Error:
    """Failed operation result with reason."""
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {"reason": self.reason}


# ── TransportRuntime ─────────────────────────────────────────────────────

class TransportRuntime:
    """Orchestrates transport lifecycle.

    Pure functions: frozen inputs → (frozen output, event_payload).
    """

    @staticmethod
    def register_transport(
        manifest: TransportManifest,
        reference_time: datetime | None = None,
    ) -> tuple[TransportManifest, ConnectorRegisteredPayload]:
        """Register a transport with the runtime.

        Args:
            manifest: Transport manifest.
            reference_time: Deterministic datetime override.

        Returns:
            (Manifest, event payload).
        """
        now = (reference_time or datetime.now(timezone.utc)).isoformat()

        event = ConnectorRegisteredPayload(
            manifest_id=manifest.manifest_id,
            transport_type=manifest.transport_type.value,
            name=manifest.name,
            version=manifest.version,
            registered_at=now,
        )

        return manifest, event

    @staticmethod
    def negotiate(
        manifest: TransportManifest,
        reference_time: datetime | None = None,
    ) -> tuple[TransportNegotiation, ConnectorNegotiatedPayload] | Error:
        """Negotiate transport compatibility.

        Args:
            manifest: Transport manifest to negotiate.
            reference_time: Deterministic datetime override.

        Returns:
            (Negotiation, event payload) or Error.
        """
        negotiation = NegotiationEngine.negotiate(
            manifest=manifest, reference_time=reference_time,
        )

        if negotiation.outcome == NegotiationOutcome.REJECTED:
            return Error(
                f"Transport {manifest.name} rejected: {negotiation.warnings}"
            )

        event = ConnectorNegotiatedPayload(
            negotiation_id=negotiation.negotiation_id,
            manifest_id=manifest.manifest_id,
            outcome=negotiation.outcome.value,
            matched_capabilities=negotiation.matched_capabilities,
            missing_capabilities=negotiation.missing_capabilities,
            negotiated_at=negotiation.negotiated_at,
        )

        return negotiation, event

    @staticmethod
    def attach(
        manifest: TransportManifest,
        negotiation: TransportNegotiation,
        agent_session_id: str,
        workspace_id: str,
        reference_time: datetime | None = None,
    ) -> tuple[TransportSession, ConnectorAttachedPayload] | Error:
        """Attach a transport session.

        Args:
            manifest: Transport manifest.
            negotiation: Completed negotiation.
            agent_session_id: Agent session ID (AGS-[hash]).
            workspace_id: Workspace ID (WS-[hash]).
            reference_time: Deterministic datetime override.

        Returns:
            (TransportSession, event payload) or Error.
        """
        if negotiation.outcome != NegotiationOutcome.COMPATIBLE:
            return Error(
                f"Cannot attach: negotiation outcome is {negotiation.outcome.value}"
            )

        now = (reference_time or datetime.now(timezone.utc)).isoformat()

        session = TransportSession(
            session_id=TransportSession.generate_session_id(
                manifest.manifest_id, agent_session_id, now
            ),
            transport_manifest_id=manifest.manifest_id,
            negotiation_id=negotiation.negotiation_id,
            agent_session_id=agent_session_id,
            workspace_id=workspace_id,
            status=TransportStatus.CREATED,
            created_at=now,
            last_active_at=now,
        )

        event = ConnectorAttachedPayload(
            session_id=session.session_id,
            transport_manifest_id=manifest.manifest_id,
            agent_session_id=agent_session_id,
            workspace_id=workspace_id,
            attached_at=now,
        )

        return session, event

    @staticmethod
    def stream_package(
        session: TransportSession,
        package_dict: dict[str, Any],
        format_name: str,
        reference_time: datetime | None = None,
    ) -> tuple[TransportSession, TransportPackageStreamedPayload, bytes] | Error:
        """Stream a package over a transport session.

        Args:
            session: Active transport session.
            package_dict: WorkspacePackage as dict.
            format_name: Serialization format name.
            reference_time: Deterministic datetime override.

        Returns:
            (Updated session, event payload, serialized bytes) or Error.
        """
        if session.status in (TransportStatus.CLOSED, TransportStatus.DISCONNECTED):
            return Error(
                f"Cannot stream: session is {session.status.value}"
            )

        now = (reference_time or datetime.now(timezone.utc)).isoformat()

        try:
            serialized, content_type = SerializationPipeline.serialize(
                package_dict, format_name,
            )
        except ValueError as e:
            return Error(str(e))

        updated = TransportSession(
            session_id=session.session_id,
            transport_manifest_id=session.transport_manifest_id,
            negotiation_id=session.negotiation_id,
            agent_session_id=session.agent_session_id,
            workspace_id=session.workspace_id,
            status=TransportStatus.STREAMING,
            packages_sent=session.packages_sent + 1,
            bytes_transferred=session.bytes_transferred + len(serialized),
            created_at=session.created_at,
            last_active_at=now,
            closed_at=session.closed_at,
        )

        event = TransportPackageStreamedPayload(
            session_id=session.session_id,
            package_id=package_dict.get("package_id", ""),
            bytes_transferred=len(serialized),
            serialization_format=format_name,
            streamed_at=now,
        )

        return updated, event, serialized

    @staticmethod
    def detach(
        session: TransportSession,
        reference_time: datetime | None = None,
    ) -> tuple[TransportSession, ConnectorDetachedPayload] | Error:
        """Detach a transport session.

        Args:
            session: Active transport session.
            reference_time: Deterministic datetime override.

        Returns:
            (Updated session, event payload) or Error.
        """
        if session.status == TransportStatus.CLOSED:
            return Error("Session is already closed")

        now = (reference_time or datetime.now(timezone.utc)).isoformat()

        closed = TransportSession(
            session_id=session.session_id,
            transport_manifest_id=session.transport_manifest_id,
            negotiation_id=session.negotiation_id,
            agent_session_id=session.agent_session_id,
            workspace_id=session.workspace_id,
            status=TransportStatus.CLOSED,
            packages_sent=session.packages_sent,
            bytes_transferred=session.bytes_transferred,
            created_at=session.created_at,
            last_active_at=now,
            closed_at=now,
        )

        event = ConnectorDetachedPayload(
            session_id=session.session_id,
            workspace_id=session.workspace_id,
            packages_sent=session.packages_sent,
            bytes_transferred=session.bytes_transferred,
            detached_at=now,
        )

        return closed, event

    @staticmethod
    def unregister_transport(
        manifest: TransportManifest,
        reason: str = "Deprecated",
        reference_time: datetime | None = None,
    ) -> ConnectorUnregisteredPayload:
        """Produce an unregistration event.

        Args:
            manifest: Transport manifest to unregister.
            reason: Reason for unregistration.
            reference_time: Deterministic datetime override.

        Returns:
            Event payload.
        """
        now = (reference_time or datetime.now(timezone.utc)).isoformat()

        return ConnectorUnregisteredPayload(
            manifest_id=manifest.manifest_id,
            reason=reason,
            unregistered_at=now,
        )
