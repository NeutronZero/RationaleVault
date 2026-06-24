from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Iterator, Optional
from uuid import UUID

from rationalevault.schema.events import EventMetadata, EventRecord, EventType


class BaseEventStore(ABC):
    """
    Abstract base class for Relay Event Ledger backends.
    """

    @abstractmethod
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
        """Append a single event to the ledger."""
        pass

    @abstractmethod
    def get_project_stream(
        self,
        project_id: UUID,
        since_sequence: int = 0,
    ) -> list[EventRecord]:
        """Return all events for a project ordered by event_sequence ASC."""
        pass

    @abstractmethod
    def replay_stream(
        self,
        project_id: UUID,
        since_sequence: int = 0,
    ) -> Iterator[EventRecord]:
        """Generator yielding events in event_sequence order."""
        pass

    @abstractmethod
    def get_stream(
        self,
        project_id: UUID,
        stream_id: str,
        since_sequence: int = 0,
    ) -> list[EventRecord]:
        """Return events for a specific sub-stream within a project."""
        pass

    @abstractmethod
    def get_event_count(self, project_id: UUID) -> int:
        """Return the total event count for a project."""
        pass

    @abstractmethod
    def get_session_events(self, project_id: UUID, session_id: str) -> list[EventRecord]:
        """Return all events for a project's session ordered by event_sequence ASC."""
        pass

    @abstractmethod
    def get_last_session_id(self, project_id: UUID) -> Optional[str]:
        """Return the session_id of the most recent event of any type."""
        pass

    @abstractmethod
    def get_recent_events(self, project_id: UUID, limit: int = 20) -> list[EventRecord]:
        """Return the most recent events for a project ordered by event_sequence DESC."""
        pass

