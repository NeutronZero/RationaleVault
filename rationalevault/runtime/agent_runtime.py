"""RationaleVault Agent Runtime — Orchestrator for agent session lifecycle.

AgentRuntime orchestrates:
  SessionRegistry → CapabilityResolver → WorkspaceBinder → PackageStreamer

Design rules:
  - Pure functions: frozen inputs → (frozen output, event_payload).
  - No I/O, no mutation, no side effects.
  - Deterministic: same inputs → identical state.
  - Mirrors the Workspace Service pattern.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from rationalevault.projections.workspace import WorkspaceState
from rationalevault.runtime.capability_resolver import CapabilityResolver
from rationalevault.runtime.events import (
    SessionAttachedPayload,
    SessionClosedPayload,
    SessionCreatedPayload,
    SessionDetachedPayload,
    SessionPausedPayload,
    SessionResumedPayload,
)
from rationalevault.runtime.models import (
    AgentCapabilities,
    AgentProfile,
    AgentSession,
    Capability,
    ProtocolVersion,
    RuntimeContext,
    SessionSnapshot,
    SessionStatus,
    WorkspaceBinding,
)
from rationalevault.runtime.package_streamer import PackageStreamer
from rationalevault.runtime.workspace_binder import WorkspaceBinder
from rationalevault.workspace.models import Workspace, WorkspacePackage


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


# ── AgentRuntime ─────────────────────────────────────────────────────────

class AgentRuntime:
    """Orchestrates agent session lifecycle in the runtime.

    Pure functions: frozen inputs → (frozen output, event_payload).
    """

    @staticmethod
    def create_session(
        profile: AgentProfile,
        workspace: Workspace,
        protocol_version: str = "1.0.0",
        denied: frozenset[Capability] | None = None,
        reference_time: datetime | None = None,
    ) -> tuple[AgentSession, WorkspaceBinding, AgentCapabilities,
               SessionCreatedPayload] | Error:
        """Create a new agent session.

        Args:
            profile: Agent profile.
            workspace: Target workspace.
            protocol_version: Protocol version for compatibility.
            denied: Capabilities denied by workspace policy.
            reference_time: Deterministic datetime override.

        Returns:
            (Session, Binding, Capabilities, event) or Error.
        """
        now = (reference_time or datetime.now(timezone.utc)).isoformat()

        # Check protocol compatibility
        runtime_version = ProtocolVersion.parse("1.0.0")
        agent_version = ProtocolVersion.parse(protocol_version)
        if not runtime_version.is_compatible(agent_version):
            return Error(
                f"Protocol version mismatch: runtime={runtime_version}, "
                f"agent={agent_version}"
            )

        # Check agent is active
        if profile.status.value != "ACTIVE":
            return Error(f"Agent profile {profile.profile_id} is not active")

        # Create binding
        binding = WorkspaceBinding(
            binding_id=WorkspaceBinding.generate_binding_id(
                f"pending-{profile.profile_id}", workspace.workspace_id
            ),
            session_id="pending",
            workspace_id=workspace.workspace_id,
            role="PRIMARY",
            attached_at=now,
        )

        # Create session
        session = WorkspaceBinder.create_session(
            profile_id=profile.profile_id,
            workspace_id=workspace.workspace_id,
            binding=binding,
            protocol_version=protocol_version,
            reference_time=reference_time,
        )

        # Resolve capabilities
        capabilities = CapabilityResolver.resolve(
            profile=profile,
            denied=denied,
            reference_time=reference_time,
        )

        # Update binding with real session ID
        binding = WorkspaceBinding(
            binding_id=binding.binding_id,
            session_id=session.session_id,
            workspace_id=binding.workspace_id,
            role=binding.role,
            attached_at=binding.attached_at,
        )

        # Produce event
        event = SessionCreatedPayload(
            session_id=session.session_id,
            profile_id=profile.profile_id,
            workspace_id=workspace.workspace_id,
            binding_id=binding.binding_id,
            protocol_version=protocol_version,
            created_at=now,
        )

        return session, binding, capabilities, event

    @staticmethod
    def attach(
        session: AgentSession,
        workspace: Workspace,
        capabilities: AgentCapabilities,
        reference_time: datetime | None = None,
    ) -> tuple[AgentSession, WorkspaceBinding, SessionAttachedPayload] | Error:
        """Attach a session to a workspace.

        Args:
            session: The session to attach.
            workspace: Target workspace.
            capabilities: Resolved capabilities.
            reference_time: Deterministic datetime override.

        Returns:
            (Updated session, binding, event) or Error.
        """
        if session.status != SessionStatus.CREATED:
            return Error(
                f"Cannot attach session in {session.status.value} status "
                f"(must be CREATED)"
            )

        updated_session, binding = WorkspaceBinder.attach(
            session=session,
            workspace_id=workspace.workspace_id,
            reference_time=reference_time,
        )

        event = SessionAttachedPayload(
            session_id=updated_session.session_id,
            workspace_id=workspace.workspace_id,
            binding_id=binding.binding_id,
            capabilities=sorted(c.value for c in capabilities.effective),
            attached_at=binding.attached_at,
        )

        return updated_session, binding, event

    @staticmethod
    def pause(
        session: AgentSession,
        reference_time: datetime | None = None,
    ) -> tuple[AgentSession, SessionPausedPayload] | Error:
        """Pause an active session.

        Args:
            session: The session to pause.
            reference_time: Deterministic datetime override.

        Returns:
            (Updated session, event) or Error.
        """
        if session.status not in (SessionStatus.ATTACHED, SessionStatus.STREAMING,
                                   SessionStatus.RESUMED):
            return Error(
                f"Cannot pause session in {session.status.value} status"
            )

        now = (reference_time or datetime.now(timezone.utc)).isoformat()

        paused = AgentSession(
            session_id=session.session_id,
            profile_id=session.profile_id,
            workspace_id=session.workspace_id,
            status=SessionStatus.PAUSED,
            binding_id=session.binding_id,
            context_id=session.context_id,
            snapshot_id=session.snapshot_id,
            protocol_version=session.protocol_version,
            started_at=session.started_at,
            last_active_at=now,
            ended_at=session.ended_at,
        )

        event = SessionPausedPayload(
            session_id=session.session_id,
            workspace_id=session.workspace_id,
            paused_at=now,
        )

        return paused, event

    @staticmethod
    def resume(
        session: AgentSession,
        reference_time: datetime | None = None,
    ) -> tuple[AgentSession, SessionResumedPayload] | Error:
        """Resume a paused session.

        Args:
            session: The session to resume.
            reference_time: Deterministic datetime override.

        Returns:
            (Updated session, event) or Error.
        """
        if session.status != SessionStatus.PAUSED:
            return Error(
                f"Cannot resume session in {session.status.value} status "
                f"(must be PAUSED)"
            )

        now = (reference_time or datetime.now(timezone.utc)).isoformat()

        resumed = AgentSession(
            session_id=session.session_id,
            profile_id=session.profile_id,
            workspace_id=session.workspace_id,
            status=SessionStatus.RESUMED,
            binding_id=session.binding_id,
            context_id=session.context_id,
            snapshot_id=session.snapshot_id,
            protocol_version=session.protocol_version,
            started_at=session.started_at,
            last_active_at=now,
            ended_at=session.ended_at,
        )

        event = SessionResumedPayload(
            session_id=session.session_id,
            workspace_id=session.workspace_id,
            resumed_at=now,
        )

        return resumed, event

    @staticmethod
    def detach(
        session: AgentSession,
        binding: WorkspaceBinding,
        reference_time: datetime | None = None,
    ) -> tuple[AgentSession, WorkspaceBinding, SessionDetachedPayload] | Error:
        """Detach a session from a workspace.

        Args:
            session: The session to detach.
            binding: The active binding.
            reference_time: Deterministic datetime override.

        Returns:
            (Updated session, updated binding, event) or Error.
        """
        if session.status in (SessionStatus.CLOSED, SessionStatus.DETACHED):
            return Error(
                f"Cannot detach session in {session.status.value} status"
            )

        updated_session, closed_binding = WorkspaceBinder.detach(
            session=session,
            binding=binding,
            reference_time=reference_time,
        )

        event = SessionDetachedPayload(
            session_id=session.session_id,
            workspace_id=session.workspace_id,
            binding_id=binding.binding_id,
            detached_at=closed_binding.detached_at or "",
        )

        return updated_session, closed_binding, event

    @staticmethod
    def close(
        session: AgentSession,
        packages_streamed: int = 0,
        events_emitted: int = 0,
        reference_time: datetime | None = None,
    ) -> tuple[AgentSession, SessionClosedPayload] | Error:
        """Close an agent session.

        Args:
            session: The session to close.
            packages_streamed: Total packages streamed.
            events_emitted: Total events emitted.
            reference_time: Deterministic datetime override.

        Returns:
            (Closed session, event) or Error.
        """
        if session.status == SessionStatus.CLOSED:
            return Error("Session is already closed")

        closed = WorkspaceBinder.close_session(
            session=session,
            packages_streamed=packages_streamed,
            events_emitted=events_emitted,
            reference_time=reference_time,
        )

        event = SessionClosedPayload(
            session_id=closed.session_id,
            workspace_id=closed.workspace_id,
            profile_id=closed.profile_id,
            packages_streamed=packages_streamed,
            events_emitted=events_emitted,
            closed_at=closed.ended_at or "",
        )

        return closed, event

    @staticmethod
    def snapshot(
        session: AgentSession,
        capabilities: AgentCapabilities,
        packages_streamed: int = 0,
        events_emitted: int = 0,
        reference_time: datetime | None = None,
    ) -> SessionSnapshot:
        """Take a point-in-time snapshot of a session.

        Args:
            session: The session to snapshot.
            capabilities: Resolved capabilities.
            packages_streamed: Total packages streamed.
            events_emitted: Total events emitted.
            reference_time: Deterministic datetime override.

        Returns:
            SessionSnapshot.
        """
        now = (reference_time or datetime.now(timezone.utc)).isoformat()

        return SessionSnapshot(
            snapshot_id=SessionSnapshot.generate_snapshot_id(
                session.session_id, now
            ),
            session_id=session.session_id,
            workspace_id=session.workspace_id,
            agent_id=session.profile_id,
            status=session.status.value,
            capabilities=capabilities.effective,
            packages_streamed=packages_streamed,
            events_emitted=events_emitted,
            created_at=now,
        )

    @staticmethod
    def stream_package(
        session: AgentSession,
        workspace: Workspace,
        workspace_state: WorkspaceState,
        reference_time: datetime | None = None,
    ) -> tuple[AgentSession, WorkspacePackage, RuntimeContext] | Error:
        """Stream a context package to an agent.

        Args:
            session: Active agent session.
            workspace: The workspace.
            workspace_state: Current workspace state.
            reference_time: Deterministic datetime override.

        Returns:
            (Updated session, package, runtime context) or Error.
        """
        if session.status not in (SessionStatus.ATTACHED, SessionStatus.RESUMED,
                                   SessionStatus.STREAMING):
            return Error(
                f"Cannot stream to session in {session.status.value} status"
            )

        ctx, package, payload = PackageStreamer.stream(
            session=session,
            workspace=workspace,
            workspace_state=workspace_state,
            reference_time=reference_time,
        )

        now = (reference_time or datetime.now(timezone.utc)).isoformat()

        updated_session = AgentSession(
            session_id=session.session_id,
            profile_id=session.profile_id,
            workspace_id=session.workspace_id,
            status=SessionStatus.STREAMING,
            binding_id=session.binding_id,
            context_id=ctx.context_id,
            snapshot_id=session.snapshot_id,
            protocol_version=session.protocol_version,
            started_at=session.started_at,
            last_active_at=now,
            ended_at=session.ended_at,
        )

        return updated_session, package, ctx
