"""Replay domain value objects — immutable dataclasses for the Replay Engine's executable vocabulary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, order=True)
class ReplayBoundary:
    """The greatest committed global_order value included in a reconstructed Understanding."""

    global_order: int

    def __post_init__(self) -> None:
        if self.global_order < 0:
            raise ValueError(f"ReplayBoundary must be non-negative, got {self.global_order}")


@dataclass(frozen=True)
class ReplayScope:
    """Defines which Events are included in a replay.

    Default: global (all streams, ordered by global_order).
    Stream scope requires a stream_id.
    """

    kind: str = "global"
    stream_id: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in ("global", "stream"):
            raise ValueError(f"ReplayScope kind must be 'global' or 'stream', got {self.kind!r}")
        if self.kind == "global" and self.stream_id is not None:
            raise ValueError(
                f"ReplayScope global scope must have stream_id=None, got {self.stream_id!r}"
            )
        if self.kind == "stream" and self.stream_id is None:
            raise ValueError("ReplayScope stream scope requires a stream_id")


@dataclass(frozen=True)
class ReplayMode:
    """Replay strategy selector.

    - auto: Engine chooses the optimal mode (default)
    - full: Replay from the beginning of the Ledger
    - delta: Replay from a Snapshot
    - fast_path: Optimized delta replay
    """

    value: str = "auto"

    VALID_MODES = frozenset({"auto", "full", "delta", "fast_path"})

    def __post_init__(self) -> None:
        if self.value not in self.VALID_MODES:
            raise ValueError(
                f"ReplayMode must be one of {sorted(self.VALID_MODES)}, got {self.value!r}"
            )


@dataclass(frozen=True)
class Understanding:
    """The composite state of all active Projections at a specific Replay Boundary.

    Understanding is the primary domain output of Replay.
    It is immutable for a given Ledger state and ProjectionSet.
    """

    projections: dict[str, Any]
    boundary: ReplayBoundary


@dataclass(frozen=True)
class ReplayReport:
    """Observability metadata about how replay was performed.

    Not a source of truth — informational only.
    """

    mode: str
    events_processed: int
    snapshot_used: bool
    replay_position: ReplayBoundary
    version: int


@dataclass(frozen=True)
class ReplayResult:
    """The sole output of Replay — packages Understanding together with replay metadata.

    - understanding: the primary domain output
    - report: replay telemetry
    - version: the rvcj_version governing canonical Event interpretation
    - replay_boundary: the Replay Boundary at which Understanding was materialized
    """

    understanding: Understanding
    report: ReplayReport
    version: int
    replay_boundary: ReplayBoundary
