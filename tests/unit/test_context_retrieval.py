"""Sprint I5: Knowledge Retrieval & Context Construction — Unit Tests."""
from __future__ import annotations

import uuid
from datetime import datetime

import pytest

from relay.memory.models import MemoryRecord, MemoryType
from relay.memory.query_analyzer import analyze_query, RetrievalProfile
from relay.knowledge.models import (
    KnowledgeObject,
    KnowledgeType,
    KnowledgeDomain,
    KnowledgeConfidence,
    ProvenanceChain,
)
from relay.knowledge.context_types import (
    EventContext,
    MemoryContext,
    KnowledgeContext,
    ContextCitation,
)
from relay.knowledge.knowledge_citation import (
    KnowledgeScore,
    KnowledgeCitation,
    build_knowledge_citation,
    compute_knowledge_score,
    extract_keywords,
)
from relay.knowledge.knowledge_retrieval import (
    search_knowledge_rrf,
    execute_knowledge_plan,
    retrieve_ranked_knowledge_citations,
)
from relay.knowledge.context_compiler import (
    ContextPackage,
    compile_context,
    _get_slot_allocation,
    PROFILE_SOURCE_WEIGHTS,
)
from relay.knowledge.evaluation_i5 import (
    ContextMetrics,
    compute_context_metrics,
    MIN_CONTEXT_COMPLETENESS,
    MIN_SOURCE_TRACEABILITY,
    MIN_SOURCE_BALANCE,
    MIN_BLENDING_DETERMINISM,
    MAX_CONTEXT_COMPILE_MS,
    MAX_CONTEXT_REDUNDANCY,
    MIN_CONTEXT_PRECISION,
)


# ── Helpers ────────────────────────────────────────────────────────────────


def _make_knowledge(
    k_id: str,
    title: str,
    content: str,
    knowledge_type: KnowledgeType = KnowledgeType.ARCHITECTURE_PRINCIPLE,
    knowledge_domain: KnowledgeDomain = KnowledgeDomain.ARCHITECTURE,
    importance: str = "medium",
    tags: list[str] | None = None,
) -> KnowledgeObject:
    confidence = KnowledgeConfidence(
        memory_count=2,
        source_event_count=3,
        contradiction_count=0,
        average_memory_confidence=0.9,
    )
    provenance = ProvenanceChain(
        knowledge_id=k_id,
        source_memory_ids=["mem-1", "mem-2"],
        source_event_ids=["evt-1", "evt-2", "evt-3"],
        synthesis_event_id="",
        confidence=confidence,
        evidence_count=2,
    )
    return KnowledgeObject(
        id=k_id,
        version=1,
        title=title,
        content=content,
        knowledge_type=knowledge_type,
        knowledge_domain=knowledge_domain,
        confidence=confidence,
        importance=importance,
        provenance=provenance,
        supporting_memory_ids=["mem-1", "mem-2"],
        tags=tags or [],
    )


# ── Query Analyzer Tests ───────────────────────────────────────────────────


def test_query_analyzer_new_profiles() -> None:
    """New profiles must be detected from query keywords."""
    intent1 = analyze_query("Show me the synthesized knowledge")
    assert intent1.profile == RetrievalProfile.KNOWLEDGE_REVIEW

    intent2 = analyze_query("Give me a project overview")
    assert intent2.profile == RetrievalProfile.PROJECT_OVERVIEW

    intent3 = analyze_query("Construct full context for this query")
    assert intent3.profile == RetrievalProfile.CONTEXT_CONSTRUCTION


def test_query_analyzer_context_construction_priority() -> None:
    """CONTEXT_CONSTRUCTION should take priority over other profiles."""
    intent = analyze_query("construct full knowledge context")
    assert intent.profile == RetrievalProfile.CONTEXT_CONSTRUCTION


def test_query_analyzer_backward_compatibility() -> None:
    """Existing profile detection must still work."""
    intent = analyze_query("What decisions were made about SQLite?")
    assert intent.profile == RetrievalProfile.DECISION_LOOKUP


# ── Knowledge Citation Tests ───────────────────────────────────────────────


def test_knowledge_score_computation() -> None:
    """KnowledgeScore must be deterministic and explainable."""
    k = _make_knowledge("k1", "SQLite First", "Use SQLite for simplicity", importance="critical")
    keywords = ["sqlite"]
    score = compute_knowledge_score(k, keywords)

    assert score.total > 0.0
    assert score.confidence > 0.0
    assert score.importance_bonus == 5.0
    assert score.evidence_strength > 0.0


def test_knowledge_score_determinism() -> None:
    """Same input must produce identical KnowledgeScore (within floating point tolerance)."""
    k = _make_knowledge("k1", "Test", "Content", importance="high")
    s1 = compute_knowledge_score(k, ["test"])
    s2 = compute_knowledge_score(k, ["test"])
    assert abs(s1.total - s2.total) < 0.001


def test_knowledge_citation_build() -> None:
    """KnowledgeCitation must have valid structure and traceability."""
    k = _make_knowledge("k1", "SQLite First", "Use SQLite for storage")
    citation = build_knowledge_citation(k, "sqlite storage", ["test_path"])

    assert citation.knowledge_id == "k1"
    assert len(citation.source_event_ids) > 0
    assert len(citation.source_memory_ids) > 0
    assert len(citation.reasons) > 0
    assert "test_path" in citation.retrieval_path
    assert citation.score.total > 0.0


def test_knowledge_citation_reasons() -> None:
    """Citation reasons must reflect query-match analysis."""
    k = _make_knowledge("k1", "SQLite First", "Use SQLite for storage", importance="critical")
    citation = build_knowledge_citation(k, "sqlite first", ["path1"])

    assert "keyword_match_title" in citation.reasons
    assert "critical_importance" in citation.reasons
    assert "high_confidence" in citation.reasons


def test_extract_keywords() -> None:
    """Keyword extraction must filter stopwords."""
    kw = extract_keywords("What is the architecture decision?")
    assert "what" not in kw
    assert "is" not in kw
    assert "the" not in kw
    assert "architecture" in kw
    assert "decision" in kw


# ── Knowledge Retrieval Tests ──────────────────────────────────────────────


def test_search_knowledge_rrf() -> None:
    """Keyword search must return matching knowledge objects."""
    k1 = _make_knowledge("k1", "SQLite First", "Use SQLite for storage")
    k2 = _make_knowledge("k2", "Postgres Scale", "Use PostgreSQL for scale")
    k3 = _make_knowledge("k3", "Architecture Principles", "Follow clean architecture")

    results = search_knowledge_rrf("SQLite storage", [k1, k2, k3])
    assert len(results) >= 1
    assert results[0].id == "k1"


def test_search_knowledge_rrf_empty_query() -> None:
    """Empty query must return all knowledge."""
    k1 = _make_knowledge("k1", "Test", "Content")
    results = search_knowledge_rrf("", [k1])
    assert len(results) == 1


def test_execute_knowledge_plan() -> None:
    """Profile weights must affect ranking."""
    from relay.memory.query_analyzer import QueryIntent

    k1 = _make_knowledge(
        "k1", "Architecture Principle",
        "Use SQLite",
        knowledge_type=KnowledgeType.ARCHITECTURE_PRINCIPLE,
        importance="critical",
    )
    k2 = _make_knowledge(
        "k2", "Lesson Learned",
        "Test everything",
        knowledge_type=KnowledgeType.LESSON,
        importance="medium",
    )

    intent = QueryIntent(
        profile=RetrievalProfile.KNOWLEDGE_REVIEW,
        keywords=["architecture"],
        intent="knowledge_review",
    )

    scored, meta = execute_knowledge_plan(intent, [k1, k2])
    assert len(scored) == 2
    assert scored[0][0].id == "k1"


# ── Context Type Tests ─────────────────────────────────────────────────────


def test_context_citation_serialization() -> None:
    """ContextCitation must round-trip through dict."""
    c = ContextCitation(
        source_type="memory",
        source_id="mem-1",
        title="Test Memory",
        content="Test content",
        relevance_score=3.5,
        confidence=0.9,
        reasons=["keyword_match"],
        source_event_ids=["evt-1"],
    )
    d = c.to_dict()
    assert d["source_type"] == "memory"
    assert d["source_id"] == "mem-1"
    assert d["relevance_score"] == 3.5


def test_event_context_serialization() -> None:
    """EventContext must round-trip through dict."""
    ec = EventContext(
        event_id="evt-1",
        event_type="TASK_CREATED",
        stream_id="tasks",
        recorded_at="2024-01-01T00:00:00",
        actor="agent",
        source="test",
        summary="Task created: Build X",
    )
    d = ec.to_dict()
    assert d["event_id"] == "evt-1"
    assert d["event_type"] == "TASK_CREATED"
    assert "Build X" in d["summary"]


# ── Context Package Tests ─────────────────────────────────────────────────


def test_context_package_serialization() -> None:
    """ContextPackage must round-trip through dict."""
    pkg = ContextPackage(
        context_id="abc123",
        query="test query",
        profile="GENERAL_SEARCH",
        created_at="2024-01-01T00:00:00",
        citations=[
            ContextCitation(
                source_type="memory",
                source_id="mem-1",
                title="Test",
                content="Content",
                relevance_score=3.0,
                confidence=0.9,
                reasons=["keyword_match"],
                source_event_ids=["evt-1"],
            )
        ],
        source_counts={"events": 0, "memories": 1, "knowledge": 0},
        timing={"total_ms": 1.5},
    )
    d = pkg.to_dict()
    assert d["context_id"] == "abc123"
    assert d["query"] == "test query"
    assert len(d["citations"]) == 1
    assert d["citations"][0]["source_type"] == "memory"


def test_context_package_has_context_id() -> None:
    """ContextPackage must have context_id and created_at."""
    pkg = compile_context("test query")
    assert pkg.context_id
    assert pkg.created_at
    assert len(pkg.context_id) == 16


# ── Context Compiler Tests ─────────────────────────────────────────────────


def test_compile_context_determinism() -> None:
    """compile_context must produce identical output for same input."""
    pkg1 = compile_context("architecture principles")
    pkg2 = compile_context("architecture principles")

    assert pkg1.query == pkg2.query
    assert pkg1.profile == pkg2.profile
    assert len(pkg1.citations) == len(pkg2.citations)
    assert pkg1.source_counts == pkg2.source_counts


def test_compile_context_has_timing() -> None:
    """ContextPackage must include timing breakdown."""
    pkg = compile_context("test query")
    assert "total_ms" in pkg.timing
    assert pkg.timing["total_ms"] >= 0.0
    assert "query_analysis_ms" in pkg.timing


def test_compile_context_has_source_counts() -> None:
    """ContextPackage must include source counts."""
    pkg = compile_context("test query")
    assert "events" in pkg.source_counts
    assert "memories" in pkg.source_counts
    assert "knowledge" in pkg.source_counts


def test_compile_context_has_inclusion_reasons() -> None:
    """ContextPackage must include inclusion reasons."""
    pkg = compile_context("test query")
    assert len(pkg.inclusion_reasons) > 0
    assert any("Profile" in r for r in pkg.inclusion_reasons)


# ── Slot Allocation Tests ──────────────────────────────────────────────────


def test_slot_allocation_context_construction() -> None:
    """CONTEXT_CONSTRUCTION profile must balance all three sources."""
    slots = _get_slot_allocation(RetrievalProfile.CONTEXT_CONSTRUCTION, 30)
    total = slots["event"] + slots["memory"] + slots["knowledge"]
    assert total <= 30
    assert slots["event"] > 0
    assert slots["memory"] > 0
    assert slots["knowledge"] > 0


def test_slot_allocation_knowledge_review() -> None:
    """KNOWLEDGE_REVIEW must heavily favor knowledge source."""
    slots = _get_slot_allocation(RetrievalProfile.KNOWLEDGE_REVIEW, 30)
    assert slots["knowledge"] > slots["memory"]
    assert slots["knowledge"] > slots["event"]


def test_slot_allocation_total_never_exceeds_limit() -> None:
    """Slot allocation must never exceed total_limit."""
    for profile in RetrievalProfile:
        slots = _get_slot_allocation(profile, 30)
        total = slots["event"] + slots["memory"] + slots["knowledge"]
        assert total <= 30


def test_profile_source_weights_defined_for_all_profiles() -> None:
    """All profiles must have source weights defined."""
    for profile in RetrievalProfile:
        assert profile in PROFILE_SOURCE_WEIGHTS
        weights = PROFILE_SOURCE_WEIGHTS[profile]
        assert abs(sum(weights.values()) - 1.0) < 0.01


# ── Evaluation Tests ───────────────────────────────────────────────────────


def test_context_metrics_computation() -> None:
    """ContextMetrics must compute all required values."""
    pkg = ContextPackage(
        context_id="test",
        query="test",
        profile="GENERAL_SEARCH",
        created_at="2024-01-01T00:00:00",
        citations=[
            ContextCitation("memory", "m1", "Mem", "Content", 3.0, 0.9, ["reason"], ["e1"]),
            ContextCitation("knowledge", "k1", "Know", "Content", 4.0, 0.8, ["reason"], ["e2"]),
            ContextCitation("event", "e1", "Event", "Content", 0.5, 1.0, ["reason"], ["e3"]),
        ],
        timing={"total_ms": 10.0},
    )
    metrics = compute_context_metrics(pkg, keywords=["content"])

    assert metrics.context_completeness == 1.0
    assert metrics.source_traceability == 1.0
    assert metrics.total_citations == 3
    assert metrics.within_timing_budget is True
    assert metrics.context_precision > 0.0


def test_context_metrics_exit_gates() -> None:
    """Exit gates must be enforced."""
    metrics = ContextMetrics(
        context_completeness=1.0,
        source_traceability=1.0,
        source_balance=1.0,
        blending_determinism=1.0,
        total_ms=10.0,
        within_timing_budget=True,
        context_redundancy=0.0,
        context_precision=1.0,
    )
    passed, failures = metrics.passes_exit_gates()
    assert passed
    assert len(failures) == 0


def test_context_metrics_exit_gates_fail() -> None:
    """Exit gates must detect failures."""
    metrics = ContextMetrics(
        context_completeness=0.33,
        source_traceability=0.5,
        source_balance=0.1,
        blending_determinism=0.5,
        total_ms=1000.0,
        within_timing_budget=False,
        context_redundancy=0.5,
        context_precision=0.3,
    )
    passed, failures = metrics.passes_exit_gates()
    assert not passed
    assert "context_completeness" in failures
    assert "source_traceability" in failures
    assert "source_balance" in failures
    assert "blending_determinism" in failures
    assert "timing_budget" in failures
    assert "context_redundancy" in failures
    assert "context_precision" in failures


def test_context_metrics_exit_gate_constants() -> None:
    """Exit gate constants must be defined correctly."""
    assert MIN_CONTEXT_COMPLETENESS == 0.67
    assert MIN_SOURCE_TRACEABILITY == 1.0
    assert MIN_SOURCE_BALANCE == 0.15
    assert MIN_BLENDING_DETERMINISM == 1.0
    assert MAX_CONTEXT_COMPILE_MS == 500.0
    assert MAX_CONTEXT_REDUNDANCY == 0.25
    assert MIN_CONTEXT_PRECISION == 0.70


def test_timing_budget_enforcement() -> None:
    """Context must compile within the timing budget."""
    pkg = compile_context("architecture decisions")
    assert pkg.timing["total_ms"] < MAX_CONTEXT_COMPILE_MS


def test_source_balance_computation() -> None:
    """Source balance must compute correctly."""
    from relay.knowledge.evaluation_i5 import _compute_source_balance

    # Perfect balance for GENERAL_SEARCH
    pkg = ContextPackage(
        context_id="test",
        query="test",
        profile="GENERAL_SEARCH",
        created_at="2024-01-01T00:00:00",
        citations=[
            ContextCitation("memory", "m1", "", "", 1.0, 1.0, [], []),
            ContextCitation("knowledge", "k1", "", "", 1.0, 1.0, [], []),
            ContextCitation("event", "e1", "", "", 1.0, 1.0, [], []),
        ],
    )
    balance = _compute_source_balance(pkg)
    assert balance > 0.0


def test_redundancy_computation() -> None:
    """Redundancy must detect duplicate content."""
    from relay.knowledge.evaluation_i5 import _compute_redundancy

    citations = [
        ContextCitation("memory", "m1", "Title", "Same content", 1.0, 1.0, [], []),
        ContextCitation("knowledge", "k1", "Title", "Same content", 1.0, 1.0, [], []),
        ContextCitation("event", "e1", "Title", "Different content", 1.0, 1.0, [], []),
    ]
    total, unique, redundancy = _compute_redundancy(citations)
    assert total == 3
    assert unique == 2
    assert redundancy > 0.0
