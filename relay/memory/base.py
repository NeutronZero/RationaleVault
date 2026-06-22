from __future__ import annotations

from abc import ABC, abstractmethod
from relay.memory.models import MemoryRecord


class BaseMemoryProvider(ABC):
    """
    Abstract base class for Relay Memory Bridge providers.
    """

    @abstractmethod
    def add_record(self, record: MemoryRecord) -> None:
        """Add or update a memory record."""
        pass

    @abstractmethod
    def search_records(self, query: str, limit: int = 5) -> list[MemoryRecord]:
        """Query memory records using keyword search."""
        pass

    @abstractmethod
    def get_all_records(self) -> list[MemoryRecord]:
        """Return all memory records stored."""
        pass
