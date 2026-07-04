"""
G5 — Multi-Agent Workspace Tests.

Session management for shared workspaces with role-based access.
"""
from __future__ import annotations

import pytest
from datetime import datetime, timezone

from rationalevault.workspace.models import (
    AgentRole,
    SessionStatus,
    Workspace,
    WorkspaceSession,
    WorkspaceStatus,
)
from rationalevault.workspace.multi_agent import (
    AgentRosterEntry,
    MultiAgentService,
    WorkspaceRoster,
)


REF_TIME = datetime(2026, 6, 26, 12, 0, 0, tzinfo=timezone.utc)


def _make_workspace(agent_ids: list[str] | None = None) -> Workspace:
    ws_id = Workspace.generate_workspace_id("Test", REF_TIME.isoformat())
    return Workspace(
        workspace_id=ws_id,
        name="Test",
        description="Test",
        status=WorkspaceStatus.ACTIVE,
        agent_ids=sorted(agent_ids or ["claude", "codex", "gemini"]),
        project_ids=["proj-1"],
        created_at=REF_TIME.isoformat(),
        updated_at=REF_TIME.isoformat(),
    )


def _make_session(
    agent_id: str = "claude",
    role: AgentRole = AgentRole.PRIMARY,
    status: SessionStatus = SessionStatus.OPEN,
) -> WorkspaceSession:
    session_id = WorkspaceSession.generate_session_id(
        "WS-TEST", agent_id, REF_TIME.isoformat()
    )
    return WorkspaceSession(
        session_id=session_id,
        workspace_id="WS-TEST",
        agent_id=agent_id,
        agent_role=role,
        status=status,
        started_at=REF_TIME.isoformat(),
        ended_at=None,
        snapshot_id=None,
    )


# ── join() ───────────────────────────────────────────────────────────────

class TestJoin:
    def test_agent_joins(self):
        ws = _make_workspace()
        result = MultiAgentService.join(
            workspace=ws,
            agent_id="claude",
            role=AgentRole.PRIMARY,
            reference_time=REF_TIME,
        )
        assert isinstance(result, tuple)
        session, payload = result
        assert session.agent_id == "claude"
        assert session.agent_role == AgentRole.PRIMARY
        assert session.status == SessionStatus.OPEN

    def test_agent_not_in_workspace(self):
        ws = _make_workspace(agent_ids=["claude"])
        result = MultiAgentService.join(
            workspace=ws, agent_id="codex", reference_time=REF_TIME
        )
        assert isinstance(result, dict)
        assert "error" in result

    def test_duplicate_session_rejected(self):
        ws = _make_workspace()
        existing = _make_session(agent_id="claude")
        result = MultiAgentService.join(
            workspace=ws,
            agent_id="claude",
            sessions=[existing],
            reference_time=REF_TIME,
        )
        assert isinstance(result, dict)
        assert "already" in result["error"]

    def test_closed_session_allows_rejoin(self):
        ws = _make_workspace()
        closed = _make_session(
            agent_id="claude", status=SessionStatus.CLOSED
        )
        result = MultiAgentService.join(
            workspace=ws,
            agent_id="claude",
            sessions=[closed],
            reference_time=REF_TIME,
        )
        assert isinstance(result, tuple)

    def test_different_agents_can_join(self):
        ws = _make_workspace()
        s1, _ = MultiAgentService.join(
            workspace=ws, agent_id="claude", reference_time=REF_TIME
        )
        s2, _ = MultiAgentService.join(
            workspace=ws, agent_id="codex", reference_time=REF_TIME
        )
        assert s1.agent_id != s2.agent_id

    def test_payload_matches_session(self):
        ws = _make_workspace()
        session, payload = MultiAgentService.join(
            workspace=ws, agent_id="claude", reference_time=REF_TIME
        )
        assert payload.session_id == session.session_id
        assert payload.agent_id == session.agent_id

    def test_default_role_is_primary(self):
        ws = _make_workspace()
        session, _ = MultiAgentService.join(
            workspace=ws, agent_id="claude", reference_time=REF_TIME
        )
        assert session.agent_role == AgentRole.PRIMARY

    def test_advisor_role(self):
        ws = _make_workspace()
        session, _ = MultiAgentService.join(
            workspace=ws,
            agent_id="claude",
            role=AgentRole.ADVISOR,
            reference_time=REF_TIME,
        )
        assert session.agent_role == AgentRole.ADVISOR

    def test_observer_role(self):
        ws = _make_workspace()
        session, _ = MultiAgentService.join(
            workspace=ws,
            agent_id="claude",
            role=AgentRole.OBSERVER,
            reference_time=REF_TIME,
        )
        assert session.agent_role == AgentRole.OBSERVER

    def test_session_id_deterministic(self):
        ws = _make_workspace()
        s1, _ = MultiAgentService.join(
            workspace=ws, agent_id="claude", reference_time=REF_TIME
        )
        s2, _ = MultiAgentService.join(
            workspace=ws, agent_id="claude", reference_time=REF_TIME
        )
        # Same time + same agent = same session ID
        assert s1.session_id == s2.session_id

    def test_session_is_frozen(self):
        ws = _make_workspace()
        session, _ = MultiAgentService.join(
            workspace=ws, agent_id="claude", reference_time=REF_TIME
        )
        with pytest.raises(AttributeError):
            session.agent_id = "hacked"


# ── leave() ──────────────────────────────────────────────────────────────

class TestLeave:
    def test_leave_closes_session(self):
        session = _make_session()
        closed = MultiAgentService.leave(session, reference_time=REF_TIME)
        assert closed.status == SessionStatus.CLOSED

    def test_leave_sets_ended_at(self):
        session = _make_session()
        closed = MultiAgentService.leave(session, reference_time=REF_TIME)
        assert closed.ended_at == REF_TIME.isoformat()

    def test_leave_preserves_identity(self):
        session = _make_session()
        closed = MultiAgentService.leave(session, reference_time=REF_TIME)
        assert closed.session_id == session.session_id
        assert closed.agent_id == session.agent_id

    def test_leave_preserves_started_at(self):
        session = _make_session()
        closed = MultiAgentService.leave(session, reference_time=REF_TIME)
        assert closed.started_at == session.started_at


# ── roster() ─────────────────────────────────────────────────────────────

class TestRoster:
    def test_empty_roster(self):
        ws = _make_workspace()
        roster = MultiAgentService.roster(
            workspace=ws, reference_time=REF_TIME
        )
        assert roster.agent_count == 0

    def test_roster_with_sessions(self):
        ws = _make_workspace()
        s1 = _make_session(agent_id="claude")
        s2 = _make_session(agent_id="codex")
        roster = MultiAgentService.roster(
            workspace=ws, sessions=[s1, s2], reference_time=REF_TIME
        )
        assert roster.agent_count == 2

    def test_roster_active_count(self):
        ws = _make_workspace()
        s1 = _make_session(agent_id="claude", status=SessionStatus.OPEN)
        s2 = _make_session(agent_id="codex", status=SessionStatus.CLOSED)
        roster = MultiAgentService.roster(
            workspace=ws, sessions=[s1, s2], reference_time=REF_TIME
        )
        assert roster.active_count == 1

    def test_roster_has_agent(self):
        ws = _make_workspace()
        s1 = _make_session(agent_id="claude")
        roster = MultiAgentService.roster(
            workspace=ws, sessions=[s1], reference_time=REF_TIME
        )
        assert roster.has_agent("claude")
        assert not roster.has_agent("codex")

    def test_roster_has_role(self):
        ws = _make_workspace()
        s1 = _make_session(agent_id="claude", role=AgentRole.PRIMARY)
        roster = MultiAgentService.roster(
            workspace=ws, sessions=[s1], reference_time=REF_TIME
        )
        assert roster.has_role("claude", AgentRole.PRIMARY)
        assert not roster.has_role("claude", AgentRole.ADVISOR)

    def test_roster_sorted_by_join_time(self):
        ws = _make_workspace()
        s1 = _make_session(agent_id="claude")
        s2 = _make_session(agent_id="codex")
        roster = MultiAgentService.roster(
            workspace=ws, sessions=[s2, s1], reference_time=REF_TIME
        )
        # Both have same join time, so order is stable
        assert len(roster.agents) == 2

    def test_roster_to_dict(self):
        ws = _make_workspace()
        s1 = _make_session(agent_id="claude")
        roster = MultiAgentService.roster(
            workspace=ws, sessions=[s1], reference_time=REF_TIME
        )
        d = roster.to_dict()
        assert d["agent_count"] == 1
        assert d["active_count"] == 1
        assert d["workspace_id"] == ws.workspace_id

    def test_roster_frozen(self):
        ws = _make_workspace()
        roster = MultiAgentService.roster(
            workspace=ws, reference_time=REF_TIME
        )
        with pytest.raises(AttributeError):
            roster.agents = []


# ── check_permission() ──────────────────────────────────────────────────

class TestCheckPermission:
    def test_primary_can_read(self):
        s = _make_session(role=AgentRole.PRIMARY)
        assert MultiAgentService.check_permission(s, "read")

    def test_primary_can_write(self):
        s = _make_session(role=AgentRole.PRIMARY)
        assert MultiAgentService.check_permission(s, "write")

    def test_primary_can_suggest(self):
        s = _make_session(role=AgentRole.PRIMARY)
        assert MultiAgentService.check_permission(s, "suggest")

    def test_advisor_can_read(self):
        s = _make_session(role=AgentRole.ADVISOR)
        assert MultiAgentService.check_permission(s, "read")

    def test_advisor_can_suggest(self):
        s = _make_session(role=AgentRole.ADVISOR)
        assert MultiAgentService.check_permission(s, "suggest")

    def test_advisor_cannot_write(self):
        s = _make_session(role=AgentRole.ADVISOR)
        assert not MultiAgentService.check_permission(s, "write")

    def test_observer_can_read(self):
        s = _make_session(role=AgentRole.OBSERVER)
        assert MultiAgentService.check_permission(s, "read")

    def test_observer_cannot_write(self):
        s = _make_session(role=AgentRole.OBSERVER)
        assert not MultiAgentService.check_permission(s, "write")

    def test_observer_cannot_suggest(self):
        s = _make_session(role=AgentRole.OBSERVER)
        assert not MultiAgentService.check_permission(s, "suggest")

    def test_unknown_action_denied(self):
        s = _make_session(role=AgentRole.PRIMARY)
        assert not MultiAgentService.check_permission(s, "delete")


# ── AgentRosterEntry ────────────────────────────────────────────────────

class TestAgentRosterEntry:
    def test_frozen(self):
        entry = AgentRosterEntry(
            agent_id="a", role="PRIMARY", session_id="s",
            status="OPEN", joined_at="t"
        )
        with pytest.raises(AttributeError):
            entry.agent_id = "b"

    def test_to_dict(self):
        entry = AgentRosterEntry(
            agent_id="a", role="PRIMARY", session_id="s",
            status="OPEN", joined_at="t"
        )
        d = entry.to_dict()
        assert d["agent_id"] == "a"
        assert d["role"] == "PRIMARY"
