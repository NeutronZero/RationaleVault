"""RationaleVault Context Types — Source-specific context objects and unified citation model.

Explicit source types (EventContext, MemoryContext, KnowledgeContext) scale better
than a generic discriminator enum. The unified ContextCitation provides a single
interface for agent compilers regardless of source.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class EventContext:
    """Lightweight view of an event for context packages.

    Does not store the full EventRecord payload — just the fields
    needed for context construction and provenance traceability.
    """
    event_id: str
    event_type: str
    stream_id: str
    recorded_at: str
    actor: str
    source: str
    summary: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "stream_id": self.stream_id,
            "recorded_at": self.recorded_at,
            "actor": self.actor,
            "source": self.source,
            "summary": self.summary,
        }


@dataclass
class MemoryContext:
    """Memory citation with explainable scoring for context packages."""
    memory_id: str
    title: str
    content: str
    memory_type: str
    relevance_score: float
    source_event_ids: list[str]
    reasons: list[str]
    retrieval_path: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "title": self.title,
            "content": self.content,
            "memory_type": self.memory_type,
            "relevance_score": self.relevance_score,
            "source_event_ids": self.source_event_ids,
            "reasons": self.reasons,
            "retrieval_path": self.retrieval_path,
        }


@dataclass
class KnowledgeContext:
    """Knowledge citation with explainable scoring for context packages."""
    knowledge_id: str
    title: str
    content: str
    knowledge_type: str
    knowledge_domain: str
    relevance_score: float
    confidence: float
    source_event_ids: list[str]
    source_memory_ids: list[str]
    reasons: list[str]
    retrieval_path: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "knowledge_id": self.knowledge_id,
            "title": self.title,
            "content": self.content,
            "knowledge_type": self.knowledge_type,
            "knowledge_domain": self.knowledge_domain,
            "relevance_score": self.relevance_score,
            "confidence": self.confidence,
            "source_event_ids": self.source_event_ids,
            "source_memory_ids": self.source_memory_ids,
            "reasons": self.reasons,
            "retrieval_path": self.retrieval_path,
        }


@dataclass
class ContextCitation:
    """Unified citation model for all context sources.

    Agent compilers see one interface regardless of source.
    """
    source_type: str          # "event" | "memory" | "knowledge"
    source_id: str            # event_id, memory_id, or knowledge_id
    title: str
    content: str
    relevance_score: float
    confidence: float
    reasons: list[str]
    source_event_ids: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_type": self.source_type,
            "source_id": self.source_id,
            "title": self.title,
            "content": self.content,
            "relevance_score": self.relevance_score,
            "confidence": self.confidence,
            "reasons": self.reasons,
            "source_event_ids": self.source_event_ids,
        }
