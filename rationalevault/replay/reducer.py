"""Reducer Protocol — the constitutional contract for Projection Reducers (I-12).

A Reducer is a pure function: given (state, event) it returns new state.
It MUST NOT mutate its inputs or have observable side effects.

This module provides:
- Reducer Protocol: formal type contract
- ReducerFunc: type alias for convenience
- verify_purity: wraps a reducer to enforce I-12 at runtime
- verify_determinism: verifies reducer determinism
- ignore_unknown_types: wraps a reducer to silently handle unknown event types
"""

from __future__ import annotations

import copy
from typing import Any, Callable, Protocol, runtime_checkable


ReducerFunc = Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]
"""A reducer takes (state, event_dict) and returns new state.

state:  The current accumulated state for this projection (mutable copy).
event_dict: A flat dict representation of a committed event, containing
    at minimum: event_id, event_type, stream_id, sequence, global_order,
    timestamp, payload, rvcj_version, event_schema_version, commit_id.

Returns an updated state dict.
"""


@runtime_checkable
class Reducer(Protocol):
    """Protocol for projection reducer functions.

    A Reducer is a pure function that transforms projection state
    in response to an event. It MUST satisfy I-12 (Reducer Purity):
    - Deterministic: same (state, event) → same result
    - No side effects: does not mutate inputs
    - Referentially transparent: output depends only on inputs
    """

    def __call__(
        self, state: dict[str, Any], event: dict[str, Any]
    ) -> dict[str, Any]:
        ...


def _get_deep_size(obj: Any) -> int:
    """Get a deterministic hash-like value for an object tree."""
    return len(repr(copy.deepcopy(obj)))


def _snapshot(obj: Any) -> Any:
    """Create a deep snapshot for later comparison."""
    return copy.deepcopy(obj)


def verify_purity(reducer: ReducerFunc) -> ReducerFunc:
    """Wrap a reducer to enforce I-12 (Reducer Purity).

    The wrapper:
    1. Deep-copies input state and event
    2. Calls the reducer
    3. Checks that the original inputs were not mutated
    4. Returns the reducer's output

    Raises:
        PurityViolationError: if inputs were mutated.
    """
    from rationalevault.replay.errors import PurityViolationError

    def pure_wrapper(
        state: dict[str, Any], event: dict[str, Any]
    ) -> dict[str, Any]:
        state_snapshot = _snapshot(state)
        event_snapshot = _snapshot(event)

        result = reducer(state, event)

        if state != state_snapshot:
            raise PurityViolationError(
                "Reducer mutated input state (I-12 violation)"
            )
        if event != event_snapshot:
            raise PurityViolationError(
                "Reducer mutated input event (I-12 violation)"
            )

        return result

    return pure_wrapper


def verify_determinism(reducer: ReducerFunc) -> ReducerFunc:
    """Wrap a reducer to verify determinism (I-12).

    The wrapper runs the reducer twice with the same inputs and
    asserts the outputs match. This adds overhead — use for testing
    or when registering trusted reducers.

    Raises:
        AssertionError: if the reducer is not deterministic.
    """

    def deterministic_wrapper(
        state: dict[str, Any], event: dict[str, Any]
    ) -> dict[str, Any]:
        result1 = reducer(copy.deepcopy(state), copy.deepcopy(event))
        result2 = reducer(copy.deepcopy(state), copy.deepcopy(event))
        assert result1 == result2, (
            f"Reducer is not deterministic: {result1!r} != {result2!r}"
        )
        return result1

    return deterministic_wrapper


def ignore_unknown_types(
    reducer: ReducerFunc,
    known_types: set[str] | None = None,
) -> ReducerFunc:
    """Wrap a reducer to silently ignore unknown event types.

    If an event's event_type is not in known_types, the wrapper
    returns the state unchanged without calling the reducer.
    This protects fragile reducers from unexpected event types.

    Args:
        reducer: The reducer to wrap.
        known_types: Set of event_type strings the reducer handles.
            If None, the wrapper passes all events through.

    Returns:
        A wrapped reducer that ignores unknown event types.
    """
    if known_types is None:
        return reducer

    def safe_wrapper(
        state: dict[str, Any], event: dict[str, Any]
    ) -> dict[str, Any]:
        if event.get("event_type", "") not in known_types:
            return state
        return reducer(state, event)

    return safe_wrapper
