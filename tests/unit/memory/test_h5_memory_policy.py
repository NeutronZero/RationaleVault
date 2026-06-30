"""
H5 — Memory Policy Engine Tests.

RetrievalPolicy, CachePolicy, ProvenancePolicy, WritePolicy, DedupPolicy,
MemoryPolicy, MemoryPolicyEngine.
"""
from __future__ import annotations

import time
import pytest
from typing import Any

from rationalevault.memory.integration_models import (
    MemoryLifecycleState,
    MemoryRecordType,
    MemoryResult,
    MemoryWriteRequest,
    MemoryWriteResult,
)
from rationalevault.memory.policy_models import (
    CacheInvalidation,
    CachePolicy,
    DedupPolicy,
    DedupStrategy,
    MemoryPolicy,
    ProvenanceDepth,
    ProvenancePolicy,
    RetrievalPolicy,
    RetrievalStrategy,
    WritePolicy,
    WriteValidation,
)
from rationalevault.memory.policy_engine import MemoryPolicyEngine


# ── Helpers ───────────────────────────────────────────────────────────────

def _make_result(
    memory_id: str = "MEM-1",
    title: str = "Test Memory",
    score: float = 5.0,
    memory_type: MemoryRecordType = MemoryRecordType.LESSON_LEARNED,
    lifecycle_state: str = "active",
) -> MemoryResult:
    state_map = {
        "active": MemoryLifecycleState.ACTIVE,
        "superceded": MemoryLifecycleState.SUPERSEDED,
        "archived": MemoryLifecycleState.ARCHIVED,
    }
    return MemoryResult(
        result_id=f"MRES-{memory_id}",
        memory_id=memory_id,
        memory_type=memory_type,
        title=title,
        content="Test content",
        score=score,
        lifecycle_state=state_map.get(lifecycle_state, MemoryLifecycleState.ACTIVE),
        source_event_ids=["EVT-1"],
        confidence=0.8,
        reference_count=3,
    )


def _make_write_request(
    title: str = "New Pattern",
    content: str = "Use event sourcing",
    importance: str = "medium",
    project_id: str | None = "proj-1",
    memory_type: MemoryRecordType = MemoryRecordType.ARCHITECTURE,
) -> MemoryWriteRequest:
    return MemoryWriteRequest(
        request_id=MemoryWriteRequest.generate_request_id(title, content, project_id),
        memory_type=memory_type,
        title=title,
        content=content,
        project_id=project_id,
        importance=importance,
    )


# ── RetrievalPolicy ───────────────────────────────────────────────────────

class TestRetrievalPolicy:
    def test_frozen(self):
        p = RetrievalPolicy(policy_id="MPOL-RET-1")
        with pytest.raises(AttributeError):
            p.strategy = RetrievalStrategy.LEXICAL

    def test_to_dict(self):
        p = RetrievalPolicy(policy_id="MPOL-RET-1")
        d = p.to_dict()
        assert d["strategy"] == "HYBRID"
        assert d["max_results"] == 10
        assert "DECISION" in d["type_weights"]

    def test_generate_id_deterministic(self):
        id1 = RetrievalPolicy.generate_policy_id("default")
        id2 = RetrievalPolicy.generate_policy_id("default")
        assert id1 == id2
        assert id1.startswith("MPOL-RET-")

    def test_custom_type_weights(self):
        p = RetrievalPolicy(
            policy_id="MPOL-RET-1",
            type_weights={"CUSTOM": 3.0},
        )
        assert p.type_weights["CUSTOM"] == 3.0


# ── CachePolicy ───────────────────────────────────────────────────────────

class TestCachePolicy:
    def test_frozen(self):
        p = CachePolicy(policy_id="MPOL-CAC-1")
        with pytest.raises(AttributeError):
            p.enabled = False

    def test_to_dict(self):
        p = CachePolicy(policy_id="MPOL-CAC-1")
        d = p.to_dict()
        assert d["enabled"] is True
        assert d["invalidation"] == "TTL"
        assert d["ttl_seconds"] == 300

    def test_generate_id_deterministic(self):
        id1 = CachePolicy.generate_policy_id("default")
        id2 = CachePolicy.generate_policy_id("default")
        assert id1 == id2
        assert id1.startswith("MPOL-CAC-")


# ── ProvenancePolicy ──────────────────────────────────────────────────────

class TestProvenancePolicy:
    def test_frozen(self):
        p = ProvenancePolicy(policy_id="MPOL-PRV-1")
        with pytest.raises(AttributeError):
            p.depth = ProvenanceDepth.NONE

    def test_to_dict(self):
        p = ProvenancePolicy(policy_id="MPOL-PRV-1")
        d = p.to_dict()
        assert d["depth"] == "FULL"
        assert d["require_source_events"] is True

    def test_generate_id_deterministic(self):
        id1 = ProvenancePolicy.generate_policy_id("default")
        id2 = ProvenancePolicy.generate_policy_id("default")
        assert id1 == id2
        assert id1.startswith("MPOL-PRV-")


# ── WritePolicy ───────────────────────────────────────────────────────────

class TestWritePolicy:
    def test_frozen(self):
        p = WritePolicy(policy_id="MPOL-WRT-1")
        with pytest.raises(AttributeError):
            p.validation = WriteValidation.NONE

    def test_to_dict(self):
        p = WritePolicy(policy_id="MPOL-WRT-1")
        d = p.to_dict()
        assert d["validation"] == "FULL"
        assert d["min_importance"] == "low"

    def test_generate_id_deterministic(self):
        id1 = WritePolicy.generate_policy_id("default")
        id2 = WritePolicy.generate_policy_id("default")
        assert id1 == id2
        assert id1.startswith("MPOL-WRT-")


# ── DedupPolicy ───────────────────────────────────────────────────────────

class TestDedupPolicy:
    def test_frozen(self):
        p = DedupPolicy(policy_id="MPOL-DUP-1")
        with pytest.raises(AttributeError):
            p.strategy = DedupStrategy.NONE

    def test_to_dict(self):
        p = DedupPolicy(policy_id="MPOL-DUP-1")
        d = p.to_dict()
        assert d["strategy"] == "EXACT"
        assert d["similarity_threshold"] == 0.35

    def test_generate_id_deterministic(self):
        id1 = DedupPolicy.generate_policy_id("default")
        id2 = DedupPolicy.generate_policy_id("default")
        assert id1 == id2
        assert id1.startswith("MPOL-DUP-")


# ── MemoryPolicy (Composite) ──────────────────────────────────────────────

class TestMemoryPolicy:
    def test_frozen(self):
        p = MemoryPolicy(policy_id="MPOL-1", name="test")
        with pytest.raises(AttributeError):
            p.name = "hacked"

    def test_to_dict(self):
        p = MemoryPolicy(policy_id="MPOL-1", name="test")
        d = p.to_dict()
        assert d["name"] == "test"
        assert "retrieval" in d
        assert "cache" in d
        assert "provenance" in d
        assert "write" in d
        assert "dedup" in d

    def test_default_policy(self):
        p = MemoryPolicy.default()
        assert p.name == "default"
        assert p.retrieval.strategy == RetrievalStrategy.HYBRID
        assert p.cache.enabled is True
        assert p.provenance.depth == ProvenanceDepth.FULL
        assert p.write.validation == WriteValidation.FULL
        assert p.dedup.strategy == DedupStrategy.EXACT

    def test_aggressive_policy(self):
        p = MemoryPolicy.aggressive()
        assert p.name == "aggressive"
        assert p.retrieval.max_results == 20
        assert p.cache.ttl_seconds == 600
        assert p.dedup.strategy == DedupStrategy.SIMILARITY

    def test_strict_policy(self):
        p = MemoryPolicy.strict()
        assert p.name == "strict"
        assert p.provenance.depth == ProvenanceDepth.COMPLETE
        assert p.write.require_project_id is True
        assert p.write.require_tags is True
        assert p.dedup.similarity_threshold == 0.25

    def test_generate_id_deterministic(self):
        id1 = MemoryPolicy.generate_policy_id("test")
        id2 = MemoryPolicy.generate_policy_id("test")
        assert id1 == id2
        assert id1.startswith("MPOL-")


# ── MemoryPolicyEngine ────────────────────────────────────────────────────

class TestMemoryPolicyEngine:
    def test_default_engine(self):
        engine = MemoryPolicyEngine()
        assert engine.policy.name == "default"

    def test_validate_write_valid(self):
        engine = MemoryPolicyEngine()
        request = _make_write_request()
        result = engine.validate_write(request)
        assert result is None  # Valid

    def test_validate_write_empty_title(self):
        engine = MemoryPolicyEngine()
        request = _make_write_request(title="")
        result = engine.validate_write(request)
        assert result is not None
        assert result.success is False
        assert "Title" in result.error

    def test_validate_write_empty_content(self):
        engine = MemoryPolicyEngine()
        request = _make_write_request(content="")
        result = engine.validate_write(request)
        assert result is not None
        assert result.success is False
        assert "Content" in result.error

    def test_validate_write_content_too_long(self):
        engine = MemoryPolicyEngine()
        request = _make_write_request(content="x" * 10001)
        result = engine.validate_write(request)
        assert result is not None
        assert "max length" in result.error

    def test_validate_write_importance_too_low(self):
        engine = MemoryPolicyEngine(policy=MemoryPolicy(
            policy_id="MPOL-1",
            name="strict",
            write=WritePolicy(
                policy_id="MPOL-WRT-1",
                validation=WriteValidation.IMPORTANCE,
                min_importance="high",
            ),
        ))
        request = _make_write_request(importance="low")
        result = engine.validate_write(request)
        assert result is not None
        assert "below minimum" in result.error

    def test_validate_write_no_project_id(self):
        engine = MemoryPolicyEngine(policy=MemoryPolicy(
            policy_id="MPOL-1",
            name="strict",
            write=WritePolicy(
                policy_id="MPOL-WRT-1",
                validation=WriteValidation.FULL,
                require_project_id=True,
            ),
        ))
        request = _make_write_request(project_id=None)
        result = engine.validate_write(request)
        assert result is not None
        assert "project_id" in result.error

    def test_validate_write_no_tags(self):
        engine = MemoryPolicyEngine(policy=MemoryPolicy(
            policy_id="MPOL-1",
            name="strict",
            write=WritePolicy(
                policy_id="MPOL-WRT-1",
                validation=WriteValidation.FULL,
                require_tags=True,
            ),
        ))
        request = _make_write_request()
        result = engine.validate_write(request)
        assert result is not None
        assert "tag" in result.error

    def test_validate_write_disabled(self):
        engine = MemoryPolicyEngine(policy=MemoryPolicy(
            policy_id="MPOL-1",
            name="no-validate",
            write=WritePolicy(
                policy_id="MPOL-WRT-1",
                validation=WriteValidation.NONE,
            ),
        ))
        request = _make_write_request(title="", content="")
        result = engine.validate_write(request)
        assert result is None  # No validation

    def test_dedup_exact_match(self):
        engine = MemoryPolicyEngine()
        request = _make_write_request(title="Test", content="Content")
        # Create a mock existing record with same ID
        from rationalevault.memory.models import MemoryRecord, MemoryType
        from rationalevault.memory.policy_engine import _generate_memory_id
        existing_id = _generate_memory_id("ARCHITECTURE", "Test", "Content")
        existing = MemoryRecord(
            id=existing_id,
            memory_type=MemoryType.ARCHITECTURE,
            title="Test",
            content="Content",
            version=1,
            importance="medium",
            lifecycle_status="active",
            source_event_ids=[],
            source_type="test",
        )
        is_dup, dup_id = engine.check_dedup(request, [existing])
        assert is_dup is True
        assert dup_id == existing.id

    def test_dedup_exact_no_match(self):
        engine = MemoryPolicyEngine()
        request = _make_write_request(title="New", content="Different content")
        from rationalevault.memory.models import MemoryRecord, MemoryType
        from rationalevault.memory.policy_engine import _generate_memory_id
        existing_id = _generate_memory_id("ARCHITECTURE", "Test", "Content")
        existing = MemoryRecord(
            id=existing_id,
            memory_type=MemoryType.ARCHITECTURE,
            title="Test",
            content="Content",
            version=1,
            importance="medium",
            lifecycle_status="active",
            source_event_ids=[],
            source_type="test",
        )
        is_dup, dup_id = engine.check_dedup(request, [existing])
        assert is_dup is False

    def test_dedup_disabled(self):
        engine = MemoryPolicyEngine(policy=MemoryPolicy(
            policy_id="MPOL-1",
            name="no-dedup",
            dedup=DedupPolicy(
                policy_id="MPOL-DUP-1",
                strategy=DedupStrategy.NONE,
            ),
        ))
        request = _make_write_request()
        is_dup, dup_id = engine.check_dedup(request, [])
        assert is_dup is False

    def test_enforce_provenance_none(self):
        engine = MemoryPolicyEngine(policy=MemoryPolicy(
            policy_id="MPOL-1",
            name="no-provenance",
            provenance=ProvenancePolicy(
                policy_id="MPOL-PRV-1",
                depth=ProvenanceDepth.NONE,
            ),
        ))
        result = _make_result()
        enriched = engine.enforce_provenance(result)
        assert enriched.source_event_ids == []
        assert enriched.source_memory_ids == []

    def test_enforce_provenance_full(self):
        engine = MemoryPolicyEngine()
        result = _make_result()
        enriched = engine.enforce_provenance(result)
        assert enriched.source_event_ids == ["EVT-1"]

    def test_enforce_provenance_insufficient(self):
        engine = MemoryPolicyEngine(policy=MemoryPolicy(
            policy_id="MPOL-1",
            name="strict",
            provenance=ProvenancePolicy(
                policy_id="MPOL-PRV-1",
                depth=ProvenanceDepth.FULL,
                min_chain_length=2,
            ),
        ))
        result = _make_result()
        enriched = engine.enforce_provenance(result)
        assert "insufficient_provenance" in enriched.reasons
        assert enriched.score < result.score

    def test_shape_retrieval(self):
        engine = MemoryPolicyEngine()
        results = [
            _make_result("MEM-1", "R1", score=3.0, memory_type=MemoryRecordType.LESSON_LEARNED),
            _make_result("MEM-2", "R2", score=5.0, memory_type=MemoryRecordType.DECISION),
            _make_result("MEM-3", "R3", score=8.0, memory_type=MemoryRecordType.ARCHITECTURE),
        ]
        shaped = engine.shape_retrieval(results)
        # DECISION type has 2.0 weight, so MEM-2 should rank higher
        assert shaped[0].memory_id == "MEM-2"  # 5.0 * 2.0 = 10.0
        assert shaped[1].memory_id == "MEM-3"  # 8.0 * 1.0 = 8.0

    def test_shape_retrieval_min_score_filter(self):
        engine = MemoryPolicyEngine(policy=MemoryPolicy(
            policy_id="MPOL-1",
            name="high-threshold",
            retrieval=RetrievalPolicy(
                policy_id="MPOL-RET-1",
                min_score=10.0,
            ),
        ))
        results = [_make_result("MEM-1", "R1", score=5.0)]
        shaped = engine.shape_retrieval(results)
        assert len(shaped) == 0  # Filtered out

    def test_shape_retrieval_limit(self):
        engine = MemoryPolicyEngine(policy=MemoryPolicy(
            policy_id="MPOL-1",
            name="limited",
            retrieval=RetrievalPolicy(
                policy_id="MPOL-RET-1",
                max_results=2,
            ),
        ))
        results = [
            _make_result(f"MEM-{i}", f"R{i}", score=float(i))
            for i in range(5)
        ]
        shaped = engine.shape_retrieval(results)
        assert len(shaped) == 2

    def test_should_cache(self):
        engine = MemoryPolicyEngine()
        assert engine.should_cache() is True

    def test_should_cache_disabled(self):
        engine = MemoryPolicyEngine(policy=MemoryPolicy(
            policy_id="MPOL-1",
            name="no-cache",
            cache=CachePolicy(policy_id="MPOL-CAC-1", enabled=False),
        ))
        assert engine.should_cache() is False

    def test_cache_key(self):
        engine = MemoryPolicyEngine()
        from rationalevault.memory.integration_models import MemoryQuery, MemoryQueryType
        query = MemoryQuery(
            query_id="MQRY-1",
            query_type=MemoryQueryType.SEARCH,
            text="test query",
            project_id="proj-1",
        )
        key = engine.cache_key(query)
        assert "SEARCH" in key
        assert "test query" in key
        assert "proj-1" in key

    def test_is_cache_valid_ttl(self):
        engine = MemoryPolicyEngine()
        now = time.time()
        assert engine.is_cache_valid(now - 100, now) is True  # 100s < 300s TTL
        assert engine.is_cache_valid(now - 400, now) is False  # 400s > 300s TTL

    def test_is_cache_valid_disabled(self):
        engine = MemoryPolicyEngine(policy=MemoryPolicy(
            policy_id="MPOL-1",
            name="no-cache",
            cache=CachePolicy(policy_id="MPOL-CAC-1", enabled=False),
        ))
        assert engine.is_cache_valid(time.time() - 1, time.time()) is False

    def test_engine_with_aggressive_policy(self):
        engine = MemoryPolicyEngine(policy=MemoryPolicy.aggressive())
        assert engine.policy.retrieval.max_results == 20
        request = _make_write_request(title="", content="")
        result = engine.validate_write(request)
        assert result is not None  # Still validates schema

    def test_engine_with_strict_policy(self):
        engine = MemoryPolicyEngine(policy=MemoryPolicy.strict())
        request = _make_write_request(project_id=None)
        result = engine.validate_write(request)
        assert result is not None
        assert "project_id" in result.error
