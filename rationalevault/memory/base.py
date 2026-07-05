from __future__ import annotations

from abc import ABC, abstractmethod
from rationalevault.memory.models import MemoryRecord


class BaseMemoryProvider(ABC):
    """
    Abstract base class for RationaleVault Memory Bridge providers.

    Capability methods (search, get_by_ids, count) have default
    implementations that fall back to get_all_records(). Providers
    should override with optimized versions where possible.
    """

    @abstractmethod
    def add_record(self, record: MemoryRecord) -> None:
        """Add or update a memory record."""
        pass

    @abstractmethod
    def get_all_records(self) -> list[MemoryRecord]:
        """Return all memory records stored."""
        pass

    def search_records(self, query: str, limit: int = 5) -> list[MemoryRecord]:
        """Keyword search across records. Default: substring match on all records."""
        if not query:
            return self.get_all_records()[:limit]
        q = query.lower().strip()
        matched = [
            r for r in self.get_all_records()
            if q in r.title.lower()
            or q in r.content.lower()
            or any(q in tag.lower() for tag in r.tags)
        ]
        matched.sort(key=lambda x: x.retrieval_priority, reverse=True)
        return matched[:limit]

    def get_by_ids(self, ids: list[str]) -> list[MemoryRecord]:
        """Batch lookup by ID. Default: filter from all records."""
        id_set = set(ids)
        return [r for r in self.get_all_records() if r.id in id_set]

    def count(self) -> int:
        """Return total number of records. Default: len of all records."""
        return len(self.get_all_records())
