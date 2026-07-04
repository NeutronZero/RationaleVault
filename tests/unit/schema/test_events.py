"""
Unit tests for event schema serialization and invariants.
"""
from __future__ import annotations

import json
import uuid
from rationalevault.schema.events import EventMetadata, EventType, EventRecord
from datetime import datetime, timezone


def test_event_metadata_serialization_invariants():
    # Construct metadata
    meta = EventMetadata(
        actor="ClaudeAgent",
        source="ContextBuilder",
        correlation_id=str(uuid.uuid4()),
        session_id=str(uuid.uuid4()),
    )

    # 1. to_dict -> from_dict roundtrip preserves equality
    serialized = meta.to_dict()
    deserialized = EventMetadata.from_dict(serialized)

    assert deserialized.actor == meta.actor
    assert deserialized.source == meta.source
    assert deserialized.correlation_id == meta.correlation_id
    assert deserialized.session_id == meta.session_id

    # 2. JSON compatibility: dump -> load yields identical dict
    json_str = json.dumps(serialized)
    json_dict = json.loads(json_str)
    assert json_dict == serialized

    # 3. Normalization Invariant: from_dict(to_dict(obj)).to_dict() == to_dict(obj)
    assert deserialized.to_dict() == serialized


def test_governance_record_serialization_invariants() -> None:
    from rationalevault.schema.events import GovernanceRecord, GovernanceDomain, GovernanceAction

    record = GovernanceRecord(
        domain=GovernanceDomain.POLICY,
        action=GovernanceAction.ADJUSTED,
        target="memory_retrieval_threshold",
        rationale="Optimize context window usage under high traffic",
        previous_version="0.7",
        new_version="0.85",
        approved_by="Chief Architect",
        effective_sequence=150,
    )

    # 1. to_dict -> from_dict roundtrip preserves equality
    serialized = record.to_dict()
    deserialized = GovernanceRecord.from_dict(serialized)

    assert deserialized.domain == record.domain
    assert deserialized.action == record.action
    assert deserialized.target == record.target
    assert deserialized.rationale == record.rationale
    assert deserialized.previous_version == record.previous_version
    assert deserialized.new_version == record.new_version
    assert deserialized.approved_by == record.approved_by
    assert deserialized.effective_sequence == record.effective_sequence

    # 2. JSON serialization compatibility
    json_str = json.dumps(serialized)
    json_dict = json.loads(json_str)
    assert json_dict == serialized
    assert deserialized.to_dict() == serialized
