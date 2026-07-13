"""Ledger-specific exceptions."""

from __future__ import annotations

from rationalevault.ledger.commit import CommitReceipt


class LedgerError(Exception):
    """Base exception for Ledger errors."""


class DuplicateCommitError(LedgerError):
    """Raised when appending a Commit with an existing commit_id.

    Contains the original CommitReceipt for idempotent retry handling.
    """

    def __init__(self, commit_id: str, existing_receipt: CommitReceipt):
        self.commit_id = commit_id
        self.existing_receipt = existing_receipt
        super().__init__(f"Duplicate commit: {commit_id}")


class StreamConflictError(LedgerError):
    """Raised when a Commit would create a sequence gap in a stream."""