from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from rationalevault.schema.events import EventRecord, EventType


@dataclass(frozen=True)
class MigrationStep:
    """Describes one version transition. No executable code."""
    from_version: int
    to_version: int


@dataclass(frozen=True)
class MigrationPath:
    """Ordered sequence of migration steps for an event type."""
    steps: tuple[MigrationStep, ...] = ()

    def exists(self) -> bool:
        """True if any migration steps exist."""
        return len(self.steps) > 0


@dataclass(frozen=True)
class EventSchema:
    """Schema metadata for a single event type."""
    event_type: EventType
    latest_version: int
    migration_path: MigrationPath


@dataclass(frozen=True)
class SchemaPolicy:
    """Immutable snapshot of schema rules derived from GovernanceState.

    NOT a projection. A compiled execution contract built by SchemaPolicyFactory.
    Contains only facts — no executable code, no callables.
    """
    _schemas: Mapping[EventType, EventSchema]

    def latest_version(self, event_type: EventType) -> int:
        """Canonical latest version for this event type. Defaults to 1."""
        if event_type in self._schemas:
            return self._schemas[event_type].latest_version
        return 1

    def schema(self, event_type: EventType) -> EventSchema:
        """Full schema metadata for an event type."""
        if event_type in self._schemas:
            return self._schemas[event_type]
        return EventSchema(
            event_type=event_type,
            latest_version=1,
            migration_path=MigrationPath(),
        )

    def migration_path(self, event_type: EventType) -> MigrationPath:
        """Ordered migration steps for this event type."""
        return self.schema(event_type).migration_path

    def is_current(self, event: EventRecord) -> bool:
        """True if event is exactly at its canonical version. Strict equality."""
        return event.schema_version == self.latest_version(event.event_type)

    def can_resolve(self, event: EventRecord) -> bool:
        """True if the policy has a valid migration path for this event.

        An event can be resolved if:
        - It is already at canonical version (no migration needed), OR
        - A complete migration path exists from its version to canonical
        """
        if self.is_current(event):
            return True
        path = self.migration_path(event.event_type)
        if not path.exists():
            return False
        current = event.schema_version
        target = self.latest_version(event.event_type)
        for step in path.steps:
            if step.from_version == current:
                current = step.to_version
        return current == target

    def event_types(self) -> Iterable[EventType]:
        """All event types with explicit schema metadata."""
        return self._schemas.keys()
