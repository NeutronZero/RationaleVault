"""
SQLiteEventStore integration tests.
"""
from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path
from uuid import UUID

import pytest

from rationalevault.db.sqlite_store import SQLiteEventStore
from rationalevault.schema.events import EventMetadata, EventType


def meta(actor: str = "TestAgent", session: str = "test_session") -> EventMetadata:
    return EventMetadata(actor=actor, source="test_suite",
                         session_id=session, correlation_id="test_corr")


def bootstrap_project(store: SQLiteEventStore, name: str = "Test Project") -> UUID:
    pid = uuid.uuid4()
    m = meta()
    store.append_event(pid, "main", EventType.PROJECT_CREATED, {"name": name}, m)
    store.append_event(pid, "main", EventType.PROJECT_GOAL_SET, {"goal": f"Goal of {name}"}, m)
    store.append_event(pid, "main", EventType.PROJECT_FOCUS_CHANGED, {"focus": "Testing"}, m)
    return pid


@pytest.fixture
def temp_db() -> str:
    # Use a temporary SQLite database file
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    try:
        os.unlink(path)
    except OSError:
        pass


@pytest.fixture
def store(temp_db) -> SQLiteEventStore:
    return SQLiteEventStore(db_path=temp_db)


@pytest.fixture
def project(store: SQLiteEventStore) -> UUID:
    return bootstrap_project(store)


class TestSQLiteAppendAndRetrieve:
    def test_append_returns_event_record(self, store: SQLiteEventStore, project: UUID):
        record = store.append_event(
            project, "tasks", EventType.TASK_CREATED,
            {"task_id": "t1", "title": "First task"},
            meta(),
        )
        assert record.event_type == EventType.TASK_CREATED
        assert record.event_sequence > 0
        assert record.version > 0
        assert record.project_id == project
        assert record.stream_id == "tasks"

    def test_get_project_stream_returns_all_events(self, store: SQLiteEventStore, project: UUID):
        events = store.get_project_stream(project)
        assert len(events) >= 3
        for e in events:
            assert e.project_id == project

    def test_events_ordered_by_sequence(self, store: SQLiteEventStore, project: UUID):
        m = meta()
        for i in range(5):
            store.append_event(project, "tasks", EventType.TASK_CREATED,
                               {"task_id": f"t{i}", "title": f"Task {i}"}, m)
        events = store.get_project_stream(project)
        sequences = [e.event_sequence for e in events]
        assert sequences == sorted(sequences)

    def test_metadata_preserved_round_trip(self, store: SQLiteEventStore, project: UUID):
        m = EventMetadata(
            actor="Claude",
            source="ClaudeCompiler",
            correlation_id="corr-abc-123",
            session_id="sess-xyz-789",
        )
        store.append_event(project, "main", EventType.TASK_CREATED,
                           {"task_id": "t_meta", "title": "Metadata test"}, m)
        events = store.get_project_stream(project)
        last = events[-1]
        assert last.metadata.actor == "Claude"
        assert last.metadata.source == "ClaudeCompiler"
        assert last.metadata.correlation_id == "corr-abc-123"
        assert last.metadata.session_id == "sess-xyz-789"


class TestSQLiteOrdering:
    def test_100_event_sequence_ordering(self, store: SQLiteEventStore):
        pid = bootstrap_project(store, "Bulk Test")
        m = meta()

        for i in range(97):
            store.append_event(
                pid, "tasks", EventType.TASK_CREATED,
                {"task_id": f"task_{i}", "title": f"Task {i}"},
                m,
            )

        events = store.get_project_stream(pid)
        assert len(events) == 100

        sequences = [e.event_sequence for e in events]
        versions = [e.version for e in events]

        seq_violations = sum(
            1 for i in range(1, len(sequences))
            if sequences[i] <= sequences[i - 1]
        )
        ver_violations = sum(
            1 for i in range(1, len(versions))
            if versions[i] != versions[i - 1] + 1
        )

        assert seq_violations == 0
        assert ver_violations == 0


class TestDatetimeFallback:
    def test_invalid_datetime_falls_back_to_now(self, store: SQLiteEventStore) -> None:
        """Events with invalid recorded_at still load via public API."""
        import sqlite3
        from datetime import datetime

        pid = bootstrap_project(store, "DateTime Test")

        with sqlite3.connect(store.db_path) as conn:
            conn.execute(
                "UPDATE rationalevault_events SET recorded_at = 'not-a-date' WHERE project_id = ?",
                (str(pid),),
            )

        events = store.get_project_stream(pid)
        assert len(events) == 3
        for e in events:
            assert isinstance(e.recorded_at, datetime)
