from __future__ import annotations
import pytest
from datetime import datetime, timezone
from typing import ClassVar
from rationalevault.projections.base import BaseProjection, ProjectionKind, SemVer
from rationalevault.projections.cache import CacheKey, CacheEntry, ProjectionCache
from rationalevault.projections.fingerprint import (
    compute_event_stream_fingerprint,
    compute_knowledge_fingerprint,
    compute_composite_fingerprint,
)
from rationalevault.projections.planner import RebuildMetrics, RebuildPlan, RebuildPlanner
from rationalevault.projections.registry import ProjectionRegistry
from rationalevault.schema.events import EventRecord, EventType
from rationalevault.knowledge.models import KnowledgeObject, KnowledgeConfidence, ProvenanceChain

def test_fingerprint_stability():
    import uuid
    from rationalevault.schema.events import EventMetadata
    meta = EventMetadata(actor="test", source="test")
    p_id = uuid.uuid4()
    
    ev1 = EventRecord(
        event_sequence=1,
        id=uuid.uuid4(),
        project_id=p_id,
        stream_id="main",
        version=1,
        event_type=EventType.PROJECT_CREATED,
        metadata=meta,
        payload={},
        parent_id=None,
        recorded_at=datetime.now()
    )
    ev2 = EventRecord(
        event_sequence=2,
        id=uuid.uuid4(),
        project_id=p_id,
        stream_id="main",
        version=2,
        event_type=EventType.PROJECT_GOAL_SET,
        metadata=meta,
        payload={},
        parent_id=None,
        recorded_at=datetime.now()
    )

    events = [ev1, ev2]

    fp1 = compute_event_stream_fingerprint(events, "proj_123", SemVer(1, 0, 0))
    fp2 = compute_event_stream_fingerprint(events, "proj_123", SemVer(1, 0, 0))
    assert fp1 == fp2

    # Ordering stability
    k_conf = KnowledgeConfidence(1, 1, 0, 1.0)
    prov = ProvenanceChain(
        knowledge_id="k1",
        source_memory_ids=[],
        source_event_ids=[],
        synthesis_event_id="se1",
        confidence=k_conf,
        evidence_count=1
    )

    from rationalevault.knowledge.models import KnowledgeType, KnowledgeDomain
    k1 = KnowledgeObject(
        id="k1",
        version=1,
        title="K1",
        content="content",
        knowledge_type=KnowledgeType.PROJECT_INVARIANT,
        knowledge_domain=KnowledgeDomain.ARCHITECTURE,
        confidence=k_conf,
        importance="critical",
        provenance=prov,
        project_id="proj_123"
    )
    k2 = KnowledgeObject(
        id="k2",
        version=2,
        title="K2",
        content="content",
        knowledge_type=KnowledgeType.PROJECT_INVARIANT,
        knowledge_domain=KnowledgeDomain.ARCHITECTURE,
        confidence=k_conf,
        importance="critical",
        provenance=prov,
        project_id="proj_123"
    )

    
    fp_k1 = compute_knowledge_fingerprint([k1, k2], "proj_123", SemVer(1, 0, 0))
    fp_k2 = compute_knowledge_fingerprint([k2, k1], "proj_123", SemVer(1, 0, 0))
    assert fp_k1 == fp_k2

def test_rebuild_planner_cache_hit_and_miss():
    class ProjA(BaseProjection):
        projection_name: ClassVar[str] = "ProjA"
        version: ClassVar[SemVer] = SemVer(1, 0, 0)
        projection_kind: ClassVar[ProjectionKind] = ProjectionKind.BASE
        dependencies: ClassVar[list[type[BaseProjection]]] = []

    class ProjB(BaseProjection):
        projection_name: ClassVar[str] = "ProjB"
        version: ClassVar[SemVer] = SemVer(1, 0, 0)
        projection_kind: ClassVar[ProjectionKind] = ProjectionKind.COMPOSITE
        dependencies: ClassVar[list[type[BaseProjection]]] = [ProjA]

    registry = ProjectionRegistry()
    registry.register(ProjA)
    registry.register(ProjB)

    cache = ProjectionCache()
    
    # Run plan with empty cache (Miss)
    current_fps = {
        "ProjA": "hash_a_1",
    }
    
    plan1 = RebuildPlanner.plan("proj_123", current_fps, cache, registry)
    assert plan1.metrics.cache_misses == 2
    assert plan1.metrics.cache_hits == 0
    assert plan1.ordered_nodes == ["ProjA", "ProjB"]
    
    # Store in cache
    now = datetime.now(timezone.utc)
    # ProjA
    fp_a = current_fps["ProjA"]
    cache.set(
        CacheKey("proj_123", "ProjA", ProjA.version),
        CacheEntry(compiled_projection="state_a", fingerprint=fp_a, version=ProjA.version, build_time=now, build_duration_ms=5.0)
    )
    # ProjB
    fp_b = plan1.resolved_fingerprints["ProjB"]
    cache.set(
        CacheKey("proj_123", "ProjB", ProjB.version),
        CacheEntry(compiled_projection="state_b", fingerprint=fp_b, version=ProjB.version, build_time=now, build_duration_ms=10.0)
    )

    # Run plan again (Hit)
    plan2 = RebuildPlanner.plan("proj_123", current_fps, cache, registry)
    assert plan2.metrics.cache_misses == 0
    assert plan2.metrics.cache_hits == 2
    assert plan2.ordered_nodes == []

def test_version_invalidation():
    class ProjA(BaseProjection):
        projection_name: ClassVar[str] = "ProjA"
        version: ClassVar[SemVer] = SemVer(1, 0, 0)
        projection_kind: ClassVar[ProjectionKind] = ProjectionKind.BASE
        dependencies: ClassVar[list[type[BaseProjection]]] = []

    registry = ProjectionRegistry()
    registry.register(ProjA)

    cache = ProjectionCache()
    current_fps = {"ProjA": "hash_a_1"}

    # Store in cache with version 1.0.0
    cache.set(
        CacheKey("proj_123", "ProjA", SemVer(1, 0, 0)),
        CacheEntry("state", "hash_a_1", SemVer(1, 0, 0), datetime.now(timezone.utc), 1.0)
    )

    # Upgrade class version to 1.1.0
    ProjA.version = SemVer(1, 1, 0)

    # Planner should invalid version mismatch and schedule rebuild
    plan = RebuildPlanner.plan("proj_123", current_fps, cache, registry)
    assert "ProjA" in plan.dirty_nodes
    assert any(msg in plan.reasons["ProjA"].lower() for msg in ["version mismatch", "missing cache entry"])
    
    # Restore class version
    ProjA.version = SemVer(1, 0, 0)

def test_dependency_invalidation_and_independent_branches():
    # Tree 1: BaseProj1 -> ChildProj1
    # Tree 2: BaseProj2 -> ChildProj2
    class BaseProj1(BaseProjection):
        projection_name: ClassVar[str] = "BaseProj1"
        version: ClassVar[SemVer] = SemVer(1, 0, 0)
        projection_kind: ClassVar[ProjectionKind] = ProjectionKind.BASE
        dependencies: ClassVar[list[type[BaseProjection]]] = []
        build_priority: ClassVar[int] = 10

    class ChildProj1(BaseProjection):
        projection_name: ClassVar[str] = "ChildProj1"
        version: ClassVar[SemVer] = SemVer(1, 0, 0)
        projection_kind: ClassVar[ProjectionKind] = ProjectionKind.COMPOSITE
        dependencies: ClassVar[list[type[BaseProjection]]] = [BaseProj1]
        build_priority: ClassVar[int] = 20

    class BaseProj2(BaseProjection):
        projection_name: ClassVar[str] = "BaseProj2"
        version: ClassVar[SemVer] = SemVer(1, 0, 0)
        projection_kind: ClassVar[ProjectionKind] = ProjectionKind.BASE
        dependencies: ClassVar[list[type[BaseProjection]]] = []
        build_priority: ClassVar[int] = 10

    class ChildProj2(BaseProjection):
        projection_name: ClassVar[str] = "ChildProj2"
        version: ClassVar[SemVer] = SemVer(1, 0, 0)
        projection_kind: ClassVar[ProjectionKind] = ProjectionKind.COMPOSITE
        dependencies: ClassVar[list[type[BaseProjection]]] = [BaseProj2]
        build_priority: ClassVar[int] = 20

    registry = ProjectionRegistry()
    registry.register(BaseProj1)
    registry.register(ChildProj1)
    registry.register(BaseProj2)
    registry.register(ChildProj2)

    cache = ProjectionCache()
    now = datetime.now(timezone.utc)

    # Populate cache for all nodes
    cache.set(CacheKey("p_123", "BaseProj1", SemVer(1, 0, 0)), CacheEntry("s1", "hash_b1_1", SemVer(1, 0, 0), now, 1.0))
    # We resolve the child fingerprint using dependency fingerprint map
    fp_child1 = compute_composite_fingerprint(SemVer(1, 0, 0), {"BaseProj1": "hash_b1_1"})
    cache.set(CacheKey("p_123", "ChildProj1", SemVer(1, 0, 0)), CacheEntry("c1", fp_child1, SemVer(1, 0, 0), now, 1.0))

    cache.set(CacheKey("p_123", "BaseProj2", SemVer(1, 0, 0)), CacheEntry("s2", "hash_b2_1", SemVer(1, 0, 0), now, 1.0))
    fp_child2 = compute_composite_fingerprint(SemVer(1, 0, 0), {"BaseProj2": "hash_b2_1"})
    cache.set(CacheKey("p_123", "ChildProj2", SemVer(1, 0, 0)), CacheEntry("c2", fp_child2, SemVer(1, 0, 0), now, 1.0))

    # Trigger change in BaseProj1 input only (Tree 2 remains unchanged)
    current_fps = {
        "BaseProj1": "hash_b1_CHANGED",
        "BaseProj2": "hash_b2_1",
    }

    plan = RebuildPlanner.plan("p_123", current_fps, cache, registry)
    
    # Verification:
    # 1. BaseProj1 is dirty because of fingerprint mismatch
    assert "BaseProj1" in plan.dirty_nodes
    # 2. ChildProj1 is dirty because BaseProj1 changed (dependency propagation)
    assert "ChildProj1" in plan.dirty_nodes
    # 3. BaseProj2 and ChildProj2 are unchanged (independent branches)
    assert "BaseProj2" not in plan.dirty_nodes
    assert "ChildProj2" not in plan.dirty_nodes
    
    assert plan.metrics.cache_hits == 2
    assert plan.metrics.cache_misses == 2
    assert plan.ordered_nodes == ["BaseProj1", "ChildProj1"]
