from datetime import datetime, timezone

import pytest

from rationalevault.canonical.envelope import CanonicalEnvelope
from rationalevault.canonical.payload import CanonicalPayload
from rationalevault.canonical.timestamp import CanonicalTimestamp
from rationalevault.canonical.types import EventType


def test_envelope_create():
    ts = CanonicalTimestamp.from_datetime(
        datetime(2026, 7, 13, 14, 35, 42, 123456, tzinfo=timezone.utc)
    )
    env = CanonicalEnvelope(
        rvcj_version=1,
        event_schema_version=1,
        experience_id="EXP-a1b2c3d4e5f6",
        event_type=EventType.DECISION_RECORDED,
        stream_id="project-42",
        sequence=1,
        timestamp=ts,
        actor="agent-001",
        payload=CanonicalPayload(data={"key": "value"}),
    )
    assert env.rvcj_version == 1
    assert env.event_type == EventType.DECISION_RECORDED


def test_envelope_to_dict():
    ts = CanonicalTimestamp.from_datetime(
        datetime(2026, 7, 13, 14, 35, 42, 123456, tzinfo=timezone.utc)
    )
    env = CanonicalEnvelope(
        rvcj_version=1,
        event_schema_version=1,
        experience_id="EXP-a1b2c3d4e5f6",
        event_type=EventType.DECISION_RECORDED,
        stream_id="project-42",
        sequence=1,
        timestamp=ts,
        actor="agent-001",
        payload=CanonicalPayload(data={"key": "value"}),
    )
    d = env.to_dict()
    assert d["rvcj_version"] == 1
    assert d["event_type"] == "decision_recorded"
    assert d["timestamp"] == "2026-07-13T14:35:42.123456Z"
    assert d["payload"] == {"key": "value"}


def test_envelope_from_dict():
    d = {
        "rvcj_version": 1,
        "event_schema_version": 1,
        "experience_id": "EXP-a1b2c3d4e5f6",
        "event_type": "decision_recorded",
        "stream_id": "project-42",
        "sequence": 1,
        "timestamp": "2026-07-13T14:35:42.123456Z",
        "actor": "agent-001",
        "payload": {"key": "value"},
    }
    env = CanonicalEnvelope.from_dict(d)
    assert env.rvcj_version == 1
    assert env.event_type == EventType.DECISION_RECORDED
    assert env.timestamp.to_iso8601() == "2026-07-13T14:35:42.123456Z"


def test_envelope_optional_fields():
    d = {
        "rvcj_version": 1,
        "event_schema_version": 1,
        "experience_id": "EXP-a1b2c3d4e5f6",
        "event_type": "decision_recorded",
        "stream_id": "project-42",
        "sequence": 1,
        "timestamp": "2026-07-13T14:35:42.123456Z",
        "actor": "agent-001",
        "payload": {"key": "value"},
        "correlation_id": "ctx-123",
        "causation_id": "EVT-456",
    }
    env = CanonicalEnvelope.from_dict(d)
    assert env.correlation_id == "ctx-123"
    assert env.causation_id == "EVT-456"
