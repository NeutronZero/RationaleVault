from datetime import datetime, timezone

import pytest

from rationalevault.canonical.envelope import CanonicalEnvelope
from rationalevault.canonical.payload import CanonicalPayload
from rationalevault.canonical.timestamp import CanonicalTimestamp
from rationalevault.canonical.types import EventType
from rationalevault.ledger.commit import CommitBuilder
from rationalevault.ledger.storage.memory import MemoryLedger
from rationalevault.ledger.errors import DuplicateCommitError


def _make_envelope(**overrides) -> CanonicalEnvelope:
    defaults = {
        "rvcj_version": 1,
        "event_schema_version": 1,
        "experience_id": "EXP-a1b2c3d4e5f6",
        "event_type": EventType.DECISION_RECORDED,
        "stream_id": "test-stream",
        "sequence": 1,
        "timestamp": CanonicalTimestamp.from_datetime(
            datetime(2026, 7, 13, 14, 35, 42, 123456, tzinfo=timezone.utc)
        ),
        "actor": "agent-001",
        "payload": CanonicalPayload(data={"key": "value"}),
    }
    defaults.update(overrides)
    return CanonicalEnvelope(**defaults)


def _commit(*events) -> "tuple":
    """Helper: build a commit and return (ledger, commit, receipt)."""
    ledger = MemoryLedger()
    commit = CommitBuilder.from_events(stream_id=events[0].stream_id, events=list(events))
    receipt = ledger.append(commit)
    return ledger, commit, receipt


def test_append_returns_receipt():
    ledger = MemoryLedger()
    env = _make_envelope()
    commit = CommitBuilder.from_events("test-stream", [env])
    receipt = ledger.append(commit)
    assert receipt.commit_id == commit.commit_id
    assert receipt.stream_id == "test-stream"
    assert receipt.sequence_start == 1
    assert receipt.sequence_end == 1


def test_read_stream_returns_events_in_order():
    ledger = MemoryLedger()
    env1 = _make_envelope(sequence=1)
    env2 = _make_envelope(sequence=2)
    c1 = CommitBuilder.from_events("test-stream", [env1])
    r1 = ledger.append(c1)
    c2 = CommitBuilder.from_events("test-stream", [env2])
    r2 = ledger.append(c2)

    entries = ledger.read_stream("test-stream")
    assert len(entries) == 2
    assert entries[0].sequence == 1
    assert entries[1].sequence == 2


def test_read_stream_unknown_stream():
    ledger = MemoryLedger()
    assert ledger.read_stream("nonexistent") == []


def test_exists_true():
    ledger = MemoryLedger()
    env = _make_envelope()
    commit = CommitBuilder.from_events("test-stream", [env])
    ledger.append(commit)
    assert ledger.exists(commit.commit_id)


def test_exists_false():
    ledger = MemoryLedger()
    assert not ledger.exists("nonexistent-id")


def test_stream_exists_true():
    ledger = MemoryLedger()
    env = _make_envelope()
    commit = CommitBuilder.from_events("test-stream", [env])
    ledger.append(commit)
    assert ledger.stream_exists("test-stream")


def test_stream_exists_false():
    ledger = MemoryLedger()
    assert not ledger.stream_exists("nonexistent")


def test_read_from_returns_events_after_global_order():
    ledger = MemoryLedger()
    env1 = _make_envelope(sequence=1)
    env2 = _make_envelope(sequence=2)
    ledger.append(CommitBuilder.from_events("test-stream", [env1]))
    ledger.append(CommitBuilder.from_events("test-stream", [env2]))

    entries = ledger.read_from(1)
    assert len(entries) == 1
    assert entries[0].sequence == 2


def test_read_from_zero_returns_all():
    ledger = MemoryLedger()
    env1 = _make_envelope(sequence=1)
    env2 = _make_envelope(sequence=2)
    ledger.append(CommitBuilder.from_events("test-stream", [env1]))
    ledger.append(CommitBuilder.from_events("test-stream", [env2]))

    entries = ledger.read_from(0)
    assert len(entries) == 2


def test_idempotent_append_same_commit():
    ledger = MemoryLedger()
    env = _make_envelope()
    commit = CommitBuilder.from_events("test-stream", [env])
    r1 = ledger.append(commit)
    r2 = ledger.append(commit)
    assert r1 == r2
    # Verify no duplicate entries
    entries = ledger.read_stream("test-stream")
    assert len(entries) == 1


def test_append_rejects_sequence_gap():
    ledger = MemoryLedger()
    env1 = _make_envelope(sequence=1)
    env3 = _make_envelope(sequence=3)  # gap: seq 2 missing
    c1 = CommitBuilder.from_events("test-stream", [env1])
    ledger.append(c1)
    c3 = CommitBuilder.from_events("test-stream", [env3])
    with pytest.raises(ValueError, match="Sequence gap"):
        ledger.append(c3)


def test_global_order_monotonic_increasing():
    ledger = MemoryLedger()
    env1 = _make_envelope(sequence=1)
    env2 = _make_envelope(sequence=2)
    env3 = _make_envelope(sequence=3)
    r1 = ledger.append(CommitBuilder.from_events("test-stream", [env1]))
    r2 = ledger.append(CommitBuilder.from_events("test-stream", [env2]))
    r3 = ledger.append(CommitBuilder.from_events("test-stream", [env3]))
    assert r1.global_order < r2.global_order < r3.global_order


def test_sequence_contiguity_within_commit():
    ledger = MemoryLedger()
    env1 = _make_envelope(sequence=1)
    env2 = _make_envelope(sequence=2)
    commit = CommitBuilder.from_events("test-stream", [env1, env2])
    receipt = ledger.append(commit)
    assert receipt.sequence_start == 1
    assert receipt.sequence_end == 2
    entries = ledger.read_stream("test-stream")
    assert len(entries) == 2
    assert entries[0].sequence == 1
    assert entries[1].sequence == 2
