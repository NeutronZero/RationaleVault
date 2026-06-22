from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from rationalevault.memory.models import MemoryRecord
from rationalevault.memory.ranking import RetrievalScore, compute_retrieval_score


@dataclass
class MemoryCitation:
    memory_id: str
    score: RetrievalScore
    source_event_ids: list[str]
    reasons: list[str]
    retrieval_path: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "score": self.score.to_dict(),
            "source_event_ids": self.source_event_ids,
            "reasons": self.reasons,
            "retrieval_path": self.retrieval_path,
        }


def build_citation(
    record: MemoryRecord,
    query: str,
    retrieval_path: list[str]
) -> MemoryCitation:
    """
    Constructs explainable citations mapping query terms and metadata logic.
    """
    score = compute_retrieval_score(record)
    
    # Reason analysis heuristics
    reasons = []
    query_clean = query.lower().strip() if query else ""
    if query_clean:
        if query_clean in record.title.lower():
            reasons.append("keyword_match_title")
        if query_clean in record.content.lower():
            reasons.append("keyword_match_content")
            
    if record.reference_count > 5:
        reasons.append("high_reference_count")
    elif record.reference_count > 0:
        reasons.append("referenced_active_knowledge")
        
    if record.retrieval_priority >= 5.0:
        reasons.append("critical_priority")
    elif record.retrieval_priority >= 3.0:
        reasons.append("high_priority")
        
    if record.confidence >= 0.9:
        reasons.append("high_confidence")

    if not reasons:
        reasons.append("general_relevance")
        
    return MemoryCitation(
        memory_id=record.id,
        score=score,
        source_event_ids=record.source_event_ids,
        reasons=reasons,
        retrieval_path=retrieval_path
    )
