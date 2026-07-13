"""Behavioral equivalence: MemoryLedger and SQLiteLedger produce identical outputs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

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
        "experience_id": "EXP-equivalence",
        "event_type": EventType.DECISION_RECORDED,
        "stream_id": "eq-stream",
        "sequence": 1,
        "timestamp": CanonicalTimestamp.from_datetime(
            datetime(2026, 7, 14, 0, 0, 0, tzinfo=timezone.utc)
        ),
        "actor": "equivalence-test",
        "payload": CanonicalPayload(data={"eq": True}),
    }
    defaults.update(overrides)
    return CanonicalEnvelope(**defaults)


def _run_operations(ledger) -> tuple[list, list]:
    """Execute a sequence of append+read operations and return (receipts, entries)."""
    receipts = []
    all_entries = []

    e1 = _make_envelope(sequence=1, stream_id="stream-a", payload=CanonicalPayload(data={"n": 1}))
    e2 = _make_envelope(sequence=2, stream_id="stream-a", payload=CanonicalPayload(data={"n": 2}))
    e3 = _make_envelope(sequence=1, stream_id="stream-b", payload=CanonicalPayload(data={"s": "x"}))
    e4 = _make_envelope(sequence=2, stream_id="stream-b", payload=CanonicalPayload(data={"s": "y"}))
    e5 = _make_envelope(sequence=3, stream_id="stream-b", payload=CanonicalPayload(data={"s": "z"}))
    e6 = _make_envelope(sequence=3, stream_id="stream-a", payload=CanonicalPayload(data={"n": 3}))
    e7 = _make_envelope(sequence=4, stream_id="stream-a", payload=CanonicalPayload(data={"n": 4}))

    r = ledger.append(CommitBuilder.from_events("stream-a", [e1]))
    receipts.append(r)

    r = ledger.append(CommitBuilder.from_events("stream-a", [e2]))
    receipts.append(r)

    r = ledger.append(CommitBuilder.from_events("stream-b", [e3, e4]))
    receipts.append(r)

    r = ledger.append(CommitBuilder.from_events("stream-b", [e5]))
    receipts.append(r)

    r = ledger.append(CommitBuilder.from_events("stream-a", [e6, e7]))
    receipts.append(r)

    all_entries.extend(ledger.read_stream("stream-a"))
    all_entries.extend(ledger.read_stream("stream-b"))

    all_entries.extend(ledger.read_from(0))
    all_entries.extend(ledger.read_from(2))

    return receipts, all_entries


def _to_comparable(entries: list) -> list[dict[str, Any]]:
    return [
        {
            "stream_id": e.stream_id,
            "sequence": e.sequence,
            "commit_id": e.commit_id,
            "event_id": e.event_id,
            "rvcj_version": e.rvcj_version,
            "event_schema_version": e.event_schema_version,
            "event_type": e.event_type,
            "timestamp": e.timestamp,
            "payload": e.payload,
            "global_order": e.global_order,
        }
        for e in entries
    ]


def _receipts_to_comparable(receipts: list) -> list[dict[str, Any]]:
    return [
        {
            "commit_id": r.commit_id,
            "stream_id": r.stream_id,
            "sequence_start": r.sequence_start,
            "sequence_end": r.sequence_end,
            "global_order": r.global_order,
        }
        for r in receipts
    ]


def test_backend_equivalence_same_receipts():
    mem = MemoryLedger()
    sql = SQLiteLedger(":memory:")

    mem_receipts, _ = _run_operations(mem)
    sql_receipts, _ = _run_operations(sql)

    mem_comp = _receipts_to_comparable(mem_receipts)
    sql_comp = _receipts_to_comparable(sql_receipts)

    assert mem_comp == sql_comp, (
        f"Receipt mismatch:\nMemory: {mem_comp}\nSQLite: {sql_comp}"
    )


def test_backend_equivalence_same_entries():
    mem = MemoryLedger()
    sql = SQLiteLedger(":memory:")

    _, mem_entries = _run_operations(mem)
    _, sql_entries = _run_operations(sql)

    mem_comp = _to_comparable(mem_entries)
    sql_comp = _to_comparable(sql_entries)

    assert mem_comp == sql_comp, (
        f"Entry mismatch:\nMemory: {mem_comp}\nSQLite: {sql_comp}"
    )


def test_backend_equivalence_idempotency():
    mem = MemoryLedger()
    sql = SQLiteLedger(":memory:")

    env = _make_envelope(sequence=1)
    commit = CommitBuilder.from_events("eq-stream", [env])

    for b in [mem, sql]:
        r1 = b.append(commit)
        r2 = b.append(commit)
        assert r1 == r2
        entries = b.read_stream("eq-stream")
        assert len(entries) == 1


def test_backend_equivalence_rejects_gaps():
    mem = MemoryLedger()
    sql = SQLiteLedger(":memory:")

    e1 = _make_envelope(sequence=1)
    e3 = _make_envelope(sequence=3)

    for b in [mem, sql]:
        b.append(CommitBuilder.from_events("eq-stream", [e1]))
        with pytest.raises(ValueError, match="gap"):
            b.append(CommitBuilder.from_events("eq-stream", [e3]))
