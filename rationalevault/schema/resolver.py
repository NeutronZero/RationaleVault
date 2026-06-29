from __future__ import annotations

from rationalevault.schema.events import EventRecord, EventType
from rationalevault.schema.policy import SchemaPolicy
from rationalevault.schema.upcaster import UpcasterRegistry


class UnknownSchemaError(ValueError):
    """Raised when an event carries a schema_version that the system does not know how to resolve."""
    pass


class ReplayResolver:
    """Resolves and upcasts EventRecord payloads based on SchemaPolicy and registered upcasters.

    Pure policy executor with no knowledge of versions or governance.
    """

    def __init__(self, policy: SchemaPolicy, registry: UpcasterRegistry) -> None:
        self._policy = policy
        self._registry = registry

    def can_resolve(self, schema_version: int, event_type: EventType | None = None) -> bool:
        """Check if the resolver can handle events at the given schema version."""
        if event_type is None:
            return True
        return self._policy.latest_version(event_type) >= schema_version

    def resolve(self, event: EventRecord) -> EventRecord:
        if self._policy.is_current(event):
            return event
        if not self._policy.can_resolve(event):
            raise UnknownSchemaError(
                f"Cannot resolve event type '{event.event_type.value}' "
                f"at schema_version={event.schema_version} (seq={event.event_sequence}): "
                f"no migration path to canonical version {self._policy.latest_version(event.event_type)}."
            )
        path = self._policy.migration_path(event.event_type)
        current_payload = dict(event.payload)
        current_version = event.schema_version
        for step in path.steps:
            if step.from_version == current_version:
                upcaster = self._registry.get_upcaster(event.event_type, step.from_version)
                if upcaster is None:
                    raise UnknownSchemaError(
                        f"No upcaster registered for event type '{event.event_type.value}' "
                        f"from version {step.from_version} to {step.to_version} (seq={event.event_sequence})."
                    )
                current_payload = upcaster(current_payload)
                current_version = step.to_version
        return EventRecord(
            event_sequence=event.event_sequence,
            id=event.id,
            project_id=event.project_id,
            stream_id=event.stream_id,
            version=event.version,
            event_type=event.event_type,
            metadata=event.metadata,
            payload=current_payload,
            parent_id=event.parent_id,
            recorded_at=event.recorded_at,
            schema_version=current_version,
        )
