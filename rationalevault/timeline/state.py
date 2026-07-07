"""Timeline projection state — TimelineCategory, TimelineEntry, TimelineState."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rationalevault.schema.events import EventType


class TimelineCategory(Enum):
    """Narrative category for timeline entries."""

    DECISION = "decision"
    KNOWLEDGE = "knowledge"
    TASK = "task"
    QUESTION = "question"
    MEMORY = "memory"
    MILESTONE = "milestone"
    SYSTEM = "system"


@dataclass
class TimelineEntry:
    """Normalized historical record — one per narratively significant event.

    This is a stable domain model, not a UI object. The CLI, MCP, and
    future REST API all consume it directly. Do not add display-oriented
    fields.
    """

    sequence: int
    timestamp: datetime
    event_type: EventType
    category: TimelineCategory
    actor: str | None
    subject_entity: str | None
    summary: str
    references: list[int] = field(default_factory=list)


@dataclass
class TimelineState:
    """Projection state — append-only list of normalized entries.

    Attributes:
        entries: ordered list of TimelineEntry (sorted by sequence)
        sequence: last processed event sequence (for snapshot fast-path)
    """

    entries: list[TimelineEntry] = field(default_factory=list)
    sequence: int = 0

    @property
    def entry_count(self) -> int:
        """Number of entries in the timeline."""
        return len(self.entries)

    @property
    def categories(self) -> set[TimelineCategory]:
        """Set of categories present in the timeline."""
        return {e.category for e in self.entries}
