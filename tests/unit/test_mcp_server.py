from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import UUID

import pytest

try:
    import mcp
    from rationalevault.mcp.server import server
    mcp_installed = True
except ImportError:
    mcp_installed = False

from rationalevault.schema.events import EventMetadata, EventRecord, EventType
from rationalevault.projections.continuation import ContinuationState
from rationalevault.mcp.tools import (
    get_cognitive_head,
    get_context,
    continue_project,
    search_memories,
    search_knowledge,
    get_project_events,
    record_event,
    record_task_progress,
)


def _meta(actor: str = "test-actor", session_id: str = "session-alpha") -> EventMetadata:
    return EventMetadata(
        actor=actor,
        source="test-suite",
        session_id=session_id,
        correlation_id="corr-1",
    )


def _event(
    event_type: EventType,
    payload: dict,
    sequence: int,
    project_id: UUID,
    recorded_at: datetime,
    actor: str = "test-actor",
    session_id: str = "session-alpha",
) -> EventRecord:
    return EventRecord(
        event_sequence=sequence,
        id=uuid.uuid4(),
        project_id=project_id,
        stream_id="main",
        version=sequence,
        event_type=event_type,
        metadata=_meta(actor, session_id),
        payload=payload,
        parent_id=None,
        recorded_at=recorded_at,
    )


@pytest.fixture
def mcp_setup():
    pid = uuid.uuid4()
    recorded_at = datetime.now(timezone.utc)
    
    events = [
        _event(EventType.PROJECT_CREATED, {"name": "Alpha Project"}, 1, pid, recorded_at),
        _event(EventType.PROJECT_GOAL_SET, {"goal": "Build awesome things"}, 2, pid, recorded_at),
        _event(EventType.PROJECT_FOCUS_CHANGED, {"focus": "Sprint 1"}, 3, pid, recorded_at),
        _event(EventType.TASK_CREATED, {"task_id": "t1", "details": {"summary": "Implement MCP server", "body": ""}}, 4, pid, recorded_at),
        _event(EventType.DECISION_PROPOSED, {"decision_id": "d1", "title": "Use mcp SDK", "rationale": "Best SDK available"}, 5, pid, recorded_at),
        _event(EventType.DECISION_ACCEPTED, {"decision_id": "d1"}, 6, pid, recorded_at),
        _event(EventType.TASK_MUTATED, {"task_id": "t1", "status": "in_progress"}, 7, pid, recorded_at),
        _event(EventType.TASK_PROGRESS_NOTED, {"task_id": "t1", "note": "server.py scaffold created"}, 8, pid, recorded_at),
        _event(EventType.OPEN_QUESTION_RAISED, {"question_id": "q1", "title": "Which transport: stdio or SSE?", "priority": "high"}, 9, pid, recorded_at),
        _event(EventType.CONTEXT_SNAPSHOT_RECORDED, {
            "summary": "MCP server 40% done",
            "next_action": "Implement tools.py",
            "blocked_on": "Decision: stdio or SSE?"
        }, 10, pid, recorded_at),
    ]

    mock_store = MagicMock()
    mock_store.get_project_stream.return_value = events
    mock_store.get_recent_events.return_value = events
    mock_store.get_session_events.return_value = events
    mock_store.get_last_session_id.return_value = "session-alpha"
    mock_store.append_event.return_value = events[3]  # dummy TASK_CREATED

    return pid, mock_store, events


@pytest.mark.skipif(not mcp_installed, reason="mcp package not installed")
class TestMCPServerTools:
    @pytest.fixture(autouse=True)
    def patch_event_store(self, mcp_setup, monkeypatch):
        pid, store, _ = mcp_setup
        monkeypatch.setattr("rationalevault.db.event_store.EventStore", lambda: store)
        monkeypatch.setattr("rationalevault.mcp.tools.EventStore", lambda: store)

    def test_get_cognitive_head_tool(self, mcp_setup):
        pid, store, _ = mcp_setup
        res = get_cognitive_head(str(pid))
        assert res["project_name"] == "Alpha Project"
        assert len(res["active_tasks"]) > 0

    def test_get_context_tool(self, mcp_setup):
        pid, store, _ = mcp_setup
        res = get_context("test query", project_id=str(pid))
        assert "citations" in res
        assert "source_counts" in res

    def test_continue_project_tool(self, mcp_setup):
        pid, store, _ = mcp_setup
        res = continue_project(str(pid), agent="claude")
        assert "Where You Left Off" in res
        assert "Latest Context Snapshot" in res

    def test_search_memories_tool(self, monkeypatch):
        mock_c = MagicMock()
        mock_c.to_dict.return_value = {"id": "m1", "title": "Memory Title"}
        monkeypatch.setattr(
            "rationalevault.mcp.tools.retrieve_ranked_citations",
            lambda query, limit: ([mock_c], None)
        )
        res = search_memories("query")
        assert len(res) == 1
        assert res[0]["title"] == "Memory Title"

    def test_search_knowledge_tool(self, monkeypatch):
        mock_c = MagicMock()
        mock_c.to_dict.return_value = {"id": "k1", "title": "Knowledge Title"}
        monkeypatch.setattr(
            "rationalevault.mcp.tools.retrieve_ranked_knowledge_citations",
            lambda query, limit, **kwargs: ([mock_c], None)
        )
        res = search_knowledge("query")
        assert len(res) == 1
        assert res[0]["title"] == "Knowledge Title"

    def test_get_project_events_tool(self, mcp_setup):
        pid, store, _ = mcp_setup
        res = get_project_events(str(pid))
        assert len(res) > 0
        assert "event_sequence" in res[0]

    def test_record_event_tool_success(self, mcp_setup):
        pid, store, _ = mcp_setup
        res = record_event(
            project_id=str(pid),
            stream_id="main",
            event_type="PROJECT_GOAL_SET",
            payload={"goal": "New Goal"},
            actor="test-actor",
            source="test-suite",
        )
        assert res is not None

    def test_record_event_tool_invalid_type(self, mcp_setup):
        pid, store, _ = mcp_setup
        with pytest.raises(ValueError, match="Invalid event_type"):
            record_event(
                project_id=str(pid),
                stream_id="main",
                event_type="INVALID_EVENT_TYPE",
                payload={},
                actor="test-actor",
                source="test-suite",
            )

    def test_record_task_progress_tool(self, mcp_setup):
        pid, store, _ = mcp_setup
        res = record_task_progress(
            project_id=str(pid),
            task_id="t1",
            note="Progress Note",
            actor="test-actor",
            source="test-suite",
        )
        assert res is not None

