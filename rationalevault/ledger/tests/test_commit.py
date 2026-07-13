from datetime import datetime, timezone

import pytest

from rationalevault.canonical.envelope import CanonicalEnvelope
from rationalevault.canonical.payload import CanonicalPayload
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


def test_commit_immutable():
    from rationalevault.ledger.commit import Commit
    env = _make_envelope()
    c = Commit(commit_id="abc123", stream_id="test", events=[env])
    with pytest.raises(AttributeError):
        c.commit_id = "other"


def test_commit_fields():
    from rationalevault.ledger.commit import Commit
    env = _make_envelope()
    c = Commit(commit_id="abc123", stream_id="test", events=[env])
    assert c.commit_id == "abc123"
    assert c.stream_id == "test"
    assert c.events == [env]


def test_commit_builder_produces_commit():
    from rationalevault.ledger.commit import Commit, CommitBuilder
    env = _make_envelope()
    commit = CommitBuilder.from_events(stream_id="test", events=[env])
    assert isinstance(commit, Commit)
    assert commit.stream_id == "test"
    assert commit.events == [env]


def test_commit_builder_computes_commit_id():
    from rationalevault.ledger.commit import CommitBuilder
    env = _make_envelope()
    commit = CommitBuilder.from_events(stream_id="test", events=[env])
    assert commit.commit_id is not None
    assert len(commit.commit_id) == 64  # SHA-256 hex


def test_commit_builder_deterministic():
    from rationalevault.ledger.commit import CommitBuilder
    env = _make_envelope()
    c1 = CommitBuilder.from_events(stream_id="test", events=[env])
    c2 = CommitBuilder.from_events(stream_id="test", events=[env])
    assert c1.commit_id == c2.commit_id


def test_commit_builder_validates_same_experience_id():
    from rationalevault.ledger.commit import CommitBuilder
    env1 = _make_envelope(experience_id="EXP-aaa")
    env2 = _make_envelope(experience_id="EXP-bbb")
    with pytest.raises(ValueError, match="experience_id"):
        CommitBuilder.from_events(stream_id="test", events=[env1, env2])


def test_commit_builder_validates_events_not_empty():
    from rationalevault.ledger.commit import CommitBuilder
    with pytest.raises(ValueError, match="at least one event"):
        CommitBuilder.from_events(stream_id="test", events=[])


def test_commit_receipt_immutable():
    from rationalevault.ledger.commit import CommitReceipt
    r = CommitReceipt(commit_id="abc", stream_id="test", sequence_start=1, sequence_end=1, global_order=0)
    with pytest.raises(AttributeError):
        r.commit_id = "other"


def test_commit_receipt_fields():
    from rationalevault.ledger.commit import CommitReceipt
    r = CommitReceipt(commit_id="abc", stream_id="test", sequence_start=1, sequence_end=1, global_order=0)
    assert r.commit_id == "abc"
    assert r.stream_id == "test"
    assert r.sequence_start == 1
    assert r.sequence_end == 1
    assert r.global_order == 0


def test_ledger_entry_immutable():
    from rationalevault.ledger.entry import LedgerEntry
    e = LedgerEntry(
        stream_id="test", sequence=1, commit_id="abc",
        event_id="EVT-123", rvcj_version=1, event_schema_version=1,
        event_type="decision_recorded", timestamp="2026-07-13T14:35:42.123456Z",
        payload={"key": "value"}, global_order=0
    )
    with pytest.raises(AttributeError):
        e.stream_id = "other"


def test_ledger_entry_fields():
    from rationalevault.ledger.entry import LedgerEntry
    e = LedgerEntry(
        stream_id="test", sequence=1, commit_id="abc",
        event_id="EVT-123", rvcj_version=1, event_schema_version=1,
        event_type="decision_recorded", timestamp="2026-07-13T14:35:42.123456Z",
        payload={"key": "value"}, global_order=0
    )
    assert e.stream_id == "test"
    assert e.sequence == 1
    assert e.global_order == 0
