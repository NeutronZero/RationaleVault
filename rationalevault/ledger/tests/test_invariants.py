"""Constitutional invariant tests (I-02 through I-06, I-11).

Each invariant is tested against both MemoryLedger and SQLiteLedger.
"""

from datetime import datetime, timezone

import pytest

from rationalevault.canonical.envelope import CanonicalEnvelope
from rationalevault.canonical.payload import CanonicalPayload
from rationalevault.canonical.timestamp import CanonicalTimestamp
from rationalevault.canonical.types import EventType
from rationalevault.ledger.commit import CommitBuilder
from rationalevault.ledger.storage.memory import MemoryLedger
from rationalevault.ledger.storage.sqlite import SQLiteLedger


def _make_envelope(**overrides) -> CanonicalEnvelope:
    defaults = {
        "rvcj_version": 1,
        "event_schema_version": 1,
        "experience_id": "EXP-invariant-test",
        "event_type": EventType.DECISION_RECORDED,
        "stream_id": "inv-stream",
        "sequence": 1,
        "timestamp": CanonicalTimestamp.from_datetime(
            datetime(2026, 7, 14, 0, 0, 0, tzinfo=timezone.utc)
        ),
        "actor": "invariant-test",
        "payload": CanonicalPayload(data={"test": "data"}),
    }
    defaults.update(overrides)
    return CanonicalEnvelope(**defaults)


def _commit(stream_id: str, *events) -> "tuple":
    ledger = MemoryLedger()
    commit = CommitBuilder.from_events(stream_id=stream_id, events=list(events))
    receipt = ledger.append(commit)
    return ledger, commit, receipt


@pytest.fixture
def memory_ledger():
    return MemoryLedger()


@pytest.fixture
def sqlite_ledger(tmp_path):
    return SQLiteLedger(str(tmp_path / "invariants.db"))


BACKENDS = ["memory", "sqlite"]


@pytest.fixture(params=BACKENDS)
def ledger(request, memory_ledger, sqlite_ledger):
    if request.param == "memory":
        return memory_ledger
    return sqlite_ledger


# --- I-02: Never Mutates History ---

def test_i02_never_mutates_history(ledger):
    env = _make_envelope(sequence=1, payload=CanonicalPayload(data={"key": "original"}))
    commit = CommitBuilder.from_events("inv-stream", [env])
    ledger.append(commit)

    entries = ledger.read_stream("inv-stream")
    assert len(entries) == 1
    entry = entries[0]
    assert entry.sequence == 1
    assert entry.event_type == EventType.DECISION_RECORDED
    assert entry.payload == {"key": "original"}
    assert entry.commit_id == commit.commit_id


# --- I-02a: Append-Only ---

def test_i02a_ledger_has_no_delete_method(ledger):
    assert not hasattr(ledger, "delete")
    assert not hasattr(ledger, "remove")


def test_i02a_ledger_has_no_update_method(ledger):
    assert not hasattr(ledger, "update")
    assert not hasattr(ledger, "modify")


def test_i02a_appended_data_unchanged_on_reread(ledger):
    env = _make_envelope(sequence=1, payload=CanonicalPayload(data={"x": 1}))
    commit = CommitBuilder.from_events("inv-stream", [env])
    ledger.append(commit)

    read1 = ledger.read_stream("inv-stream")
    read2 = ledger.read_stream("inv-stream")

    assert len(read1) == 1
    assert len(read2) == 1
    assert read1[0].payload == read2[0].payload == {"x": 1}
    assert read1[0].sequence == read2[0].sequence == 1


# --- I-03: Stream Ordering ---

def test_i03_stream_ordering_deterministic(ledger):
    env1 = _make_envelope(sequence=1, payload=CanonicalPayload(data={"order": 1}))
    env2 = _make_envelope(sequence=2, payload=CanonicalPayload(data={"order": 2}))
    env3 = _make_envelope(sequence=3, payload=CanonicalPayload(data={"order": 3}))

    ledger.append(CommitBuilder.from_events("inv-stream", [env1]))
    ledger.append(CommitBuilder.from_events("inv-stream", [env2]))
    ledger.append(CommitBuilder.from_events("inv-stream", [env3]))

    entries = ledger.read_stream("inv-stream")
    assert len(entries) == 3
    assert [e.sequence for e in entries] == [1, 2, 3]
    assert [e.payload["order"] for e in entries] == [1, 2, 3]

    entries2 = ledger.read_stream("inv-stream")
    assert entries == entries2


# --- I-04: Commit Atomicity ---

def test_i04_commit_atomicity_single_event(ledger):
    env = _make_envelope(sequence=1)
    commit = CommitBuilder.from_events("inv-stream", [env])
    receipt = ledger.append(commit)

    entries = ledger.read_stream("inv-stream")
    assert len(entries) == 1
    assert entries[0].sequence == 1
    assert entries[0].commit_id == commit.commit_id
    assert receipt.sequence_start == 1
    assert receipt.sequence_end == 1


def test_i04_commit_atomicity_multi_event(ledger):
    env1 = _make_envelope(sequence=1, payload=CanonicalPayload(data={"n": 1}))
    env2 = _make_envelope(sequence=2, payload=CanonicalPayload(data={"n": 2}))
    commit = CommitBuilder.from_events("inv-stream", [env1, env2])
    receipt = ledger.append(commit)

    entries = ledger.read_stream("inv-stream")
    assert len(entries) == 2
    assert receipt.sequence_start == 1
    assert receipt.sequence_end == 2


# --- I-05: Idempotent Append ---

def test_i05_idempotent_append_same_receipt(ledger):
    env = _make_envelope(sequence=1)
    commit = CommitBuilder.from_events("inv-stream", [env])
    r1 = ledger.append(commit)
    r2 = ledger.append(commit)

    assert r1 == r2
    assert r1.commit_id == commit.commit_id


def test_i05_idempotent_append_no_duplication(ledger):
    env = _make_envelope(sequence=1)
    commit = CommitBuilder.from_events("inv-stream", [env])
    ledger.append(commit)
    ledger.append(commit)

    entries = ledger.read_stream("inv-stream")
    assert len(entries) == 1


def test_i05_idempotent_append_different_commits_distinct(ledger):
    env1 = _make_envelope(sequence=1)
    env2 = _make_envelope(sequence=2)
    c1 = CommitBuilder.from_events("inv-stream", [env1])
    c2 = CommitBuilder.from_events("inv-stream", [env2])
    r1 = ledger.append(c1)
    r2 = ledger.append(c2)

    assert r1 != r2
    assert r1.commit_id != r2.commit_id


# --- I-06: Commit Order Preservation ---

def test_i06_commit_order_preservation(ledger):
    env1 = _make_envelope(sequence=1, payload=CanonicalPayload(data={"idx": "first"}))
    env2 = _make_envelope(sequence=2, payload=CanonicalPayload(data={"idx": "second"}))
    env3 = _make_envelope(sequence=3, payload=CanonicalPayload(data={"idx": "third"}))

    commit = CommitBuilder.from_events("inv-stream", [env1, env2, env3])
    receipt = ledger.append(commit)

    entries = ledger.read_stream("inv-stream")
    assert len(entries) == 3
    assert entries[0].payload["idx"] == "first"
    assert entries[1].payload["idx"] == "second"
    assert entries[2].payload["idx"] == "third"
    assert receipt.sequence_start == 1
    assert receipt.sequence_end == 3


# --- I-11: Replay Completeness ---

def test_i11_replay_completeness_all_events_returned(ledger):
    events = []
    for i in range(1, 11):
        env = _make_envelope(sequence=i, payload=CanonicalPayload(data={"n": i}))
        events.append(env)

    ledger.append(CommitBuilder.from_events("inv-stream", events[:3]))
    ledger.append(CommitBuilder.from_events("inv-stream", events[3:7]))
    ledger.append(CommitBuilder.from_events("inv-stream", events[7:]))

    entries = ledger.read_stream("inv-stream")
    assert len(entries) == 10
    assert [e.sequence for e in entries] == list(range(1, 11))


def test_i11_replay_completeness_empty_stream(ledger):
    assert ledger.read_stream("empty-stream") == []


def test_i11_replay_completeness_single_event(ledger):
    env = _make_envelope(sequence=1)
    ledger.append(CommitBuilder.from_events("inv-stream", [env]))
    assert len(ledger.read_stream("inv-stream")) == 1
