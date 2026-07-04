"""RationaleVault Multi-Agent Workspace — Session management for shared workspaces.

Multiple agents (Claude, Codex, Gemini, OpenCode, Human) share:
  - Planner policy
  - Memory
  - Lineage
  - Knowledge

Without sharing:
  - Temporary context (each agent gets its own WorkspaceContext)

Design rules:
  - WorkspaceSession tracks each agent's interaction.
  - Roles: PRIMARY (read/write), ADVISOR (suggest), OBSERVER (read-only).
  - Session lifecycle: join → work → leave.
  - Deterministic: same inputs → identical session state.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from rationalevault.workspace.events import WorkspaceSessionOpenedPayload
from rationalevault.workspace.models import (
    AgentRole,
    SessionStatus,
    Workspace,
    WorkspaceSession,
)


# ── Roster Entry ─────────────────────────────────────────────────────────

@dataclass(frozen=True)
class AgentRosterEntry:
    """An agent's status in a workspace."""
    agent_id: str
    role: str
    session_id: str
    status: str
    joined_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "role": self.role,
            "session_id": self.session_id,
            "status": self.status,
            "joined_at": self.joined_at,
        }


# ── Workspace Roster ─────────────────────────────────────────────────────

@dataclass(frozen=True)
class WorkspaceRoster:
    """Snapshot of all agents in a workspace."""
    workspace_id: str
    compiled_at: str
    agents: list[AgentRosterEntry] = field(default_factory=list)

    @property
    def active_agents(self) -> list[AgentRosterEntry]:
        return [a for a in self.agents if a.status == SessionStatus.OPEN.value]

    @property
    def agent_count(self) -> int:
        return len(self.agents)

    @property
    def active_count(self) -> int:
        return len(self.active_agents)

    def has_agent(self, agent_id: str) -> bool:
        return any(a.agent_id == agent_id for a in self.agents)

    def has_role(self, agent_id: str, role: AgentRole) -> bool:
        return any(
            a.agent_id == agent_id and a.role == role.value
            for a in self.agents
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "workspace_id": self.workspace_id,
            "compiled_at": self.compiled_at,
            "agents": [a.to_dict() for a in self.agents],
            "agent_count": self.agent_count,
            "active_count": self.active_count,
        }


# ── MultiAgentService ────────────────────────────────────────────────────

class MultiAgentService:
    """Service for managing multi-agent workspace sessions.

    Pure functions: frozen inputs → (frozen output, event_payload).
    """

    @staticmethod
    def join(
        workspace: Workspace,
        agent_id: str,
        role: AgentRole = AgentRole.PRIMARY,
        sessions: list[WorkspaceSession] | None = None,
        reference_time: datetime | None = None,
    ) -> tuple[WorkspaceSession, WorkspaceSessionOpenedPayload] | dict[str, str]:
        """Agent joins a workspace.

        Args:
            workspace: The workspace to join.
            agent_id: Agent identifier.
            role: Agent role (PRIMARY, ADVISOR, OBSERVER).
            sessions: Current sessions in the workspace (for duplicate check).
            reference_time: Deterministic datetime override.

        Returns:
            (WorkspaceSession, WorkspaceSessionOpenedPayload) or error dict.
        """
        now = (reference_time or datetime.now(timezone.utc)).isoformat()

        # Check if agent already has an open session
        sessions = sessions or []
        for s in sessions:
            if s.agent_id == agent_id and s.status == SessionStatus.OPEN.value:
                return {"error": f"Agent {agent_id} already has an open session"}

        # Check if agent is in workspace agent_ids
        if agent_id not in workspace.agent_ids:
            return {"error": f"Agent {agent_id} is not in workspace agent list"}

        session_id = WorkspaceSession.generate_session_id(
            workspace.workspace_id, agent_id, now
        )

        session = WorkspaceSession(
            session_id=session_id,
            workspace_id=workspace.workspace_id,
            agent_id=agent_id,
            agent_role=role,
            status=SessionStatus.OPEN,
            started_at=now,
            ended_at=None,
            snapshot_id=None,
        )

        payload = WorkspaceSessionOpenedPayload(
            session_id=session_id,
            workspace_id=workspace.workspace_id,
            agent_id=agent_id,
            agent_role=role.value,
            snapshot_id=None,
            created_at=now,
        )

        return session, payload

    @staticmethod
    def leave(
        session: WorkspaceSession,
        reference_time: datetime | None = None,
    ) -> WorkspaceSession:
        """Agent leaves a workspace (close session).

        Args:
            session: The session to close.
            reference_time: Deterministic datetime override.

        Returns:
            Closed WorkspaceSession.
        """
        now = (reference_time or datetime.now(timezone.utc)).isoformat()

        return WorkspaceSession(
            session_id=session.session_id,
            workspace_id=session.workspace_id,
            agent_id=session.agent_id,
            agent_role=session.agent_role,
            status=SessionStatus.CLOSED,
            started_at=session.started_at,
            ended_at=now,
            snapshot_id=session.snapshot_id,
        )

    @staticmethod
    def roster(
        workspace: Workspace,
        sessions: list[WorkspaceSession] | None = None,
        reference_time: datetime | None = None,
    ) -> WorkspaceRoster:
        """Build a roster of agents in the workspace.

        Args:
            workspace: The workspace.
            sessions: All sessions (open and closed).
            reference_time: Deterministic datetime override.

        Returns:
            WorkspaceRoster snapshot.
        """
        now = (reference_time or datetime.now(timezone.utc)).isoformat()
        sessions = sessions or []

        entries = []
        for s in sessions:
            entries.append(AgentRosterEntry(
                agent_id=s.agent_id,
                role=s.agent_role.value if hasattr(s.agent_role, 'value') else s.agent_role,
                session_id=s.session_id,
                status=s.status.value if hasattr(s.status, 'value') else s.status,
                joined_at=s.started_at,
            ))

        # Sort by join time for determinism
        entries.sort(key=lambda e: e.joined_at)

        return WorkspaceRoster(
            workspace_id=workspace.workspace_id,
            compiled_at=now,
            agents=entries,
        )

    @staticmethod
    def check_permission(
        session: WorkspaceSession,
        action: str = "read",
    ) -> bool:
        """Check if an agent session has permission for an action.

        Roles:
          - PRIMARY: read + write + suggest
          - ADVISOR: read + suggest
          - OBSERVER: read only

        Args:
            session: The agent session.
            action: The action to check ("read", "write", "suggest").

        Returns:
            True if permitted.
        """
        role = session.agent_role
        if isinstance(role, AgentRole):
            role = role.value

        if action == "read":
            return True  # All roles can read
        elif action == "suggest":
            return role in (AgentRole.PRIMARY.value, AgentRole.ADVISOR.value)
        elif action == "write":
            return role == AgentRole.PRIMARY.value

        return False
