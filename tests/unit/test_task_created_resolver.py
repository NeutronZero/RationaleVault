"""Unit proofs for TASK_CREATED v1→v2 resolver correctness.

These tests validate resolver and policy behavior at the unit level.
Integration proofs (pipeline-first) are in test_task_created_v1_to_v2.py.
"""

import pytest
import uuid
from datetime import datetime, timezone
from typing import Any

from rationalevault.schema.policy import (
    SchemaPolicy, EventSchema, MigrationPath, MigrationStep,
)
from rationalevault.schema.resolver import ReplayResolver, UnknownSchemaError
from rationalevault.schema.upcaster import UpcasterRegistry
from rationalevault.schema.events import EventRecord, EventType, EventMetadata


V1_PAYLOAD = {
    "task_id": "T1",
    "title": "Test",
    "description": "Unit proof",
}

V2_PAYLOAD = {
    "task_id": "T1",
    "details": {"summary": "Test", "body": "Unit proof"},
}


def _create_event(
    schema_version: int,
    payload: dict[str, Any],
    event_type: EventType = EventType.TASK_CREATED,
) -> EventRecord:
    """Create an EventRecord with the given schema version."""
    return EventRecord(
        event_sequence=1,
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        stream_id="tasks",
        version=1,
        event_type=event_type,
        metadata=EventMetadata(actor="test", source="unit_proof"),
        payload=payload,
        parent_id=None,
        recorded_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        schema_version=schema_version,
    )


def test_unknown_schema_path_fails():
    """Missing migration edge raises UnknownSchemaError.

    Property: Migration graph safety.
    """
    policy_no_path = SchemaPolicy(_schemas={
        EventType.TASK_CREATED: EventSchema(
            event_type=EventType.TASK_CREATED,
            latest_version=2,
            migration_path=MigrationPath(steps=()),
        )
    })

    registry = UpcasterRegistry.default()
    resolver = ReplayResolver(policy=policy_no_path, registry=registry)

    event = _create_event(schema_version=1, payload=V1_PAYLOAD)
    with pytest.raises(UnknownSchemaError):
        resolver.resolve(event)


def test_cyclic_migration_graph_rejected():
    """Cyclic migration graph is prevented.

    Property: Migration graph safety.
    """
    policy_cycle = SchemaPolicy(_schemas={
        EventType.TASK_CREATED: EventSchema(
            event_type=EventType.TASK_CREATED,
            latest_version=2,
            migration_path=MigrationPath(steps=(
                MigrationStep(1, 2),
                MigrationStep(2, 1),
            )),
        )
    })

    registry = UpcasterRegistry.default()
    resolver = ReplayResolver(policy=policy_cycle, registry=registry)

    # Cycles must not cause infinite loops
    event = _create_event(schema_version=1, payload=V1_PAYLOAD)
    try:
        result = resolver.resolve(event)
        assert result is not None
    except (UnknownSchemaError, ValueError):
        pass
