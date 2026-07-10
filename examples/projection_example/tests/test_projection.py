"""Unit tests for the Task Tracker projection."""
from __future__ import annotations

import datetime

import datetime
from typing import cast
from uuid import uuid4

from rationalevault.schema import EventRecord, EventType, EventMetadata

from ..events import TaskCreatedPayload, TaskCompletedPayload
from ..projection import TaskTrackerProjection
from ..state import TaskTrackerState


def test_task_creation():
    """Verify that a task is created correctly in the projection state."""
    projection = TaskTrackerProjection()

    event = EventRecord(
        event_sequence=1,
        id=uuid4(),
        project_id=uuid4(),
        stream_id="test-stream",
        version=1,
        event_type=cast(EventType, "TaskCreated"),
        metadata=EventMetadata(actor="test", source="test"),
        payload=TaskCreatedPayload(task_id="t-1", description="Fix bug", owner="alice").to_dict(),
        parent_id=None,
        recorded_at=datetime.datetime.now(datetime.timezone.utc)
    )

    new_state = projection.reduce([event])
    assert "t-1" in new_state.tasks
    assert new_state.tasks["t-1"].owner == "alice"
    assert not new_state.tasks["t-1"].completed


def test_task_completion():
    """Verify that a task is marked completed correctly."""
    projection = TaskTrackerProjection()

    # First create
    create_evt = EventRecord(
        event_sequence=1,
        id=uuid4(),
        project_id=uuid4(),
        stream_id="test-stream",
        version=1,
        event_type=cast(EventType, "TaskCreated"),
        metadata=EventMetadata(actor="test", source="test"),
        payload=TaskCreatedPayload(task_id="t-1", description="Fix bug", owner="alice").to_dict(),
        parent_id=None,
        recorded_at=datetime.datetime.now(datetime.timezone.utc)
    )
    state = projection.reduce([create_evt])

    # Then complete
    complete_evt = EventRecord(
        event_sequence=2,
        id=uuid4(),
        project_id=uuid4(),
        stream_id="test-stream",
        version=2,
        event_type=cast(EventType, "TaskCompleted"),
        metadata=EventMetadata(actor="test", source="test"),
        payload=TaskCompletedPayload(task_id="t-1").to_dict(),
        parent_id=None,
        recorded_at=datetime.datetime.now(datetime.timezone.utc)
    )
    state = projection.reduce([complete_evt], initial_state=state)

    assert state.tasks["t-1"].completed is True
