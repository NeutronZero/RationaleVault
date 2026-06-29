from __future__ import annotations

import pytest
import uuid
from datetime import datetime, timezone
from typing import Any

from rationalevault.schema.events import EventMetadata, EventRecord, EventType
from rationalevault.schema.resolver import ReplayResolver, UnknownSchemaError
from rationalevault.schema.upcaster import UpcasterRegistry, task_created_v1_to_v2
from rationalevault.schema.policy import SchemaPolicy, EventSchema, MigrationPath, MigrationStep
from rationalevault.projections.context import ReplayContext
from rationalevault.projections.pipeline import ReplayPipeline


def _create_event(sequence: int, schema_version: int, payload: dict[str, Any], event_type: EventType = EventType.PROJECT_CREATED) -> EventRecord:
    return EventRecord(
        event_sequence=sequence,
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        stream_id="main",
        version=sequence,
        event_type=event_type,
        metadata=EventMetadata(actor="test", source="test"),
        payload=payload,
        parent_id=None,
        recorded_at=datetime.now(timezone.utc),
        schema_version=schema_version,
    )


def test_resolver_with_schema_policy() -> None:
    policy = SchemaPolicy(_schemas={})
    registry = UpcasterRegistry()
    resolver = ReplayResolver(policy=policy, registry=registry)
    assert resolver is not None


def test_resolver_current_event_unchanged() -> None:
    policy = SchemaPolicy(_schemas={
        EventType.TASK_CREATED: EventSchema(
            event_type=EventType.TASK_CREATED,
            latest_version=2,
            migration_path=MigrationPath(steps=(MigrationStep(1, 2),)),
        )
    })
    registry = UpcasterRegistry()
    resolver = ReplayResolver(policy=policy, registry=registry)
    event = _create_event(
        100, 2,
        {"details": {"summary": "test", "body": ""}},
        event_type=EventType.TASK_CREATED,
    )
    result = resolver.resolve(event)
    assert result.schema_version == 2
    assert result.payload == event.payload


def test_resolver_upcasts_event_with_policy() -> None:
    policy = SchemaPolicy(_schemas={
        EventType.TASK_CREATED: EventSchema(
            event_type=EventType.TASK_CREATED,
            latest_version=2,
            migration_path=MigrationPath(steps=(MigrationStep(1, 2),)),
        )
    })
    registry = UpcasterRegistry({"TASK_CREATED": {1: task_created_v1_to_v2}})
    resolver = ReplayResolver(policy=policy, registry=registry)
    event = _create_event(
        101, 1,
        {"title": "test", "description": "desc"},
        event_type=EventType.TASK_CREATED,
    )
    result = resolver.resolve(event)
    assert result.schema_version == 2
    assert "details" in result.payload


def test_resolver_policy_raises_on_unresolvable() -> None:
    policy = SchemaPolicy(_schemas={
        EventType.TASK_CREATED: EventSchema(
            event_type=EventType.TASK_CREATED,
            latest_version=3,
            migration_path=MigrationPath(steps=(MigrationStep(1, 2),)),
        )
    })
    registry = UpcasterRegistry()
    resolver = ReplayResolver(policy=policy, registry=registry)
    event = _create_event(
        102, 1,
        {"title": "test", "description": "desc"},
        event_type=EventType.TASK_CREATED,
    )
    with pytest.raises(UnknownSchemaError):
        resolver.resolve(event)


def test_replay_pipeline_applies_context_filtering_and_resolution() -> None:
    registry = UpcasterRegistry({"TASK_CREATED": {1: task_created_v1_to_v2}})
    policy = SchemaPolicy(_schemas={
        EventType.TASK_CREATED: EventSchema(
            event_type=EventType.TASK_CREATED,
            latest_version=2,
            migration_path=MigrationPath(steps=(MigrationStep(1, 2),)),
        )
    })
    context = ReplayContext(max_sequence=50, schema_policy=policy)
    pipeline = ReplayPipeline(context, registry)
    
    events = [
        _create_event(10, 1, {"title": "first", "description": "body1"}, event_type=EventType.TASK_CREATED),
        _create_event(20, 2, {"details": {"summary": "second", "body": "body2"}}, event_type=EventType.TASK_CREATED),
        _create_event(60, 1, {"title": "too far", "description": "body3"}, event_type=EventType.TASK_CREATED),
    ]
    
    processed = pipeline.process(events)
    assert len(processed) == 2
    
    assert processed[0].event_sequence == 10
    assert processed[0].payload == {"details": {"summary": "first", "body": "body1"}}
    assert processed[0].schema_version == 2
    
    assert processed[1].event_sequence == 20
    assert processed[1].payload == {"details": {"summary": "second", "body": "body2"}}
    assert processed[1].schema_version == 2


def test_replay_service_loads_and_processes_events() -> None:
    from unittest.mock import MagicMock
    from rationalevault.projections.service import ReplayService

    mock_store = MagicMock()
    events = [
        _create_event(10, 1, {"name": "first"}),
        _create_event(20, 1, {"name": "second"}),
    ]
    mock_store.get_project_stream.return_value = events

    policy = SchemaPolicy(_schemas={})
    context = ReplayContext(max_sequence=15, schema_policy=policy)
    service = ReplayService(mock_store)

    replayed = service.load_project_events(uuid.uuid4(), context)
    assert len(replayed) == 1
    assert replayed[0].event_sequence == 10
    mock_store.get_project_stream.assert_called_once()


def test_resolver_can_resolve_with_event_type() -> None:
    policy = SchemaPolicy(_schemas={
        EventType.TASK_CREATED: EventSchema(
            event_type=EventType.TASK_CREATED,
            latest_version=2,
            migration_path=MigrationPath(steps=(MigrationStep(1, 2),)),
        )
    })
    registry = UpcasterRegistry()
    resolver = ReplayResolver(policy=policy, registry=registry)
    assert resolver.can_resolve(1, EventType.TASK_CREATED) is True
    assert resolver.can_resolve(2, EventType.TASK_CREATED) is True
    assert resolver.can_resolve(3, EventType.TASK_CREATED) is False


def test_resolver_can_resolve_without_event_type() -> None:
    policy = SchemaPolicy(_schemas={})
    registry = UpcasterRegistry()
    resolver = ReplayResolver(policy=policy, registry=registry)
    assert resolver.can_resolve(1) is True
    assert resolver.can_resolve(100) is True


def test_resolver_unknown_event_type_with_empty_policy() -> None:
    policy = SchemaPolicy(_schemas={})
    registry = UpcasterRegistry()
    resolver = ReplayResolver(policy=policy, registry=registry)
    event = _create_event(1, 1, {"name": "test"}, event_type=EventType.PROJECT_CREATED)
    result = resolver.resolve(event)
    assert result.schema_version == 1
    assert result.payload == event.payload


def test_resolver_raises_on_missing_upcaster() -> None:
    policy = SchemaPolicy(_schemas={
        EventType.TASK_CREATED: EventSchema(
            event_type=EventType.TASK_CREATED,
            latest_version=2,
            migration_path=MigrationPath(steps=(MigrationStep(1, 2),)),
        )
    })
    registry = UpcasterRegistry()
    resolver = ReplayResolver(policy=policy, registry=registry)
    event = _create_event(1, 1, {"title": "test", "description": "desc"}, event_type=EventType.TASK_CREATED)
    with pytest.raises(UnknownSchemaError) as exc_info:
        resolver.resolve(event)
    assert "No upcaster registered" in str(exc_info.value)


def test_resolver_multi_step_migration() -> None:
    def upcaster_v1_to_v2(payload: dict[str, Any]) -> dict[str, Any]:
        payload_copy = dict(payload)
        payload_copy["details"] = {"summary": payload_copy.pop("title", ""), "body": payload_copy.pop("description", "")}
        return payload_copy

    def upcaster_v2_to_v3(payload: dict[str, Any]) -> dict[str, Any]:
        payload_copy = dict(payload)
        payload_copy["details"]["priority"] = "normal"
        return payload_copy

    policy = SchemaPolicy(_schemas={
        EventType.TASK_CREATED: EventSchema(
            event_type=EventType.TASK_CREATED,
            latest_version=3,
            migration_path=MigrationPath(steps=(MigrationStep(1, 2), MigrationStep(2, 3))),
        )
    })
    registry = UpcasterRegistry({
        "TASK_CREATED": {1: upcaster_v1_to_v2, 2: upcaster_v2_to_v3}
    })
    resolver = ReplayResolver(policy=policy, registry=registry)
    
    event = _create_event(1, 1, {"title": "test", "description": "desc"}, event_type=EventType.TASK_CREATED)
    result = resolver.resolve(event)
    
    assert result.schema_version == 3
    assert result.payload == {"details": {"summary": "test", "body": "desc", "priority": "normal"}}


def test_resolver_partial_migration_path() -> None:
    def upcaster_v1_to_v2(payload: dict[str, Any]) -> dict[str, Any]:
        payload_copy = dict(payload)
        payload_copy["details"] = {"summary": payload_copy.pop("title", ""), "body": payload_copy.pop("description", "")}
        return payload_copy

    policy = SchemaPolicy(_schemas={
        EventType.TASK_CREATED: EventSchema(
            event_type=EventType.TASK_CREATED,
            latest_version=3,
            migration_path=MigrationPath(steps=(MigrationStep(1, 2),)),
        )
    })
    registry = UpcasterRegistry({"TASK_CREATED": {1: upcaster_v1_to_v2}})
    resolver = ReplayResolver(policy=policy, registry=registry)
    
    event = _create_event(1, 1, {"title": "test", "description": "desc"}, event_type=EventType.TASK_CREATED)
    with pytest.raises(UnknownSchemaError):
        resolver.resolve(event)
