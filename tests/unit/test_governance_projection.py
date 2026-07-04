from __future__ import annotations

import uuid
from datetime import datetime, timezone

from rationalevault.schema.events import EventMetadata, EventRecord, EventType, GovernanceRecord, GovernanceDomain, GovernanceAction
from rationalevault.projections.governance import GovernanceProjection, GovernanceState


def _create_gov_event(sequence: int, record: GovernanceRecord) -> EventRecord:
    return EventRecord(
        event_sequence=sequence,
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        stream_id="governance",
        version=sequence,
        event_type=EventType.GOVERNANCE_DECISION_RECORDED,
        metadata=EventMetadata(actor="architect", source="governance_portal"),
        payload=record.to_dict(),
        parent_id=None,
        recorded_at=datetime.now(timezone.utc),
        schema_version=1,
    )


def test_governance_projection_processes_rules() -> None:
    events = [
        # Adjust policy at sequence 10
        _create_gov_event(
            10,
            GovernanceRecord(
                domain=GovernanceDomain.POLICY,
                action=GovernanceAction.ADJUSTED,
                target="retrieval_threshold",
                new_version="0.85",
                rationale="Optimize latency",
                effective_sequence=15,  # specified future sequence
            ),
        ),
        # Topology change at sequence 20
        _create_gov_event(
            20,
            GovernanceRecord(
                domain=GovernanceDomain.PROJECTION,
                action=GovernanceAction.TOPOLOGY_CHANGED,
                target="topology_v2_active",
                rationale="Enable workspace caching",
            ),
        ),
    ]

    state = GovernanceProjection.project(events)
    
    # Specified effective_sequence is 15
    assert state.get_effective_policy("retrieval_threshold", 14) is None
    assert state.get_effective_policy("retrieval_threshold", 15) == "0.85"

    # Default fallback to event sequence (20)
    assert state.projection_topology == "topology_v2_active"
    assert state.topology_effective_sequence == 20
