"""
Shared EventStoreContract class containing baseline tests for BaseEventStore implementations.
"""
from __future__ import annotations

import inspect
import uuid
from uuid import UUID
from typing import Generator
import pytest

from rationalevault.db.base import BaseEventStore
from rationalevault.schema.events import EventMetadata, EventType, EventRecord


def meta(actor: str = "TestAgent", session: str = "test_session") -> EventMetadata:
    return EventMetadata(actor=actor, source="test_suite",
                         session_id=session, correlation_id="test_corr")


class EventStoreContract:
    """
    Contract test suite representing specification for event store implementations.
    All subclasses must provide a 'store' fixture returning a BaseEventStore.
    """

    def bootstrap_project(self, store: BaseEventStore, name: str = "Test Project") -> UUID:
        pid = uuid.uuid4()
        m = meta()
        store.append_event(pid, "main", EventType.PROJECT_CREATED, {"name": name}, m)
        store.append_event(pid, "main", EventType.PROJECT_GOAL_SET, {"goal": f"Goal of {name}"}, m)
        store.append_event(pid, "main", EventType.PROJECT_FOCUS_CHANGED, {"focus": "Testing"}, m)
        return pid

    # ── Happy Paths ─────────────────────────────────────────────────────────

    def test_append_replay_roundtrip(self, store: BaseEventStore):
        pid = self.bootstrap_project(store, "Roundtrip")
        m = meta()
        record = store.append_event(
            pid, "tasks", EventType.TASK_CREATED,
            {"task_id": "t1", "title": "First task"},
            m,
        )
        assert record.event_type == EventType.TASK_CREATED
        assert record.event_sequence > 0
        assert record.version == 4  # 3 bootstrap + 1 append
        assert record.project_id == pid
        assert record.stream_id == "tasks"

        # Verify through get_project_stream
        stream = store.get_project_stream(pid)
        assert len(stream) == 4
        assert stream[-1].id == record.id
        assert stream[-1].payload["task_id"] == "t1"

    def test_multistream_isolation(self, store: BaseEventStore):
        pid = self.bootstrap_project(store, "Isolation")
        m = meta()
        store.append_event(pid, "tasks", EventType.TASK_CREATED, {"task_id": "t1"}, m)
        store.append_event(pid, "decisions", EventType.DECISION_ACCEPTED, {"decision_id": "d1"}, m)

        tasks = store.get_stream(pid, "tasks")
        decisions = store.get_stream(pid, "decisions")

        assert len(tasks) == 1
        assert tasks[0].event_type == EventType.TASK_CREATED

        assert len(decisions) == 1
        assert decisions[0].event_type == EventType.DECISION_ACCEPTED

    def test_session_filtering(self, store: BaseEventStore):
        pid = self.bootstrap_project(store, "SessionFiltering")
        m1 = meta(session="session_1")
        m2 = meta(session="session_2")

        store.append_event(pid, "tasks", EventType.TASK_CREATED, {"task_id": "t1"}, m1)
        store.append_event(pid, "tasks", EventType.TASK_CREATED, {"task_id": "t2"}, m2)

        s1_events = store.get_session_events(pid, "session_1")
        s2_events = store.get_session_events(pid, "session_2")

        assert len(s1_events) == 1
        assert s1_events[0].payload["task_id"] == "t1"
        assert len(s2_events) == 1
        assert s2_events[0].payload["task_id"] == "t2"

    def test_ordering_guarantees(self, store: BaseEventStore):
        pid = self.bootstrap_project(store, "Ordering")
        m = meta()
        for i in range(5):
            store.append_event(pid, "tasks", EventType.TASK_CREATED, {"task_id": f"t{i}"}, m)

        stream = store.get_project_stream(pid)
        seqs = [e.event_sequence for e in stream]
        assert seqs == sorted(seqs), "Events must preserve sequence ID ordering ASC"

    def test_empty_stream_behavior(self, store: BaseEventStore):
        non_existent_pid = uuid.uuid4()
        
        # Verify empty counts, lists, and generator behaviors
        assert store.get_event_count(non_existent_pid) == 0
        assert store.get_project_stream(non_existent_pid) == []
        assert store.get_stream(non_existent_pid, "tasks") == []
        assert list(store.replay_stream(non_existent_pid)) == []
        assert store.get_last_session_id(non_existent_pid) is None

    def test_replay_is_lazy_iterator(self, store: BaseEventStore):
        pid = self.bootstrap_project(store, "Lazy")
        result = store.replay_stream(pid)

        # Result is an iterator/generator
        assert iter(result) is result
        assert not isinstance(result, list)

        # Consumes properly
        events = list(result)
        assert len(events) == 3

    def test_idempotent_reads(self, store: BaseEventStore):
        pid = self.bootstrap_project(store, "Idempotency")
        events1 = list(store.replay_stream(pid))
        events2 = list(store.replay_stream(pid))

        assert [e.id for e in events1] == [e.id for e in events2]
        assert [e.event_sequence for e in events1] == [e.event_sequence for e in events2]

    def test_large_stream_replay(self, store: BaseEventStore):
        pid = uuid.uuid4()
        m = meta()
        
        # Insert 1000 events
        first_id = None
        last_id = None
        for i in range(1000):
            rec = store.append_event(
                pid, "large", EventType.TASK_CREATED, {"idx": i}, m
            )
            if i == 0:
                first_id = rec.id
            if i == 999:
                last_id = rec.id

        events = list(store.replay_stream(pid))
        assert len(events) == 1000
        assert events[0].id == first_id
        assert events[-1].id == last_id

    # ── Failure Paths ────────────────────────────────────────────────────────

    def test_invalid_stream_id(self, store: BaseEventStore):
        pid = self.bootstrap_project(store, "InvalidStream")
        # Empty stream name is allowed but isolated
        m = meta()
        rec = store.append_event(pid, "", EventType.TASK_CREATED, {}, m)
        assert rec.stream_id == ""
        
        # Pulling stream by different name returns empty
        assert store.get_stream(pid, "does-not-exist") == []

    def test_missing_session_id(self, store: BaseEventStore):
        pid = uuid.uuid4()
        # Create metadata missing actor/session manually or with none-like values
        m = EventMetadata(actor="", source="", session_id="", correlation_id="")
        rec = store.append_event(pid, "main", EventType.PROJECT_CREATED, {}, m)
        assert rec.metadata.session_id == ""
        
        # Pulling session events with empty string
        events = store.get_session_events(pid, "")
        assert len(events) == 1
        assert events[0].id == rec.id

    def test_empty_project_id(self, store: BaseEventStore):
        # Using a nil/empty UUID
        nil_uuid = UUID("00000000-0000-0000-0000-000000000000")
        m = meta()
        rec = store.append_event(nil_uuid, "main", EventType.PROJECT_CREATED, {}, m)
        assert rec.project_id == nil_uuid

        stream = store.get_project_stream(nil_uuid)
        assert len(stream) == 1
        assert stream[0].id == rec.id
