from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional
from rationalevault.projections.base import SemVer

@dataclass(frozen=True)
class CacheKey:
    project_id: str
    projection_name: str
    projection_version: SemVer

@dataclass(frozen=True)
class CacheEntry:
    compiled_projection: Any
    fingerprint: str
    version: SemVer
    build_time: datetime
    build_duration_ms: float

class ProjectionCache:
    """Transient in-memory cache for compiled projection states."""

    def __init__(self) -> None:
        self._cache: dict[CacheKey, CacheEntry] = {}

    def get(self, key: CacheKey) -> Optional[CacheEntry]:
        """Retrieves a cache entry if it exists."""
        return self._cache.get(key)

    def set(self, key: CacheKey, entry: CacheEntry) -> None:
        """Stores a projection state and metadata in the cache."""
        self._cache[key] = entry

    def invalidate(self, project_id: str, projection_name: str, version: SemVer) -> None:
        """Removes a specific projection entry from the cache."""
        key = CacheKey(project_id, projection_name, version)
        if key in self._cache:
            del self._cache[key]

    def clear(self) -> None:
        """Clears all transient cache entries."""
        self._cache.clear()

    def get_all_entries(self) -> dict[CacheKey, CacheEntry]:
        """Returns a copy of the cache mapping."""
        return dict(self._cache)
