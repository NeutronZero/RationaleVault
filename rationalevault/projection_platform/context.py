"""ProjectionContext — runtime context passed to projections."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from rationalevault.cognitive_head.snapshot import SnapshotManager
from rationalevault.db.event_store import EventStore


class DependencyReader:
    """Read-only access to dependency projection states.

    Projections may read the output of other projections through this
    interface, but cannot mutate them.
    """

    def __init__(self) -> None:
        self._states: dict[str, Any] = {}

    def get(self, projection_id: str) -> Any:
        """Return the current state of a dependency projection."""
        return self._states.get(projection_id)

    def set(self, projection_id: str, state: Any) -> None:
        """Internal: called by the platform to update dependency states."""
        self._states[projection_id] = state


class MetricsCollector:
    """Collects per-projection metrics."""

    def __init__(self) -> None:
        self._metrics: dict[str, Any] = {}

    def record(self, key: str, value: Any) -> None:
        self._metrics[key] = value

    def snapshot(self) -> dict[str, Any]:
        return dict(self._metrics)


@dataclass
class ProjectionContext:
    """Runtime context provided to projections by the platform."""

    projection_id: str
    event_store: EventStore
    snapshot_manager: SnapshotManager
    dependency_reader: DependencyReader
    logger: logging.Logger
    metrics: MetricsCollector
    config: dict[str, Any] = field(default_factory=dict)
