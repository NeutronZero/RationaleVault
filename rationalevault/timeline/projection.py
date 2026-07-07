"""Timeline projection — narrative chronological view of system evolution.

Implements the Projection protocol with pure reducer semantics.
The reducer is append-only: new entries are added in sequence order.
No contract changes to Projection, ProjectionCompiler, ProjectionRegistry,
ProjectionContext, Projection Laws, or Conformance Suite.
"""

from __future__ import annotations

from typing import Any, Optional

from rationalevault.projection_platform.models import (
    EventSelector,
    ProjectionCapabilities,
    ProjectionHealth,
    ProjectionMetadata,
)
from rationalevault.schema.events import EventRecord
from rationalevault.timeline.normalizer import MAPPINGS, normalize_event
from rationalevault.timeline.state import TimelineState


class TimelineProjection:
    """Narrative projection — normalizes heterogeneous events into
    a uniform chronological view.

    Archetype: Narrative
    Behavior: append-only accumulation of normalized TimelineEntry objects
    """

    SCHEMA_VERSION = 1

    def __init__(self) -> None:
        self._health = ProjectionHealth.UNKNOWN
        self._ctx: Any = None

    @property
    def metadata(self) -> ProjectionMetadata:
        return ProjectionMetadata(
            id="timeline",
            version=1,
            schema_version=self.SCHEMA_VERSION,
            consumed_events=EventSelector(types=frozenset(MAPPINGS.keys())),
            capabilities=ProjectionCapabilities(
                searchable=False,
                snapshotable=True,
                observable=True,
                exportable=True,
                mutable=False,
            ),
            dependencies=(),
            description="Chronological narrative of the system's evolution",
        )

    def initialize(self, ctx: Any) -> None:
        """Called once when registered with the platform."""
        self._ctx = ctx
        self._health = ProjectionHealth.INITIALIZING

    def reduce(
        self,
        events: list[EventRecord],
        initial_state: Optional[TimelineState] = None,
    ) -> TimelineState:
        """Pure event-to-state transformer. Append-only semantics.

        Each narratively significant event produces a TimelineEntry.
        Events not in MAPPINGS are silently ignored.
        """
        state = (
            initial_state
            if initial_state is not None
            else TimelineState(entries=[], sequence=0)
        )

        self._health = ProjectionHealth.BUILDING

        for event in events:
            entry = normalize_event(event)
            if entry is not None:
                state.entries.append(entry)
            state.sequence = max(state.sequence, event.event_sequence)

        self._health = ProjectionHealth.READY
        return state

    def serialize(self, state: TimelineState) -> dict:
        """Snapshot state to a dict. Entries sorted by sequence for determinism."""
        sorted_entries = sorted(state.entries, key=lambda e: e.sequence)
        return {
            "entries": [
                {
                    "sequence": e.sequence,
                    "timestamp": e.timestamp,
                    "event_type": e.event_type.value,
                    "category": e.category.value,
                    "actor": e.actor,
                    "subject_entity": e.subject_entity,
                    "summary": e.summary,
                    "references": e.references,
                }
                for e in sorted_entries
            ],
            "sequence": state.sequence,
            "schema_version": self.SCHEMA_VERSION,
        }

    def deserialize(self, payload: dict) -> TimelineState:
        """Restore state from a dict."""
        from rationalevault.timeline.state import TimelineCategory, TimelineEntry
        from rationalevault.schema.events import EventType

        entries = []
        for e in payload.get("entries", []):
            entries.append(
                TimelineEntry(
                    sequence=e["sequence"],
                    timestamp=e["timestamp"],
                    event_type=EventType(e["event_type"]),
                    category=TimelineCategory(e["category"]),
                    actor=e.get("actor"),
                    subject_entity=e.get("subject_entity"),
                    summary=e["summary"],
                    references=e.get("references", []),
                ),
            )
        return TimelineState(
            entries=entries,
            sequence=payload.get("sequence", 0),
        )

    def health(self) -> ProjectionHealth:
        """Current health state."""
        return self._health

    def shutdown(self) -> None:
        """Clean teardown."""
        self._health = ProjectionHealth.SHUTDOWN
        self._ctx = None
