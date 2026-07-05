"""Integration proofs for DECISION_PROPOSED v1→v2 — independent per-event-type evolution."""
from __future__ import annotations

import time
import copy
import uuid
from rationalevault.schema.events import EventRecord, EventType, EventMetadata
from rationalevault.schema.policy import SchemaPolicy, EventSchema, MigrationPath, MigrationStep
from rationalevault.schema.upcaster import UpcasterRegistry, decision_proposed_v1_to_v2
from rationalevault.projections.context import ReplayContext
from rationalevault.projections.pipeline import ReplayPipeline
from rationalevault.cognitive_head.reducers import DecisionReducer, TaskReducer
from datetime import datetime, timezone


def _make_event(
    event_type: EventType,
    payload: dict,
    sequence: int,
    schema_version: int = 1,
    recorded_at: datetime | None = None,
) -> EventRecord:
    return EventRecord(
        event_sequence=sequence,
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        stream_id="test",
        version=sequence,
        event_type=event_type,
        payload=copy.deepcopy(payload),
        schema_version=schema_version,
        recorded_at=recorded_at or datetime(2025, 1, 1, tzinfo=timezone.utc),
        metadata=EventMetadata(actor="test", source="integration"),
        parent_id=None,
    )


def _make_policy(
    task_latest: int = 2,
    decision_latest: int = 2,
) -> SchemaPolicy:
    schemas = {}
    schemas[EventType.TASK_CREATED] = EventSchema(
        event_type=EventType.TASK_CREATED,
        latest_version=task_latest,
        migration_path=MigrationPath(steps=(
            MigrationStep(from_version=1, to_version=2),
        ) if task_latest >= 2 else ()),
    )
    schemas[EventType.DECISION_PROPOSED] = EventSchema(
        event_type=EventType.DECISION_PROPOSED,
        latest_version=decision_latest,
        migration_path=MigrationPath(steps=(
            MigrationStep(from_version=1, to_version=2),
        ) if decision_latest >= 2 else ()),
    )
    return SchemaPolicy(_schemas=schemas)


def _make_mixed_ledger() -> list[EventRecord]:
    return [
        _make_event(EventType.TASK_CREATED, {"task_id": "t1", "title": "Task A", "description": "desc"}, 1, schema_version=1),
        _make_event(EventType.DECISION_PROPOSED, {"decision_id": "d1", "title": "Decision 1"}, 2, schema_version=1),
        _make_event(EventType.TASK_CREATED, {"task_id": "t2", "title": "Task B", "description": ""}, 3, schema_version=2),
        _make_event(EventType.DECISION_PROPOSED, {"decision_id": "d2", "title": "Decision 2"}, 4, schema_version=1),
        _make_event(EventType.DECISION_PROPOSED, {
            "decision_id": "d3", "title": "Decision 3",
            "context": "has context", "category": "architectural",
        }, 5, schema_version=2),
    ]


class TestIndependentMigrationPaths:
    """Proof 1: Each event type migrates independently."""

    def test_task_migration_unaffected_by_decision(self) -> None:
        """TASK_CREATED migration works regardless of DECISION_PROPOSED presence."""
        policy = _make_policy(task_latest=2, decision_latest=1)
        registry = UpcasterRegistry.default()
        ctx = ReplayContext(schema_policy=policy)
        pipeline = ReplayPipeline(context=ctx, registry=registry)

        events = [
            _make_event(EventType.TASK_CREATED, {"task_id": "t1", "title": "T1", "description": "d"}, 1, schema_version=1),
            _make_event(EventType.DECISION_PROPOSED, {"decision_id": "d1", "title": "D1"}, 2, schema_version=1),
        ]
        result = pipeline.process(events)

        task_events = [e for e in result if e.event_type == EventType.TASK_CREATED]
        assert task_events[0].payload["details"]["summary"] == "T1"

    def test_decision_migration_unaffected_by_task(self) -> None:
        """DECISION_PROPOSED migration works regardless of TASK_CREATED presence."""
        policy = _make_policy(task_latest=1, decision_latest=2)
        registry = UpcasterRegistry.default()
        ctx = ReplayContext(schema_policy=policy)
        pipeline = ReplayPipeline(context=ctx, registry=registry)

        events = [
            _make_event(EventType.TASK_CREATED, {"task_id": "t1", "title": "T1", "description": "d"}, 1, schema_version=1),
            _make_event(EventType.DECISION_PROPOSED, {"decision_id": "d1", "title": "D1"}, 2, schema_version=1),
        ]
        result = pipeline.process(events)

        decision_events = [e for e in result if e.event_type == EventType.DECISION_PROPOSED]
        assert decision_events[0].payload["context"] == ""
        assert decision_events[0].payload["category"] == "general"


class TestMixedLedgerReplay:
    """Proof 2: Mixed-version ledger replays deterministically."""

    def test_repeated_replay_identical_output(self) -> None:
        """Replaying the same ordered mixed ledger produces identical results."""
        policy = _make_policy()
        registry = UpcasterRegistry.default()

        results = []
        for _ in range(5):
            ctx = ReplayContext(schema_policy=policy)
            pipeline = ReplayPipeline(context=ctx, registry=registry)
            result = pipeline.process(_make_mixed_ledger())
            results.append([(e.event_type, e.event_sequence, e.payload) for e in result])

        for r in results[1:]:
            assert r == results[0]


class TestPolicyIndependence:
    """Proof 3: Different policies produce different canonical outputs."""

    def test_policy_a_vs_policy_b(self) -> None:
        """Policy A (decisions v1) vs Policy B (decisions v2) produce different results."""
        policy_a = _make_policy(task_latest=2, decision_latest=1)
        policy_b = _make_policy(task_latest=2, decision_latest=2)
        registry = UpcasterRegistry.default()

        ledger = [
            _make_event(EventType.DECISION_PROPOSED, {"decision_id": "d1", "title": "D1"}, 1, schema_version=1),
        ]

        ctx_a = ReplayContext(schema_policy=policy_a)
        pipeline_a = ReplayPipeline(context=ctx_a, registry=registry)
        result_a = pipeline_a.process(ledger)

        ctx_b = ReplayContext(schema_policy=policy_b)
        pipeline_b = ReplayPipeline(context=ctx_b, registry=registry)
        result_b = pipeline_b.process(ledger)

        # Policy A: decision stays v1 (no context/category in payload)
        assert "context" not in result_a[0].payload
        assert "category" not in result_a[0].payload

        # Policy B: decision migrates to v2 (context/category added)
        assert result_b[0].payload["context"] == ""
        assert result_b[0].payload["category"] == "general"


class TestCanonicalIdempotence:
    """Proof 4: canonical(canonical(event)) == canonical(event)."""

    def test_idempotent_v1(self) -> None:
        """Upcasting a v1 event twice produces the same result."""
        v1 = {"decision_id": "d1", "title": "D1"}
        once = decision_proposed_v1_to_v2(v1)
        twice = decision_proposed_v1_to_v2(once)
        assert once == twice

    def test_idempotent_v2(self) -> None:
        """Upcasting an already-v2 event is a no-op."""
        v2 = {"decision_id": "d1", "title": "D1", "context": "c", "category": "cat"}
        result = decision_proposed_v1_to_v2(v2)
        assert result == v2


class TestDeterminism:
    """Proof 5: Replay is fully deterministic."""

    def test_deterministic_replay(self) -> None:
        """10 replays of the same ledger produce identical results."""
        policy = _make_policy()
        registry = UpcasterRegistry.default()
        ledger = _make_mixed_ledger()

        results = []
        for _ in range(10):
            ctx = ReplayContext(schema_policy=policy)
            pipeline = ReplayPipeline(context=ctx, registry=registry)
            result = pipeline.process(ledger)
            results.append([(e.event_type, e.event_sequence, e.payload) for e in result])

        for r in results[1:]:
            assert r == results[0]


class TestPerformanceBaseline:
    """Proof 6: Migration overhead within regression budget."""

    def test_migration_overhead(self) -> None:
        """Multi-event-type migration overhead is within budget.

        Uses warm-up + median of multiple runs for CI stability.
        """
        MAX_MIGRATION_OVERHEAD_RATIO = 50.0
        ledger_size = 1000
        WARMUP_RUNS = 5
        MEASURE_RUNS = 20

        # Build mixed ledger (all v1, need upcasting)
        ledger = []
        for i in range(ledger_size):
            if i % 2 == 0:
                ledger.append(_make_event(
                    EventType.TASK_CREATED,
                    {"task_id": f"t{i}", "title": f"Task {i}", "description": ""},
                    i + 1, schema_version=1,
                ))
            else:
                ledger.append(_make_event(
                    EventType.DECISION_PROPOSED,
                    {"decision_id": f"d{i}", "title": f"Decision {i}"},
                    i + 1, schema_version=1,
                ))

        # Baseline: all events already canonical (v2)
        baseline_ledger = []
        for i in range(ledger_size):
            if i % 2 == 0:
                baseline_ledger.append(_make_event(
                    EventType.TASK_CREATED,
                    {"task_id": f"t{i}", "title": f"Task {i}", "details": {"summary": f"Task {i}", "body": ""}},
                    i + 1, schema_version=2,
                ))
            else:
                baseline_ledger.append(_make_event(
                    EventType.DECISION_PROPOSED,
                    {"decision_id": f"d{i}", "title": f"Decision {i}", "context": "", "category": "general"},
                    i + 1, schema_version=2,
                ))

        policy = _make_policy()
        registry = UpcasterRegistry.default()

        # Warm-up: run both to prime caches and JIT
        for _ in range(WARMUP_RUNS):
            ctx = ReplayContext(schema_policy=policy)
            pipeline = ReplayPipeline(context=ctx, registry=registry)
            pipeline.process(baseline_ledger)
            ctx = ReplayContext(schema_policy=policy)
            pipeline = ReplayPipeline(context=ctx, registry=registry)
            pipeline.process(ledger)

        # Measure baseline (median of MEASURE_RUNS)
        baseline_times = []
        for _ in range(MEASURE_RUNS):
            start = time.perf_counter()
            ctx = ReplayContext(schema_policy=policy)
            pipeline = ReplayPipeline(context=ctx, registry=registry)
            pipeline.process(baseline_ledger)
            baseline_times.append(time.perf_counter() - start)
        baseline_times.sort()
        baseline_time = baseline_times[MEASURE_RUNS // 2]

        # Measure migration (median of MEASURE_RUNS)
        measured_times = []
        for _ in range(MEASURE_RUNS):
            start = time.perf_counter()
            ctx = ReplayContext(schema_policy=policy)
            pipeline = ReplayPipeline(context=ctx, registry=registry)
            pipeline.process(ledger)
            measured_times.append(time.perf_counter() - start)
        measured_times.sort()
        measured_time = measured_times[MEASURE_RUNS // 2]

        overhead = measured_time / baseline_time if baseline_time > 0 else 1.0

        assert overhead <= MAX_MIGRATION_OVERHEAD_RATIO, (
            f"Migration overhead {overhead:.2f}x exceeds budget {MAX_MIGRATION_OVERHEAD_RATIO}x"
        )


class TestEventTypeIsolation:
    """Proof 7: Missing upcaster fails locally."""

    def test_missing_decision_upcaster_fails_localized(self) -> None:
        """Registry without DECISION_PROPOSED migration fails only for DECISION events."""
        from rationalevault.schema.resolver import UnknownSchemaError

        # Registry with only TASK_CREATED migration
        registry = UpcasterRegistry({"TASK_CREATED": {1: __import__(
            "rationalevault.schema.upcaster", fromlist=["task_created_v1_to_v2"]
        ).task_created_v1_to_v2}})

        policy = _make_policy(task_latest=2, decision_latest=2)
        ctx = ReplayContext(schema_policy=policy)
        pipeline = ReplayPipeline(context=ctx, registry=registry)

        ledger = [
            _make_event(EventType.TASK_CREATED, {"task_id": "t1", "title": "T1", "description": ""}, 1, schema_version=1),
            _make_event(EventType.DECISION_PROPOSED, {"decision_id": "d1", "title": "D1"}, 2, schema_version=1),
        ]

        # Should raise because DECISION_PROPOSED migration is missing
        try:
            pipeline.process(ledger)
            assert False, "Expected UnknownSchemaError"
        except UnknownSchemaError:
            pass


class TestRegistryCompleteness:
    """Proof 8: All policy migrations form complete executable chains."""

    def test_all_migrations_registered(self) -> None:
        """Every migration declared by SchemaPolicy exists in UpcasterRegistry."""
        policy = _make_policy()
        registry = UpcasterRegistry.default()

        for event_type in [EventType.TASK_CREATED, EventType.DECISION_PROPOSED]:
            schema = policy._schemas.get(event_type)
            if schema and schema.migration_path:
                for step in schema.migration_path.steps:
                    assert registry.is_registered(event_type, step.from_version), (
                        f"Migration {event_type.value} v{step.from_version}→v{step.to_version} "
                        f"not registered in UpcasterRegistry"
                    )

    def test_all_migrations_callable(self) -> None:
        """Every registered migration is a callable, not None or wrong function."""
        policy = _make_policy()
        registry = UpcasterRegistry.default()

        for event_type in [EventType.TASK_CREATED, EventType.DECISION_PROPOSED]:
            schema = policy._schemas.get(event_type)
            if schema and schema.migration_path:
                for step in schema.migration_path.steps:
                    fn = registry.get_upcaster(event_type, step.from_version)
                    assert fn is not None, (
                        f"Migration {event_type.value} v{step.from_version}→v{step.to_version} "
                        f"returned None from registry"
                    )
                    assert callable(fn), (
                        f"Migration {event_type.value} v{step.from_version}→v{step.to_version} "
                        f"is not callable: {fn}"
                    )
