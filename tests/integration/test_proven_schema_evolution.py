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
from rationalevault.schema.factory import SchemaPolicyFactory
from rationalevault.schema.resolver import ReplayResolver


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


def test_policy_compilation_from_governance_state() -> None:
    """Test that SchemaPolicyFactory compiles SchemaPolicy from GovernanceState."""
    # Create a GovernanceState with schema_versions
    governance_state = GovernanceState(
        schema_versions={
            "TASK_CREATED": (2, 100),  # (version, effective_sequence)
            "PROJECT_CREATED": (1, 50),
        }
    )
    
    factory = SchemaPolicyFactory()
    policy = factory.compile(governance_state)
    
    # Verify policy contains the expected event types
    assert EventType.TASK_CREATED in list(policy.event_types())
    assert EventType.PROJECT_CREATED in list(policy.event_types())
    
    # Verify latest versions are correct
    assert policy.latest_version(EventType.TASK_CREATED) == 2
    assert policy.latest_version(EventType.PROJECT_CREATED) == 1
    
    # Verify default for unknown event type
    assert policy.latest_version(EventType.DECISION_PROPOSED) == 1
    
    # Verify migration paths exist (empty in this case)
    assert policy.migration_path(EventType.TASK_CREATED).exists() is False


def test_resolver_with_schema_policy_direct() -> None:
    """Test ReplayResolver directly with SchemaPolicy (not via pipeline)."""
    # Create policy with migration path
    policy = SchemaPolicy(_schemas={
        EventType.TASK_CREATED: EventSchema(
            event_type=EventType.TASK_CREATED,
            latest_version=2,
            migration_path=MigrationPath(steps=(MigrationStep(1, 2),)),
        )
    })
    
    registry = UpcasterRegistry()
    registry.register(EventType.TASK_CREATED, 1, task_created_v1_to_v2)
    resolver = ReplayResolver(policy=policy, registry=registry)
    
    # Test current event (v2) passes through unchanged
    v2_event = _create_task_event(1, 2, {
        "task_id": "T1",
        "details": {"summary": "test", "body": ""},
    })
    result = resolver.resolve(v2_event)
    assert result.schema_version == 2
    assert result.payload == v2_event.payload
    
    # Test v1 event is upcasted to v2
    v1_event = _create_task_event(2, 1, {
        "task_id": "T2",
        "title": "old format",
        "description": "old description",
    })
    result = resolver.resolve(v1_event)
    assert result.schema_version == 2
    assert "details" in result.payload
    assert result.payload["details"]["summary"] == "old format"
    assert result.payload["details"]["body"] == "old description"


def test_task_reducer_canonical_payloads() -> None:
    """Test TaskReducer receives and processes canonical v2 payloads."""
    # Create events with canonical v2 payloads (already resolved)
    events = [
        _create_task_event(1, 2, {
            "task_id": "T1",
            "details": {"summary": "Task 1", "body": "Description 1"},
            "assignee": "Alice",
        }),
        _create_task_event(2, 2, {
            "task_id": "T2",
            "details": {"summary": "Task 2", "body": "Description 2"},
            "priority": "high",
        }),
    ]
    
    tasks = TaskReducer.reduce(events)
    
    assert len(tasks) == 2
    assert tasks["T1"].title == "Task 1"
    assert tasks["T1"].description == "Description 1"
    assert tasks["T1"].assignee == "Alice"
    assert tasks["T2"].title == "Task 2"
    assert tasks["T2"].description == "Description 2"
    assert tasks["T2"].priority == "high"


def test_full_replay_flow_with_governance_state() -> None:
    """End-to-end test: GovernanceState → SchemaPolicy → ReplayResolver → ReplayPipeline → TaskReducer."""
    # 1. Create GovernanceState with schema versions
    governance_state = GovernanceState(
        schema_versions={
            "TASK_CREATED": (2, 100),
        }
    )
    
    # 2. Compile SchemaPolicy from GovernanceState
    factory = SchemaPolicyFactory()
    compiled_policy = factory.compile(governance_state)
    
    # 3. Augment policy with migration paths (GovernanceState doesn't contain migration info)
    # This simulates adding migration metadata from upcaster registry
    policy = SchemaPolicy(_schemas={
        EventType.TASK_CREATED: EventSchema(
            event_type=EventType.TASK_CREATED,
            latest_version=compiled_policy.latest_version(EventType.TASK_CREATED),
            migration_path=MigrationPath(steps=(MigrationStep(1, 2),)),
        )
    })
    
    # 4. Create registry with upcaster
    registry = UpcasterRegistry()
    registry.register(EventType.TASK_CREATED, 1, task_created_v1_to_v2)
    
    # 5. Create context and pipeline
    context = ReplayContext(schema_policy=policy)
    pipeline = ReplayPipeline(context, registry)
    
    # 6. Process mixed-version events
    raw_events = [
        _create_task_event(1, 1, {
            "task_id": "T1",
            "title": "Legacy task",
            "description": "Created in v1 format",
        }),
        _create_task_event(2, 2, {
            "task_id": "T2",
            "details": {"summary": "Modern task", "body": "Created in v2 format"},
        }),
    ]
    
    resolved_events = pipeline.process(raw_events)
    
    # 7. Verify resolution
    assert len(resolved_events) == 2
    assert all(e.schema_version == 2 for e in resolved_events)
    
    # 8. Feed to reducer
    tasks = TaskReducer.reduce(resolved_events)
    
    assert len(tasks) == 2
    assert tasks["T1"].title == "Legacy task"
    assert tasks["T1"].description == "Created in v1 format"
    assert tasks["T2"].title == "Modern task"
    assert tasks["T2"].description == "Created in v2 format"
