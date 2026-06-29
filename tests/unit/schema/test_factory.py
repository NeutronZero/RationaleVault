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