"""ProjectionConformanceProvider — projection-specific customization point.

Every projection must provide an implementation of this protocol to supply
the conformance suite with projection-specific knowledge: event streams,
state comparison, serialization canonicalization, and context creation.

The suite does not assume `state ==` works; it delegates to the provider.
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from rationalevault.projection_platform.context import ProjectionContext
from rationalevault.projection_platform.protocols import Projection
from rationalevault.schema.events import EventRecord


@runtime_checkable
class ProjectionConformanceProvider(Protocol):
    """Projection-specific customization point for the conformance suite.

    Implement this protocol to supply projection-specific knowledge.
    The suite never contains projection-specific logic.
    """

    def create_projection(self) -> Projection:
        """Create a fresh projection instance for testing.

        This replaces projection.__class__() to support projections
        that require construction arguments.
        """
        ...

    def events(self) -> list[EventRecord]:
        """Return a representative event stream for this projection."""
        ...

    def edge_case_events(self) -> list[list[EventRecord]]:
        """Return edge-case streams (empty, single event, etc.)."""
        ...

    def snapshot_points(self, events: list[EventRecord]) -> list[int]:
        """Return split indices for incrementality and equivalence tests.

        Default: [0, 25%, 50%, 75%, 100%] of event count.
        Override for projection-specific needs.
        """
        ...

    def supported_events(self) -> list[EventRecord]:
        """Return events that this projection consumes (subset of events())."""
        ...

    def unsupported_events(self) -> list[EventRecord]:
        """Return events that this projection does NOT consume."""
        ...

    def state_equal(self, a: Any, b: Any) -> bool:
        """Compare two projection states for equality.

        The suite does not assume `==` works on projection states.
        """
        ...

    def canonical_json(self, payload: dict) -> str:
        """Return deterministic JSON string for serialization comparison."""
        ...

    def create_context(self, projection: Projection) -> ProjectionContext:
        """Create a valid ProjectionContext for the projection."""
        ...
