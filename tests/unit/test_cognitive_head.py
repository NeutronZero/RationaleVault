"""
Cognitive Head Compiler unit tests.

Pure unit tests — no database required.
Uses a mock EventStore that returns pre-built event lists.

Coverage:
  - compile_cognitive_head with valid bootstrap → CognitiveHead
  - MissingProjectBootstrapError for empty / incomplete streams
  - Determinism: same events → identical to_dict() output
  - active_tasks excludes completed tasks
  - active_decisions includes only accepted decisions
  - open_questions sorted by priority (critical > high > normal > low)
  - Blockers derived from task.blocked_by and question.blocks_task_ids
  - ledger_version equals max(version) across all events
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock
from uuid import UUID

import pytest

from rationalevault.cognitive_head.compiler import (
    CognitiveHead,
    MissingProjectBootstrapError,
    compile_cognitive_head,
)
from rationalevault.schema.events import EventMetadata, EventRecord, EventType


# ── Helpers ────────────────────────────────────────────────────────────────────

def _meta(actor: str = "Claude") -> EventMetadata:
    return EventMetadata(actor=actor, source="test",
                         correlation_id="c", session_id="s")


def _event(
    event_type: EventType,
    payload: dict[str, Any],
    sequence: int,
    project_id: UUID,
    actor: str = "Claude",
) -> EventRecord:
    return EventRecord(
        event_sequence=sequence,
        id=uuid.uuid4(),
        project_id=project_id,
        stream_id="main",
        version=sequence,
        event_type=event_type,
        metadata=_meta(actor),
        payload=payload,
        parent_id=None,
        recorded_at=datetime.now(timezone.utc),
    )


def _mock_store(events: list[EventRecord]) -> MagicMock:
    store = MagicMock()
    store.get_project_stream.return_value = events
    return store


def _bootstrap(pid: UUID) -> list[EventRecord]:
    """Return minimum valid bootstrap event set."""
    return [
        _event(EventType.PROJECT_CREATED, {"name": "Relay"}, 1, pid),
        _event(EventType.PROJECT_GOAL_SET, {"goal": "Build continuity"}, 2, pid),
        _event(EventType.PROJECT_FOCUS_CHANGED, {"focus": "Event ledger"}, 3, pid),
    ]


# ── Bootstrap validation ───────────────────────────────────────────────────────

class TestBootstrapValidation:
    def test_empty_stream_raises(self):
        pid = uuid.uuid4()
        with pytest.raises(MissingProjectBootstrapError):
            compile_cognitive_head(pid, store=_mock_store([]))

    def test_missing_project_created_raises(self):
        pid = uuid.uuid4()
        events = [
            _event(EventType.PROJECT_GOAL_SET, {"goal": "Goal"}, 1, pid),
            _event(EventType.PROJECT_FOCUS_CHANGED, {"focus": "Focus"}, 2, pid),
        ]
        with pytest.raises(MissingProjectBootstrapError, match="PROJECT_CREATED"):
            compile_cognitive_head(pid, store=_mock_store(events))

    def test_missing_goal_set_raises(self):
        pid = uuid.uuid4()
        events = [
            _event(EventType.PROJECT_CREATED, {"name": "Relay"}, 1, pid),
            _event(EventType.PROJECT_FOCUS_CHANGED, {"focus": "Focus"}, 2, pid),
        ]
        with pytest.raises(MissingProjectBootstrapError, match="PROJECT_GOAL_SET"):
            compile_cognitive_head(pid, store=_mock_store(events))

    def test_missing_focus_changed_raises(self):
        pid = uuid.uuid4()
        events = [
            _event(EventType.PROJECT_CREATED, {"name": "Relay"}, 1, pid),
            _event(EventType.PROJECT_GOAL_SET, {"goal": "Goal"}, 2, pid),
        ]
        with pytest.raises(MissingProjectBootstrapError, match="PROJECT_FOCUS_CHANGED"):
            compile_cognitive_head(pid, store=_mock_store(events))

    def test_valid_bootstrap_compiles_successfully(self):
        pid = uuid.uuid4()
        head = compile_cognitive_head(pid, store=_mock_store(_bootstrap(pid)))
        assert head.project_id == pid
        assert head.project_name == "Relay"
        assert head.project_goal == "Build continuity"
        assert head.current_focus == "Event ledger"


# ── CognitiveHead output ───────────────────────────────────────────────────────

class TestCognitiveHeadOutput:
    def test_ledger_version_is_max_version(self):
        pid = uuid.uuid4()
        events = _bootstrap(pid)  # versions 1, 2, 3
        events.append(_event(EventType.TASK_CREATED, {
            "task_id": "t1", "details": {"summary": "Task", "body": ""}
        }, 4, pid))
        head = compile_cognitive_head(pid, store=_mock_store(events))
        assert head.ledger_version == 4

    def test_active_tasks_excludes_completed(self):
        pid = uuid.uuid4()
        events = _bootstrap(pid) + [
            _event(EventType.TASK_CREATED, {"task_id": "t1", "details": {"summary": "Active", "body": ""}}, 4, pid),
            _event(EventType.TASK_CREATED, {"task_id": "t2", "details": {"summary": "Done", "body": ""}}, 5, pid),
            _event(EventType.TASK_COMPLETED, {"task_id": "t2"}, 6, pid),
        ]
        head = compile_cognitive_head(pid, store=_mock_store(events))
        task_ids = [t.task_id for t in head.active_tasks]
        assert "t1" in task_ids
        assert "t2" not in task_ids

    def test_active_decisions_includes_only_accepted(self):
        pid = uuid.uuid4()
        events = _bootstrap(pid) + [
            _event(EventType.DECISION_PROPOSED, {
                "decision_id": "d1", "title": "D1 proposed only"
            }, 4, pid),
            _event(EventType.DECISION_PROPOSED, {
                "decision_id": "d2", "title": "D2 accepted"
            }, 5, pid),
            _event(EventType.DECISION_ACCEPTED, {"decision_id": "d2"}, 6, pid),
            _event(EventType.DECISION_PROPOSED, {
                "decision_id": "d3", "title": "D3 superseded"
            }, 7, pid),
            _event(EventType.DECISION_ACCEPTED, {"decision_id": "d3"}, 8, pid),
            _event(EventType.DECISION_SUPERSEDED, {"decision_id": "d3"}, 9, pid),
        ]
        head = compile_cognitive_head(pid, store=_mock_store(events))
        decision_ids = [d.decision_id for d in head.active_decisions]
        assert "d2" in decision_ids
        assert "d1" not in decision_ids
        assert "d3" not in decision_ids

    def test_open_questions_excludes_resolved(self):
        pid = uuid.uuid4()
        events = _bootstrap(pid) + [
            _event(EventType.OPEN_QUESTION_RAISED, {
                "question_id": "q1", "title": "Open Q"
            }, 4, pid),
            _event(EventType.OPEN_QUESTION_RAISED, {
                "question_id": "q2", "title": "Resolved Q"
            }, 5, pid),
            _event(EventType.OPEN_QUESTION_RESOLVED, {
                "question_id": "q2", "resolution": "Done"
            }, 6, pid),
        ]
        head = compile_cognitive_head(pid, store=_mock_store(events))
        q_ids = [q.question_id for q in head.open_questions]
        assert "q1" in q_ids
        assert "q2" not in q_ids

    def test_open_questions_sorted_by_priority(self):
        pid = uuid.uuid4()
        events = _bootstrap(pid) + [
            _event(EventType.OPEN_QUESTION_RAISED, {
                "question_id": "q_low", "title": "Low", "priority": "low"
            }, 4, pid),
            _event(EventType.OPEN_QUESTION_RAISED, {
                "question_id": "q_crit", "title": "Critical", "priority": "critical"
            }, 5, pid),
            _event(EventType.OPEN_QUESTION_RAISED, {
                "question_id": "q_high", "title": "High", "priority": "high"
            }, 6, pid),
            _event(EventType.OPEN_QUESTION_RAISED, {
                "question_id": "q_norm", "title": "Normal", "priority": "normal"
            }, 7, pid),
        ]
        head = compile_cognitive_head(pid, store=_mock_store(events))
        priorities = [q.priority for q in head.open_questions]
        assert priorities == ["critical", "high", "normal", "low"]

    def test_active_tasks_sorted_by_priority(self):
        pid = uuid.uuid4()
        events = _bootstrap(pid) + [
            _event(EventType.TASK_CREATED, {
                "task_id": "t_norm", "details": {"summary": "Normal", "body": ""}, "priority": "normal"
            }, 4, pid),
            _event(EventType.TASK_CREATED, {
                "task_id": "t_crit", "details": {"summary": "Critical", "body": ""}, "priority": "critical"
            }, 5, pid),
            _event(EventType.TASK_CREATED, {
                "task_id": "t_low", "details": {"summary": "Low", "body": ""}, "priority": "low"
            }, 6, pid),
        ]
        head = compile_cognitive_head(pid, store=_mock_store(events))
        priorities = [t.priority for t in head.active_tasks]
        assert priorities[0] == "critical"
        assert priorities[-1] == "low"


# ── Blocker detection ──────────────────────────────────────────────────────────

class TestBlockerDetection:
    def test_task_blocked_by_open_question_via_task_field(self):
        pid = uuid.uuid4()
        events = _bootstrap(pid) + [
            _event(EventType.TASK_CREATED, {
                "task_id": "t1", "details": {"summary": "Blocked Task", "body": ""},
                "blocked_by": ["q1"]
            }, 4, pid),
            _event(EventType.OPEN_QUESTION_RAISED, {
                "question_id": "q1", "title": "Blocking Question"
            }, 5, pid),
        ]
        head = compile_cognitive_head(pid, store=_mock_store(events))
        assert len(head.blockers) == 1
        assert head.blockers[0]["task_id"] == "t1"
        assert "q1" in head.blockers[0]["blocked_by_questions"]

    def test_task_blocked_via_question_blocks_task_ids(self):
        pid = uuid.uuid4()
        events = _bootstrap(pid) + [
            _event(EventType.TASK_CREATED, {
                "task_id": "t2", "details": {"summary": "Another Task", "body": ""}
            }, 4, pid),
            _event(EventType.OPEN_QUESTION_RAISED, {
                "question_id": "q2", "title": "Question",
                "blocks_task_ids": ["t2"]
            }, 5, pid),
        ]
        head = compile_cognitive_head(pid, store=_mock_store(events))
        assert len(head.blockers) == 1
        assert head.blockers[0]["task_id"] == "t2"

    def test_resolved_question_does_not_block(self):
        pid = uuid.uuid4()
        events = _bootstrap(pid) + [
            _event(EventType.TASK_CREATED, {
                "task_id": "t1", "details": {"summary": "Task", "body": ""},
                "blocked_by": ["q1"]
            }, 4, pid),
            _event(EventType.OPEN_QUESTION_RAISED, {
                "question_id": "q1", "title": "Question"
            }, 5, pid),
            _event(EventType.OPEN_QUESTION_RESOLVED, {
                "question_id": "q1", "resolution": "Done"
            }, 6, pid),
        ]
        head = compile_cognitive_head(pid, store=_mock_store(events))
        assert len(head.blockers) == 0


# ── Determinism ────────────────────────────────────────────────────────────────

class TestDeterminism:
    def test_same_events_produce_identical_head(self):
        pid = uuid.uuid4()
        events = _bootstrap(pid) + [
            _event(EventType.TASK_CREATED, {"task_id": "t1", "details": {"summary": "Task", "body": ""}}, 4, pid),
            _event(EventType.DECISION_PROPOSED, {"decision_id": "d1", "title": "D1"}, 5, pid),
            _event(EventType.DECISION_ACCEPTED, {"decision_id": "d1"}, 6, pid),
            _event(EventType.OPEN_QUESTION_RAISED, {
                "question_id": "q1", "title": "Q1", "priority": "high"
            }, 7, pid),
        ]

        head1 = compile_cognitive_head(pid, store=_mock_store(events))
        head2 = compile_cognitive_head(pid, store=_mock_store(events))

        d1 = head1.to_dict()
        d2 = head2.to_dict()

        # Exclude compiled_at (wall-clock timestamp)
        d1.pop("compiled_at")
        d2.pop("compiled_at")

        assert d1 == d2, "Compiler is not deterministic!"

    def test_to_dict_is_json_serializable(self):
        import json
        pid = uuid.uuid4()
        head = compile_cognitive_head(pid, store=_mock_store(_bootstrap(pid)))
        # Should not raise
        json.dumps(head.to_dict())
