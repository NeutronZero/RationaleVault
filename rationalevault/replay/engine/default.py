"""DefaultReplayer — reference ReplayEngine implementation.

Pipeline:
    Ledger
    ↓
    Commits (via read_stream / read_from)
    ↓
    LedgerEntry list (sorted by global_order)
    ↓
    Event dicts (flattened LedgerEntry → reducer-compatible dict)
    ↓
    Projection Registry (reducers applied in registration order)
    ↓
    Understanding (composite projection states + boundary)
    ↓
    ReplayResult (Understanding + report + version + boundary)
"""

from __future__ import annotations

from typing import Any

from rationalevault.ledger.entry import LedgerEntry
from rationalevault.ledger.interface import Ledger
from rationalevault.replay.interface import ReplayEngine
from rationalevault.replay.registry import ProjectionRegistry
from rationalevault.replay.types import (
    ReplayBoundary,
    ReplayMode,
    ReplayReport,
    ReplayResult,
    ReplayScope,
    Understanding,
)


def _entry_to_event(entry: LedgerEntry) -> dict[str, Any]:
    """Convert a LedgerEntry to a flat event dict for reducer consumption."""
    return {
        "event_id": entry.event_id,
        "event_type": entry.event_type,
        "stream_id": entry.stream_id,
        "sequence": entry.sequence,
        "global_order": entry.global_order,
        "timestamp": entry.timestamp,
        "payload": entry.payload,
        "rvcj_version": entry.rvcj_version,
        "event_schema_version": entry.event_schema_version,
        "commit_id": entry.commit_id,
    }


class DefaultReplayer(ReplayEngine):
    """Reference ReplayEngine implementation.

    Simple, readable, deterministic, and obviously correct.
    This is a reference implementation, not a production-optimized one.
    """

    def __init__(self, registry: ProjectionRegistry) -> None:
        self._registry = registry

    def replay(
        self,
        ledger: Ledger,
        scope: ReplayScope = ReplayScope(),
        mode: ReplayMode = ReplayMode(),
        projections: ProjectionRegistry | None = None,
    ) -> ReplayResult:
        registry = projections if projections is not None else self._registry

        entries = self._read_entries(ledger, scope)
        events = [_entry_to_event(e) for e in entries]
        boundary = self._compute_boundary(entries)

        projection_states = self._apply_reducers(registry, events)

        understanding = Understanding(
            projections=projection_states,
            boundary=boundary,
        )
        report = ReplayReport(
            mode=mode.value,
            events_processed=len(events),
            snapshot_used=False,
            replay_position=boundary,
            version=1,
        )
        return ReplayResult(
            understanding=understanding,
            report=report,
            version=1,
            replay_boundary=boundary,
        )

    def replay_to(
        self,
        ledger: Ledger,
        boundary: ReplayBoundary,
        mode: ReplayMode = ReplayMode(),
        projections: ProjectionRegistry | None = None,
    ) -> ReplayResult:
        registry = projections if projections is not None else self._registry

        entries = [
            e for e in ledger.read_from(0)
            if e.global_order <= boundary.global_order
        ]
        events = [_entry_to_event(e) for e in entries]
        actual_boundary = self._compute_boundary(entries)

        projection_states = self._apply_reducers(registry, events)

        understanding = Understanding(
            projections=projection_states,
            boundary=actual_boundary,
        )
        report = ReplayReport(
            mode=mode.value,
            events_processed=len(events),
            snapshot_used=False,
            replay_position=actual_boundary,
            version=1,
        )
        return ReplayResult(
            understanding=understanding,
            report=report,
            version=1,
            replay_boundary=actual_boundary,
        )

    def replay_stream(
        self,
        ledger: Ledger,
        stream_id: str,
        mode: ReplayMode = ReplayMode(),
        projections: ProjectionRegistry | None = None,
    ) -> ReplayResult:
        return self.replay(
            ledger,
            scope=ReplayScope(kind="stream", stream_id=stream_id),
            mode=mode,
            projections=projections,
        )

    def _read_entries(self, ledger: Ledger, scope: ReplayScope) -> list[LedgerEntry]:
        if scope.kind == "global":
            return ledger.read_from(0)
        return ledger.read_stream(scope.stream_id)

    def _compute_boundary(self, entries: list[LedgerEntry]) -> ReplayBoundary:
        if not entries:
            return ReplayBoundary(0)
        return ReplayBoundary(max(e.global_order for e in entries))

    def _apply_reducers(
        self,
        registry: ProjectionRegistry,
        events: list[dict[str, Any]],
    ) -> dict[str, Any]:
        states: dict[str, Any] = {}
        for name in registry.list_projections():
            reducer = registry.get_reducer(name)
            state: dict[str, Any] = {}
            for event in events:
                state = reducer(state, event)
            states[name] = state
        return states
