"""
RationaleVault Snapshot Policy — Pluggable trigger policies for snapshot saves.

SnapshotPolicy is a Protocol: any object with should_snapshot() works.
EventCountPolicy is the default: save after N new events since last snapshot.
Future policies: TimePolicy, AdaptivePolicy, LatencyPolicy.
"""
from __future__ import annotations

from typing import Optional, Protocol


class SnapshotPolicy(Protocol):
    """Decides when a snapshot should be saved."""

    def should_snapshot(
        self,
        current_sequence: int,
        last_snapshot_sequence: Optional[int],
    ) -> bool:
        """Return True if a new snapshot should be saved."""
        ...


class EventCountPolicy:
    """Save after N new events since the last snapshot."""

    def __init__(self, threshold: int = 100) -> None:
        self.threshold = threshold

    def should_snapshot(
        self,
        current_sequence: int,
        last_snapshot_sequence: Optional[int],
    ) -> bool:
        if last_snapshot_sequence is None:
            return True
        return (current_sequence - last_snapshot_sequence) >= self.threshold


DEFAULT_POLICY = EventCountPolicy()
