"""Unit tests for TimelineProjection, normalizer, state, and serialization.

Tests the timeline package independently of the conformance suite.
"""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from rationalevault.projection_platform.models import ProjectionHealth
from rationalevault.schema.events import EventMetadata, EventRecord, EventType
from rationalevault.timeline.normalizer import MAPPINGS, normalize_event
from rationalevault.timeline.projection import TimelineProjection
from rationalevault.timeline.state import TimelineCategory, TimelineEntry, TimelineState


# ── Helpers ──────────────────────────────────────────────────────────────────


def _event(
    event_type: EventType,
    payload: dict,
    seq: int = 1,
    project_id=None,
) -> EventRecord:
    return EventRecord(
        event_sequence=seq,
        id=uuid4(),
        project_id=project_id or uuid4(),
        stream_id="main",
        version=seq,
        event_type=event_type,
        metadata=EventMetadata(actor="test", source="test"),
        payload=payload,
        parent_id=None,
        recorded_at=None,
    )


# ── TimelineCategory Tests ──────────────────────────────────────────────────


class TestTimelineCategory:
    def test_all_values(self):
        categories = list(TimelineCategory)
        assert len(categories) == 7
        assert TimelineCategory.DECISION.value == "decision"
        assert TimelineCategory.KNOWLEDGE.value == "knowledge"
        assert TimelineCategory.TASK.value == "task"
        assert TimelineCategory.QUESTION.value == "question"
        assert TimelineCategory.MEMORY.value == "memory"
        assert TimelineCategory.MILESTONE.value == "milestone"
        assert TimelineCategory.SYSTEM.value == "system"

    def test_from_value(self):
        assert TimelineCategory("decision") == TimelineCategory.DECISION
        assert TimelineCategory("knowledge") == TimelineCategory.KNOWLEDGE


# ── TimelineEntry Tests ─────────────────────────────────────────────────────


class TestTimelineEntry:
    def test_creation(self):
        entry = TimelineEntry(
            sequence=1,
            timestamp=datetime(2026, 1, 1),
            event_type=EventType.TASK_CREATED,
            category=TimelineCategory.TASK,
            actor="alice",
            subject_entity="t1",
            summary="Task created",
            references=[],
        )
        assert entry.sequence == 1
        assert entry.category == TimelineCategory.TASK
        assert entry.actor == "alice"

    def test_default_references(self):
        entry = TimelineEntry(
            sequence=1,
            timestamp=datetime(2026, 1, 1),
            event_type=EventType.TASK_CREATED,
            category=TimelineCategory.TASK,
            actor=None,
            subject_entity=None,
            summary="Task",
        )
        assert entry.references == []


# ── TimelineState Tests ─────────────────────────────────────────────────────


class TestTimelineState:
    def test_empty_state(self):
        state = TimelineState()
        assert state.entries == []
        assert state.sequence == 0
        assert state.entry_count == 0
        assert state.categories == set()

    def test_entry_count(self):
        state = TimelineState(
            entries=[
                TimelineEntry(
                    sequence=1,
                    timestamp=datetime(2026, 1, 1),
                    event_type=EventType.TASK_CREATED,
                    category=TimelineCategory.TASK,
                    actor=None,
                    subject_entity=None,
                    summary="Task",
                ),
                TimelineEntry(
                    sequence=2,
                    timestamp=datetime(2026, 1, 2),
                    event_type=EventType.KNOWLEDGE_CREATED,
                    category=TimelineCategory.KNOWLEDGE,
                    actor=None,
                    subject_entity=None,
                    summary="Knowledge",
                ),
            ],
            sequence=2,
        )
        assert state.entry_count == 2
        assert state.categories == {TimelineCategory.TASK, TimelineCategory.KNOWLEDGE}


# ── normalize_event Tests ───────────────────────────────────────────────────


class TestNormalizeEvent:
    def test_known_event_type(self):
        event = _event(EventType.TASK_CREATED, {
            "task_id": "t1",
            "title": "My task",
            "actor": "alice",
        })
        entry = normalize_event(event)
        assert entry is not None
        assert entry.event_type == EventType.TASK_CREATED
        assert entry.category == TimelineCategory.TASK
        assert entry.subject_entity == "t1"
        assert "My task" in entry.summary

    def test_unknown_event_returns_none(self):
        event = _event(EventType.TASK_MUTATED, {"task_id": "t1"})
        entry = normalize_event(event)
        assert entry is None

    def test_all_consumed_event_types_produce_entries(self):
        for event_type in MAPPINGS:
            event = _event(event_type, {"title": "test"})
            entry = normalize_event(event)
            assert entry is not None, f"{event_type} should produce an entry"

    def test_metadata_actor_extraction(self):
        event = _event(EventType.KNOWLEDGE_CREATED, {
            "knowledge_id": "k1",
            "title": "Test",
        })
        entry = normalize_event(event)
        assert entry is not None
        assert entry.actor == "test"

    def test_payload_actor_extraction(self):
        event = _event(EventType.TASK_CREATED, {
            "task_id": "t1",
            "title": "Task",
            "actor": "bob",
        })
        entry = normalize_event(event)
        assert entry is not None
        assert entry.actor == "bob"

    def test_subject_entity_extraction(self):
        event = _event(EventType.KNOWLEDGE_CREATED, {
            "knowledge_id": "k1",
            "title": "Test",
        })
        entry = normalize_event(event)
        assert entry is not None
        assert entry.subject_entity == "k1"


# ── TimelineProjection Tests ────────────────────────────────────────────────


class TestTimelineProjection:
    def _get_projection(self):
        return TimelineProjection()

    def test_metadata(self):
        proj = self._get_projection()
        m = proj.metadata
        assert m.id == "timeline"
        assert m.version == 1
        assert m.schema_version == 1
        assert m.capabilities.searchable is False
        assert m.capabilities.snapshotable is True
        assert m.capabilities.mutable is False
        assert m.capabilities.exportable is True
        assert len(m.consumed_events.types) == len(MAPPINGS)

    def test_health_lifecycle(self):
        proj = self._get_projection()
        assert proj.health() == ProjectionHealth.UNKNOWN

        proj.initialize(None)
        assert proj.health() == ProjectionHealth.INITIALIZING

        events = [_event(EventType.TASK_CREATED, {"task_id": "t1", "title": "Task"}, 1)]
        proj.reduce(events)
        assert proj.health() == ProjectionHealth.READY

        proj.shutdown()
        assert proj.health() == ProjectionHealth.SHUTDOWN

    def test_reduce_empty_events(self):
        proj = self._get_projection()
        state = proj.reduce([])
        assert state.entries == []
        assert state.sequence == 0

    def test_reduce_single_event(self):
        proj = self._get_projection()
        events = [_event(EventType.TASK_CREATED, {
            "task_id": "t1",
            "title": "My task",
        }, 1)]
        state = proj.reduce(events)
        assert len(state.entries) == 1
        assert state.entries[0].event_type == EventType.TASK_CREATED
        assert state.entries[0].category == TimelineCategory.TASK
        assert state.sequence == 1

    def test_reduce_multiple_events(self):
        proj = self._get_projection()
        events = [
            _event(EventType.TASK_CREATED, {
                "task_id": "t1", "title": "Task",
            }, 1),
            _event(EventType.KNOWLEDGE_CREATED, {
                "knowledge_id": "k1", "title": "Knowledge",
            }, 2),
            _event(EventType.DECISION_PROPOSED, {
                "decision_id": "d1", "title": "Decision",
            }, 3),
        ]
        state = proj.reduce(events)
        assert len(state.entries) == 3
        assert state.sequence == 3

    def test_reduce_ignores_unknown_events(self):
        proj = self._get_projection()
        events = [
            _event(EventType.TASK_CREATED, {
                "task_id": "t1", "title": "Task",
            }, 1),
            _event(EventType.TASK_MUTATED, {
                "task_id": "t1", "details": {},
            }, 2),
            _event(EventType.KNOWLEDGE_CREATED, {
                "knowledge_id": "k1", "title": "K",
            }, 3),
        ]
        state = proj.reduce(events)
        assert len(state.entries) == 2
        assert state.sequence == 3

    def test_reduce_with_initial_state(self):
        proj1 = self._get_projection()
        events1 = [_event(EventType.TASK_CREATED, {
            "task_id": "t1", "title": "Task",
        }, 1)]
        state1 = proj1.reduce(events1)

        proj2 = self._get_projection()
        events2 = [_event(EventType.KNOWLEDGE_CREATED, {
            "knowledge_id": "k1", "title": "K",
        }, 2)]
        state2 = proj2.reduce(events2, initial_state=state1)

        assert len(state2.entries) == 2
        assert state2.sequence == 2

    def test_serialize_deterministic(self):
        proj = self._get_projection()
        events = [
            _event(EventType.TASK_CREATED, {
                "task_id": "t1", "title": "Task",
            }, 1),
            _event(EventType.KNOWLEDGE_CREATED, {
                "knowledge_id": "k1", "title": "K",
            }, 2),
        ]
        state = proj.reduce(events)
        s1 = proj.serialize(state)
        s2 = proj.serialize(state)
        assert s1 == s2

    def test_serialize_sorted_by_sequence(self):
        proj = self._get_projection()
        events = [
            _event(EventType.KNOWLEDGE_CREATED, {
                "knowledge_id": "k1", "title": "K",
            }, 2),
            _event(EventType.TASK_CREATED, {
                "task_id": "t1", "title": "Task",
            }, 1),
        ]
        state = proj.reduce(events)
        serialized = proj.serialize(state)
        sequences = [e["sequence"] for e in serialized["entries"]]
        assert sequences == [1, 2]

    def test_serialize_enums_are_strings(self):
        proj = self._get_projection()
        events = [_event(EventType.TASK_CREATED, {
            "task_id": "t1", "title": "Task",
        }, 1)]
        state = proj.reduce(events)
        serialized = proj.serialize(state)
        entry = serialized["entries"][0]
        assert isinstance(entry["event_type"], str)
        assert isinstance(entry["category"], str)

    def test_deserialize_restores_state(self):
        proj = self._get_projection()
        events = [
            _event(EventType.TASK_CREATED, {
                "task_id": "t1", "title": "Task",
            }, 1),
            _event(EventType.KNOWLEDGE_CREATED, {
                "knowledge_id": "k1", "title": "K",
            }, 2),
        ]
        state = proj.reduce(events)
        serialized = proj.serialize(state)
        restored = proj.deserialize(serialized)

        assert len(restored.entries) == 2
        assert restored.entries[0].event_type == EventType.TASK_CREATED
        assert restored.entries[0].category == TimelineCategory.TASK
        assert restored.entries[1].event_type == EventType.KNOWLEDGE_CREATED
        assert restored.sequence == 2

    def test_serialize_deserialize_roundtrip(self):
        proj = self._get_projection()
        events = [
            _event(EventType.TASK_CREATED, {
                "task_id": "t1", "title": "Task",
            }, 1),
            _event(EventType.KNOWLEDGE_CREATED, {
                "knowledge_id": "k1", "title": "K",
            }, 2),
            _event(EventType.DECISION_PROPOSED, {
                "decision_id": "d1", "title": "D",
            }, 3),
        ]
        state = proj.reduce(events)
        serialized = proj.serialize(state)
        restored = proj.deserialize(serialized)
        re_serialized = proj.serialize(restored)
        assert serialized == re_serialized

    def test_delta_replay(self):
        proj1 = self._get_projection()
        full_events = [
            _event(EventType.TASK_CREATED, {
                "task_id": "t1", "title": "Task",
            }, 1),
            _event(EventType.KNOWLEDGE_CREATED, {
                "knowledge_id": "k1", "title": "K",
            }, 2),
            _event(EventType.DECISION_PROPOSED, {
                "decision_id": "d1", "title": "D",
            }, 3),
        ]
        full_state = proj1.reduce(full_events)

        proj2 = self._get_projection()
        prefix_state = proj2.reduce(full_events[:1])

        proj3 = self._get_projection()
        delta_state = proj3.reduce(full_events[1:], initial_state=prefix_state)

        full_seqs = {e.sequence for e in full_state.entries}
        delta_seqs = {e.sequence for e in delta_state.entries}
        assert full_seqs == delta_seqs
        assert full_state.sequence == delta_state.sequence

    def test_reduce_appends_in_sequence_order(self):
        proj = self._get_projection()
        events = [
            _event(EventType.KNOWLEDGE_CREATED, {
                "knowledge_id": "k1", "title": "K",
            }, 3),
            _event(EventType.TASK_CREATED, {
                "task_id": "t1", "title": "Task",
            }, 1),
            _event(EventType.DECISION_PROPOSED, {
                "decision_id": "d1", "title": "D",
            }, 2),
        ]
        state = proj.reduce(events)
        sequences = [e.sequence for e in state.entries]
        assert sequences == [3, 1, 2]

    def test_shutdown_clears_context(self):
        proj = self._get_projection()
        ctx = object()
        proj.initialize(ctx)
        assert proj._ctx is ctx
        proj.shutdown()
        assert proj._ctx is None
