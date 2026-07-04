"""
Profiling script for cross-project conflict detection.
"""
from __future__ import annotations

import time
import uuid
import json
from rationalevault.knowledge.models import KnowledgeObject, KnowledgeType, KnowledgeDomain, KnowledgeLifecycle, KnowledgeConfidence, ProvenanceChain
from rationalevault.organization.projection import OrganizationProjection

def make_mock_conf():
    return KnowledgeConfidence(
        memory_count=1, source_event_count=1, contradiction_count=0,
        average_memory_confidence=1.0, score=1.0
    )

def make_mock_prov(kid: str):
    return ProvenanceChain(
        knowledge_id=kid, source_memory_ids=["m1"],
        source_event_ids=["e1"], synthesis_event_id="syn-1",
        confidence=make_mock_conf(), evidence_count=1
    )

def generate_knowledge_items(count: int, divergence: bool = False) -> list[KnowledgeObject]:
    items = []
    for i in range(count):
        kid = f"k-{i}"
        content = f"Deterministic standard baseline content for knowledge number {i}."
        if divergence and i % 2 == 0:
            content = f"Diverging content modification to test conflict detection. Index {i} has changed."

        items.append(KnowledgeObject(
            id=kid,
            version=1,
            title=f"Knowledge Object Title {i}",
            content=content,
            knowledge_type=KnowledgeType.PROJECT_INVARIANT,
            knowledge_domain=KnowledgeDomain.ARCHITECTURE,
            confidence=make_mock_conf(),
            importance="high",
            provenance=make_mock_prov(kid),
            supporting_memory_ids=[],
            lifecycle_status=KnowledgeLifecycle.ACTIVE.value,
            project_id="",
        ))
    return items

def run_profile():
    # Setup data: 5 projects, 100 knowledge objects each
    num_projects = 5
    items_per_project = 100
    
    knowledge_by_project = {}
    for p in range(num_projects):
        pid = f"proj-{p}"
        # Inject diverging contents in some projects to ensure similarity checks execute lexical comparison
        knowledge_by_project[pid] = generate_knowledge_items(items_per_project, divergence=(p % 2 == 0))

    print(f"Profiling _detect_cross_project_conflicts with {num_projects} projects, {items_per_project} items per project.")
    
    start_time = time.perf_counter()
    conflicts = OrganizationProjection._detect_cross_project_conflicts(knowledge_by_project)
    end_time = time.perf_counter()
    
    duration_ms = (end_time - start_time) * 1000.0
    print(f"Profiling results:")
    print(f"  Projects count:  {num_projects}")
    print(f"  Items per proj:  {items_per_project}")
    print(f"  Conflicts found: {len(conflicts)}")
    print(f"  Duration:        {duration_ms:.4f} ms")
    
    # Save statistics report
    report = {
        "projects_count": num_projects,
        "items_per_project": items_per_project,
        "conflicts_found": len(conflicts),
        "duration_ms": duration_ms,
    }
    with open("scripts/profile_cross_project_results.json", "w") as f:
        json.dump(report, f, indent=2)

if __name__ == "__main__":
    run_profile()
