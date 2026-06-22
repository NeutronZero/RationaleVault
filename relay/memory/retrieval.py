from __future__ import annotations

from typing import Any
from relay.memory.factory import get_memory_provider
from relay.memory.models import MemoryRecord
from relay.memory.ranking import RetrievalScore
from relay.memory.query_analyzer import analyze_query
from relay.memory.retrieval_planner import execute_retrieval_plan, RetrievalExecution
from relay.memory.semantic_search import search_memories_rrf
from relay.memory.citation_builder import build_citation, MemoryCitation


import time
from relay.memory.timing import RetrievalTiming

def retrieve_ranked_citations(
    query: str,
    limit: int = 5,
    semantic_provider: Any = None
) -> tuple[list[MemoryCitation], RetrievalExecution]:
    """
    Retrieves memory citations matching intent, applying profile weight boosters
    and returning explainable retrieval paths and execution metadata.
    """
    t_start = time.perf_counter()
    retrieval_path = ["query_analyzer", "retrieval_planner"]
    
    # 1. Analyze query intent
    t_analysis_start = time.perf_counter()
    intent = analyze_query(query)
    t_analysis_end = time.perf_counter()
    
    # 2. Fetch all candidates
    provider = get_memory_provider()
    all_records = provider.get_all_records()
    
    # 3. Filter candidates
    t_search_start = time.perf_counter()
    retrieval_path.append("search_memories_rrf")
    candidates = search_memories_rrf(query, all_records, semantic_provider=semantic_provider)
    t_search_end = time.perf_counter()
    
    # 4. Plan and Rank candidates
    t_planning_start = time.perf_counter()
    retrieval_path.append("execute_retrieval_plan")
    scored, execution = execute_retrieval_plan(intent, candidates)
    t_planning_end = time.perf_counter()
    
    # 5. Build citations
    t_citation_start = time.perf_counter()
    retrieval_path.append("citation_builder")
    citations = []
    for r, score in scored[:limit]:
        citation = build_citation(r, query, retrieval_path=list(retrieval_path))
        citations.append(citation)
    t_citation_end = time.perf_counter()
    
    t_end = time.perf_counter()
    
    timing = RetrievalTiming(
        query_analysis_ms=(t_analysis_end - t_analysis_start) * 1000.0,
        planning_ms=(t_planning_end - t_planning_start) * 1000.0,
        search_ms=(t_search_end - t_search_start) * 1000.0,
        ranking_ms=execution.execution_ms,
        citation_ms=(t_citation_end - t_citation_start) * 1000.0,
        total_ms=(t_end - t_start) * 1000.0
    )
    
    execution.timing = timing
    execution.execution_ms = timing.total_ms
    execution.semantic_used = (semantic_provider is not None)
    execution.rrf_used = (semantic_provider is not None)
    execution.vector_candidates = len(candidates) if semantic_provider is not None else 0
    execution.keyword_candidates = len(candidates)
    
    return citations, execution


def retrieve_ranked_memories(query: str, limit: int = 5) -> list[tuple[MemoryRecord, RetrievalScore]]:
    """
    Backward-compatible adapter returning tuples of MemoryRecord and RetrievalScore.
    """
    provider = get_memory_provider()
    records = provider.get_all_records()
    
    citations, _ = retrieve_ranked_citations(query, limit)
    scored_tuples = []
    for c in citations:
        rec = next((r for r in records if r.id == c.memory_id), None)
        if rec:
            scored_tuples.append((rec, c.score))
    return scored_tuples
