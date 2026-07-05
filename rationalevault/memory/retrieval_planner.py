from __future__ import annotations

from dataclasses import dataclass
import time
from rationalevault.memory.query_analyzer import RetrievalProfile, QueryIntent
from rationalevault.memory.models import MemoryRecord, MemoryType
from rationalevault.knowledge.models import KnowledgeType


from rationalevault.memory.timing import RetrievalTiming

@dataclass
class RetrievalExecution:
    profile: RetrievalProfile
    planner_sources: list[str]
    candidate_count: int
    retrieved_count: int
    execution_ms: float
    timing: RetrievalTiming | None = None
    semantic_used: bool = False
    rrf_used: bool = False
    vector_candidates: int = 0
    keyword_candidates: int = 0
    provider_latency_ms: float = 0.0
    provider_total_records: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile.value,
            "planner_sources": self.planner_sources,
            "candidate_count": self.candidate_count,
            "retrieved_count": self.retrieved_count,
            "execution_ms": self.execution_ms,
            "timing": self.timing.to_dict() if self.timing else None,
            "semantic_used": self.semantic_used,
            "rrf_used": self.rrf_used,
            "vector_candidates": self.vector_candidates,
            "keyword_candidates": self.keyword_candidates,
            "provider_latency_ms": self.provider_latency_ms,
            "provider_total_records": self.provider_total_records,
        }


from types import MappingProxyType

def get_profile_weights(profile: RetrievalProfile) -> MappingProxyType[MemoryType, float]:
    """
    Returns weights for each MemoryType based on the active RetrievalProfile.
    """
    weights = {t: 1.0 for t in MemoryType}
    
    if profile == RetrievalProfile.DECISION_LOOKUP:
        weights[MemoryType.DECISION] = 5.0
        weights[MemoryType.DECISION_RATIONALE] = 4.0
    elif profile == RetrievalProfile.FAILURE_ANALYSIS:
        weights[MemoryType.FAILURE] = 5.0
        weights[MemoryType.LESSON_LEARNED] = 4.0
    elif profile == RetrievalProfile.ARCHITECTURE_REVIEW:
        weights[MemoryType.ARCHITECTURE] = 5.0
        weights[MemoryType.DECISION] = 4.0
    elif profile == RetrievalProfile.LESSON_DISCOVERY:
        weights[MemoryType.LESSON_LEARNED] = 5.0
    elif profile == RetrievalProfile.WORKFLOW_RETRIEVAL:
        weights[MemoryType.WORKFLOW] = 5.0
        
    return MappingProxyType(weights)


def get_knowledge_profile_weights(profile: RetrievalProfile) -> MappingProxyType[KnowledgeType, float]:
    """Returns weights for each KnowledgeType based on the active RetrievalProfile."""
    weights = {t: 1.0 for t in KnowledgeType}

    if profile == RetrievalProfile.KNOWLEDGE_REVIEW:
        weights = {t: 3.0 for t in KnowledgeType}
        weights[KnowledgeType.ARCHITECTURE_PRINCIPLE] = 5.0
        weights[KnowledgeType.PROJECT_INVARIANT] = 5.0
    elif profile == RetrievalProfile.PROJECT_OVERVIEW:
        weights[KnowledgeType.ARCHITECTURE_PRINCIPLE] = 5.0
        weights[KnowledgeType.PROJECT_INVARIANT] = 5.0
        weights[KnowledgeType.DECISION_LINEAGE] = 4.0
        weights[KnowledgeType.LESSON] = 3.0
    elif profile == RetrievalProfile.CONTEXT_CONSTRUCTION:
        weights[KnowledgeType.ARCHITECTURE_PRINCIPLE] = 4.0
        weights[KnowledgeType.PROJECT_INVARIANT] = 5.0
        weights[KnowledgeType.LESSON] = 3.0
        weights[KnowledgeType.FAILURE_PATTERN] = 3.0
        weights[KnowledgeType.WORKFLOW_PATTERN] = 3.0
        weights[KnowledgeType.DECISION_LINEAGE] = 4.0
    elif profile == RetrievalProfile.FAILURE_ANALYSIS:
        weights[KnowledgeType.FAILURE_PATTERN] = 5.0
        weights[KnowledgeType.LESSON] = 4.0
    elif profile == RetrievalProfile.ARCHITECTURE_REVIEW:
        weights[KnowledgeType.ARCHITECTURE_PRINCIPLE] = 5.0
        weights[KnowledgeType.PROJECT_INVARIANT] = 5.0
        weights[KnowledgeType.DECISION_LINEAGE] = 4.0
    elif profile == RetrievalProfile.DECISION_LOOKUP:
        weights[KnowledgeType.DECISION_LINEAGE] = 5.0
        weights[KnowledgeType.ARCHITECTURE_PRINCIPLE] = 3.0

    return MappingProxyType(weights)


def execute_retrieval_plan(
    intent: QueryIntent,
    candidates: list[MemoryRecord],
) -> tuple[list[tuple[MemoryRecord, float]], RetrievalExecution]:
    """
    Applies profile-specific weighting to candidate memory scores and outputs
    the final ranked candidates list alongside execution metadata.
    """
    start_time = time.perf_counter()
    weights = get_profile_weights(intent.profile)
    
    scored_candidates = []
    from rationalevault.memory.ranking import compute_retrieval_score
    for c in candidates:
        score = compute_retrieval_score(c)
        booster = weights.get(c.memory_type, 1.0)
        final_score = score.total * booster
        scored_candidates.append((c, final_score))
        
    scored_candidates.sort(key=lambda x: x[1], reverse=True)
    
    execution_ms = (time.perf_counter() - start_time) * 1000.0
    
    execution = RetrievalExecution(
        profile=intent.profile,
        planner_sources=list(set([c.source_type for c, _ in scored_candidates])),
        candidate_count=len(candidates),
        retrieved_count=len(scored_candidates),
        execution_ms=execution_ms
    )
    
    return scored_candidates, execution
