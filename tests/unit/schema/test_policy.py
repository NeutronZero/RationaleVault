from rationalevault.schema.policy import MigrationStep, MigrationPath, EventSchema, SchemaPolicy
from rationalevault.schema.events import EventType


def test_migration_step_creation():
    step = MigrationStep(from_version=1, to_version=2)
    assert step.from_version == 1
    assert step.to_version == 2


def test_migration_step_is_frozen():
    step = MigrationStep(from_version=1, to_version=2)
    try:
        step.from_version = 3
        assert False, "Should be frozen"
    except AttributeError:
        pass


def test_migration_path_empty():
    path = MigrationPath(steps=())
    assert path.exists() is False


def test_migration_path_with_steps():
    path = MigrationPath(steps=(MigrationStep(1, 2),))
    assert path.exists() is True
    assert len(path.steps) == 1


def test_migration_path_is_frozen():
    path = MigrationPath(steps=())
    try:
        path.steps = (MigrationStep(1, 2),)
        assert False, "Should be frozen"
    except AttributeError:
        pass


def test_event_schema_creation():
    schema = EventSchema(
        event_type=EventType.TASK_CREATED,
        latest_version=2,
        migration_path=MigrationPath(steps=(MigrationStep(1, 2),)),
    )
    assert schema.event_type == EventType.TASK_CREATED
    assert schema.latest_version == 2
    assert schema.migration_path.exists() is True


def test_event_schema_no_migration():
    schema = EventSchema(
        event_type=EventType.PROJECT_CREATED,
        latest_version=1,
        migration_path=MigrationPath(),
    )
    assert schema.latest_version == 1
    assert schema.migration_path.exists() is False


def test_schema_policy_default_event_type():
    policy = SchemaPolicy(_schemas={})
    assert policy.latest_version(EventType.PROJECT_CREATED) == 1
    assert policy.migration_path(EventType.PROJECT_CREATED).exists() is False


def test_schema_policy_explicit_event_type():
    policy = SchemaPolicy(_schemas={
        EventType.TASK_CREATED: EventSchema(
            event_type=EventType.TASK_CREATED,
            latest_version=2,
            migration_path=MigrationPath(steps=(MigrationStep(1, 2),)),
        )
    })
    assert policy.latest_version(EventType.TASK_CREATED) == 2
    assert policy.migration_path(EventType.TASK_CREATED).exists() is True


def test_schema_policy_is_current():
    from rationalevault.schema.events import EventRecord, EventMetadata
    from datetime import datetime
    from uuid import uuid4
    policy = SchemaPolicy(_schemas={
        EventType.TASK_CREATED: EventSchema(
            event_type=EventType.TASK_CREATED,
            latest_version=2,
            migration_path=MigrationPath(steps=(MigrationStep(1, 2),)),
        )
    })
    event = EventRecord(
        event_sequence=1, id=uuid4(), project_id=uuid4(), stream_id="test",
        version=1, event_type=EventType.TASK_CREATED, parent_id=None,
        schema_version=2, payload={},
        metadata=EventMetadata(actor="test", source="test"),
        recorded_at=datetime.now(),
    )
    assert policy.is_current(event) is True


def test_schema_policy_is_not_current():
    from rationalevault.schema.events import EventRecord, EventMetadata
    from datetime import datetime
    from uuid import uuid4
    policy = SchemaPolicy(_schemas={
        EventType.TASK_CREATED: EventSchema(
            event_type=EventType.TASK_CREATED,
            latest_version=2,
            migration_path=MigrationPath(steps=(MigrationStep(1, 2),)),
        )
    })
    event = EventRecord(
        event_sequence=1, id=uuid4(), project_id=uuid4(), stream_id="test",
        version=1, event_type=EventType.TASK_CREATED, parent_id=None,
        schema_version=1, payload={},
        metadata=EventMetadata(actor="test", source="test"),
        recorded_at=datetime.now(),
    )
    assert policy.is_current(event) is False


def test_schema_policy_event_types():
    policy = SchemaPolicy(_schemas={
        EventType.TASK_CREATED: EventSchema(
            event_type=EventType.TASK_CREATED,
            latest_version=2,
            migration_path=MigrationPath(),
        )
    })
    assert EventType.TASK_CREATED in list(policy.event_types())


def test_schema_policy_schema_returns_full_metadata():
    schema = EventSchema(
        event_type=EventType.TASK_CREATED,
        latest_version=3,
        migration_path=MigrationPath(steps=(MigrationStep(1, 2), MigrationStep(2, 3))),
    )
    policy = SchemaPolicy(_schemas={EventType.TASK_CREATED: schema})
    result = policy.schema(EventType.TASK_CREATED)
    assert result.event_type == EventType.TASK_CREATED
    assert result.latest_version == 3
    assert len(result.migration_path.steps) == 2


def test_schema_policy_schema_default_for_unknown():
    policy = SchemaPolicy(_schemas={})
    result = policy.schema(EventType.PROJECT_CREATED)
    assert result.event_type == EventType.PROJECT_CREATED
    assert result.latest_version == 1
    assert result.migration_path.exists() is False


def test_schema_policy_can_resolve_current_event():
    from rationalevault.schema.events import EventRecord, EventMetadata
    from datetime import datetime
    from uuid import uuid4
    policy = SchemaPolicy(_schemas={
        EventType.TASK_CREATED: EventSchema(
            event_type=EventType.TASK_CREATED,
            latest_version=2,
            migration_path=MigrationPath(steps=(MigrationStep(1, 2),)),
        )
    })
    event = EventRecord(
        event_sequence=1, id=uuid4(), project_id=uuid4(), stream_id="test",
        version=1, event_type=EventType.TASK_CREATED, parent_id=None,
        schema_version=2, payload={},
        metadata=EventMetadata(actor="test", source="test"),
        recorded_at=datetime.now(),
    )
    assert policy.can_resolve(event) is True


def test_schema_policy_can_resolve_via_migration():
    from rationalevault.schema.events import EventRecord, EventMetadata
    from datetime import datetime
    from uuid import uuid4
    policy = SchemaPolicy(_schemas={
        EventType.TASK_CREATED: EventSchema(
            event_type=EventType.TASK_CREATED,
            latest_version=2,
            migration_path=MigrationPath(steps=(MigrationStep(1, 2),)),
        )
    })
    event = EventRecord(
        event_sequence=1, id=uuid4(), project_id=uuid4(), stream_id="test",
        version=1, event_type=EventType.TASK_CREATED, parent_id=None,
        schema_version=1, payload={},
        metadata=EventMetadata(actor="test", source="test"),
        recorded_at=datetime.now(),
    )
    assert policy.can_resolve(event) is True


def test_schema_policy_cannot_resolve_no_path():
    from rationalevault.schema.events import EventRecord, EventMetadata
    from datetime import datetime
    from uuid import uuid4
    policy = SchemaPolicy(_schemas={
        EventType.TASK_CREATED: EventSchema(
            event_type=EventType.TASK_CREATED,
            latest_version=2,
            migration_path=MigrationPath(),
        )
    })
    event = EventRecord(
        event_sequence=1, id=uuid4(), project_id=uuid4(), stream_id="test",
        version=1, event_type=EventType.TASK_CREATED, parent_id=None,
        schema_version=1, payload={},
        metadata=EventMetadata(actor="test", source="test"),
        recorded_at=datetime.now(),
    )
    assert policy.can_resolve(event) is False


def test_schema_policy_can_resolve_multi_step():
    from rationalevault.schema.events import EventRecord, EventMetadata
    from datetime import datetime
    from uuid import uuid4
    policy = SchemaPolicy(_schemas={
        EventType.TASK_CREATED: EventSchema(
            event_type=EventType.TASK_CREATED,
            latest_version=3,
            migration_path=MigrationPath(steps=(
                MigrationStep(1, 2), MigrationStep(2, 3),
            )),
        )
    })
    event = EventRecord(
        event_sequence=1, id=uuid4(), project_id=uuid4(), stream_id="test",
        version=1, event_type=EventType.TASK_CREATED, parent_id=None,
        schema_version=1, payload={},
        metadata=EventMetadata(actor="test", source="test"),
        recorded_at=datetime.now(),
    )
    assert policy.can_resolve(event) is True


def test_schema_policy_can_resolve_partial_path():
    from rationalevault.schema.events import EventRecord, EventMetadata
    from datetime import datetime
    from uuid import uuid4
    policy = SchemaPolicy(_schemas={
        EventType.TASK_CREATED: EventSchema(
            event_type=EventType.TASK_CREATED,
            latest_version=3,
            migration_path=MigrationPath(steps=(MigrationStep(2, 3),)),
        )
    })
    event = EventRecord(
        event_sequence=1, id=uuid4(), project_id=uuid4(), stream_id="test",
        version=1, event_type=EventType.TASK_CREATED, parent_id=None,
        schema_version=1, payload={},
        metadata=EventMetadata(actor="test", source="test"),
        recorded_at=datetime.now(),
    )
    assert policy.can_resolve(event) is False


def test_schema_policy_default_event_type_can_resolve():
    from rationalevault.schema.events import EventRecord, EventMetadata
    from datetime import datetime
    from uuid import uuid4
    policy = SchemaPolicy(_schemas={})
    event = EventRecord(
        event_sequence=1, id=uuid4(), project_id=uuid4(), stream_id="test",
        version=1, event_type=EventType.PROJECT_CREATED, parent_id=None,
        schema_version=1, payload={},
        metadata=EventMetadata(actor="test", source="test"),
        recorded_at=datetime.now(),
    )
    assert policy.can_resolve(event) is True


def test_migration_path_multi_step_exists():
    path = MigrationPath(steps=(MigrationStep(1, 2), MigrationStep(2, 3)))
    assert path.exists() is True
    assert len(path.steps) == 2