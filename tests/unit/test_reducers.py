"""
State Reducer unit tests.

Pure unit tests — no database required.
Reducers operate on lists of EventRecord; we construct them in-place.

Coverage:
  ProjectReducer: bootstrap, focus override, unknown events ignored
  TaskReducer:    full lifecycle, multi-task, field-level mutation, missing task_id
  DecisionReducer: lifecycle, supersede chain
  QuestionReducer: raised/resolved, priority preserved
  Determinism: same events → same state (all reducers)
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import pytest

from relay.cognitive_head.reducers import (
    DecisionReducer,
    DecisionState,
    ProjectReducer,
    QuestionReducer,
    QuestionState,
    TaskReducer,
    TaskState,
)
from relay.schema.events import EventMetadata, EventRecord, EventType


# ── Test helpers ───────────────────────────────────────────────────────────────

def _meta(actor: str = "Claude") -> EventMetadata:
    return EventMetadata(actor=actor, source="test",
                         correlation_id="test-corr", session_id="test-sess")


def _event(
    event_type: EventType,
    payload: dict[str, Any],
    sequence: int = 1,
    project_id: UUID | None = None,
    actor: str = "Claude",
) -> EventRecord:
    return EventRecord(
        event_sequence=sequence,
        id=uuid.uuid4(),
        project_id=project_id or uuid.uuid4(),
        stream_id="main",
        version=sequence,
        event_type=event_type,
        metadata=_meta(actor),
        payload=payload,
        parent_id=None,
        recorded_at=datetime.now(timezone.utc),
    )


# ── ProjectReducer ─────────────────────────────────────────────────────────────

class TestProjectReducer:
    def test_reduces_full_bootstrap(self):
        pid = uuid.uuid4()
        events = [
            _event(EventType.PROJECT_CREATED, {"name": "Relay"}, 1, pid),
            _event(EventType.PROJECT_GOAL_SET, {"goal": "Build continuity"}, 2, pid),
            _event(EventType.PROJECT_FOCUS_CHANGED, {"focus": "Event ledger"}, 3, pid),
        ]
        state = ProjectReducer.reduce(events)
        assert state.name == "Relay"
        assert state.goal == "Build continuity"
        assert state.current_focus == "Event ledger"
        assert state.created_by == "Claude"

    def test_later_focus_change_overwrites_earlier(self):
        pid = uuid.uuid4()
        events = [
            _event(EventType.PROJECT_CREATED, {"name": "Relay"}, 1, pid),
            _event(EventType.PROJECT_GOAL_SET, {"goal": "Goal"}, 2, pid),
            _event(EventType.PROJECT_FOCUS_CHANGED, {"focus": "First"}, 3, pid),
            _event(EventType.PROJECT_FOCUS_CHANGED, {"focus": "Second"}, 4, pid),
            _event(EventType.PROJECT_FOCUS_CHANGED, {"focus": "Third"}, 5, pid),
        ]
        state = ProjectReducer.reduce(events)
        assert state.current_focus == "Third"

    def test_later_goal_set_overwrites_earlier(self):
        pid = uuid.uuid4()
        events = [
            _event(EventType.PROJECT_CREATED, {"name": "Relay"}, 1, pid),
            _event(EventType.PROJECT_GOAL_SET, {"goal": "First goal"}, 2, pid),
            _event(EventType.PROJECT_FOCUS_CHANGED, {"focus": "Focus"}, 3, pid),
            _event(EventType.PROJECT_GOAL_SET, {"goal": "Revised goal"}, 4, pid),
        ]
        state = ProjectReducer.reduce(events)
        assert state.goal == "Revised goal"

    def test_unknown_events_are_silently_ignored(self):
        pid = uuid.uuid4()
        events = [
            _event(EventType.PROJECT_CREATED, {"name": "Relay"}, 1, pid),
            _event(EventType.PROJECT_GOAL_SET, {"goal": "Goal"}, 2, pid),
            _event(EventType.PROJECT_FOCUS_CHANGED, {"focus": "Focus"}, 3, pid),
            _event(EventType.TASK_CREATED, {"task_id": "t1", "title": "Task"}, 4, pid),
            _event(EventType.DECISION_PROPOSED, {"decision_id": "d1", "title": "D"}, 5, pid),
            _event(EventType.FACT_RECORDED, {"fact_id": "f1", "content": "Fact"}, 6, pid),
        ]
        state = ProjectReducer.reduce(events)
        assert state.name == "Relay"
        assert state.goal == "Goal"
        assert state.current_focus == "Focus"

    def test_empty_stream_returns_default_state(self):
        state = ProjectReducer.reduce([])
        assert state.name == ""
        assert state.goal == ""
        assert state.current_focus == ""

    def test_created_by_set_from_actor(self):
        pid = uuid.uuid4()
        events = [
            _event(EventType.PROJECT_CREATED, {"name": "Relay"}, 1, pid, actor="Human"),
            _event(EventType.PROJECT_GOAL_SET, {"goal": "Goal"}, 2, pid),
            _event(EventType.PROJECT_FOCUS_CHANGED, {"focus": "Focus"}, 3, pid),
        ]
        state = ProjectReducer.reduce(events)
        assert state.created_by == "Human"


# ── TaskReducer ────────────────────────────────────────────────────────────────

class TestTaskReducer:
    def test_task_created(self):
        events = [_event(EventType.TASK_CREATED, {
            "task_id": "t1", "title": "Write EventStore",
            "priority": "high", "tags": ["core"]
        }, 1)]
        tasks = TaskReducer.reduce(events)
        assert "t1" in tasks
        assert tasks["t1"].title == "Write EventStore"
        assert tasks["t1"].priority == "high"
        assert tasks["t1"].tags == ["core"]
        assert tasks["t1"].status == "open"

    def test_task_mutated_updates_specified_fields_only(self):
        events = [
            _event(EventType.TASK_CREATED, {
                "task_id": "t1", "title": "Original", "priority": "low"
            }, 1),
            _event(EventType.TASK_MUTATED, {
                "task_id": "t1", "priority": "critical", "status": "in_progress"
            }, 2),
        ]
        tasks = TaskReducer.reduce(events)
        assert tasks["t1"].title == "Original"       # unchanged
        assert tasks["t1"].priority == "critical"    # updated
        assert tasks["t1"].status == "in_progress"   # updated

    def test_task_completed(self):
        events = [
            _event(EventType.TASK_CREATED, {"task_id": "t1", "title": "Task"}, 1),
            _event(EventType.TASK_COMPLETED, {"task_id": "t1"}, 2),
        ]
        tasks = TaskReducer.reduce(events)
        assert tasks["t1"].status == "completed"
        assert tasks["t1"].completed_at is not None

    def test_full_lifecycle_open_to_completed(self):
        events = [
            _event(EventType.TASK_CREATED, {"task_id": "t1", "title": "Task"}, 1),
            _event(EventType.TASK_MUTATED, {"task_id": "t1", "status": "in_progress"}, 2),
            _event(EventType.TASK_MUTATED, {"task_id": "t1", "assignee": "Claude"}, 3),
            _event(EventType.TASK_COMPLETED, {"task_id": "t1"}, 4),
        ]
        tasks = TaskReducer.reduce(events)
        assert tasks["t1"].status == "completed"
        assert tasks["t1"].assignee == "Claude"

    def test_multiple_tasks_tracked_independently(self):
        events = [
            _event(EventType.TASK_CREATED, {"task_id": "t1", "title": "Task 1"}, 1),
            _event(EventType.TASK_CREATED, {"task_id": "t2", "title": "Task 2"}, 2),
            _event(EventType.TASK_COMPLETED, {"task_id": "t1"}, 3),
        ]
        tasks = TaskReducer.reduce(events)
        assert tasks["t1"].status == "completed"
        assert tasks["t2"].status == "open"

    def test_missing_task_id_in_created_skipped(self):
        events = [_event(EventType.TASK_CREATED, {"title": "No ID"}, 1)]
        tasks = TaskReducer.reduce(events)
        assert len(tasks) == 0

    def test_mutate_unknown_task_id_skipped(self):
        events = [
            _event(EventType.TASK_MUTATED, {"task_id": "nonexistent", "status": "completed"}, 1)
        ]
        tasks = TaskReducer.reduce(events)
        assert "nonexistent" not in tasks

    def test_blocked_by_preserved(self):
        events = [_event(EventType.TASK_CREATED, {
            "task_id": "t1", "title": "Task",
            "blocked_by": ["q1", "q2"]
        }, 1)]
        tasks = TaskReducer.reduce(events)
        assert tasks["t1"].blocked_by == ["q1", "q2"]

    def test_determinism(self):
        events = [
            _event(EventType.TASK_CREATED, {"task_id": "t1", "title": "Task"}, 1),
            _event(EventType.TASK_MUTATED, {"task_id": "t1", "status": "in_progress"}, 2),
        ]
        state_a = TaskReducer.reduce(events)
        state_b = TaskReducer.reduce(events)
        assert state_a["t1"].status == state_b["t1"].status
        assert state_a["t1"].title == state_b["t1"].title


# ── DecisionReducer ────────────────────────────────────────────────────────────

class TestDecisionReducer:
    def test_decision_proposed(self):
        events = [_event(EventType.DECISION_PROPOSED, {
            "decision_id": "d1",
            "title": "Use psycopg3",
            "rationale": "Simpler",
        }, 1)]
        decisions = DecisionReducer.reduce(events)
        assert decisions["d1"].status == "proposed"
        assert decisions["d1"].rationale == "Simpler"

    def test_decision_accepted(self):
        events = [
            _event(EventType.DECISION_PROPOSED, {
                "decision_id": "d1", "title": "Use psycopg3"
            }, 1),
            _event(EventType.DECISION_ACCEPTED, {"decision_id": "d1"}, 2),
        ]
        decisions = DecisionReducer.reduce(events)
        assert decisions["d1"].status == "accepted"
        assert decisions["d1"].accepted_at is not None

    def test_decision_superseded(self):
        events = [
            _event(EventType.DECISION_PROPOSED, {
                "decision_id": "d1", "title": "Use asyncpg"
            }, 1),
            _event(EventType.DECISION_ACCEPTED, {"decision_id": "d1"}, 2),
            _event(EventType.DECISION_PROPOSED, {
                "decision_id": "d2", "title": "Use psycopg3"
            }, 3),
            _event(EventType.DECISION_ACCEPTED, {"decision_id": "d2"}, 4),
            _event(EventType.DECISION_SUPERSEDED, {
                "decision_id": "d1", "superseded_by": "d2"
            }, 5),
        ]
        decisions = DecisionReducer.reduce(events)
        assert decisions["d1"].status == "superseded"
        assert decisions["d1"].superseded_by == "d2"
        assert decisions["d2"].status == "accepted"

    def test_accept_unknown_decision_skipped(self):
        events = [_event(EventType.DECISION_ACCEPTED, {"decision_id": "unknown"}, 1)]
        decisions = DecisionReducer.reduce(events)
        assert "unknown" not in decisions

    def test_missing_decision_id_skipped(self):
        events = [_event(EventType.DECISION_PROPOSED, {"title": "No ID"}, 1)]
        decisions = DecisionReducer.reduce(events)
        assert len(decisions) == 0

    def test_determinism(self):
        events = [
            _event(EventType.DECISION_PROPOSED, {"decision_id": "d1", "title": "D1"}, 1),
            _event(EventType.DECISION_ACCEPTED, {"decision_id": "d1"}, 2),
        ]
        a = DecisionReducer.reduce(events)
        b = DecisionReducer.reduce(events)
        assert a["d1"].status == b["d1"].status


# ── QuestionReducer ────────────────────────────────────────────────────────────

class TestQuestionReducer:
    def test_question_raised(self):
        events = [_event(EventType.OPEN_QUESTION_RAISED, {
            "question_id": "q1",
            "title": "Which DB driver?",
            "priority": "high",
            "blocks_task_ids": ["t1", "t2"],
        }, 1)]
        questions = QuestionReducer.reduce(events)
        assert questions["q1"].status == "open"
        assert questions["q1"].priority == "high"
        assert questions["q1"].blocks_task_ids == ["t1", "t2"]

    def test_question_resolved(self):
        events = [
            _event(EventType.OPEN_QUESTION_RAISED, {
                "question_id": "q1", "title": "Which driver?"
            }, 1),
            _event(EventType.OPEN_QUESTION_RESOLVED, {
                "question_id": "q1",
                "resolution": "psycopg3 — simpler for V1",
            }, 2),
        ]
        questions = QuestionReducer.reduce(events)
        assert questions["q1"].status == "resolved"
        assert "psycopg3" in questions["q1"].resolution
        assert questions["q1"].resolved_at is not None

    def test_multiple_questions(self):
        events = [
            _event(EventType.OPEN_QUESTION_RAISED, {
                "question_id": "q1", "title": "Q1", "priority": "critical"
            }, 1),
            _event(EventType.OPEN_QUESTION_RAISED, {
                "question_id": "q2", "title": "Q2", "priority": "low"
            }, 2),
            _event(EventType.OPEN_QUESTION_RESOLVED, {
                "question_id": "q1", "resolution": "Resolved"
            }, 3),
        ]
        questions = QuestionReducer.reduce(events)
        assert questions["q1"].status == "resolved"
        assert questions["q2"].status == "open"

    def test_resolve_unknown_question_skipped(self):
        events = [_event(EventType.OPEN_QUESTION_RESOLVED, {
            "question_id": "nonexistent", "resolution": "Nothing"
        }, 1)]
        questions = QuestionReducer.reduce(events)
        assert "nonexistent" not in questions

    def test_missing_question_id_skipped(self):
        events = [_event(EventType.OPEN_QUESTION_RAISED, {"title": "No ID"}, 1)]
        questions = QuestionReducer.reduce(events)
        assert len(questions) == 0

    def test_raised_by_set_from_actor(self):
        events = [_event(EventType.OPEN_QUESTION_RAISED, {
            "question_id": "q1", "title": "Q1"
        }, 1, actor="Human")]
        questions = QuestionReducer.reduce(events)
        assert questions["q1"].raised_by == "Human"

    def test_determinism(self):
        events = [
            _event(EventType.OPEN_QUESTION_RAISED, {
                "question_id": "q1", "title": "Q1", "priority": "high"
            }, 1),
        ]
        a = QuestionReducer.reduce(events)
        b = QuestionReducer.reduce(events)
        assert a["q1"].priority == b["q1"].priority
        assert a["q1"].status == b["q1"].status
