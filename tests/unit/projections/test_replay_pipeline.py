"""Tests for ReplayPipeline execution ownership."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from rationalevault.schema.events import EventMetadata, EventRecord, EventType
from rationalevault.projections.context import ReplayContext
from rationalevault.projections.governance import GovernanceState
from rationalevault.projections.pipeline import ReplayPipeline
from rationalevault.schema.policy import SchemaPolicy, EventSchema, MigrationPath, MigrationStep
from rationalevault.schema.factory import SchemaPolicyFactory
from rationalevault.schema.upcaster import UpcasterRegistry, task_created_v1_to_v2


def _create_event(
    seq: int,
    event_type: EventType,
    schema_version: int,
    payload: dict,
) -> EventRecord:
    return EventRecord(
        event_sequence=seq,
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        stream_id="test-stream",
        version=seq,
        event_type=event_type,
        metadata=EventMetadata(actor="test", source="test"),
        payload=payload,
        parent_id=None,
        recorded_at=datetime.now(timezone.utc),
        schema_version=schema_version,
    )


def test_pipeline_with_policy_factory():
    """Pipeline accepts policy_factory parameter."""
    factory = SchemaPolicyFactory()
    pipeline = ReplayPipeline(policy_factory=factory)
    assert pipeline._policy_factory is factory


def test_pipeline_run_applies_reducer():
    """run() method orchestrates reducer calls with canonical payloads."""
    registry = UpcasterRegistry()
    registry.register(EventType.TASK_CREATED, 1, task_created_v1_to_v2)

    policy = SchemaPolicy(_schemas={
        EventType.TASK_CREATED: EventSchema(
            event_type=EventType.TASK_CREATED,
            latest_version=2,
            migration_path=MigrationPath(steps=(MigrationStep(1, 2),)),
        )
    })
    context = ReplayContext(schema_policy=policy)

    events = [
        _create_event(1, EventType.TASK_CREATED, 1, {
            "title": "Task 1",
            "description": "Description 1",
        }),
        _create_event(2, EventType.TASK_CREATED, 2, {
            "details": {"summary": "Task 2", "body": "Description 2"},
        }),
    ]

    def count_reducer(resolved_events):
        return len(resolved_events)

    pipeline = ReplayPipeline(context, registry)
    result = pipeline.run(count_reducer, events)
    assert result == 2


def test_pipeline_run_resolves_events():
    """run() resolves events to canonical version before reducer."""
    registry = UpcasterRegistry()
    registry.register(EventType.TASK_CREATED, 1, task_created_v1_to_v2)

    policy = SchemaPolicy(_schemas={
        EventType.TASK_CREATED: EventSchema(
            event_type=EventType.TASK_CREATED,
            latest_version=2,
            migration_path=MigrationPath(steps=(MigrationStep(1, 2),)),
        )
    })
    context = ReplayContext(schema_policy=policy)

    events = [
        _create_event(1, EventType.TASK_CREATED, 1, {
            "title": "Task 1",
            "description": "Description 1",
        }),
    ]

    def extract_schema_versions(resolved_events):
        return [e.schema_version for e in resolved_events]

    pipeline = ReplayPipeline(context, registry)
    result = pipeline.run(extract_schema_versions, events)
    assert result == [2]


def test_pipeline_run_respects_max_sequence():
    """run() respects max_sequence limit from context."""
    registry = UpcasterRegistry()
    policy = SchemaPolicy(_schemas={})
    context = ReplayContext(max_sequence=5, schema_policy=policy)

    events = [
        _create_event(3, EventType.TASK_CREATED, 1, {"x": 1}),
        _create_event(6, EventType.TASK_CREATED, 1, {"x": 2}),
        _create_event(10, EventType.TASK_CREATED, 1, {"x": 3}),
    ]

    def collect_ids(resolved_events):
        return [e.event_sequence for e in resolved_events]

    pipeline = ReplayPipeline(context, registry)
    result = pipeline.run(collect_ids, events)
    assert result == [3]


def test_pipeline_run_empty_events():
    """run() handles empty event list."""
    policy = SchemaPolicy(_schemas={})
    context = ReplayContext(schema_policy=policy)

    def identity(reduced):
        return reduced

    pipeline = ReplayPipeline(context, UpcasterRegistry())
    result = pipeline.run(identity, [])
    assert result == []


def test_pipeline_backward_compatible_process():
    """process() still works for backward compatibility."""
    registry = UpcasterRegistry()
    registry.register(EventType.TASK_CREATED, 1, task_created_v1_to_v2)

    policy = SchemaPolicy(_schemas={
        EventType.TASK_CREATED: EventSchema(
            event_type=EventType.TASK_CREATED,
            latest_version=2,
            migration_path=MigrationPath(steps=(MigrationStep(1, 2),)),
        )
    })
    context = ReplayContext(schema_policy=policy)

    events = [
        _create_event(1, EventType.TASK_CREATED, 1, {
            "title": "Task 1",
            "description": "Description 1",
        }),
    ]

    pipeline = ReplayPipeline(context, registry)
    result = pipeline.process(events)
    assert len(result) == 1
    assert result[0].schema_version == 2
