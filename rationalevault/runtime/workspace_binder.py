"""RationaleVault Workspace Binder — Attaches and detaches agents to workspaces.

WorkspaceBinder manages the binding between agent sessions and workspaces.

Design rules:
  - Pure functions: frozen inputs → new state.
  - No I/O, no mutation.
  - Deterministic: same inputs → identical binding.
  - One active binding per session.
"""
from __future__ import annotations

from datetime import datetime, timezone

from rationalevault.runtime.models import (
    AgentSession,
    SessionStatus,
    WorkspaceBinding,
)
from rationalevault.workspace.models import AgentRole


class WorkspaceBinder:
    """Manages workspace bindings for agent sessions."""

    @staticmethod
    def attach(
        session: AgentSession,
        workspace_id: str,
        role: AgentRole = AgentRole.PRIMARY,
        reference_time: datetime | None = None,
    ) -> tuple[AgentSession, WorkspaceBinding]:
        """Attach an agent session to a workspace.

        Args:
            session: The session to attach.
            workspace_id: Target workspace ID.
            role: Agent role in the workspace.
            reference_time: Deterministic datetime override.

        Returns:
            (Updated session, new WorkspaceBinding).
        """
        now = (reference_time or datetime.now(timezone.utc)).isoformat()

        binding = WorkspaceBinding(
            binding_id=WorkspaceBinding.generate_binding_id(
                session.session_id, workspace_id
            ),
            session_id=session.session_id,
            workspace_id=workspace_id,
            role=role.value,
            attached_at=now,
        )

        updated_session = AgentSession(
            session_id=session.session_id,
            profile_id=session.profile_id,
            workspace_id=workspace_id,
            status=SessionStatus.ATTACHED,
            binding_id=binding.binding_id,
            context_id=session.context_id,
            snapshot_id=session.snapshot_id,
            protocol_version=session.protocol_version,
            started_at=session.started_at,
            last_active_at=now,
            ended_at=session.ended_at,
        )

        return updated_session, binding

    @staticmethod
    def detach(
        session: AgentSession,
        binding: WorkspaceBinding,
        reference_time: datetime | None = None,
    ) -> tuple[AgentSession, WorkspaceBinding]:
        """Detach an agent session from a workspace.

        Args:
            session: The session to detach.
            binding: The active binding to close.
            reference_time: Deterministic datetime override.

        Returns:
            (Updated session, updated binding).
        """
        now = (reference_time or datetime.now(timezone.utc)).isoformat()

        closed_binding = WorkspaceBinding(
            binding_id=binding.binding_id,
            session_id=binding.session_id,
            workspace_id=binding.workspace_id,
            role=binding.role,
            attached_at=binding.attached_at,
            detached_at=now,
        )

        updated_session = AgentSession(
            session_id=session.session_id,
            profile_id=session.profile_id,
            workspace_id=session.workspace_id,
            status=SessionStatus.DETACHED,
            binding_id=session.binding_id,
            context_id=session.context_id,
            snapshot_id=session.snapshot_id,
            protocol_version=session.protocol_version,
            started_at=session.started_at,
            last_active_at=now,
            ended_at=session.ended_at,
        )

        return updated_session, closed_binding

    @staticmethod
    def create_session(
        profile_id: str,
        workspace_id: str,
        binding: WorkspaceBinding,
        protocol_version: str = "1.0",
        reference_time: datetime | None = None,
    ) -> AgentSession:
        """Create a new agent session.

        Args:
            profile_id: Agent profile ID.
            workspace_id: Target workspace ID.
            binding: Pre-created workspace binding.
            protocol_version: Protocol version.
            reference_time: Deterministic datetime override.

        Returns:
            New AgentSession.
        """
        now = (reference_time or datetime.now(timezone.utc)).isoformat()

        return AgentSession(
            session_id=AgentSession.generate_session_id(
                profile_id, workspace_id, now
            ),
            profile_id=profile_id,
            workspace_id=workspace_id,
            status=SessionStatus.CREATED,
            binding_id=binding.binding_id,
            protocol_version=protocol_version,
            started_at=now,
            last_active_at=now,
        )

    @staticmethod
    def close_session(
        session: AgentSession,
        packages_streamed: int = 0,
        events_emitted: int = 0,
        reference_time: datetime | None = None,
    ) -> AgentSession:
        """Close an agent session.

        Args:
            session: The session to close.
            packages_streamed: Total packages streamed during session.
            events_emitted: Total events emitted during session.
            reference_time: Deterministic datetime override.

        Returns:
            Closed AgentSession.
        """
        now = (reference_time or datetime.now(timezone.utc)).isoformat()

        return AgentSession(
            session_id=session.session_id,
            profile_id=session.profile_id,
            workspace_id=session.workspace_id,
            status=SessionStatus.CLOSED,
            binding_id=session.binding_id,
            context_id=session.context_id,
            snapshot_id=session.snapshot_id,
            protocol_version=session.protocol_version,
            started_at=session.started_at,
            last_active_at=now,
            ended_at=now,
        )
