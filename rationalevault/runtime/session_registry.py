"""RationaleVault Session Registry — Manages active agent sessions.

SessionRegistry tracks all active sessions, enforces single-session-per-agent-per-workspace,
and provides deterministic query capabilities.

Design rules:
  - Pure functions: frozen inputs → new state.
  - No I/O, no mutation.
  - Deterministic: same inputs → identical registry state.
  - Enforces at most one OPEN session per agent per workspace.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rationalevault.runtime.models import AgentSession, SessionStatus


@dataclass(frozen=True)
class SessionRegistry:
    """
    Registry of all agent sessions.

    Immutable snapshot. Mutations produce new registry instances.
    """
    sessions: tuple[AgentSession, ...] = ()
    compiled_at: str = ""

    @property
    def active_sessions(self) -> list[AgentSession]:
        """All sessions that are not CLOSED."""
        return [
            s for s in self.sessions
            if s.status not in (SessionStatus.CLOSED,)
        ]

    @property
    def active_count(self) -> int:
        return len(self.active_sessions)

    def get_session(self, session_id: str) -> AgentSession | None:
        """Get a session by ID."""
        for s in self.sessions:
            if s.session_id == session_id:
                return s
        return None

    def get_agent_sessions(
        self, agent_id: str, workspace_id: str | None = None
    ) -> list[AgentSession]:
        """Get all sessions for an agent, optionally filtered by workspace."""
        results = []
        for s in self.sessions:
            if s.profile_id == agent_id:
                if workspace_id is None or s.workspace_id == workspace_id:
                    results.append(s)
        return results

    def has_open_session(self, agent_id: str, workspace_id: str) -> bool:
        """Check if an agent already has an OPEN session in a workspace."""
        for s in self.sessions:
            if (s.profile_id == agent_id
                    and s.workspace_id == workspace_id
                    and s.status in (SessionStatus.CREATED, SessionStatus.ATTACHED,
                                     SessionStatus.STREAMING, SessionStatus.RESUMED)):
                return True
        return False

    def get_workspace_sessions(self, workspace_id: str) -> list[AgentSession]:
        """Get all sessions for a workspace."""
        return [s for s in self.sessions if s.workspace_id == workspace_id]

    def add_session(self, session: AgentSession) -> SessionRegistry:
        """Return a new registry with the session added."""
        return SessionRegistry(
            sessions=self.sessions + (session,),
            compiled_at=self.compiled_at,
        )

    def update_session(self, session: AgentSession) -> SessionRegistry:
        """Return a new registry with the session updated (matched by session_id)."""
        updated = tuple(
            session if s.session_id == session.session_id else s
            for s in self.sessions
        )
        return SessionRegistry(
            sessions=updated,
            compiled_at=self.compiled_at,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_count": len(self.sessions),
            "active_count": self.active_count,
            "sessions": [s.to_dict() for s in self.sessions],
            "compiled_at": self.compiled_at,
        }
