from __future__ import annotations

from typing import Any
from rationalevault.memory.models import MemoryRecord


def perform_rrf_blending(
    keyword_results: list[MemoryRecord],
    semantic_results: list[MemoryRecord],
    k: int = 60
) -> list[MemoryRecord]:
    """
    Combines keyword search and semantic search results using Reciprocal Rank Fusion (RRF).
    """
    scores = {}
    
    # Process keyword ranks
    for rank, rec in enumerate(keyword_results):
        scores[rec.id] = scores.get(rec.id, 0.0) + (1.0 / (k + rank + 1))
        
    # Process semantic ranks
    for rank, rec in enumerate(semantic_results):
        scores[rec.id] = scores.get(rec.id, 0.0) + (1.0 / (k + rank + 1))
        
    # Gather distinct records and sort by RRF score descending
    all_records = {r.id: r for r in keyword_results + semantic_results}
    sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
    
    return [all_records[rid] for rid in sorted_ids]


def search_memories_rrf(
    query: str,
    all_records: list[MemoryRecord],
    semantic_provider: Any = None
) -> list[MemoryRecord]:
    """
    Performs keyword search using token-based matching, and blends it with optional semantic search.
    """
    if not query:
        return all_records

    # Split query into tokens and filter stopwords
    q_clean = query.lower().strip()
    words = [w.strip("?,.:;\"'()[]{}") for w in q_clean.split()]
    stopwords = {"what", "is", "a", "the", "of", "and", "in", "to", "exist", "are", "about", "for", "with", "on", "exist", "exists", "did", "occur", "why"}
    keywords = [w for w in words if w and w not in stopwords]

    if not keywords:
        keywords = [q_clean]

    keyword_tuples = []
    for r in all_records:
        match_count = 0
        for kw in keywords:
            # check word stems / substring matching
            if (
                kw in r.title.lower() or
                kw in r.content.lower() or
                any(kw in tag.lower() for tag in r.tags) or
                r.memory_type.value.lower() in kw or
                kw in r.memory_type.value.lower()
            ):
                match_count += 1
        if match_count > 0:
            keyword_tuples.append((r, match_count))

    # Sort matched records by keyword match density
    keyword_tuples.sort(key=lambda x: x[1], reverse=True)
    keyword_results = [r for r, _ in keyword_tuples]
            
    if semantic_provider is None:
        return keyword_results
        
    try:
        semantic_results = semantic_provider.search(query, all_records)
        return perform_rrf_blending(keyword_results, semantic_results)
    except Exception:
        return keyword_results

