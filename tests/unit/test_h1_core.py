"""Unit tests for H1-Core features."""
from __future__ import annotations

from datetime import datetime, timezone
import pytest
from types import MappingProxyType
from uuid import uuid4
from pathlib import Path
import tempfile
import time
import os

from rationalevault.knowledge.models import (
    KnowledgeObject,
    KnowledgeLifecycle,
    KnowledgeType,
    KnowledgeConfidence,
    ProvenanceChain,
    KnowledgeDomain,
)
from rationalevault.memory.models import MemoryType, MemoryRecord
from rationalevault.projections.continuation import ContinuationProjection
from rationalevault.projections.knowledge import KnowledgeProjection
from rationalevault.projections.cross_project import CrossProjectProjection
from rationalevault.projections.graph import GraphProjection
from rationalevault.organization.projection import OrganizationProjection
from rationalevault.retrieval.models import (
    INTENT_PROJECTION_MAP,
    INTENT_WEIGHT_MAP,
    INTENT_KEYWORDS,
)
from rationalevault.memory.retrieval_planner import get_profile_weights, get_knowledge_profile_weights
from rationalevault.memory.query_analyzer import RetrievalProfile
from rationalevault.knowledge.project_registry import ProjectRegistry


def _conf(
    score: float = 0.8,
    memory_count: int = 3,
    contradiction_count: int = 0,
) -> KnowledgeConfidence:
    return KnowledgeConfidence(
        memory_count=memory_count,
        source_event_count=memory_count,
        contradiction_count=contradiction_count,
        average_memory_confidence=score,
        score=score,
    )


def _prov(kid: str, memory_ids: list[str] | None = None) -> ProvenanceChain:
    return ProvenanceChain(
        knowledge_id=kid,
        source_memory_ids=memory_ids or [],
        source_event_ids=["100", "101", "102"],
        synthesis_event_id="syn-1",
        confidence=_conf(),
        evidence_count=len(memory_ids or []),
    )


def _k(
    title: str,
    content: str,
    ktype: KnowledgeType = KnowledgeType.ARCHITECTURE_PRINCIPLE,
    lifecycle: str = KnowledgeLifecycle.ACTIVE.value,
    confidence_score: float = 0.8,
    memory_count: int = 3,
    contradicting_memory_ids: list[str] | None = None,
    supporting_memory_ids: list[str] | None = None,
    tags: list[str] | None = None,
    knowledge_id: str | None = None,
) -> KnowledgeObject:
    kid = knowledge_id or f"k-{title.lower().replace(' ', '-')[:20]}"
    return KnowledgeObject(
        id=kid,
        version=1,
        title=title,
        content=content,
        knowledge_type=ktype,
        knowledge_domain=KnowledgeDomain.ARCHITECTURE,
        confidence=_conf(score=confidence_score, memory_count=memory_count,
                         contradiction_count=len(contradicting_memory_ids or [])),
        importance="high",
        provenance=_prov(kid, supporting_memory_ids),
        tags=tags or [],
        supporting_memory_ids=supporting_memory_ids or [],
        contradicting_memory_ids=contradicting_memory_ids or [],
        lifecycle_status=lifecycle,
    )


def test_full_projection_determinism() -> None:
    ref_time = datetime(2026, 6, 24, 12, 0, 0, tzinfo=timezone.utc)
    proj_id = uuid4()
    
    # 1. Knowledge State
    knowledge_objs = [
        _k("First Knowledge", "Content here", ktype=KnowledgeType.ARCHITECTURE_PRINCIPLE, knowledge_id="k1")
    ]
    
    k_state1 = KnowledgeProjection.project(str(proj_id), knowledge=knowledge_objs, reference_time=ref_time)
    k_state2 = KnowledgeProjection.project(str(proj_id), knowledge=knowledge_objs, reference_time=ref_time)
    assert k_state1.to_dict() == k_state2.to_dict()
    assert k_state1.compiled_at == ref_time.isoformat()

    # 2. Graph State
    g_state1 = GraphProjection.project(k_state1, reference_time=ref_time)
    g_state2 = GraphProjection.project(k_state2, reference_time=ref_time)
    assert g_state1.to_dict() == g_state2.to_dict()
    assert g_state1.compiled_at == ref_time.isoformat()

    # 3. Cross Project State
    target_k = {"other_proj": [
        _k("Second Knowledge", "Content here", ktype=KnowledgeType.PROJECT_INVARIANT, knowledge_id="k2")
    ]}
    cp_state1 = CrossProjectProjection.project(str(proj_id), knowledge_objs, target_k, reference_time=ref_time)
    cp_state2 = CrossProjectProjection.project(str(proj_id), knowledge_objs, target_k, reference_time=ref_time)
    assert cp_state1.to_dict() == cp_state2.to_dict()
    assert cp_state1.compiled_at == ref_time.isoformat()

    # 4. Organization State
    class MockRegistry:
        def list_projects(self):
            return []
    
    registry = MockRegistry()
    org_state1 = OrganizationProjection.project(registry, {str(proj_id): cp_state1}, {str(proj_id): knowledge_objs}, reference_time=ref_time)
    org_state2 = OrganizationProjection.project(registry, {str(proj_id): cp_state2}, {str(proj_id): knowledge_objs}, reference_time=ref_time)
    assert org_state1.to_dict() == org_state2.to_dict()
    assert org_state1.compiled_at == ref_time.isoformat()


def test_retrieval_config_immutability() -> None:
    # Verify that retrieval constants are MappingProxyTypes and underlying sets are frozen
    assert isinstance(INTENT_PROJECTION_MAP, MappingProxyType)
    assert isinstance(INTENT_WEIGHT_MAP, MappingProxyType)
    assert isinstance(INTENT_KEYWORDS, MappingProxyType)

    with pytest.raises(TypeError):
        INTENT_PROJECTION_MAP["new_key"] = "value"

    with pytest.raises(TypeError):
        INTENT_KEYWORDS[list(INTENT_KEYWORDS.keys())[0]] = "value"

    # Check frozenset
    assert isinstance(INTENT_PROJECTION_MAP[list(INTENT_PROJECTION_MAP.keys())[0]], frozenset)
    assert isinstance(INTENT_KEYWORDS[list(INTENT_KEYWORDS.keys())[0]], frozenset)

    # Check weight planners returning MappingProxyType
    w1 = get_profile_weights(RetrievalProfile.DECISION_LOOKUP)
    assert isinstance(w1, MappingProxyType)
    with pytest.raises(TypeError):
        w1[MemoryType.DECISION] = 10.0

    w2 = get_knowledge_profile_weights(RetrievalProfile.KNOWLEDGE_REVIEW)
    assert isinstance(w2, MappingProxyType)
    with pytest.raises(TypeError):
        w2[KnowledgeType.PROJECT_INVARIANT] = 10.0


def test_registry_locking(monkeypatch) -> None:
    # Isolate registry file
    with tempfile.TemporaryDirectory() as tmpdir:
        reg_file = Path(tmpdir) / "registry.yaml"
        monkeypatch.setattr("rationalevault.knowledge.project_registry.REGISTRY_FILE", reg_file)
        monkeypatch.setattr("rationalevault.knowledge.project_registry.REGISTRY_DIR", Path(tmpdir))

        registry = ProjectRegistry()
        
        # Test basic save works
        registry.save()
        assert reg_file.exists()

        # Simulate another process holding the lock by making the lock directory
        lock_dir = reg_file.with_suffix(".lockdir")
        os.mkdir(lock_dir)

        # Make the lock timeout pass quickly: patch time.time to advance
        # and time.sleep to be a no-op so the 0.05s delay loop runs instantly
        import time as _time_mod
        _real_time_fn = _time_mod.time
        _elapsed = [0.0]

        def fast_time():
            _elapsed[0] += 0.1
            return _real_time_fn() + _elapsed[0]

        monkeypatch.setattr(_time_mod, "time", fast_time)
        monkeypatch.setattr(_time_mod, "sleep", lambda _: None)

        # registry.save() should fail with TimeoutError since lock is held
        with pytest.raises(TimeoutError, match="Could not acquire write lock"):
            registry.save()

        # Cleanup lock dir
        os.rmdir(lock_dir)
        # Should now succeed
        registry.save()
