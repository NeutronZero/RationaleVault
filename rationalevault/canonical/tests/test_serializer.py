from datetime import datetime, timezone

import pytest

from rationalevault.canonical.envelope import CanonicalEnvelope
from rationalevault.canonical.payload import CanonicalPayload
from rationalevault.canonical.serializer import CanonicalSerializer
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


def test_serialize_deterministic():
    env = _make_envelope()
    b1 = CanonicalSerializer.serialize(env)
    b2 = CanonicalSerializer.serialize(env)
    assert b1 == b2


def test_serialize_no_whitespace():
    env = _make_envelope()
    b = CanonicalSerializer.serialize(env)
    assert b'{"' in b
    assert b": " not in b


def test_serialize_canonical_keys():
    env = _make_envelope(
        payload=CanonicalPayload(data={"z": 1, "a": 2})
    )
    b = CanonicalSerializer.serialize(env)
    assert b.index(b"\"a\"") < b.index(b"\"z\"")


def test_deserialize_roundtrip():
    env = _make_envelope()
    b = CanonicalSerializer.serialize(env)
    env2 = CanonicalSerializer.deserialize(b)
    assert env == env2


def test_content_digest_deterministic():
    env = _make_envelope()
    d1 = CanonicalSerializer.content_digest(env)
    d2 = CanonicalSerializer.content_digest(env)
    assert d1 == d2
    assert len(d1) == 64  # full SHA-256 hex


def test_version():
    assert CanonicalSerializer.version() == 1


def test_algorithm():
    assert CanonicalSerializer.algorithm() == "sha-256"


def test_schema_fingerprint():
    fp = CanonicalSerializer.schema_fingerprint()
    assert isinstance(fp, str)
    assert len(fp) == 64  # SHA-256 hex
