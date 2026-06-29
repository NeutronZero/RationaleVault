"""Integration proofs for TASK_CREATED v1→v2 migration.

Proves the SchemaPolicy architecture works under real schema evolution.
Each test validates one architectural property.

These tests exercise the public replay API (ReplayPipeline),
not internal resolver details.
"""

import time
import copy
import uuid
from datetime import datetime, timezone

import pytest

from rationalevault.schema.policy import (
    SchemaPolicy, EventSchema, MigrationPath, MigrationStep,
)
from rationalevault.schema.factory import SchemaPolicyFactory
from rationalevault.schema.upcaster import UpcasterRegistry
from rationalevault.schema.events import EventRecord, EventMetadata, EventType
from rationalevault.projections.context import ReplayContext
from rationalevault.projections.pipeline import ReplayPipeline
from rationalevault.projections.governance import GovernanceState
from rationalevault.cognitive_head.reducers import TaskReducer


# --- Fixtures ---

V1_PAYLOAD = {
    "task_id": "T1",
    "title": "Implement F15",
    "description": "Prove the architecture",
    "assignee": "Orchestrator",
}

V2_PAYLOAD = {
    "task_id": "T1",
    "details": {
        "summary": "Implement F15",
        "body": "Prove the architecture",
    },
    "assignee": "Orchestrator",
}


def _create_event(
    seq: int,
    schema_version: int,
    payload: dict,
    event_type: EventType = EventType.TASK_CREATED,
) -> EventRecord:
    """Create an EventRecord with the given schema version."""
    return EventRecord(
        event_sequence=seq,
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        stream_id="test-tasks",
        version=seq,
        event_type=event_type,
        metadata=EventMetadata(actor="test", source="integration"),
        payload=copy.deepcopy(payload),
        parent_id=None,
        recorded_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        schema_version=schema_version,
    )


POLICY_V2 = SchemaPolicy(_schemas={
    EventType.TASK_CREATED: EventSchema(
        event_type=EventType.TASK_CREATED,
        latest_version=2,
        migration_path=MigrationPath(steps=(MigrationStep(1, 2),)),
    )
})

POLICY_V1 = SchemaPolicy(_schemas={
    EventType.TASK_CREATED: EventSchema(
        event_type=EventType.TASK_CREATED,
        latest_version=1,
        migration_path=MigrationPath(steps=()),
    )
})


def _replay_via_pipeline(events, policy):
    """Replay events through the public pipeline API."""
    context = ReplayContext(schema_policy=policy)
    registry = UpcasterRegistry.default()
    pipeline = ReplayPipeline(context=context, registry=registry)

    resolved_events = pipeline.process(events)
    state = TaskReducer.reduce(resolved_events)
    return state


def test_mixed_replay_canonical_output():
    """Interleaved v1/v2 events replay to canonical v2.

    Property: Mixed-version normalization.
    Exercises: ReplayPipeline (public API).
    """
    events = [
        _create_event(seq=1, schema_version=1, payload=V1_PAYLOAD),
        _create_event(seq=2, schema_version=1, payload=V1_PAYLOAD),
        _create_event(seq=3, schema_version=2, payload=V2_PAYLOAD),
        _create_event(seq=4, schema_version=1, payload=V1_PAYLOAD),
        _create_event(seq=5, schema_version=2, payload=V2_PAYLOAD),
    ]

    state = _replay_via_pipeline(events, POLICY_V2)

    # Reducer should produce correct TaskState
    assert "T1" in state
    assert state["T1"].title == "Implement F15"
    assert state["T1"].description == "Prove the architecture"


def test_projection_equivalence():
    """Native v2 projection equals v1→upcast→projection.

    Property: Canonical projection equivalence.
    Exercises: ReplayPipeline (public API).
    """
    # Native v2 path
    v2_event = _create_event(seq=1, schema_version=2, payload=V2_PAYLOAD)
    state_v2 = _replay_via_pipeline([v2_event], POLICY_V2)

    # Upcasted v1 path
    v1_event = _create_event(seq=1, schema_version=1, payload=V1_PAYLOAD)
    state_v1 = _replay_via_pipeline([v1_event], POLICY_V2)

    # Projected state must be equal
    assert state_v2 == state_v1


def test_policy_authority():
    """Policy alone controls canonical interpretation.

    Property: T15 — Policy Authority.
    Exercises: ReplayPipeline (public API).

    Same v1 event, two different policies:
    - POLICY_V1 (latest=1): no upcasting, reducer receives flat v1 format → fails
      because reducer expects canonical v2 format.
    - POLICY_V2 (latest=2): upcasting applied, reducer receives v2 format → succeeds.
    """
    v1_event = _create_event(seq=1, schema_version=1, payload=V1_PAYLOAD)

    # Policy A: latest_version=1 (no migration) — reducer crashes on v1 format
    with pytest.raises(KeyError):
        _replay_via_pipeline([v1_event], POLICY_V1)

    # Policy B: latest_version=2 (migration applied) — succeeds
    state_b = _replay_via_pipeline([v1_event], POLICY_V2)

    # The policy alone determines whether replay succeeds or fails
    assert "T1" in state_b
    assert state_b["T1"].title == "Implement F15"


def test_governance_compiles_different_policies():
    """Different governance snapshots produce different policies.

    Property: F14 + F15 integration.
    Exercises: SchemaPolicyFactory (public API).
    """
    # Governance at sequence 50: TASK_CREATED latest = v1
    state_v1 = GovernanceState(
        schema_versions={"TASK_CREATED": (1, 1)}
    )

    # Governance at sequence 100: TASK_CREATED latest = v2
    state_v2 = GovernanceState(
        schema_versions={"TASK_CREATED": (2, 1)}
    )

    factory = SchemaPolicyFactory()
    policy_v1 = factory.compile(state_v1)
    policy_v2 = factory.compile(state_v2)

    # Policies must be different
    assert policy_v1.latest_version(EventType.TASK_CREATED) == 1
    assert policy_v2.latest_version(EventType.TASK_CREATED) == 2

    # Both must be immutable snapshots
    assert isinstance(policy_v1, SchemaPolicy)
    assert isinstance(policy_v2, SchemaPolicy)
