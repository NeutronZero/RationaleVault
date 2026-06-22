"""
RationaleVault Cognitive Head — SnapshotStore interface (V1 placeholder).

Snapshots are point-in-time captures of a compiled CognitiveHead.
They allow compile_cognitive_head() to avoid replaying the entire event
ledger by loading a recent snapshot and applying only new events.

V1 STATUS: Interface defined. Not implemented.
  - load_latest_snapshot() always returns None (triggers full replay).
  - save_snapshot() is a no-op.

This placeholder exists so:
  1. The compiler can call snapshot_store.load_latest_snapshot() today.
  2. A future V2 implementation can be dropped in without changing the
     compile_cognitive_head() API.
  3. The interface documents the expected contract clearly.

When to implement:
  Implement when compile_cognitive_head() takes more than ~500ms.
  At V1 scale (local DB, hundreds of events), full replay is fast enough.

V2 implementation sketch:
  - Add relay_snapshots table (project_id, sequence, head_json, created_at)
  - save_snapshot() after every N events or on explicit call
  - load_latest_snapshot() returns most recent entry
  - compile_cognitive_head() calls apply_events_after_snapshot(snapshot, new_events)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from rationalevault.cognitive_head.compiler import CognitiveHead


@dataclass
class Snapshot:
    """
    A point-in-time capture of a compiled CognitiveHead.

    Attributes:
        project_id: The project this snapshot belongs to.

        sequence:   The event_sequence of the last event included in this snapshot.
                    To bring the snapshot up to date, load events with
                    event_sequence > snapshot.sequence and apply them.

        head:       The compiled CognitiveHead at the time of snapshot.
    """
    project_id: UUID
    sequence: int
    head: CognitiveHead


class SnapshotStore:
    """
    Interface for the RationaleVault snapshot system.

    V1: All operations are no-ops. load_latest_snapshot() returns None,
    which causes compile_cognitive_head() to perform a full replay.

    Thread safety: V1 implementation is trivially thread-safe (no state).
    Future implementations must consider concurrent snapshot writes.
    """

    def load_latest_snapshot(self, project_id: UUID) -> Optional[Snapshot]:
        """
        Load the most recent snapshot for a project.

        Returns None if no snapshot exists. The caller must then perform
        a full event replay via EventStore.get_project_stream().

        V1: Always returns None.
        """
        return None

    def save_snapshot(self, snapshot: Snapshot) -> None:
        """
        Persist a snapshot to durable storage.

        V1: No-op. Snapshots are not stored in V1.
        """
        pass

    def delete_snapshots_before(self, project_id: UUID, sequence: int) -> int:
        """
        Delete snapshots older than the given sequence number.
        Returns the number of snapshots deleted.

        V1: No-op. Returns 0.
        """
        return 0
