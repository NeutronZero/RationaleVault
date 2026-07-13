"""Projection Registry — maps named projections to their reducer functions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


ReducerFunc = Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]
"""A reducer takes (state, event_dict) and returns new state.

state:  The current accumulated state for this projection (mutable copy).
event_dict: A flat dict representation of a committed event, containing
    at minimum: event_id, event_type, stream_id, sequence, global_order,
    timestamp, payload, rvcj_version, event_schema_version, commit_id, experience_id.

Returns an updated state dict.
"""


@dataclass(frozen=True)
class ProjectionIdentity:
    """Immutable identity for a registered projection."""

    name: str


class ProjectionRegistry:
    """Registry of named projections with deterministic registration order.

    Registration order defines the order in which reducers are executed
    during replay. This guarantees deterministic Understanding construction.

    ProjectionRegistry is generic — it does not import or depend on any
    specific projection implementation.
    """

    def __init__(self) -> None:
        self._reducers: dict[str, ReducerFunc] = {}
        self._order: list[str] = []

    def register(self, name: str, reducer: ReducerFunc) -> ProjectionIdentity:
        """Register a projection with a ReducerFunc.

        Args:
            name: Unique projection name.
            reducer: Function conforming to ReducerFunc signature.

        Returns:
            ProjectionIdentity for the registered projection.

        Raises:
            ValueError: If a projection with this name is already registered.
        """
        if name in self._reducers:
            raise ValueError(f"Projection {name!r} already registered")
        self._reducers[name] = reducer
        self._order.append(name)
        return ProjectionIdentity(name=name)

    def get_reducer(self, name: str) -> ReducerFunc:
        """Get the reducer for a named projection.

        Raises:
            KeyError: If no projection is registered with this name.
        """
        if name not in self._reducers:
            raise KeyError(f"Unknown projection: {name!r}")
        return self._reducers[name]

    def list_projections(self) -> list[str]:
        """Return projection names in registration order."""
        return list(self._order)

    def has(self, name: str) -> bool:
        """Return True if a projection with this name is registered."""
        return name in self._reducers
