from __future__ import annotations

from rationalevault.schema.events import EventRecord
from rationalevault.schema.policy import SchemaPolicy
from rationalevault.schema.upcaster import UpcasterRegistry


class UnknownSchemaError(ValueError):
    """Raised when an event carries a schema_version that the system does not know how to resolve."""
    pass


class ReplayResolver:
    """
    Resolves and upcasts EventRecord payload shapes based on schema_version and registered upcasters.

    Supports two resolution strategies during migration:
    - Policy-based (new): uses SchemaPolicy + UpcasterRegistry
    - Legacy (deprecated): uses target_schema_version + UpcasterRegistry

    When policy is provided, it takes precedence.
    """

    def __init__(
        self,
        policy: SchemaPolicy | UpcasterRegistry | None = None,
        registry: UpcasterRegistry | None = None,
        target_schema_version: int = 2,
    ) -> None:
        if isinstance(policy, UpcasterRegistry):
            # Legacy positional: ReplayResolver(registry, target_schema_version)
            self._policy = None
            self._registry = policy
            if isinstance(registry, int):
                target_schema_version = registry
                registry = None
            if registry is not None:
                self._registry = registry
        elif isinstance(policy, SchemaPolicy):
            self._policy = policy
            self._registry = registry or UpcasterRegistry.default()
        else:
            self._policy = None
            self._registry = registry or UpcasterRegistry.default()
        # Legacy attributes kept for backward compatibility
        self.registry = self._registry
        self.target_schema_version = target_schema_version

    def resolve(self, event: EventRecord) -> EventRecord:
        if self._policy is not None:
            return self._resolve_with_policy(event)
        return self._resolve_legacy(event)

    def _resolve_with_policy(self, event: EventRecord) -> EventRecord:
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

    def _resolve_legacy(self, event: EventRecord) -> EventRecord:
        current_version = event.schema_version

        if current_version >= self.target_schema_version:
            return event

        payload = event.payload
        version = current_version

        event_type_val = event.event_type.value if hasattr(event.event_type, "value") else str(event.event_type)

        EVOLVED_EVENT_TYPES = {"TASK_CREATED"}
        has_evolutions = event_type_val in EVOLVED_EVENT_TYPES

        while version < self.target_schema_version:
            upcaster = self._registry.get_upcaster(event.event_type, version)
            if not upcaster:
                if has_evolutions:
                    raise UnknownSchemaError(
                        f"No upcaster registered to resolve event type '{event_type_val}' "
                        f"from version {version} to {self.target_schema_version} (seq={event.event_sequence})."
                    )
                break
            payload = upcaster(payload)
            version += 1

        return EventRecord(
            event_sequence=event.event_sequence,
            id=event.id,
            project_id=event.project_id,
            stream_id=event.stream_id,
            version=event.version,
            event_type=event.event_type,
            metadata=event.metadata,
            payload=payload,
            parent_id=event.parent_id,
            recorded_at=event.recorded_at,
            schema_version=version,
        )
