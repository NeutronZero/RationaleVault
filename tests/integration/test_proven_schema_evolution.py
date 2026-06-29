from __future__ import annotations

import uuid
from datetime import datetime, timezone
from rationalevault.schema.events import EventMetadata, EventRecord, EventType
from rationalevault.projections.context import ReplayContext, ReplayRequest, InterpretiveContextBuilder
from rationalevault.projections.governance import GovernanceState
from rationalevault.projections.pipeline import ReplayPipeline
from rationalevault.schema.policy import SchemaPolicy, EventSchema, MigrationPath, MigrationStep
from rationalevault.schema.upcaster import UpcasterRegistry
from rationalevault.schema.upcaster import task_created_v1_to_v2
from rationalevault.cognitive_head.reducers import TaskReducer


def _create_task_event(seq: int, schema_version: int, payload: dict) -> EventRecord:
    return EventRecord(
        event_sequence=seq,
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        stream_id="test-tasks",
        version=seq,
        event_type=EventType.TASK_CREATED,
        metadata=EventMetadata(actor="test-suite", source="integration"),
        payload=payload,
        parent_id=None,
        recorded_at=datetime.now(timezone.utc),
        schema_version=schema_version,
    )


def test_mixed_schema_versions_replay_equivalence() -> None:
    # Set up raw event stream with mixed versions
    raw_events = [
        # Event 1: Version 1 (flat format)
        _create_task_event(1, 1, {
            "task_id": "T1",
            "title": "Complete phase F15",
            "description": "Verify upcasting mechanics in integration tests",
            "assignee": "Orchestrator",
        }),
        # Event 2: Version 2 (nested details format)
        _create_task_event(2, 2, {
            "task_id": "T2",
            "details": {
                "summary": "Implement active interpretation",
                "body": "Hook up F16 governance policies next",
            },
            "assignee": "Orchestrator",
        }),
    ]

    # Build policy and registry for upcasting
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
    pipeline = ReplayPipeline(context, registry)
    resolved_events = pipeline.process(raw_events)

    assert len(resolved_events) == 2
    assert resolved_events[0].schema_version == 2
    assert resolved_events[1].schema_version == 2

    # Assert V1 was upcasted cleanly to V2 format
    assert resolved_events[0].payload["details"]["summary"] == "Complete phase F15"
    assert resolved_events[0].payload["details"]["body"] == "Verify upcasting mechanics in integration tests"

    # Fold events through TaskReducer
    tasks = TaskReducer.reduce(resolved_events)

    assert len(tasks) == 2
    assert tasks["T1"].title == "Complete phase F15"
    assert tasks["T1"].description == "Verify upcasting mechanics in integration tests"
    assert tasks["T2"].title == "Implement active interpretation"
    assert tasks["T2"].description == "Hook up F16 governance policies next"
