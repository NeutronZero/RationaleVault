from rationalevault.schema.factory import SchemaPolicyFactory
from rationalevault.schema.policy import SchemaPolicy
from rationalevault.projections.governance import GovernanceState

def test_factory_compiles_empty_governance():
    state = GovernanceState(policies={}, schema_versions={})
    factory = SchemaPolicyFactory()
    policy = factory.compile(state)
    assert isinstance(policy, SchemaPolicy)

def test_factory_default_event_type():
    from rationalevault.schema.events import EventType
    state = GovernanceState(policies={}, schema_versions={})
    factory = SchemaPolicyFactory()
    policy = factory.compile(state)
    assert policy.latest_version(EventType.PROJECT_CREATED) == 1

def test_factory_compile_at_sequence():
    from rationalevault.schema.events import EventType
    state = GovernanceState(policies={}, schema_versions={})
    factory = SchemaPolicyFactory()
    policy = factory.compile_at_sequence(state, sequence=100)
    assert isinstance(policy, SchemaPolicy)
    assert policy.latest_version(EventType.PROJECT_CREATED) == 1


def test_factory_compiles_with_invalid_event_type():
    """Invalid event type strings are silently skipped."""
    from rationalevault.schema.events import EventType
    state = GovernanceState(
        policies={},
        schema_versions={"INVALID_TYPE": (2, 10)},
    )
    factory = SchemaPolicyFactory()
    policy = factory.compile(state)
    assert isinstance(policy, SchemaPolicy)
    assert policy.latest_version(EventType.PROJECT_CREATED) == 1


def test_factory_compile_at_sequence_filters_by_eff_seq():
    """Only schemas with eff_seq <= sequence are included."""
    from rationalevault.schema.events import EventType
    state = GovernanceState(
        policies={},
        schema_versions={
            "PROJECT_CREATED": (3, 50),
            "TASK_CREATED": (2, 100),
        },
    )
    factory = SchemaPolicyFactory()
    policy = factory.compile_at_sequence(state, sequence=75)
    assert policy.latest_version(EventType.PROJECT_CREATED) == 3
    assert policy.latest_version(EventType.TASK_CREATED) == 1