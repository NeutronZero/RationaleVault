"""Ledger ABC — abstract storage contract for the Ledger."""

from __future__ import annotations

from abc import ABC, abstractmethod

from rationalevault.ledger.commit import Commit, CommitReceipt
from rationalevault.ledger.entry import LedgerEntry


class Ledger(ABC):
    """Abstract ledger: append-only event store with stream ordering."""

    @abstractmethod
    def append(self, commit: Commit) -> CommitReceipt:
        """Append a Commit atomically.

        Returns a CommitReceipt containing commit_id and sequence assignments.

        Raises:
            DuplicateCommitError: if commit_id already exists (idempotent)
            StreamConflictError:  if sequence gap detected
        """
        ...

    @abstractmethod
    def read_stream(self, stream_id: str) -> list[LedgerEntry]:
        """Read all events in a stream, in sequence order."""
        ...

    @abstractmethod
    def read_from(self, global_order: int) -> list[LedgerEntry]:
        """Read all events with global_order >= given value, in order."""
        ...

    @abstractmethod
    def exists(self, commit_id: str) -> bool:
        """Return True if a Commit has already been persisted."""
        ...

    @abstractmethod
    def stream_exists(self, stream_id: str) -> bool:
        """Return True if the stream has any committed events."""
        ...
