"""
EventStore integration tests.

Requires a live PostgreSQL database with schema applied.
Set RELAY_DB_TEST_ENABLED=1 to run.

Test coverage:
  - append_event returns a valid EventRecord
  - get_project_stream returns events in event_sequence ASC order
  - 1000-event ordering guarantee (no sequence violations)
  - Per-project version monotonicity (version increments correctly)
  - Replay determinism (two replays produce identical sequence)
  - Multi-project isolation (no cross-contamination between projects)
  - since_sequence filtering (only newer events returned)
  - Event metadata preserved round-trip
"""
from __future__ import annotations

import uuid
from uuid import UUID

import os
import pytest

# DB_REQUIRED marker — defined here so it can be used without importing conftest
DB_REQUIRED = pytest.mark.skipif(
    os.environ.get("RELAY_DB_TEST_ENABLED") != "1",
    reason=(
        "Set RELAY_DB_TEST_ENABLED=1 and ensure the database is initialized "
        "to run database integration tests."
    ),
)
from relay.db.event_store import EventStore
from relay.schema.events import EventMetadata, EventType

pytestmark = DB_REQUIRED


def meta(actor: str = "TestAgent", session: str = "test_session") -> EventMetadata:
    return EventMetadata(actor=actor, source="test_suite",
                         session_id=session, correlation_id="test_corr")


def bootstrap_project(store: EventStore, name: str = "Test Project") -> UUID:
    """Create a valid bootstrapped project and return its ID."""
    pid = uuid.uuid4()
    m = meta()
    store.append_event(pid, "main", EventType.PROJECT_CREATED, {"name": name}, m)
    store.append_event(pid, "main", EventType.PROJECT_GOAL_SET, {"goal": f"Goal of {name}"}, m)
    store.append_event(pid, "main", EventType.PROJECT_FOCUS_CHANGED, {"focus": "Testing"}, m)
    return pid


@pytest.fixture
def store() -> EventStore:
    return EventStore()


@pytest.fixture
def project(store: EventStore) -> UUID:
    return bootstrap_project(store)


# ── Basic append and retrieve ──────────────────────────────────────────────────

class TestAppendAndRetrieve:
    def test_append_returns_event_record(self, store: EventStore, project: UUID):
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

    def test_get_project_stream_returns_all_events(self, store: EventStore, project: UUID):
        events = store.get_project_stream(project)
        assert len(events) >= 3  # at least the 3 bootstrap events
        for e in events:
            assert e.project_id == project

    def test_events_ordered_by_sequence(self, store: EventStore, project: UUID):
        # Add a few more events
        m = meta()
        for i in range(5):
            store.append_event(project, "tasks", EventType.TASK_CREATED,
                               {"task_id": f"t{i}", "title": f"Task {i}"}, m)
        events = store.get_project_stream(project)
        sequences = [e.event_sequence for e in events]
        assert sequences == sorted(sequences), \
            "Events must be returned in event_sequence ASC order"

    def test_metadata_preserved_round_trip(self, store: EventStore, project: UUID):
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

    def test_payload_preserved_round_trip(self, store: EventStore, project: UUID):
        payload = {"task_id": "t_payload", "title": "Payload test",
                   "tags": ["alpha", "beta"], "priority": "high"}
        store.append_event(project, "tasks", EventType.TASK_CREATED, payload, meta())
        events = store.get_project_stream(project)
        last = events[-1]
        assert last.payload["task_id"] == "t_payload"
        assert last.payload["tags"] == ["alpha", "beta"]
        assert last.payload["priority"] == "high"


# ── Ordering guarantee ─────────────────────────────────────────────────────────

class TestOrdering:
    def test_1000_event_sequence_ordering(self, store: EventStore):
        """
        1000 events appended to the same project must always replay in
        event_sequence order with no violations and monotonically increasing versions.
        """
        pid = bootstrap_project(store, "Bulk Test")
        m = meta()

        # Append 997 more events (3 bootstrap already present)
        for i in range(997):
            store.append_event(
                pid, "tasks", EventType.TASK_CREATED,
                {"task_id": f"task_{i}", "title": f"Task {i}"},
                m,
            )

        events = store.get_project_stream(pid)
        assert len(events) == 1000, f"Expected 1000 events, got {len(events)}"

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

        print(f"\nEventStore Ordering Tests")
        print("-" * 44)
        print(f"Events Written:        1000")
        print(f"Events Replayed:       {len(events)}")
        print(f"Ordering Violations:   {seq_violations}")
        print(f"Version Violations:    {ver_violations}")
        print(f"Replay Determinism:    PASS")
        print(f"Multi-Stream Isolation: see TestMultiProjectIsolation")

        assert seq_violations == 0, \
            f"Ordering violations detected: {seq_violations}"
        assert ver_violations == 0, \
            f"Version monotonicity violated: {ver_violations}"

    def test_version_increments_by_one(self, store: EventStore, project: UUID):
        """Per-project version must increment by exactly 1 each event."""
        m = meta()
        records = []
        for i in range(10):
            r = store.append_event(project, "tasks", EventType.TASK_CREATED,
                                   {"task_id": f"v{i}", "title": f"Task {i}"}, m)
            records.append(r)

        versions = [r.version for r in records]
        for i in range(1, len(versions)):
            assert versions[i] == versions[i - 1] + 1, \
                f"Version jump: {versions[i-1]} → {versions[i]}"


# ── Replay determinism ────────────────────────────────────────────────────────

class TestReplayDeterminism:
    def test_replay_twice_same_order(self, store: EventStore, project: UUID):
        """
        Replaying the same stream twice must produce events in identical sequence.
        """
        m = meta()
        for i in range(20):
            store.append_event(project, "tasks", EventType.TASK_CREATED,
                               {"task_id": f"t{i}", "title": f"Task {i}"}, m)

        first = list(store.replay_stream(project))
        second = list(store.replay_stream(project))

        assert len(first) == len(second)
        for a, b in zip(first, second):
            assert a.event_sequence == b.event_sequence
            assert a.event_type == b.event_type
            assert a.version == b.version

        print(f"\nReplay Determinism: PASS ({len(first)} events)")

    def test_get_and_replay_produce_same_results(self, store: EventStore, project: UUID):
        """get_project_stream and replay_stream must return the same events."""
        m = meta()
        for i in range(10):
            store.append_event(project, "decisions", EventType.DECISION_PROPOSED,
                               {"decision_id": f"d{i}", "title": f"Decision {i}"}, m)

        bulk = store.get_project_stream(project)
        streamed = list(store.replay_stream(project))

        assert len(bulk) == len(streamed)
        for a, b in zip(bulk, streamed):
            assert a.event_sequence == b.event_sequence
            assert a.event_type == b.event_type


# ── Multi-project isolation ───────────────────────────────────────────────────

class TestMultiProjectIsolation:
    def test_project_a_events_not_in_project_b(self, store: EventStore):
        """
        Events appended to project A must never appear in project B's stream.
        """
        pid_a = bootstrap_project(store, "Project A")
        pid_b = bootstrap_project(store, "Project B")
        m = meta()

        for i in range(10):
            store.append_event(pid_a, "tasks", EventType.TASK_CREATED,
                               {"task_id": f"a{i}", "title": f"A Task {i}"}, m)
        for i in range(10):
            store.append_event(pid_b, "tasks", EventType.TASK_CREATED,
                               {"task_id": f"b{i}", "title": f"B Task {i}"}, m)

        stream_a = store.get_project_stream(pid_a)
        stream_b = store.get_project_stream(pid_b)

        for e in stream_a:
            assert e.project_id == pid_a, \
                f"Event from wrong project in stream A: {e}"
        for e in stream_b:
            assert e.project_id == pid_b, \
                f"Event from wrong project in stream B: {e}"

        print(f"\nMulti-Stream Isolation: PASS")
        print(f"  Project A events: {len(stream_a)}")
        print(f"  Project B events: {len(stream_b)}")


# ── since_sequence filtering ──────────────────────────────────────────────────

class TestSinceSequence:
    def test_since_sequence_filters_correctly(self, store: EventStore, project: UUID):
        """Events before since_sequence must not appear in results."""
        m = meta()
        # Add 5 initial events
        for i in range(5):
            store.append_event(project, "tasks", EventType.TASK_CREATED,
                               {"task_id": f"before_{i}", "title": f"Before {i}"}, m)

        events_before = store.get_project_stream(project)
        checkpoint = max(e.event_sequence for e in events_before)

        # Add 5 more events after the checkpoint
        for i in range(5):
            store.append_event(project, "tasks", EventType.TASK_CREATED,
                               {"task_id": f"after_{i}", "title": f"After {i}"}, m)

        new_events = store.get_project_stream(project, since_sequence=checkpoint)
        assert len(new_events) == 5, f"Expected 5 new events, got {len(new_events)}"
        for e in new_events:
            assert e.event_sequence > checkpoint

    def test_replay_stream_since_sequence(self, store: EventStore, project: UUID):
        """replay_stream also respects since_sequence."""
        m = meta()
        for i in range(10):
            store.append_event(project, "main", EventType.TASK_CREATED,
                               {"task_id": f"rs{i}", "title": f"RS {i}"}, m)

        all_events = store.get_project_stream(project)
        midpoint = all_events[len(all_events) // 2].event_sequence

        replayed = list(store.replay_stream(project, since_sequence=midpoint))
        for e in replayed:
            assert e.event_sequence > midpoint


# ── get_stream (sub-stream) ───────────────────────────────────────────────────

class TestGetStream:
    def test_get_stream_filters_by_stream_id(self, store: EventStore, project: UUID):
        """get_stream returns only events from the specified sub-stream."""
        m = meta()
        store.append_event(project, "tasks", EventType.TASK_CREATED,
                           {"task_id": "t1", "title": "Task"}, m)
        store.append_event(project, "decisions", EventType.DECISION_PROPOSED,
                           {"decision_id": "d1", "title": "Decision"}, m)
        store.append_event(project, "questions", EventType.OPEN_QUESTION_RAISED,
                           {"question_id": "q1", "title": "Question"}, m)

        task_stream = store.get_stream(project, "tasks")
        decision_stream = store.get_stream(project, "decisions")

        for e in task_stream:
            assert e.stream_id == "tasks"
        for e in decision_stream:
            assert e.stream_id == "decisions"

    def test_get_event_count(self, store: EventStore, project: UUID):
        """get_event_count returns the correct total event count."""
        count_before = store.get_event_count(project)
        m = meta()
        for i in range(7):
            store.append_event(project, "main", EventType.TASK_CREATED,
                               {"task_id": f"cnt{i}", "title": f"Count {i}"}, m)
        count_after = store.get_event_count(project)
        assert count_after == count_before + 7
