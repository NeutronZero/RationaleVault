"""Replay helper — owns projection lifecycle for law tests.

Every law test needs to replay events through a projection. This helper
owns the lifecycle (initialize, reduce, shutdown) so law tests stay
focused on verification logic.
"""
from __future__ import annotations

from typing import Any, Optional

from rationalevault.projection_platform.conformance.providers import (
    ProjectionConformanceProvider,
)
from rationalevault.projection_platform.models import ProjectionHealth
from rationalevault.projection_platform.protocols import Projection
from rationalevault.schema.events import EventRecord


def replay_events(
    projection: Projection,
    events: list[EventRecord],
    provider: ProjectionConformanceProvider,
    initial_state: Optional[Any] = None,
) -> Any:
    """Replay events through a projection, returning the resulting state.

    Handles initialize → reduce lifecycle. Does NOT call shutdown.
    If initial_state is supplied, performs delta replay.
    """
    if projection.health() == ProjectionHealth.UNKNOWN:
        ctx = provider.create_context(projection)
        projection.initialize(ctx)

    return projection.reduce(events, initial_state=initial_state)
