"""SQLite Ledger backend — production implementation."""

from __future__ import annotations

import json
import sqlite3

from rationalevault.canonical.serializer import CanonicalSerializer
from rationalevault.ledger.commit import Commit, CommitReceipt
from rationalevault.ledger.entry import LedgerEntry
from rationalevault.ledger.interface import Ledger
from rationalevault.ledger.errors import DuplicateCommitError


SCHEMA = """
CREATE TABLE IF NOT EXISTS ledger_entries (
    stream_id           TEXT NOT NULL,
    sequence            INTEGER NOT NULL,
    commit_id           TEXT NOT NULL,
    event_id            TEXT NOT NULL,
    rvcj_version        INTEGER NOT NULL,
    event_schema_version INTEGER NOT NULL,
    event_type          TEXT NOT NULL,
    timestamp           TEXT NOT NULL,
    payload             TEXT NOT NULL,
    global_order        INTEGER NOT NULL,
    PRIMARY KEY (stream_id, sequence)
);
CREATE INDEX IF NOT EXISTS idx_global_order ON ledger_entries(global_order);
CREATE INDEX IF NOT EXISTS idx_commit_id ON ledger_entries(commit_id);
"""


class SQLiteLedger(Ledger):
    """SQLite-backed Ledger implementation.

    Uses one SQLite transaction per Commit to preserve atomicity.
    Schema mirrors the logical model exactly — no denormalization.
    """

    def __init__(self, db_path: str) -> None:
        self._conn = sqlite3.connect(db_path)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(SCHEMA)

    def close(self) -> None:
        self._conn.close()

    def append(self, commit: Commit) -> CommitReceipt:
        cursor = self._conn.execute(
            "SELECT global_order FROM ledger_entries WHERE commit_id = ? LIMIT 1",
            (commit.commit_id,),
        )
        row = cursor.fetchone()
        if row is not None:
            cursor = self._conn.execute(
                "SELECT stream_id, sequence, global_order FROM ledger_entries "
                "WHERE commit_id = ? ORDER BY sequence LIMIT 1",
                (commit.commit_id,),
            )
            existing = cursor.fetchone()
            cursor = self._conn.execute(
                "SELECT sequence FROM ledger_entries "
                "WHERE commit_id = ? ORDER BY sequence DESC LIMIT 1",
                (commit.commit_id,),
            )
            last = cursor.fetchone()
            return CommitReceipt(
                commit_id=commit.commit_id,
                stream_id=existing[0],
                sequence_start=existing[1],
                sequence_end=last[0],
                global_order=existing[2],
            )

        stream_id = commit.stream_id
        cursor = self._conn.execute(
            "SELECT MAX(sequence) FROM ledger_entries WHERE stream_id = ?",
            (stream_id,),
        )
        current_seq = cursor.fetchone()[0] or 0

        for i, event in enumerate(commit.events):
            expected = current_seq + 1 + i
            if event.sequence != expected:
                raise ValueError(
                    f"Sequence gap in stream {stream_id}: "
                    f"expected seq {expected}, got {event.sequence}"
                )

        try:
            cursor = self._conn.execute(
                "SELECT COALESCE(MAX(global_order), -1) FROM ledger_entries"
            )
            global_order = cursor.fetchone()[0] + 1

            sequence_start = commit.events[0].sequence
            sequence_end = sequence_start + len(commit.events) - 1

            for i, event in enumerate(commit.events):
                digest = CanonicalSerializer.content_digest(event)
                self._conn.execute(
                    """INSERT INTO ledger_entries
                       (stream_id, sequence, commit_id, event_id,
                        rvcj_version, event_schema_version, event_type,
                        timestamp, payload, global_order)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        stream_id,
                        event.sequence,
                        commit.commit_id,
                        f"EVT-{digest[:12]}",
                        event.rvcj_version,
                        event.event_schema_version,
                        event.event_type.value,
                        event.timestamp.to_iso8601(),
                        json.dumps(event.payload.data, separators=(",", ":")),
                        global_order,
                    ),
                )

            self._conn.commit()

            return CommitReceipt(
                commit_id=commit.commit_id,
                stream_id=stream_id,
                sequence_start=sequence_start,
                sequence_end=sequence_end,
                global_order=global_order,
            )
        except Exception:
            self._conn.rollback()
            raise

    def read_stream(self, stream_id: str) -> list[LedgerEntry]:
        cursor = self._conn.execute(
            "SELECT stream_id, sequence, commit_id, event_id, "
            "rvcj_version, event_schema_version, event_type, "
            "timestamp, payload, global_order "
            "FROM ledger_entries WHERE stream_id = ? ORDER BY sequence",
            (stream_id,),
        )
        return [self._row_to_entry(r) for r in cursor.fetchall()]

    def read_from(self, global_order: int) -> list[LedgerEntry]:
        cursor = self._conn.execute(
            "SELECT stream_id, sequence, commit_id, event_id, "
            "rvcj_version, event_schema_version, event_type, "
            "timestamp, payload, global_order "
            "FROM ledger_entries WHERE global_order >= ? ORDER BY global_order",
            (global_order,),
        )
        return [self._row_to_entry(r) for r in cursor.fetchall()]

    def exists(self, commit_id: str) -> bool:
        cursor = self._conn.execute(
            "SELECT 1 FROM ledger_entries WHERE commit_id = ? LIMIT 1",
            (commit_id,),
        )
        return cursor.fetchone() is not None

    def stream_exists(self, stream_id: str) -> bool:
        cursor = self._conn.execute(
            "SELECT 1 FROM ledger_entries WHERE stream_id = ? LIMIT 1",
            (stream_id,),
        )
        return cursor.fetchone() is not None

    def _row_to_entry(self, row: tuple) -> LedgerEntry:
        return LedgerEntry(
            stream_id=row[0],
            sequence=row[1],
            commit_id=row[2],
            event_id=row[3],
            rvcj_version=row[4],
            event_schema_version=row[5],
            event_type=row[6],
            timestamp=row[7],
            payload=json.loads(row[8]),
            global_order=row[9],
        )
