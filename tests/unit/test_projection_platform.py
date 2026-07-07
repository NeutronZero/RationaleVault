"""Tests for the Projection Platform (ADR-027)."""
from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

import pytest

from rationalevault.cognitive_head.compiler import (
    CognitiveHead,
    compile_cognitive_head,
    compile_cognitive_head_v2,
)
from rationalevault.cognitive_head.cognitive_head_projection import (
    CognitiveHeadProjection,
)
from rationalevault.projection_platform.compiler import ProjectionCompiler
from rationalevault.projection_platform.context import (
    DependencyReader,
    MetricsCollector,
)
from rationalevault.projection_platform.models import (
    DependencyKind,
    EventSelector,
    ProjectionCapabilities,
    ProjectionDependency,
    ProjectionHealth,
    ProjectionMetadata,
    SnapshotKey,
)
from rationalevault.projection_platform.registry import (
    CyclicDependencyError,
    ProjectionNotFoundError,
    ProjectionRegistry,
)
from rationalevault.schema.events import EventMetadata, EventRecord, EventType


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
        stream_id="default",
        version=1,
        event_type=event_type,
        metadata=EventMetadata(actor="test", source="test"),
        payload=payload,
        parent_id=None,
        recorded_at=None,
    )


def _append_event(store, event: EventRecord) -> EventRecord:
    """Append an EventRecord to a store using its API."""
    return store.append_event(
        project_id=event.project_id,
        stream_id=event.stream_id,
        event_type=event.event_type,
        payload=event.payload,
        metadata=event.metadata,
    )


def _make_cognitive_head_events(project_id=None):
    """Create a valid bootstrap event sequence for CognitiveHead."""
    pid = project_id or uuid4()
    return [
        _event(EventType.PROJECT_CREATED, {"name": "Test"}, 1, pid),
        _event(EventType.PROJECT_GOAL_SET, {"goal": "Goal"}, 2, pid),
        _event(EventType.PROJECT_FOCUS_CHANGED, {"focus": "Focus"}, 3, pid),
        _event(EventType.TASK_CREATED, {
            "task_id": "t1",
            "details": {"summary": "Task 1", "body": ""},
            "priority": "high",
        }, 4, pid),
        _event(EventType.DECISION_PROPOSED, {
            "decision_id": "d1",
            "title": "Decision 1",
        }, 5, pid),
        _event(EventType.OPEN_QUESTION_RAISED, {
            "question_id": "q1",
            "title": "Question 1",
            "priority": "critical",
        }, 6, pid),
    ]


# ── Models Tests ─────────────────────────────────────────────────────────────


class TestProjectionMetadata:
    def test_frozen(self):
        meta = ProjectionMetadata(
            id="test",
            version=1,
            schema_version=1,
            consumed_events=EventSelector(),
            capabilities=ProjectionCapabilities(),
        )
        with pytest.raises(AttributeError):
            meta.id = "changed"  # type: ignore[misc]

    def test_defaults(self):
        meta = ProjectionMetadata(
            id="test",
            version=1,
            schema_version=1,
            consumed_events=EventSelector(),
            capabilities=ProjectionCapabilities(),
        )
        assert meta.dependencies == ()
        assert meta.description == ""


class TestEventSelector:
    def test_frozen_types(self):
        sel = EventSelector(types=frozenset({EventType.TASK_CREATED}))
        assert EventType.TASK_CREATED in sel.types

    def test_defaults(self):
        sel = EventSelector()
        assert sel.types == frozenset()
        assert sel.namespace == ""
        assert sel.tags == frozenset()


class TestProjectionCapabilities:
    def test_defaults(self):
        cap = ProjectionCapabilities()
        assert cap.searchable is False
        assert cap.snapshotable is True
        assert cap.observable is True
        assert cap.exportable is False
        assert cap.mutable is False


class TestSnapshotKey:
    def test_frozen(self):
        key = SnapshotKey(
            projection_id="test",
            projection_version=1,
            schema_version=1,
        )
        with pytest.raises(AttributeError):
            key.projection_version = 2  # type: ignore[misc]


# ── Registry Tests ───────────────────────────────────────────────────────────


class TestProjectionRegistry:
    def test_register_and_get(self):
        registry = ProjectionRegistry()
        proj = CognitiveHeadProjection()
        registry.register(proj)
        assert registry.get("cognitive_head") is proj

    def test_get_not_found(self):
        registry = ProjectionRegistry()
        with pytest.raises(ProjectionNotFoundError):
            registry.get("nonexistent")

    def test_all(self):
        registry = ProjectionRegistry()
        proj = CognitiveHeadProjection()
        registry.register(proj)
        assert len(registry.all()) == 1

    def test_metadata(self):
        registry = ProjectionRegistry()
        proj = CognitiveHeadProjection()
        registry.register(proj)
        meta = registry.metadata("cognitive_head")
        assert meta.id == "cognitive_head"

    def test_duplicate_registration(self):
        registry = ProjectionRegistry()
        proj = CognitiveHeadProjection()
        registry.register(proj)
        with pytest.raises(ValueError, match="already registered"):
            registry.register(proj)

    def test_freeze(self):
        registry = ProjectionRegistry()
        proj = CognitiveHeadProjection()
        registry.register(proj)
        registry.freeze()
        assert registry.is_frozen is True

    def test_register_after_freeze(self):
        registry = ProjectionRegistry()
        proj = CognitiveHeadProjection()
        registry.register(proj)
        registry.freeze()
        with pytest.raises(RuntimeError, match="frozen"):
            registry.register(CognitiveHeadProjection())

    def test_missing_dependency(self):
        @dataclass(frozen=True)
        class MockMeta:
            id: str = "test"
            version: int = 1
            schema_version: int = 1
            consumed_events: EventSelector = EventSelector()
            capabilities: ProjectionCapabilities = ProjectionCapabilities()
            dependencies: tuple = (
                ProjectionDependency(
                    projection_id="missing",
                    kind=DependencyKind.STATE,
                ),
            )
            description: str = ""

        class MockProjection:
            @property
            def metadata(self):
                return MockMeta()

        registry = ProjectionRegistry()
        registry.register(MockProjection())
        with pytest.raises(ProjectionNotFoundError, match="missing"):
            registry.freeze()

    def test_cycle_detection(self):
        @dataclass(frozen=True)
        class MetaA:
            id: str = "a"
            version: int = 1
            schema_version: int = 1
            consumed_events: EventSelector = EventSelector()
            capabilities: ProjectionCapabilities = ProjectionCapabilities()
            dependencies: tuple = (
                ProjectionDependency(
                    projection_id="b",
                    kind=DependencyKind.STATE,
                ),
            )
            description: str = ""

        @dataclass(frozen=True)
        class MetaB:
            id: str = "b"
            version: int = 1
            schema_version: int = 1
            consumed_events: EventSelector = EventSelector()
            capabilities: ProjectionCapabilities = ProjectionCapabilities()
            dependencies: tuple = (
                ProjectionDependency(
                    projection_id="a",
                    kind=DependencyKind.STATE,
                ),
            )
            description: str = ""

        class ProjA:
            @property
            def metadata(self):
                return MetaA()

        class ProjB:
            @property
            def metadata(self):
                return MetaB()

        registry = ProjectionRegistry()
        registry.register(ProjA())
        registry.register(ProjB())
        with pytest.raises(CyclicDependencyError):
            registry.freeze()


# ── CognitiveHeadProjection Tests ────────────────────────────────────────────


class TestCognitiveHeadProjection:
    def test_metadata(self):
        proj = CognitiveHeadProjection()
        meta = proj.metadata
        assert meta.id == "cognitive_head"
        assert meta.version == 1
        assert meta.capabilities.snapshotable is True
        assert meta.capabilities.searchable is False

    def test_health_initial(self):
        proj = CognitiveHeadProjection()
        assert proj.health() == ProjectionHealth.UNKNOWN

    def test_reduce_full_replay(self):
        proj = CognitiveHeadProjection()
        events = _make_cognitive_head_events()
        head = proj.reduce(events)
        assert isinstance(head, CognitiveHead)
        assert head.project_name == "Test"
        assert head.project_goal == "Goal"
        assert head.current_focus == "Focus"
        assert len(head.active_tasks) == 1
        assert head.active_tasks[0].task_id == "t1"

    def test_reduce_empty_events_no_state_raises(self):
        proj = CognitiveHeadProjection()
        with pytest.raises(Exception):
            proj.reduce([])

    def test_reduce_with_initial_state(self):
        proj = CognitiveHeadProjection()
        events = _make_cognitive_head_events()
        head = proj.reduce(events)

        # Delta replay with no new events returns initial state
        head2 = proj.reduce([], initial_state=head)
        assert head2 is head

    def test_reduce_delta_replay(self):
        proj = CognitiveHeadProjection()
        events = _make_cognitive_head_events()
        head = proj.reduce(events)

        # Add a new event
        delta_events = [
            _event(EventType.TASK_COMPLETED, {"task_id": "t1"}, 7,
                   events[0].project_id),
        ]
        head2 = proj.reduce(delta_events, initial_state=head)
        # t1 was completed, so no active tasks
        assert len(head2.active_tasks) == 0

    def test_serialize_deserialize(self):
        proj = CognitiveHeadProjection()
        events = _make_cognitive_head_events()
        head = proj.reduce(events)

        serialized = proj.serialize(head)
        assert "project_name" in serialized
        assert serialized["project_name"] == "Test"

        deserialized = proj.deserialize(serialized)
        assert isinstance(deserialized, CognitiveHead)
        assert deserialized.project_name == "Test"

    def test_shutdown(self):
        proj = CognitiveHeadProjection()
        proj.shutdown()
        assert proj.health() == ProjectionHealth.SHUTDOWN


# ── ProjectionCompiler Tests ─────────────────────────────────────────────────


class TestProjectionCompiler:
    def test_compile_cognitive_head(self, tmp_path):
        from rationalevault.db.sqlite_store import SQLiteEventStore
        from rationalevault.cognitive_head.snapshot import NullSnapshotManager

        db_path = tmp_path / "test.db"
        store = SQLiteEventStore(db_path=str(db_path))

        proj = CognitiveHeadProjection()
        registry = ProjectionRegistry()
        registry.register(proj)
        registry.freeze()

        compiler = ProjectionCompiler(
            event_store=store,
            snapshot_manager=NullSnapshotManager(),
            registry=registry,
        )

        # Need to write events first
        pid = uuid4()
        events = _make_cognitive_head_events(pid)
        for e in events:
            _append_event(store, e)

        head = compiler.compile(pid, "cognitive_head")
        assert isinstance(head, CognitiveHead)
        assert head.project_name == "Test"

    def test_compile_unknown_projection(self):
        compiler = ProjectionCompiler()
        with pytest.raises(ProjectionNotFoundError):
            compiler.compile(uuid4(), "nonexistent")

    def test_health(self, tmp_path):
        from rationalevault.db.sqlite_store import SQLiteEventStore
        from rationalevault.cognitive_head.snapshot import NullSnapshotManager

        db_path = tmp_path / "test.db"
        store = SQLiteEventStore(db_path=str(db_path))

        proj = CognitiveHeadProjection()
        registry = ProjectionRegistry()
        registry.register(proj)
        registry.freeze()

        compiler = ProjectionCompiler(
            event_store=store,
            snapshot_manager=NullSnapshotManager(),
            registry=registry,
        )

        pid = uuid4()
        events = _make_cognitive_head_events(pid)
        for e in events:
            _append_event(store, e)

        compiler.compile(pid, "cognitive_head")
        assert compiler.health("cognitive_head") == ProjectionHealth.READY


# ── Backward Compatibility Tests ─────────────────────────────────────────────


class TestBackwardCompatibility:
    """Verify compile_cognitive_head_v2 produces identical output."""

    def test_v1_and_v2_identical(self, tmp_path):
        from rationalevault.db.sqlite_store import SQLiteEventStore
        from rationalevault.cognitive_head.snapshot import NullSnapshotManager

        db_path = tmp_path / "compat.db"
        store = SQLiteEventStore(db_path=str(db_path))
        pid = uuid4()
        events = _make_cognitive_head_events(pid)
        for e in events:
            _append_event(store, e)

        # v1 path
        head_v1 = compile_cognitive_head(
            project_id=pid,
            store=store,
            snapshot_manager=NullSnapshotManager(),
        )

        # v2 path
        head_v2 = compile_cognitive_head_v2(
            project_id=pid,
            store=store,
            snapshot_manager=NullSnapshotManager(),
        )

        assert head_v1.project_name == head_v2.project_name
        assert head_v1.project_goal == head_v2.project_goal
        assert head_v1.current_focus == head_v2.current_focus
        assert len(head_v1.active_tasks) == len(head_v2.active_tasks)
        assert len(head_v1.active_decisions) == len(
            head_v2.active_decisions,
        )
        assert len(head_v1.open_questions) == len(
            head_v2.open_questions,
        )


# ── Context Tests ────────────────────────────────────────────────────────────


class TestDependencyReader:
    def test_get_set(self):
        reader = DependencyReader()
        assert reader.get("test") is None
        reader.set("test", {"data": 1})
        assert reader.get("test") == {"data": 1}


class TestMetricsCollector:
    def test_record_and_snapshot(self):
        collector = MetricsCollector()
        collector.record("latency", 1.5)
        snap = collector.snapshot()
        assert snap["latency"] == 1.5
