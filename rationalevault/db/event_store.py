from __future__ import annotations

from typing import Any, Iterator, Optional
from uuid import UUID

from rationalevault.db.base import BaseEventStore
from rationalevault.db.factory import get_event_store
from rationalevault.schema.events import EventMetadata, EventRecord, EventType


class EventStore(BaseEventStore):
    """
    Backward-compatible wrapper that delegates all event operations to the
    active backend store selected by get_event_store().
    """

    def __init__(self) -> None:
        self._store = get_event_store()

    def append_event(
        self,
        project_id: UUID,
        stream_id: str,
        event_type: EventType,
        payload: dict[str, Any],
        metadata: EventMetadata,
        parent_id: Optional[UUID] = None,
        conn: Optional[Any] = None,
    ) -> EventRecord:
        record = self._store.append_event(
            project_id=project_id,
            stream_id=stream_id,
            event_type=event_type,
            payload=payload,
            metadata=metadata,
            parent_id=parent_id,
            conn=conn,
        )

        # Automatic Memory Emission Rules (Sprint I1 & I2)
        if event_type.value not in [
            "MEMORY_RECORDED",
            "MEMORY_CONSOLIDATED",
            "MEMORY_REFERENCED",
            "MEMORY_SUPERSEDED",
            "MEMORY_ARCHIVED",
            "MEMORY_RANKED",
            "CONSOLIDATION_CANDIDATE",
            "RETRIEVAL_AUDITED",
            "RETRIEVAL_EXECUTED"
        ]:
            try:
                from rationalevault.memory.extractor import extract_memories_from_event
                from rationalevault.memory.factory import get_memory_provider
                from rationalevault.memory.lifecycle import handle_lifecycle_transitions
                memories = extract_memories_from_event(record)
                if memories:
                    provider = get_memory_provider()
                    for m in memories:
                        provider.add_record(m)
                
                # Run automatic supersession lifecycle transitions
                handle_lifecycle_transitions(record)
            except Exception:
                pass

        return record

    def get_project_stream(
        self,
        project_id: UUID,
        since_sequence: int = 0,
    ) -> list[EventRecord]:
        return self._store.get_project_stream(project_id, since_sequence)

    def replay_stream(
        self,
        project_id: UUID,
        since_sequence: int = 0,
    ) -> Iterator[EventRecord]:
        return self._store.replay_stream(project_id, since_sequence)

    def get_stream(
        self,
        project_id: UUID,
        stream_id: str,
        since_sequence: int = 0,
    ) -> list[EventRecord]:
        return self._store.get_stream(project_id, stream_id, since_sequence)

    def get_event_count(self, project_id: UUID) -> int:
        return self._store.get_event_count(project_id)

    def get_session_events(self, project_id: UUID, session_id: str) -> list[EventRecord]:
        return self._store.get_session_events(project_id, session_id)

    def get_last_session_id(self, project_id: UUID) -> Optional[str]:
        return self._store.get_last_session_id(project_id)

    def get_recent_events(self, project_id: UUID, limit: int = 20) -> list[EventRecord]:
        return self._store.get_recent_events(project_id, limit)

