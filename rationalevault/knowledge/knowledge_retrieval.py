"""RationaleVault Knowledge Retrieval — Search and rank knowledge objects.

Mirrors the memory retrieval pipeline:
    analyze_query → get_all_knowledge → search_knowledge_rrf →
    execute_knowledge_plan → build_knowledge_citation

Uses the same patterns: keyword matching, profile-based weighting, explainable citations.
"""
from __future__ import annotations

import time
from typing import Any

from rationalevault.knowledge.factory import get_knowledge_provider
from rationalevault.knowledge.models import KnowledgeObject
from rationalevault.knowledge.knowledge_citation import (
    KnowledgeCitation,
    build_knowledge_citation,
    compute_knowledge_score,
    extract_keywords,
)
from rationalevault.memory.query_analyzer import QueryIntent
from rationalevault.memory.retrieval_planner import get_knowledge_profile_weights
from rationalevault.memory.timing import RetrievalTiming
from rationalevault.retrieval.orchestrator import RetrievalOrchestrator


def search_knowledge_rrf(
    query: str,
    all_knowledge: list[KnowledgeObject],
) -> list[KnowledgeObject]:
    """Performs keyword search on knowledge objects using token-based matching.

    Mirrors search_memories_rrf from rationalevault/memory/semantic_search.py.
    """
    if not query:
        return all_knowledge

    keywords = extract_keywords(query)
    if not keywords:
        keywords = [query.lower().strip()]

    scored: list[tuple[KnowledgeObject, int]] = []
    for k in all_knowledge:
        title_lower = k.title.lower()
        content_lower = k.content.lower()
        tags_lower = tuple(tag.lower() for tag in k.tags)
        type_lower = k.knowledge_type.value.lower()
        domain_lower = k.knowledge_domain.value.lower()
        match_count = 0
        for kw in keywords:
            if (
                kw in title_lower
                or kw in content_lower
                or any(kw in tag for tag in tags_lower)
                or kw in type_lower
                or kw in domain_lower
            ):
                match_count += 1
        if match_count > 0:
            scored.append((k, match_count))

    scored.sort(key=lambda x: x[1], reverse=True)
    return [k for k, _ in scored]


def execute_knowledge_plan(
    intent: QueryIntent,
    candidates: list[KnowledgeObject],
) -> tuple[list[tuple[KnowledgeObject, float]], dict[str, Any]]:
    """Applies profile-specific weighting to candidate knowledge scores.

    Mirrors execute_retrieval_plan from rationalevault/memory/retrieval_planner.py.
    """
    start_time = time.perf_counter()
    weights = get_knowledge_profile_weights(intent.profile)

    scored_candidates: list[tuple[KnowledgeObject, float]] = []
    keywords = intent.keywords

    for c in candidates:
        score = compute_knowledge_score(c, keywords)
        booster = weights.get(c.knowledge_type, 1.0)
        final_score = score.total * booster
        scored_candidates.append((c, final_score))

    scored_candidates.sort(key=lambda x: x[1], reverse=True)

    execution_ms = (time.perf_counter() - start_time) * 1000.0

    execution_meta = {
        "profile": intent.profile.value,
        "candidate_count": len(candidates),
        "retrieved_count": len(scored_candidates),
        "execution_ms": execution_ms,
    }

    return scored_candidates, execution_meta


def retrieve_ranked_knowledge_citations(
    query: str,
    limit: int = 10,
    intent: QueryIntent | None = None,
    include_stale: bool = False,
    project_id: str | None = None,
    transferable_only: bool = False,
) -> tuple[list[KnowledgeCitation], dict[str, Any]]:
    """Full knowledge retrieval pipeline: search -> rank -> cite.

    Mirrors retrieve_ranked_citations from rationalevault/memory/retrieval.py.

    Args:
        query: Search query.
        limit: Max citations to return.
        intent: Optional pre-computed query intent.
        include_stale: If False (default), only ACTIVE knowledge is returned.
        project_id: If provided, only return knowledge belonging to this project
                    (plus transferable knowledge from other projects).
        transferable_only: If True, only return REUSABLE/ORGANIZATIONAL knowledge.
    """
    t_start = time.perf_counter()
    retrieval_path = ["knowledge_query_analyzer", "knowledge_retrieval_planner"]

    t_analysis_start = time.perf_counter()
    if intent is None:
        orch = RetrievalOrchestrator()
        plan = orch.build_plan(query)
        intent = QueryIntent(profile=plan.profile, keywords=[], intent=plan.primary_intent.value)
    t_analysis_end = time.perf_counter()

    provider = get_knowledge_provider()
    if project_id:
        if transferable_only:
            # Only return transferable knowledge (reusable or organizational)
            all_knowledge = provider.get_all_knowledge(transferable_only=True)
            all_knowledge = [
                k for k in all_knowledge
                if k.project_id == project_id or k.transferability in ("REUSABLE", "ORGANIZATIONAL")
            ]
        else:
            # Blend local knowledge and transferable knowledge from other projects
            project_knowledge = provider.get_all_knowledge(project_id=project_id)
            transferable_knowledge = provider.get_all_knowledge(transferable_only=True)
            seen = set()
            all_knowledge = []
            for k in project_knowledge + transferable_knowledge:
                if k.id not in seen:
                    seen.add(k.id)
                    all_knowledge.append(k)
    else:
        all_knowledge = provider.get_all_knowledge(transferable_only=transferable_only)

    # Lifecycle filtering: default to ACTIVE only
    if not include_stale:
        from rationalevault.knowledge.models import KnowledgeLifecycle
        all_knowledge = [
            k for k in all_knowledge
            if k.lifecycle_status == KnowledgeLifecycle.ACTIVE.value
        ]

    t_search_start = time.perf_counter()
    retrieval_path.append("search_knowledge_rrf")
    candidates = search_knowledge_rrf(query, all_knowledge)
    t_search_end = time.perf_counter()

    t_planning_start = time.perf_counter()
    retrieval_path.append("execute_knowledge_plan")
    scored, execution_meta = execute_knowledge_plan(intent, candidates)
    t_planning_end = time.perf_counter()

    t_citation_start = time.perf_counter()
    retrieval_path.append("knowledge_citation_builder")
    citations: list[KnowledgeCitation] = []
    for k, _ in scored[:limit]:
        citation = build_knowledge_citation(k, query, retrieval_path=list(retrieval_path))
        citations.append(citation)
    t_citation_end = time.perf_counter()

    t_end = time.perf_counter()

    timing = RetrievalTiming(
        query_analysis_ms=(t_analysis_end - t_analysis_start) * 1000.0,
        planning_ms=(t_planning_end - t_planning_start) * 1000.0,
        search_ms=(t_search_end - t_search_start) * 1000.0,
        ranking_ms=execution_meta["execution_ms"],
        citation_ms=(t_citation_end - t_citation_start) * 1000.0,
        total_ms=(t_end - t_start) * 1000.0,
    )

    execution_meta["timing"] = timing.to_dict()

    return citations, execution_meta
