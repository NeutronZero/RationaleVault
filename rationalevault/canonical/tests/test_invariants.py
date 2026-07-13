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


def test_i00_canonical_representation():
    """I-00: Semantically equivalent objects produce identical canonical representations."""
    env1 = _make_envelope(
        payload=CanonicalPayload(data={"a": 1, "b": 2})
    )
    env2 = _make_envelope(
        payload=CanonicalPayload(data={"b": 2, "a": 1})
    )
    b1 = CanonicalSerializer.serialize(env1)
    b2 = CanonicalSerializer.serialize(env2)
    assert b1 == b2


def test_i00_unicode_normalization():
    """I-00: Unicode normalization produces identical representations."""
    env1 = _make_envelope(
        payload=CanonicalPayload(data={"text": "caf\u0065\u0301"})
    )
    env2 = _make_envelope(
        payload=CanonicalPayload(data={"text": "caf\u00e9"})
    )
    b1 = CanonicalSerializer.serialize(env1)
    b2 = CanonicalSerializer.serialize(env2)
    assert b1 == b2


def test_i08_referential_transparency():
    """I-08: All identifiers are deterministically generated via hash."""
    from rationalevault.canonical.id_generator import StableIdGenerator

    ts = CanonicalTimestamp.from_datetime(
        datetime(2026, 7, 13, 14, 35, 42, 123456, tzinfo=timezone.utc)
    )
    xid1 = StableIdGenerator.generate_experience_id("agent-001", "project-42", ts)
    xid2 = StableIdGenerator.generate_experience_id("agent-001", "project-42", ts)
    assert xid1 == xid2
    assert xid1.startswith("EXP-")
    assert len(xid1) == 16  # "EXP-" + 12 hex chars
