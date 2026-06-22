from __future__ import annotations

from datetime import datetime
from enum import Enum
import uuid
from rationalevault.memory.query_analyzer import RetrievalProfile
from rationalevault.memory.citation_builder import MemoryCitation
from rationalevault.db.event_store import EventStore
from rationalevault.schema.events import EventMetadata, EventType


class RetrievalFailure(str, Enum):
    QUERY_MISCLASSIFICATION = "QUERY_MISCLASSIFICATION"
    MEMORY_MISS = "MEMORY_MISS"
    RANKING_ERROR = "RANKING_ERROR"
    CITATION_ERROR = "CITATION_ERROR"
    SEMANTIC_MISMATCH = "SEMANTIC_MISMATCH"
    OVER_RETRIEVAL = "OVER_RETRIEVAL"


def audit_retrieval_execution(
    project_id: uuid.UUID,
    query: str,
    predicted_profile: RetrievalProfile,
    expected_profile: RetrievalProfile | None,
    expected_memory_id: str | None,
    retrieved_citations: list[MemoryCitation],
) -> list[RetrievalFailure]:
    """
    Checks retrieval results against ground truth tags and classifies failures.
    Logs RETRIEVAL_AUDITED events to the event store if audit fails.
    """
    failures = []
    
    # 1. Query Profile Misclassification
    if expected_profile and predicted_profile != expected_profile:
        failures.append(RetrievalFailure.QUERY_MISCLASSIFICATION)
        
    # 2. Memory Miss & Ranking Error
    if expected_memory_id:
        retrieved_ids = [c.memory_id for c in retrieved_citations]
        if expected_memory_id not in retrieved_ids:
            failures.append(RetrievalFailure.MEMORY_MISS)
        elif retrieved_ids[0] != expected_memory_id:
            failures.append(RetrievalFailure.RANKING_ERROR)
            
    # 3. Citation Errors
    for c in retrieved_citations:
        if not c.reasons or not c.source_event_ids:
            failures.append(RetrievalFailure.CITATION_ERROR)
            break
            
    # 4. Over Retrieval
    if len(retrieved_citations) > 2:
        failures.append(RetrievalFailure.OVER_RETRIEVAL)
        
    # Append event to event ledger
    if failures:
        try:
            store = EventStore()
            metadata = EventMetadata(actor="retrieval_auditor", source="retrieval_engine")
            store.append_event(
                project_id=project_id,
                stream_id="retrieval_audits",
                event_type=EventType.RETRIEVAL_AUDITED,
                payload={
                    "query": query,
                    "predicted_profile": predicted_profile.value,
                    "expected_profile": expected_profile.value if expected_profile else None,
                    "failures": [f.value for f in failures],
                    "timestamp": datetime.now().isoformat()
                },
                metadata=metadata
            )
        except Exception:
            pass
            
    return failures
