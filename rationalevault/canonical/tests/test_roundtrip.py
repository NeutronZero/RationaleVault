from datetime import datetime, timezone

import pytest

from rationalevault.canonical.envelope import CanonicalEnvelope
from rationalevault.canonical.payload import CanonicalPayload
from rationalevault.canonical.serializer import CanonicalSerializer
from rationalevault.canonical.id_generator import StableIdGenerator
from rationalevault.canonical.timestamp import CanonicalTimestamp
from rationalevault.canonical.types import EventType


def _make_envelope(**overrides) -> CanonicalEnvelope:
    defaults = {
        "rvcj_version": 1,
        "event_schema_version": 1,
        "experience_id": "EXP-a1b2c3d4e5f6",
        "event_type": EventType.DECISION_RECORDED,
        "stream_id": "project-42",
        "sequence": 1,
        "timestamp": CanonicalTimestamp.from_datetime(
            datetime(2026, 7, 13, 14, 35, 42, 123456, tzinfo=timezone.utc)
        ),
        "actor": "agent-001",
        "payload": CanonicalPayload(data={"key": "value"}),
    }
    defaults.update(overrides)
    return CanonicalEnvelope(**defaults)


def test_serialize_deserialize_roundtrip():
    env = _make_envelope()
    b = CanonicalSerializer.serialize(env)
    env2 = CanonicalSerializer.deserialize(b)
    b2 = CanonicalSerializer.serialize(env2)
    assert b == b2


def test_content_digest_stability():
    env = _make_envelope()
    d1 = CanonicalSerializer.content_digest(env)
    d2 = CanonicalSerializer.content_digest(env)
    assert d1 == d2


def test_unicode_roundtrip():
    env = _make_envelope(
        payload=CanonicalPayload(data={"text": "caf\u00e9"})
    )
    b = CanonicalSerializer.serialize(env)
    env2 = CanonicalSerializer.deserialize(b)
    assert env2.payload.data["text"] == "caf\u00e9"


def test_nested_payload_roundtrip():
    env = _make_envelope(
        payload=CanonicalPayload(data={"a": {"b": {"c": 1}}})
    )
    b = CanonicalSerializer.serialize(env)
    env2 = CanonicalSerializer.deserialize(b)
    assert env2.payload.data == {"a": {"b": {"c": 1}}}
