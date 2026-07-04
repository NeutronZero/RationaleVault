"""
RationaleVault Memory Runtime — MemoryBroker connecting Runtime to Memory layer.

The MemoryBroker orchestrates memory queries and writes through the existing
memory infrastructure (retrieval, synthesis, lifecycle).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from rationalevault.memory.integration_models import (
    MemoryContext,
    MemoryQuery,
    MemoryQueryType,
    MemoryRecordType,
    MemoryResult,
    MemoryWriteRequest,
    MemoryWriteResult,
)
from rationalevault.memory.models import MemoryType


# =====================================================================
# Memory Type Mapping
# =====================================================================

_RUNTIME_TO_MEMORY_TYPE: dict[MemoryRecordType, MemoryType] = {
    MemoryRecordType.DECISION: MemoryType.DECISION,
    MemoryRecordType.DECISION_RATIONALE: MemoryType.DECISION_RATIONALE,
    MemoryRecordType.LESSON_LEARNED: MemoryType.LESSON_LEARNED,
    MemoryRecordType.FAILURE: MemoryType.FAILURE,
    MemoryRecordType.ARCHITECTURE: MemoryType.ARCHITECTURE,
    MemoryRecordType.IMPLEMENTATION_NOTE: MemoryType.IMPLEMENTATION_NOTE,
    MemoryRecordType.RESEARCH: MemoryType.RESEARCH,
    MemoryRecordType.WORKFLOW: MemoryType.WORKFLOW,
}

_MEMORY_TO_RUNTIME_TYPE: dict[MemoryType, MemoryRecordType] = {
    v: k for k, v in _RUNTIME_TO_MEMORY_TYPE.items()
}


def _map_memory_type(mt: Any) -> MemoryRecordType:
    """Map a MemoryType to a MemoryRecordType."""
    if isinstance(mt, MemoryType):
        return _MEMORY_TO_RUNTIME_TYPE.get(mt, MemoryRecordType.LESSON_LEARNED)
    if isinstance(mt, MemoryRecordType):
        return mt
    return MemoryRecordType.LESSON_LEARNED


# =====================================================================
# Memory Broker
# =====================================================================

@dataclass
class MemoryBroker:
    """
    Bridges the Agent Runtime with the memory layer.

    Responsibilities:
      - Translate MemoryQuery → memory layer calls
      - Translate memory layer results → MemoryResult
      - Handle memory writes through the lifecycle pipeline
      - Cache recent contexts for session continuity
    """
    _context_cache: dict[str, MemoryContext] = field(default_factory=dict)
    _query_count: int = field(default=0, repr=False)

    def execute_query(self, query: MemoryQuery) -> MemoryContext:
        """
        Execute a memory query and return a MemoryContext.

        This is the primary read path for agents.
        """
        self._query_count += 1
        start = time.monotonic()

        try:
            from rationalevault.memory.retrieval import retrieve_ranked_citations

            # Map query types to retrieval profiles
            profile = self._query_type_to_profile(query.query_type)

            # Execute retrieval
            citations, execution = retrieve_ranked_citations(
                query.text,
                limit=query.limit,
                project_id=query.project_id,
                profile=profile,
            )

            # Convert citations to MemoryResult
            results = []
            for citation in citations:
                memory = citation.memory if hasattr(citation, 'memory') else None
                if memory is None:
                    # Try to get memory from citation attributes
                    memory_id = getattr(citation, 'memory_id', None)
                    title = getattr(citation, 'title', 'Unknown')
                    content = getattr(citation, 'content', '')
                    memory_type = getattr(citation, 'memory_type', MemoryRecordType.LESSON_LEARNED)
                    lifecycle_state = getattr(citation, 'lifecycle_state', 'active')
                    confidence = getattr(citation, 'confidence', 0.0)
                    reference_count = getattr(citation, 'reference_count', 0)
                else:
                    memory_id = str(memory.id)
                    title = memory.title
                    content = memory.content
                    memory_type = _map_memory_type(memory.memory_type)
                    lifecycle_state = memory.lifecycle_status
                    confidence = getattr(memory, 'confidence', 0.0)
                    reference_count = getattr(memory, 'reference_count', 0)

                score_val = citation.score.total if hasattr(citation, 'score') and hasattr(citation.score, 'total') else 0.0
                reasons = getattr(citation, 'reasons', [])
                retrieval_path = getattr(citation, 'retrieval_path', [])

                result = MemoryResult(
                    result_id=MemoryResult.generate_result_id(memory_id, query.query_id),
                    memory_id=memory_id,
                    memory_type=memory_type,
                    title=title,
                    content=content,
                    score=score_val,
                    lifecycle_state=lifecycle_state,
                    confidence=confidence,
                    reference_count=reference_count,
                    reasons=reasons,
                    retrieval_path=retrieval_path,
                )
                results.append(result)

            elapsed_ms = (time.monotonic() - start) * 1000

            context = MemoryContext(
                context_id=MemoryContext.generate_context_id(query.query_id),
                query_id=query.query_id,
                results=results,
                total_candidates=execution.candidate_count if execution else len(results),
                retrieval_time_ms=elapsed_ms,
                profile_used=profile.value if profile else None,
            )

            # Cache for session continuity
            self._context_cache[query.query_id] = context
            return context

        except Exception:
            # Return empty context on failure
            elapsed_ms = (time.monotonic() - start) * 1000
            return MemoryContext(
                context_id=MemoryContext.generate_context_id(query.query_id),
                query_id=query.query_id,
                results=[],
                retrieval_time_ms=elapsed_ms,
            )

    def record_memory(self, request: MemoryWriteRequest) -> MemoryWriteResult:
        """
        Record a new memory through the lifecycle pipeline.

        This is the primary write path for agents.
        """
        try:
            from rationalevault.memory.factory import get_memory_provider
            from rationalevault.memory.models import MemoryRecord, MemoryType

            provider = get_memory_provider()

            # Map importance to memory type
            mem_type = _RUNTIME_TO_MEMORY_TYPE.get(
                request.memory_type, MemoryType.LESSON_LEARNED,
            )

            # Create memory record
            record = MemoryRecord(
                id=MemoryRecord.generate_id(mem_type.value, request.title, request.content),
                memory_type=mem_type,
                title=request.title,
                content=request.content,
                importance=request.importance,
                tags=list(request.tags),
                project_id=request.project_id,
                source_event_ids=request.source_event_ids,
            )

            # Deduplication: O(1) indexed lookup instead of O(n) full table scan
            if provider.get_record_by_id(record.id) is not None:
                return MemoryWriteResult(
                    result_id=MemoryWriteResult.generate_result_id(
                        record.id, request.request_id,
                    ),
                    request_id=request.request_id,
                    success=True,
                    memory_id=record.id,
                    deduplicated=True,
                )

            # Store
            provider.add_record(record)

            return MemoryWriteResult(
                result_id=MemoryWriteResult.generate_result_id(
                    record.id, request.request_id,
                ),
                request_id=request.request_id,
                success=True,
                memory_id=record.id,
            )

        except Exception as e:
            return MemoryWriteResult(
                result_id=MemoryWriteResult.generate_result_id(
                    "FAILED", request.request_id,
                ),
                request_id=request.request_id,
                success=False,
                error=str(e),
            )

    def get_cached_context(self, query_id: str) -> MemoryContext | None:
        """Retrieve a previously cached context for session continuity."""
        return self._context_cache.get(query_id)

    def query_count(self) -> int:
        return self._query_count

    def cache_size(self) -> int:
        return len(self._context_cache)

    def _query_type_to_profile(self, qt: MemoryQueryType):
        """Map a MemoryQueryType to a RetrievalProfile."""
        from rationalevault.memory.query_analyzer import RetrievalProfile
        mapping = {
            MemoryQueryType.SEARCH: RetrievalProfile.GENERAL_SEARCH,
            MemoryQueryType.RETRIEVE: RetrievalProfile.DECISION_LOOKUP,
            MemoryQueryType.CONTEXT: RetrievalProfile.CONTEXT_CONSTRUCTION,
            MemoryQueryType.CONTINUATION: RetrievalProfile.GENERAL_SEARCH,
            MemoryQueryType.LINEAGE: RetrievalProfile.ARCHITECTURE_REVIEW,
        }
        return mapping.get(qt, RetrievalProfile.GENERAL_SEARCH)
