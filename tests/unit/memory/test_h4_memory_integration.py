"""
H4 — Memory Integration Tests.

MemoryQuery, MemoryResult, MemoryContext, MemoryWriteRequest, MemoryWriteResult, MemoryBroker.
"""
from __future__ import annotations

import pytest
from typing import Any

from rationalevault.memory.integration_models import (
    MemoryContext,
    MemoryQuery,
    MemoryQueryType,
    MemoryRecordType,
    MemoryLifecycleState,
    MemoryResult,
    MemoryWriteRequest,
    MemoryWriteResult,
)
from rationalevault.memory.memory_broker import MemoryBroker, _map_memory_type, _RUNTIME_TO_MEMORY_TYPE


# ── Helpers ───────────────────────────────────────────────────────────────

def _make_query(
    text: str = "How did we handle the cache invalidation?",
    query_type: MemoryQueryType = MemoryQueryType.SEARCH,
    project_id: str | None = "proj-1",
) -> MemoryQuery:
    query_id = MemoryQuery.generate_query_id(query_type.value, text, project_id)
    return MemoryQuery(
        query_id=query_id,
        query_type=query_type,
        text=text,
        project_id=project_id,
    )


def _make_result(
    memory_id: str = "MEM-TEST",
    title: str = "Cache Invalidation Pattern",
    score: float = 8.5,
) -> MemoryResult:
    result_id = MemoryResult.generate_result_id(memory_id, "MQRY-TEST")
    return MemoryResult(
        result_id=result_id,
        memory_id=memory_id,
        memory_type=MemoryRecordType.ARCHITECTURE,
        title=title,
        content="We used event-driven cache invalidation...",
        score=score,
        lifecycle_state=MemoryLifecycleState.ACTIVE,
        confidence=0.9,
        reference_count=5,
        reasons=["keyword_match_title", "high_confidence"],
        retrieval_path=["BM25", "SignalFusion"],
    )


def _make_write_request() -> MemoryWriteRequest:
    request_id = MemoryWriteRequest.generate_request_id(
        "New Pattern", "Use event sourcing for cache", "proj-1",
    )
    return MemoryWriteRequest(
        request_id=request_id,
        memory_type=MemoryRecordType.ARCHITECTURE,
        title="New Pattern",
        content="Use event sourcing for cache",
        project_id="proj-1",
        importance="high",
    )


# ── MemoryQuery ───────────────────────────────────────────────────────────

class TestMemoryQuery:
    def test_frozen(self):
        q = _make_query()
        with pytest.raises(AttributeError):
            q.text = "hacked"

    def test_to_dict(self):
        q = _make_query()
        d = q.to_dict()
        assert d["query_type"] == "SEARCH"
        assert d["text"] == "How did we handle the cache invalidation?"
        assert d["project_id"] == "proj-1"

    def test_generate_id_deterministic(self):
        id1 = MemoryQuery.generate_query_id("SEARCH", "test query", "proj-1")
        id2 = MemoryQuery.generate_query_id("SEARCH", "test query", "proj-1")
        assert id1 == id2
        assert id1.startswith("MQRY-")

    def test_different_queries_different_ids(self):
        id1 = MemoryQuery.generate_query_id("SEARCH", "query A", "proj-1")
        id2 = MemoryQuery.generate_query_id("SEARCH", "query B", "proj-1")
        assert id1 != id2

    def test_with_type_filter(self):
        q = MemoryQuery(
            query_id="MQRY-1",
            query_type=MemoryQueryType.SEARCH,
            text="test",
            memory_types=frozenset({MemoryRecordType.DECISION, MemoryRecordType.LESSON_LEARNED}),
        )
        d = q.to_dict()
        assert "DECISION" in d["memory_types"]
        assert "LESSON_LEARNED" in d["memory_types"]

    def test_with_lifecycle_filter(self):
        q = MemoryQuery(
            query_id="MQRY-1",
            query_type=MemoryQueryType.SEARCH,
            text="test",
            lifecycle_states=frozenset({MemoryLifecycleState.ACTIVE}),
        )
        d = q.to_dict()
        assert "ACTIVE" in d["lifecycle_states"]


# ── MemoryResult ──────────────────────────────────────────────────────────

class TestMemoryResult:
    def test_frozen(self):
        r = _make_result()
        with pytest.raises(AttributeError):
            r.score = 0.0

    def test_to_dict(self):
        r = _make_result()
        d = r.to_dict()
        assert d["memory_type"] == "ARCHITECTURE"
        assert d["score"] == 8.5
        assert "keyword_match_title" in d["reasons"]

    def test_generate_id_deterministic(self):
        id1 = MemoryResult.generate_result_id("MEM-1", "MQRY-1")
        id2 = MemoryResult.generate_result_id("MEM-1", "MQRY-1")
        assert id1 == id2
        assert id1.startswith("MRES-")

    def test_different_results_different_ids(self):
        id1 = MemoryResult.generate_result_id("MEM-1", "MQRY-1")
        id2 = MemoryResult.generate_result_id("MEM-2", "MQRY-1")
        assert id1 != id2

    def test_provenance_fields(self):
        r = MemoryResult(
            result_id="MRES-1",
            memory_id="MEM-1",
            memory_type=MemoryRecordType.DECISION,
            title="Test",
            content="Test content",
            score=5.0,
            lifecycle_state=MemoryLifecycleState.ACTIVE,
            source_event_ids=["EVT-1", "EVT-2"],
            source_memory_ids=["MEM-0"],
        )
        d = r.to_dict()
        assert d["source_event_ids"] == ["EVT-1", "EVT-2"]
        assert d["source_memory_ids"] == ["MEM-0"]


# ── MemoryContext ─────────────────────────────────────────────────────────

class TestMemoryContext:
    def test_frozen(self):
        c = MemoryContext(context_id="MCTX-1", query_id="MQRY-1")
        with pytest.raises(AttributeError):
            c.query_id = "hacked"

    def test_to_dict_empty(self):
        c = MemoryContext(context_id="MCTX-1", query_id="MQRY-1")
        d = c.to_dict()
        assert d["results"] == []
        assert d["total_candidates"] == 0

    def test_to_dict_with_results(self):
        results = [_make_result("MEM-1", "R1", 9.0), _make_result("MEM-2", "R2", 7.0)]
        c = MemoryContext(
            context_id="MCTX-1",
            query_id="MQRY-1",
            results=results,
            total_candidates=50,
            retrieval_time_ms=12.3,
        )
        d = c.to_dict()
        assert len(d["results"]) == 2
        assert d["total_candidates"] == 50

    def test_result_count(self):
        c = MemoryContext(
            context_id="MCTX-1",
            query_id="MQRY-1",
            results=[_make_result(), _make_result("MEM-2", "R2")],
        )
        assert c.result_count() == 2

    def test_top_result(self):
        r1 = _make_result("MEM-1", "R1", 9.0)
        r2 = _make_result("MEM-2", "R2", 7.0)
        c = MemoryContext(context_id="MCTX-1", query_id="MQRY-1", results=[r1, r2])
        assert c.top_result() is r1

    def test_top_result_empty(self):
        c = MemoryContext(context_id="MCTX-1", query_id="MQRY-1")
        assert c.top_result() is None

    def test_results_by_type(self):
        r1 = _make_result("MEM-1", "R1")
        r2 = MemoryResult(
            result_id="MRES-2", memory_id="MEM-2", memory_type=MemoryRecordType.DECISION,
            title="D", content="C", score=5.0, lifecycle_state=MemoryLifecycleState.ACTIVE,
        )
        c = MemoryContext(context_id="MCTX-1", query_id="MQRY-1", results=[r1, r2])
        grouped = c.results_by_type()
        assert MemoryRecordType.ARCHITECTURE in grouped
        assert MemoryRecordType.DECISION in grouped
        assert len(grouped[MemoryRecordType.ARCHITECTURE]) == 1

    def test_generate_id_deterministic(self):
        id1 = MemoryContext.generate_context_id("MQRY-1")
        id2 = MemoryContext.generate_context_id("MQRY-1")
        assert id1 == id2
        assert id1.startswith("MCTX-")


# ── MemoryWriteRequest ────────────────────────────────────────────────────

class TestMemoryWriteRequest:
    def test_frozen(self):
        r = _make_write_request()
        with pytest.raises(AttributeError):
            r.title = "hacked"

    def test_to_dict(self):
        r = _make_write_request()
        d = r.to_dict()
        assert d["memory_type"] == "ARCHITECTURE"
        assert d["title"] == "New Pattern"
        assert d["importance"] == "high"

    def test_generate_id_deterministic(self):
        id1 = MemoryWriteRequest.generate_request_id("T", "C", "p1")
        id2 = MemoryWriteRequest.generate_request_id("T", "C", "p1")
        assert id1 == id2
        assert id1.startswith("MWRT-")


# ── MemoryWriteResult ─────────────────────────────────────────────────────

class TestMemoryWriteResult:
    def test_frozen(self):
        r = MemoryWriteResult(result_id="MWRS-1", request_id="MWRT-1", success=True)
        with pytest.raises(AttributeError):
            r.success = False

    def test_to_dict_success(self):
        r = MemoryWriteResult(
            result_id="MWRS-1", request_id="MWRT-1",
            success=True, memory_id="MEM-NEW",
        )
        d = r.to_dict()
        assert d["success"] is True
        assert d["memory_id"] == "MEM-NEW"

    def test_to_dict_deduplicated(self):
        r = MemoryWriteResult(
            result_id="MWRS-1", request_id="MWRT-1",
            success=True, memory_id="MEM-EXISTING", deduplicated=True,
        )
        d = r.to_dict()
        assert d["deduplicated"] is True

    def test_to_dict_error(self):
        r = MemoryWriteResult(
            result_id="MWRS-1", request_id="MWRT-1",
            success=False, error="storage unavailable",
        )
        d = r.to_dict()
        assert d["success"] is False
        assert d["error"] == "storage unavailable"


# ── MemoryBroker ──────────────────────────────────────────────────────────

class TestMemoryBroker:
    def test_initial_state(self):
        broker = MemoryBroker()
        assert broker.query_count() == 0
        assert broker.cache_size() == 0

    def test_cache_context(self):
        broker = MemoryBroker()
        ctx = MemoryContext(context_id="MCTX-1", query_id="MQRY-1")
        broker._context_cache["MQRY-1"] = ctx
        assert broker.get_cached_context("MQRY-1") is ctx
        assert broker.get_cached_context("MQRY-2") is None
        assert broker.cache_size() == 1

    def test_type_mapping(self):
        from rationalevault.memory.models import MemoryType
        assert _map_memory_type(MemoryType.DECISION) == MemoryRecordType.DECISION
        assert _map_memory_type(MemoryType.LESSON_LEARNED) == MemoryRecordType.LESSON_LEARNED
        assert _map_memory_type(MemoryType.FAILURE) == MemoryRecordType.FAILURE

    def test_type_mapping_passthrough(self):
        assert _map_memory_type(MemoryRecordType.ARCHITECTURE) == MemoryRecordType.ARCHITECTURE

    def test_type_mapping_unknown(self):
        assert _map_memory_type("unknown") == MemoryRecordType.LESSON_LEARNED

    def test_all_record_types_mapped(self):
        from rationalevault.memory.models import MemoryType
        for rt in MemoryRecordType:
            assert rt in _RUNTIME_TO_MEMORY_TYPE
        for mt in MemoryType:
            assert mt.value in [rt.value for rt in MemoryRecordType]

    def test_query_type_to_profile(self):
        from rationalevault.memory.query_analyzer import RetrievalProfile
        broker = MemoryBroker()
        assert broker._query_type_to_profile(MemoryQueryType.SEARCH) == RetrievalProfile.GENERAL_SEARCH
        assert broker._query_type_to_profile(MemoryQueryType.RETRIEVE) == RetrievalProfile.DECISION_LOOKUP
        assert broker._query_type_to_profile(MemoryQueryType.CONTEXT) == RetrievalProfile.CONTEXT_CONSTRUCTION
        assert broker._query_type_to_profile(MemoryQueryType.LINEAGE) == RetrievalProfile.ARCHITECTURE_REVIEW
