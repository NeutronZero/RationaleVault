"""ReplayEngine ABC — the constitutional contract for Replay."""

from __future__ import annotations

from abc import ABC, abstractmethod

from rationalevault.ledger.interface import Ledger
from rationalevault.replay.registry import ProjectionRegistry
from rationalevault.replay.types import ReplayBoundary, ReplayMode, ReplayResult, ReplayScope


class ReplayEngine(ABC):
    """Abstract Replay Engine — defines the constitutional contract.

    The Replay Engine transforms Ledger state into Understanding
    by replaying events through a registry of Projection Reducers.

    This ABC defines behavior, not algorithms.
    The reference implementation (DefaultReplayer) is deliberately
    simple and deterministic.
    """

    @abstractmethod
    def replay(
        self,
        ledger: Ledger,
        scope: ReplayScope = ReplayScope(),
        mode: ReplayMode = ReplayMode(),
        projections: ProjectionRegistry | None = None,
    ) -> ReplayResult:
        """Replay events from the Ledger to produce Understanding.

        Args:
            ledger: The Ledger to read events from.
            scope: Which events to include (global or stream).
            mode: Replay strategy (auto/full/delta/fast_path).
            projections: Optional override ProjectionRegistry.
                If None, uses the engine's default registry.

        Returns:
            ReplayResult containing Understanding and replay metadata.
        """
        ...

    @abstractmethod
    def replay_to(
        self,
        ledger: Ledger,
        boundary: ReplayBoundary,
        mode: ReplayMode = ReplayMode(),
        projections: ProjectionRegistry | None = None,
    ) -> ReplayResult:
        """Replay all events up to (and including) a specific ReplayBoundary.

        Args:
            ledger: The Ledger to read events from.
            boundary: Replay only events with global_order <= this value.
            mode: Replay strategy selector.
            projections: Optional override ProjectionRegistry.

        Returns:
            ReplayResult at the specified boundary.
        """
        ...

    @abstractmethod
    def replay_stream(
        self,
        ledger: Ledger,
        stream_id: str,
        mode: ReplayMode = ReplayMode(),
        projections: ProjectionRegistry | None = None,
    ) -> ReplayResult:
        """Replay events from a single stream.

        Convenience wrapper around replay() with ReplayScope(kind='stream').

        Args:
            ledger: The Ledger to read events from.
            stream_id: The stream to replay.
            mode: Replay strategy selector.
            projections: Optional override ProjectionRegistry.

        Returns:
            ReplayResult for the specified stream.
        """
        ...
