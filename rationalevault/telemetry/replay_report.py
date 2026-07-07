"""
RationaleVault Replay Report — Telemetry for replay operations.

ReplayReport captures timing, mode, and event counts for each compilation.
Produced by ReplayEngine after each build_projection() call.
"""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass
class ReplayReport:
    """
    Telemetry report for a single replay operation.

    Fields:
        project_id:         Project that was compiled.
        projection_name:    Which projection (e.g., "cognitive_head").
        replay_mode:        "full", "delta", or "fast_path".
        compile_duration_ms: Total wall-clock time for build_projection().
        snapshot_load_ms:   Time spent loading and validating snapshot.
        validation_ms:      Time spent in snapshot validation.
        snapshot_valid:     Whether the loaded snapshot passed validation.
        snapshot_used:      Whether the snapshot was used for initial state.
        snapshot_sequence:  Sequence number of the snapshot used (0 if none).
        latest_sequence:    Sequence number of the latest event.
        events_replayed:    Number of events processed by reducers.
        events_reused:      Number of events represented by the snapshot.
        total_events:       Total events in the project stream.
        snapshot_saved:     Whether a new snapshot was saved after compilation.
        snapshot_save_ms:   Time spent saving the new snapshot.
    """
    project_id: UUID
    projection_name: str
    replay_mode: str
    compile_duration_ms: float = 0.0
    snapshot_load_ms: float = 0.0
    validation_ms: float = 0.0
    snapshot_valid: bool = False
    snapshot_used: bool = False
    snapshot_sequence: int = 0
    latest_sequence: int = 0
    events_replayed: int = 0
    events_reused: int = 0
    total_events: int = 0
    snapshot_saved: bool = False
    snapshot_save_ms: float = 0.0

    def summary(self) -> str:
        """One-line summary for logging."""
        return (
            f"[replay] {self.replay_mode} | "
            f"{self.events_replayed} replayed, {self.events_reused} reused | "
            f"compile={self.compile_duration_ms:.1f}ms"
        )


class ReportCollector:
    """Collects ReplayReport instances for batch logging or persistence."""

    def __init__(self) -> None:
        self._reports: list[ReplayReport] = []

    def record(self, report: ReplayReport) -> None:
        self._reports.append(report)

    def recent(self, n: int = 10) -> list[ReplayReport]:
        return self._reports[-n:]

    def clear(self) -> None:
        self._reports.clear()

    @property
    def count(self) -> int:
        return len(self._reports)
