"""Core models for the Projection Platform.

Projection Laws (normative):
  1. Determinism — same events → same state.
  2. Replayability — state reconstructible solely from events.
  3. Snapshotability — snapshots are caches, not authority.
  4. Incrementality — replay(A+B) == replay(B, initial_state=replay(A)).
  5. Versioning — schema and logic versions evolve independently.
  6. Observability — emits ReplayReport.
  7. Isolation — reads only declared event types.
  8. Idempotence — applying an already-applied event must not duplicate state.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from rationalevault.schema.events import EventType


# ── Dependency ────────────────────────────────────────────────────────────────


class DependencyKind(Enum):
    """How one projection depends on another."""

    STATE = "state"
    SEARCH = "search"
    EVENT_STREAM = "stream"
    QUERY = "query"
    EXPORT = "export"


@dataclass(frozen=True)
class ProjectionDependency:
    """Declares a dependency on another projection."""

    projection_id: str
    kind: DependencyKind
    optional: bool = False


# ── Event Selector ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class EventSelector:
    """Declares which event types a projection consumes."""

    types: frozenset[EventType] = frozenset()
    namespace: str = ""
    tags: frozenset[str] = frozenset()


# ── Capabilities ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ProjectionCapabilities:
    """Declares what a projection can do."""

    searchable: bool = False
    snapshotable: bool = True
    observable: bool = True
    exportable: bool = False
    mutable: bool = False


# ── Health ────────────────────────────────────────────────────────────────────


class ProjectionHealth(Enum):
    """Health states for projections."""

    UNKNOWN = "unknown"
    INITIALIZING = "initializing"
    BUILDING = "building"
    READY = "ready"
    STALE = "stale"
    FAILED = "failed"
    DEGRADED = "degraded"
    SHUTDOWN = "shutdown"


# ── Metadata ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ProjectionMetadata:
    """Immutable descriptor for a projection."""

    id: str
    version: int
    schema_version: int
    consumed_events: EventSelector
    capabilities: ProjectionCapabilities
    dependencies: tuple[ProjectionDependency, ...] = ()
    description: str = ""


# ── Snapshot Key ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SnapshotKey:
    """Determines snapshot invalidation. Changed key → stale snapshot."""

    projection_id: str
    projection_version: int
    schema_version: int
    dependencies_hash: str = ""


# ── Search Result ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SearchResult:
    """Result from a projection search query."""

    id: str
    score: float
    payload: dict[str, Any] = field(default_factory=dict)


# ── Runtime Health ────────────────────────────────────────────────────────────


class RuntimeHealth(Enum):
    """Health states for runtime adapters."""

    UNKNOWN = "unknown"
    READY = "ready"
    DEGRADED = "degraded"
    FAILED = "failed"
    SHUTDOWN = "shutdown"
