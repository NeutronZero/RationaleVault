from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class MemoryType(str, Enum):
    DECISION = "DECISION"
    DECISION_RATIONALE = "DECISION_RATIONALE"
    LESSON_LEARNED = "LESSON_LEARNED"
    FAILURE = "FAILURE"
    ARCHITECTURE = "ARCHITECTURE"
    IMPLEMENTATION_NOTE = "IMPLEMENTATION_NOTE"
    RESEARCH = "RESEARCH"
    WORKFLOW = "WORKFLOW"


def generate_memory_id(memory_type: str, title: str, content: str) -> str:
    norm_content = " ".join(content.lower().strip().split())
    norm_title = " ".join(title.lower().strip().split())
    data = f"{memory_type.lower()}:{norm_title}:{norm_content}"
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


@dataclass
class MemoryRecord:
    id: str
    version: int
    title: str
    content: str
    memory_type: MemoryType
    importance: str  # low | medium | high | critical
    lifecycle_status: str  # active | historical | superseded | archived
    source_event_ids: list[str]
    source_type: str
    tags: list[str] = field(default_factory=list)
    confidence: float = 1.0
    retrieval_priority: float = 2.0
    reference_count: int = 0
    last_referenced_at: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    project_id: str = ""

    def __post_init__(self) -> None:
        weights = {"low": 1.0, "medium": 2.0, "high": 3.0, "critical": 5.0}
        self.retrieval_priority = weights.get(self.importance.lower(), 2.0)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> MemoryRecord:
        return cls(
            id=d["id"],
            version=d.get("version", 1),
            title=d["title"],
            content=d["content"],
            memory_type=MemoryType(d["memory_type"]),
            importance=d.get("importance", "medium"),
            lifecycle_status=d.get("lifecycle_status", "active"),
            source_event_ids=d.get("source_event_ids") or [],
            source_type=d.get("source_type") or "unknown",
            tags=d.get("tags") or [],
            confidence=d.get("confidence", 1.0),
            retrieval_priority=d.get("retrieval_priority", 2.0),
            reference_count=d.get("reference_count", 0),
            last_referenced_at=d.get("last_referenced_at"),
            created_at=d.get("created_at") or datetime.now().isoformat(),
            project_id=d.get("project_id", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "version": self.version,
            "title": self.title,
            "content": self.content,
            "memory_type": self.memory_type.value,
            "importance": self.importance,
            "lifecycle_status": self.lifecycle_status,
            "source_event_ids": self.source_event_ids,
            "source_type": self.source_type,
            "tags": self.tags,
            "confidence": self.confidence,
            "retrieval_priority": self.retrieval_priority,
            "reference_count": self.reference_count,
            "last_referenced_at": self.last_referenced_at,
            "created_at": self.created_at,
            "project_id": self.project_id,
        }
