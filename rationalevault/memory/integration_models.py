"""
RationaleVault Memory Integration — Contracts connecting Runtime to Memory layer.

The Memory Integration layer bridges the Agent Runtime with the graph-backed
memory substrate. Agents can query, record, and reason about memories through
a standardized interface.

Design rules:
  - Memory queries are deterministic (same query → same results).
  - Memory results carry provenance (source events, memory IDs, scores).
  - Memory context is a snapshot, not a live connection.
  - The memory layer remains the source of truth; this is a read/write bridge.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# =====================================================================
# Enums
# =====================================================================

class MemoryQueryType(str, Enum):
    """Types of memory queries."""
    SEARCH = "SEARCH"              # Keyword/semantic search
    RETRIEVE = "RETRIEVE"          # Direct ID lookup
    CONTEXT = "CONTEXT"            # Blended context compilation
    CONTINUATION = "CONTINUATION"  # Where I left off
    LINEAGE = "LINEAGE"            # Provenance chain traversal


class MemoryRecordType(str, Enum):
    """Memory record types (mirrors MemoryType)."""
    DECISION = "DECISION"
    DECISION_RATIONALE = "DECISION_RATIONALE"
    LESSON_LEARNED = "LESSON_LEARNED"
    FAILURE = "FAILURE"
    ARCHITECTURE = "ARCHITECTURE"
    IMPLEMENTATION_NOTE = "IMPLEMENTATION_NOTE"
    RESEARCH = "RESEARCH"
    WORKFLOW = "WORKFLOW"


class MemoryLifecycleState(str, Enum):
    """Memory lifecycle states."""
    CANDIDATE = "CANDIDATE"
    ACTIVE = "ACTIVE"
    PROMOTED = "PROMOTED"
    ARCHIVED = "ARCHIVED"
    SUPERSEDED = "SUPERSEDED"


# =====================================================================
# Memory Query
# =====================================================================

@dataclass(frozen=True)
class MemoryQuery:
    """
    Immutable memory query specification.

    MQRY-[hash] — deterministic query identity.
    """
    query_id: str                   # MQRY-[hash]
    query_type: MemoryQueryType
    text: str
    project_id: str | None = None
    memory_types: frozenset[MemoryRecordType] | None = None
    lifecycle_states: frozenset[MemoryLifecycleState] | None = None
    limit: int = 10
    min_score: float = 0.0
    include_provenance: bool = True
    metadata: dict[str, str] = field(default_factory=dict)

    @staticmethod
    def generate_query_id(query_type: str, text: str, project_id: str | None) -> str:
        data = f"memory_query:{query_type}:{text}:{project_id or 'global'}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"MQRY-{h}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "query_id": self.query_id,
            "query_type": self.query_type.value,
            "text": self.text,
            "project_id": self.project_id,
            "memory_types": sorted(t.value for t in self.memory_types) if self.memory_types else None,
            "lifecycle_states": sorted(s.value for s in self.lifecycle_states) if self.lifecycle_states else None,
            "limit": self.limit,
            "min_score": self.min_score,
            "include_provenance": self.include_provenance,
        }


# =====================================================================
# Memory Result
# =====================================================================

@dataclass(frozen=True)
class MemoryResult:
    """
    A single memory result with score and provenance.

    MRES-[hash] — immutable result identifier.
    """
    result_id: str                  # MRES-[hash]
    memory_id: str
    memory_type: MemoryRecordType
    title: str
    content: str
    score: float
    lifecycle_state: MemoryLifecycleState
    source_event_ids: list[str] = field(default_factory=list)
    source_memory_ids: list[str] = field(default_factory=list)
    confidence: float = 0.0
    reference_count: int = 0
    reasons: list[str] = field(default_factory=list)
    retrieval_path: list[str] = field(default_factory=list)

    @staticmethod
    def generate_result_id(memory_id: str, query_id: str) -> str:
        data = f"memory_result:{memory_id}:{query_id}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"MRES-{h}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_id": self.result_id,
            "memory_id": self.memory_id,
            "memory_type": self.memory_type.value,
            "title": self.title,
            "content": self.content,
            "score": self.score,
            "lifecycle_state": self.lifecycle_state.value,
            "source_event_ids": self.source_event_ids,
            "source_memory_ids": self.source_memory_ids,
            "confidence": self.confidence,
            "reference_count": self.reference_count,
            "reasons": self.reasons,
            "retrieval_path": self.retrieval_path,
        }


# =====================================================================
# Memory Context
# =====================================================================

@dataclass(frozen=True)
class MemoryContext:
    """
    A snapshot of memory context for an agent session.

    MCTX-[hash] — immutable context identifier.
    """
    context_id: str                 # MCTX-[hash]
    query_id: str
    results: list[MemoryResult] = field(default_factory=list)
    total_candidates: int = 0
    retrieval_time_ms: float = 0.0
    profile_used: str | None = None
    knowledge_context_hash: str | None = None  # Link to KnowledgeLayer

    @staticmethod
    def generate_context_id(query_id: str) -> str:
        data = f"memory_context:{query_id}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"MCTX-{h}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "context_id": self.context_id,
            "query_id": self.query_id,
            "results": [r.to_dict() for r in self.results],
            "total_candidates": self.total_candidates,
            "retrieval_time_ms": self.retrieval_time_ms,
            "profile_used": self.profile_used,
            "knowledge_context_hash": self.knowledge_context_hash,
        }

    def result_count(self) -> int:
        return len(self.results)

    def top_result(self) -> MemoryResult | None:
        return self.results[0] if self.results else None

    def results_by_type(self) -> dict[MemoryRecordType, list[MemoryResult]]:
        grouped: dict[MemoryRecordType, list[MemoryResult]] = {}
        for r in self.results:
            grouped.setdefault(r.memory_type, []).append(r)
        return grouped


# =====================================================================
# Memory Write Request
# =====================================================================

@dataclass(frozen=True)
class MemoryWriteRequest:
    """
    Request to record a new memory through the runtime.

    MWRT-[hash] — write request identity.
    """
    request_id: str                 # MWRT-[hash]
    memory_type: MemoryRecordType
    title: str
    content: str
    project_id: str | None = None
    importance: str = "medium"      # low, medium, high, critical
    tags: frozenset[str] = field(default_factory=frozenset)
    source_event_ids: list[str] = field(default_factory=list)
    actor: str = "agent"
    metadata: dict[str, str] = field(default_factory=dict)

    @staticmethod
    def generate_request_id(title: str, content: str, project_id: str | None) -> str:
        data = f"memory_write:{title}:{content[:64]}:{project_id or 'global'}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"MWRT-{h}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "memory_type": self.memory_type.value,
            "title": self.title,
            "content": self.content,
            "project_id": self.project_id,
            "importance": self.importance,
            "tags": sorted(self.tags),
            "source_event_ids": self.source_event_ids,
            "actor": self.actor,
        }


# =====================================================================
# Memory Write Result
# =====================================================================

@dataclass(frozen=True)
class MemoryWriteResult:
    """
    Result of a memory write operation.

    MWRS-[hash] — write result identity.
    """
    result_id: str                  # MWRS-[hash]
    request_id: str
    success: bool
    memory_id: str | None = None    # ID of created memory
    error: str | None = None
    deduplicated: bool = False      # True if memory already existed

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_id": self.result_id,
            "request_id": self.request_id,
            "success": self.success,
            "memory_id": self.memory_id,
            "error": self.error,
            "deduplicated": self.deduplicated,
        }
