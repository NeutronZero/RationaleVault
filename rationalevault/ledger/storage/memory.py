"""In-memory Ledger backend — reference implementation for testing."""

from __future__ import annotations

from rationalevault.ledger.commit import Commit, CommitReceipt
from rationalevault.ledger.entry import LedgerEntry
from rationalevault.ledger.interface import Ledger
from rationalevault.ledger.errors import DuplicateCommitError
from rationalevault.canonical.serializer import CanonicalSerializer


class MemoryLedger(Ledger):
    """In-memory reference implementation of the Ledger ABC.

    All operations are O(n) on storage size. This is intentional —
    this implementation validates correctness, not performance.
    """

    def __init__(self) -> None:
        self._entries: list[LedgerEntry] = []
        self._commits: dict[str, CommitReceipt] = {}
        self._stream_sequences: dict[str, int] = {}
        self._next_global_order: int = 0

    def append(self, commit: Commit) -> CommitReceipt:
        if commit.commit_id in self._commits:
            return self._commits[commit.commit_id]

        stream_id = commit.stream_id
        current_seq = self._stream_sequences.get(stream_id, 0)

        # Validate sequence contiguity
        first_seq = commit.events[0].sequence
        for i, event in enumerate(commit.events):
            expected = current_seq + 1 + i
            if event.sequence != expected:
                raise ValueError(
                    f"Sequence gap in stream {stream_id}: "
                    f"expected seq {expected}, got {event.sequence}"
                )

        global_order = self._next_global_order
        self._next_global_order += 1

        sequence_start = commit.events[0].sequence
        sequence_end = first_seq + len(commit.events) - 1

        for i, event in enumerate(commit.events):
            digest = CanonicalSerializer.content_digest(event)
            entry = LedgerEntry(
                stream_id=stream_id,
                sequence=event.sequence,
                commit_id=commit.commit_id,
                event_id=f"EVT-{digest[:12]}",
                rvcj_version=event.rvcj_version,
                event_schema_version=event.event_schema_version,
                event_type=event.event_type.value,
                timestamp=event.timestamp.to_iso8601(),
                payload=event.payload.data,
                global_order=global_order,
            )
            self._entries.append(entry)

        self._stream_sequences[stream_id] = sequence_end

        receipt = CommitReceipt(
            commit_id=commit.commit_id,
            stream_id=stream_id,
            sequence_start=sequence_start,
            sequence_end=sequence_end,
            global_order=global_order,
        )
        self._commits[commit.commit_id] = receipt
        return receipt

    def read_stream(self, stream_id: str) -> list[LedgerEntry]:
        return [
            e for e in self._entries
            if e.stream_id == stream_id
        ]

    def read_from(self, global_order: int) -> list[LedgerEntry]:
        return [
            e for e in self._entries
            if e.global_order >= global_order
        ]

    def exists(self, commit_id: str) -> bool:
        return commit_id in self._commits

    def stream_exists(self, stream_id: str) -> bool:
        return any(e.stream_id == stream_id for e in self._entries)
