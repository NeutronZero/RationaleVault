from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import UUID

import pytest

from rationalevault.compilers.claude_context import ClaudeContextCompiler
from rationalevault.knowledge.context_compiler import compile_context, ContextMode
from rationalevault.projections.continuation import ContinuationProjection, ContinuationState
from rationalevault.schema.events import EventMetadata, EventRecord, EventType


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
def continuation_setup():
    pid = uuid.uuid4()
    recorded_at = datetime.now(timezone.utc)
    
    events = [
        # 1. PROJECT_CREATED
        _event(EventType.PROJECT_CREATED, {"name": "Alpha Project"}, 1, pid, recorded_at),
        # 2. PROJECT_GOAL_SET
        _event(EventType.PROJECT_GOAL_SET, {"goal": "Build awesome things"}, 2, pid, recorded_at),
        # 3. PROJECT_FOCUS_CHANGED
        _event(EventType.PROJECT_FOCUS_CHANGED, {"focus": "Sprint 1"}, 3, pid, recorded_at),
        # 4. TASK_CREATED (t1, "Implement MCP server")
        _event(EventType.TASK_CREATED, {"task_id": "t1", "title": "Implement MCP server"}, 4, pid, recorded_at),
        # 5. DECISION_PROPOSED (d1, "Use mcp SDK", rationale="Best SDK available")
        _event(EventType.DECISION_PROPOSED, {"decision_id": "d1", "title": "Use mcp SDK", "rationale": "Best SDK available"}, 5, pid, recorded_at),
        # 6. DECISION_ACCEPTED (d1)
        _event(EventType.DECISION_ACCEPTED, {"decision_id": "d1"}, 6, pid, recorded_at),
        # 7. TASK_MUTATED (t1, status=in_progress)
        _event(EventType.TASK_MUTATED, {"task_id": "t1", "status": "in_progress"}, 7, pid, recorded_at),
        # 8. TASK_PROGRESS_NOTED (t1, "server.py scaffold created")
        _event(EventType.TASK_PROGRESS_NOTED, {"task_id": "t1", "note": "server.py scaffold created"}, 8, pid, recorded_at),
        # 9. OPEN_QUESTION_RAISED (q1, "Which transport: stdio or SSE?", priority=high)
        _event(EventType.OPEN_QUESTION_RAISED, {"question_id": "q1", "title": "Which transport: stdio or SSE?", "priority": "high"}, 9, pid, recorded_at),
        # 10. CONTEXT_SNAPSHOT_RECORDED
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

    return pid, mock_store, events


# ── 14 Benchmark Tests ─────────────────────────────────────────────────────────

def test_goal_recovered(continuation_setup):
    pid, store, _ = continuation_setup
    state = ContinuationProjection.project(pid, store=store)
    assert state.project_goal == "Build awesome things"


def test_decisions_recovered(continuation_setup):
    pid, store, _ = continuation_setup
    state = ContinuationProjection.project(pid, store=store)
    assert len(state.recent_decisions) > 0
    assert state.recent_decisions[0].title == "Use mcp SDK"


def test_rationale_recovered(continuation_setup):
    pid, store, _ = continuation_setup
    state = ContinuationProjection.project(pid, store=store)
    assert state.recent_decisions[0].rationale == "Best SDK available"


def test_in_progress_tasks_recovered(continuation_setup):
    pid, store, _ = continuation_setup
    state = ContinuationProjection.project(pid, store=store)
    assert len(state.in_progress_tasks) > 0
    assert state.in_progress_tasks[0].title == "Implement MCP server"


def test_progress_notes_recovered(continuation_setup):
    pid, store, _ = continuation_setup
    state = ContinuationProjection.project(pid, store=store)
    task = state.in_progress_tasks[0]
    assert len(task.progress_notes) > 0
    assert task.progress_notes[0]["note"] == "server.py scaffold created"


def test_open_questions_recovered(continuation_setup):
    pid, store, _ = continuation_setup
    state = ContinuationProjection.project(pid, store=store)
    assert len(state.open_questions) > 0
    assert state.open_questions[0].title == "Which transport: stdio or SSE?"


def test_context_snapshot_recovered(continuation_setup):
    pid, store, _ = continuation_setup
    state = ContinuationProjection.project(pid, store=store)
    assert len(state.context_snapshots) > 0
    assert state.context_snapshots[0]["summary"] == "MCP server 40% done"


def test_snapshot_blocked_on_recovered(continuation_setup):
    pid, store, _ = continuation_setup
    state = ContinuationProjection.project(pid, store=store)
    assert state.context_snapshots[0]["blocked_on"] == "Decision: stdio or SSE?"


def test_last_session_recovered(continuation_setup):
    pid, store, _ = continuation_setup
    state = ContinuationProjection.project(pid, store=store)
    assert state.last_session is not None
    assert state.last_session.session_id == "session-alpha"


def test_next_actions_prioritizes_blocked_on(continuation_setup):
    pid, store, _ = continuation_setup
    state = ContinuationProjection.project(pid, store=store)
    assert state.next_actions[0] == "Unblock: Decision: stdio or SSE?"


def test_provenance_populated(continuation_setup):
    pid, store, _ = continuation_setup
    state = ContinuationProjection.project(pid, store=store)
    assert "in_progress_tasks" in state.provenance
    assert len(state.provenance["in_progress_tasks"]) > 0


def test_continuation_mode_in_package(continuation_setup, monkeypatch):
    pid, store, _ = continuation_setup
    monkeypatch.setattr("rationalevault.db.event_store.EventStore", lambda: store)
    
    package = compile_context("continue", project_id=pid, mode=ContextMode.CONTINUATION)
    assert package.mode == "continuation"


def test_continuation_state_in_package(continuation_setup, monkeypatch):
    pid, store, _ = continuation_setup
    monkeypatch.setattr("rationalevault.db.event_store.EventStore", lambda: store)
    
    package = compile_context("continue", project_id=pid, mode=ContextMode.CONTINUATION)
    assert package.continuation_state is not None
    assert package.continuation_state.project_id == str(pid)


def test_where_i_left_off_in_output(continuation_setup, monkeypatch):
    pid, store, _ = continuation_setup
    monkeypatch.setattr("rationalevault.db.event_store.EventStore", lambda: store)
    
    package = compile_context("continue", project_id=pid, mode=ContextMode.CONTINUATION)
    output = ClaudeContextCompiler().compile(package)
    assert "Where You Left Off" in output.rendered_content
