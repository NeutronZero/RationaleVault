"""
Dedicated Jaccard Caching metrics measurement script.
"""
from __future__ import annotations

import time
import os
from rationalevault.organization.models import OrganizationState, KnowledgeLineage
from rationalevault.organization.graph import OrganizationGraphProjection

def measure_cache_metrics():
    # Setup state with overlapping clusters to trigger similarity loops
    # 20 projects, grouped in clusters of 5 to trigger high cluster comparisons
    project_ids = [f"proj-{i}" for i in range(20)]
    
    active_lineages = {}
    for i in range(20):
        active_lineages[f"k-{i}"] = KnowledgeLineage(
            knowledge_id=f"k-{i}",
            origin_project=f"proj-{i % 5}",
            current_projects=[f"proj-{i}"],
            transfer_path=[f"proj-{i % 5}", f"proj-{i}"],
            depth=1,
        )

    # 4 clusters with overlap to simulate a realistic scenario
    project_clusters = [
        ["proj-0", "proj-1", "proj-2", "proj-3", "proj-4"],
        ["proj-3", "proj-4", "proj-5", "proj-6", "proj-7"], # overlaps: proj-3, proj-4
        ["proj-6", "proj-7", "proj-8", "proj-9", "proj-10"], # overlaps: proj-6, proj-7
        ["proj-9", "proj-10", "proj-11", "proj-12", "proj-13"], # overlaps: proj-9, proj-10
    ]

    org_state = OrganizationState(
        compiled_at="2026-06-24T12:00:00Z",
        project_ids=project_ids,
        active_lineages=active_lineages,
        project_clusters=project_clusters,
    )

    # Precompute knowledge sets like project() does
    project_knowledge_sets = {}
    for kid, lineage in org_state.active_lineages.items():
        if lineage.origin_project:
            project_knowledge_sets.setdefault(lineage.origin_project, set()).add(kid)
        for pid in lineage.current_projects:
            project_knowledge_sets.setdefault(pid, set()).add(kid)
    project_knowledge_sizes = {pid: len(s) for pid, s in project_knowledge_sets.items()}

    # 1. Measurement BEFORE (Without Cache)
    start_before = time.perf_counter()
    for _ in range(1000):
        for cluster in org_state.project_clusters:
            for i in range(len(cluster)):
                for j in range(i + 1, len(cluster)):
                    a_kids = project_knowledge_sets.get(cluster[i], set())
                    b_kids = project_knowledge_sets.get(cluster[j], set())
                    intersection = len(a_kids & b_kids)
                    a_size = project_knowledge_sizes.get(cluster[i], 0)
                    b_size = project_knowledge_sizes.get(cluster[j], 0)
                    union = a_size + b_size - intersection
                    jaccard = intersection / union if union > 0 else 0.0
    end_before = time.perf_counter()
    runtime_before_ms = (end_before - start_before) * 1000.0 / 1000.0 # average per run

    # 2. Measurement AFTER (With Cache)
    start_after = time.perf_counter()
    hits = 0
    misses = 0
    
    for _ in range(1000):
        cache = {}
        for cluster in org_state.project_clusters:
            for i in range(len(cluster)):
                for j in range(i + 1, len(cluster)):
                    pair = frozenset((cluster[i], cluster[j]))
                    if pair in cache:
                        hits += 1
                        jaccard = cache[pair]
                    else:
                        misses += 1
                        a_kids = project_knowledge_sets.get(cluster[i], set())
                        b_kids = project_knowledge_sets.get(cluster[j], set())
                        intersection = len(a_kids & b_kids)
                        a_size = project_knowledge_sizes.get(cluster[i], 0)
                        b_size = project_knowledge_sizes.get(cluster[j], 0)
                        union = a_size + b_size - intersection
                        jaccard = intersection / union if union > 0 else 0.0
                        cache[pair] = jaccard
    end_after = time.perf_counter()
    runtime_after_ms = (end_after - start_after) * 1000.0 / 1000.0 # average per run

    total_ops = hits + misses
    hit_rate = (hits / total_ops) * 100.0 if total_ops > 0 else 0.0

    print(f"hits: {hits}")
    print(f"misses: {misses}")
    print(f"hit_rate: {hit_rate:.1f}%")
    print()
    print(f"before: {runtime_before_ms:.4f} ms")
    print(f"after: {runtime_after_ms:.4f} ms")

if __name__ == "__main__":
    measure_cache_metrics()
