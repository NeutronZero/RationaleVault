"""Commit and CommitReceipt value objects for the Ledger."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from rationalevault.canonical.envelope import CanonicalEnvelope
from rationalevault.canonical.canonicalizer import canonicalize


@dataclass(frozen=True)
class Commit:
    """An atomic commit containing 1..N canonically serialized events."""

    commit_id: str
    stream_id: str
    events: list[CanonicalEnvelope]


@dataclass(frozen=True)
class CommitReceipt:
    """Receipt returned by Ledger.append() — never constructed by callers."""

    commit_id: str
    stream_id: str
    sequence_start: int
    sequence_end: int
    global_order: int


def _compute_commit_id(events: list[CanonicalEnvelope]) -> str:
    """Compute content-addressed commit_id from ordered event list.

    Serializes the ordered event list as a canonical JSON array
    (via Canonicalizer.canonicalize), then applies SHA-256.
    No metadata (timestamp, actor, stream_id) is included in the digest.
    """
    dicts = [e.to_dict() for e in events]
    canonical = canonicalize(dicts)
    canonical_bytes = json.dumps(
        canonical, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(canonical_bytes).hexdigest()


class CommitBuilder:
    """Factory for constructing Commit objects — single place for validation."""

    @staticmethod
    def from_events(
        stream_id: str,
        events: list[CanonicalEnvelope],
    ) -> Commit:
        """Build a Commit from events.

        Validates:
        - At least one event
        - All events share the same experience_id
        """
        if not events:
            raise ValueError("Commit must contain at least one event")

        experience_ids = {e.experience_id for e in events}
        if len(experience_ids) > 1:
            raise ValueError(
                f"All events in a Commit must share the same experience_id. "
                f"Got: {experience_ids}"
            )

        commit_id = _compute_commit_id(events)
        return Commit(
            commit_id=commit_id,
            stream_id=stream_id,
            events=events,
        )
