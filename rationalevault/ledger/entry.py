"""LedgerEntry — persistence model only, never part of domain API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LedgerEntry:
    """Persistence projection of a committed event.

    This is a storage model only. It represents an event after:
    - sequence assignment (stream-local ordering)
    - global_order assignment (total ordering across streams)
    - commit association

    LedgerEntry should never appear in the domain API or projection API.
    Downstream consumers work with CanonicalEnvelope.
    """

    stream_id: str
    sequence: int
    commit_id: str
    event_id: str
    rvcj_version: int
    event_schema_version: int
    event_type: str
    timestamp: str
    payload: dict
    global_order: int
