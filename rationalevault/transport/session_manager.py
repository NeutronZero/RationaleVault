"""RationaleVault Transport Session Manager — Manages active transport sessions.

TransportSessionManager tracks all active transport sessions, enforces constraints,
and provides deterministic query capabilities.

Design rules:
  - Pure functions: frozen inputs → new state.
  - No I/O, no mutation.
  - Deterministic: same inputs → identical state.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rationalevault.transport.models import (
    TransportSession,
    TransportStatus,
)


@dataclass(frozen=True)
class TransportSessionManager:
    """Registry of all transport sessions."""
    sessions: tuple[TransportSession, ...] = ()
    compiled_at: str = ""

    @property
    def active_sessions(self) -> list[TransportSession]:
        """All sessions that are not CLOSED."""
        return [
            s for s in self.sessions
            if s.status not in (TransportStatus.CLOSED,)
        ]

    @property
    def active_count(self) -> int:
        return len(self.active_sessions)

    def get_session(self, session_id: str) -> TransportSession | None:
        """Get a session by ID."""
        for s in self.sessions:
            if s.session_id == session_id:
                return s
        return None

    def get_by_agent_session(self, agent_session_id: str) -> TransportSession | None:
        """Get a transport session by its associated agent session ID."""
        for s in self.sessions:
            if s.agent_session_id == agent_session_id:
                return s
        return None

    def get_by_workspace(self, workspace_id: str) -> list[TransportSession]:
        """Get all sessions for a workspace."""
        return [s for s in self.sessions if s.workspace_id == workspace_id]

    def get_by_transport(self, transport_manifest_id: str) -> list[TransportSession]:
        """Get all sessions for a specific transport."""
        return [s for s in self.sessions if s.transport_manifest_id == transport_manifest_id]

    def has_active_session(self, agent_session_id: str) -> bool:
        """Check if an agent session already has an active transport session."""
        for s in self.sessions:
            if (s.agent_session_id == agent_session_id
                    and s.status != TransportStatus.CLOSED):
                return True
        return False

    def add_session(self, session: TransportSession) -> TransportSessionManager:
        """Return a new manager with the session added."""
        return TransportSessionManager(
            sessions=self.sessions + (session,),
            compiled_at=self.compiled_at,
        )

    def update_session(self, session: TransportSession) -> TransportSessionManager:
        """Return a new manager with the session updated."""
        updated = tuple(
            session if s.session_id == session.session_id else s
            for s in self.sessions
        )
        return TransportSessionManager(
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
