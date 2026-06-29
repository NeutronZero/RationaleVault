from __future__ import annotations

from typing import Callable, Any
from rationalevault.schema.events import EventType

# An upcaster is a callable that takes a payload and returns the upcasted payload
UpcasterCallable = Callable[[dict[str, Any]], dict[str, Any]]


def task_created_v1_to_v2(payload: dict[str, Any]) -> dict[str, Any]:
    """Upcasts TASK_CREATED payload from v1 (flat) to v2 (nested details)."""
    payload_copy = dict(payload)
    title = payload_copy.pop("title", "")
    description = payload_copy.pop("description", "")
    payload_copy["details"] = {
        "summary": title,
        "body": description
    }
    return payload_copy


class UpcasterRegistry:
    """Pure data structure mapping (EventType, source_version) to upcaster callables.

    No auto-registration. Callers explicitly provide upcasters via constructor dict
    or register() calls. Use UpcasterRegistry.default() for a registry pre-populated
    with all production upcasters.
    """

    def __init__(self, upcasters: dict[str, dict[int, UpcasterCallable]] | None = None) -> None:
        self._upcasters: dict[tuple[str, int], UpcasterCallable] = {}
        if upcasters:
            for event_type_str, version_map in upcasters.items():
                for version, upcaster in version_map.items():
                    self._upcasters[(event_type_str, version)] = upcaster

    @classmethod
    def default(cls) -> UpcasterRegistry:
        """Create a registry pre-populated with all production upcasters."""
        return cls({"TASK_CREATED": {1: task_created_v1_to_v2}})

    def register(self, event_type: EventType, source_version: int, upcaster: UpcasterCallable) -> None:
        """Register an upcaster function for a specific event type and source schema version."""
        key = (event_type.value, source_version)
        self._upcasters[key] = upcaster

    def is_registered(self, event_type: EventType, version: int) -> bool:
        """Return True if an upcaster is registered for the event type at the given version."""
        return (event_type.value, version) in self._upcasters

    def get_upcaster(self, event_type: EventType, source_version: int) -> UpcasterCallable | None:
        """Retrieve an upcaster for the given event type and source version, or None if none registered."""
        return self._upcasters.get((event_type.value, source_version))
