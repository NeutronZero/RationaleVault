from __future__ import annotations

from typing import Any
from rationalevault.memory.factory import get_memory_provider
from rationalevault.memory.models import MemoryRecord
from rationalevault.memory.ranking import RetrievalScore
from rationalevault.memory.query_analyzer import QueryIntent
from rationalevault.memory.retrieval_planner import execute_retrieval_plan, RetrievalExecution
from rationalevault.memory.semantic_search import search_memories_rrf
from rationalevault.memory.citation_builder import build_citation, MemoryCitation
from rationalevault.retrieval.orchestrator import RetrievalOrchestrator


import time
from rationalevault.memory.timing import RetrievalTiming

# Candidate generation: how many records to pull from the provider
# before applying multi-keyword filtering and semantic reranking.
CANDIDATE_LIMIT = 200


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
    retrieval_path = ["orchestrator", "retrieval_planner"]

    # 1. Analyze query intent via orchestrator (unified intent classification)
    t_analysis_start = time.perf_counter()
    orch = RetrievalOrchestrator()
    plan = orch.build_plan(query)
    intent = QueryIntent(profile=plan.profile, keywords=[], intent=plan.primary_intent.value)
    t_analysis_end = time.perf_counter()

    # 2. Candidate generation: use provider search instead of loading everything
    provider = get_memory_provider()
    t_provider_start = time.perf_counter()
    candidates = provider.search_records(query, limit=CANDIDATE_LIMIT)
    total_records = provider.count()
    t_provider_end = time.perf_counter()
    # If provider returns too few, fall back to all records
    if len(candidates) < limit:
        candidates = provider.get_all_records()

    # 3. Multi-keyword filtering and optional semantic reranking
    retrieval_path.append("search_memories_rrf")
    t_search_start = time.perf_counter()
    candidates = search_memories_rrf(query, candidates, semantic_provider=semantic_provider)
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
    execution.provider_latency_ms = (t_provider_end - t_provider_start) * 1000.0
    execution.provider_total_records = total_records

    return citations, execution


def retrieve_ranked_memories(query: str, limit: int = 5) -> list[tuple[MemoryRecord, RetrievalScore]]:
    """
    Backward-compatible adapter returning tuples of MemoryRecord and RetrievalScore.
    """
    citations, _ = retrieve_ranked_citations(query, limit)
    if not citations:
        return []

    provider = get_memory_provider()
    record_ids = [c.memory_id for c in citations]
    records = provider.get_by_ids(record_ids)
    record_map = {r.id: r for r in records}

    scored_tuples = []
    for c in citations:
        rec = record_map.get(c.memory_id)
        if rec:
            scored_tuples.append((rec, c.score))
    return scored_tuples
