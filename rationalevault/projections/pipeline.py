from __future__ import annotations

from typing import Iterable
from rationalevault.schema.events import EventRecord
from rationalevault.schema.resolver import ReplayResolver
from rationalevault.schema.upcaster import UpcasterRegistry
from rationalevault.projections.context import ReplayContext


class ReplayPipeline:
    """
    Orchestration pipeline that transforms a raw EventRecord stream from storage
    into resolved, filtered, and normalized events ready for projections.

    Owns resolver construction from ReplayContext.schema_policy + UpcasterRegistry.
    Ensures projections remain isolated from schema upcasting, versioning,
    and sequence limit constraints.
    """

    def __init__(self, context: ReplayContext | None = None, registry: UpcasterRegistry | None = None) -> None:
        self.context = context or ReplayContext()
        self._registry = registry or UpcasterRegistry.default()
        self._resolver = ReplayResolver(policy=self.context.schema_policy, registry=self._registry)

    def process(self, events: Iterable[EventRecord]) -> list[EventRecord]:
        """
        Processes a raw event stream through resolution and context constraints.
        """
        processed_events: list[EventRecord] = []

        for event in events:
            # 1. Apply max_sequence upper bound constraint
            if self.context.max_sequence is not None and event.event_sequence > self.context.max_sequence:
                break

            # 2. Resolve / Upcast payload version schema
            resolved_event = self._resolver.resolve(event)
            processed_events.append(resolved_event)

        return processed_events
