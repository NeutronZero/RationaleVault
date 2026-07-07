"""Protocols defining the Projection and RuntimeAdapter contracts."""
from __future__ import annotations

from typing import Any, Optional, Protocol, runtime_checkable

from rationalevault.projection_platform.models import (
    ProjectionHealth,
    ProjectionMetadata,
    SearchResult,
    RuntimeHealth,
)
from rationalevault.schema.events import EventRecord


@runtime_checkable
class Projection(Protocol):
    """Protocol every projection must satisfy.

    Projections are deterministic state machines governed by the
    Projection Laws (see ADR-027).
    """

    @property
    def metadata(self) -> ProjectionMetadata: ...

    def initialize(self, ctx: Any) -> None:
        """Called once when the projection is registered with the platform."""
        ...

    def reduce(
        self,
        events: list[EventRecord],
        initial_state: Optional[Any] = None,
    ) -> Any:
        """Pure event → state transformer. No dependency injection allowed."""
        ...

    def serialize(self, state: Any) -> dict: ...

    def deserialize(self, payload: dict) -> Any: ...

    def health(self) -> ProjectionHealth: ...

    def shutdown(self) -> None: ...


@runtime_checkable
class RuntimeAdapter(Protocol):
    """Protocol for runtime adapters (FAISS, rustworkx, etc.).

    Adapters materialise optimized views from projection state.
    They may be reconstructed or discarded at any time without
    affecting projection correctness.
    """

    def build(self, state: Any) -> None: ...

    def destroy(self) -> None: ...

    def search(self, query: str) -> list[SearchResult]: ...

    def metrics(self) -> dict: ...

    def health(self) -> RuntimeHealth: ...
