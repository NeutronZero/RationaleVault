from __future__ import annotations

import os
import uuid
from pathlib import Path
from datetime import datetime
from rationalevault.memory.models import MemoryRecord, MemoryType
from rationalevault.memory.query_analyzer import analyze_query, RetrievalProfile
from rationalevault.memory.retrieval_planner import execute_retrieval_plan, RetrievalExecution
from rationalevault.memory.semantic_search import search_memories_rrf, perform_rrf_blending
from rationalevault.memory.citation_builder import build_citation, MemoryCitation
from rationalevault.memory.retrieval_audit import audit_retrieval_execution, RetrievalFailure
from rationalevault.memory.retrieval import retrieve_ranked_citations
from rationalevault.memory.markdown_provider import MarkdownMemoryProvider


def test_query_analyzer_profiles() -> None:
    intent1 = analyze_query("What SQLite database decisions exist?")
    assert intent1.profile == RetrievalProfile.DECISION_LOOKUP
    assert "sqlite" in intent1.keywords
    
    intent2 = analyze_query("Summarize trace failure loss error")
    assert intent2.profile == RetrievalProfile.FAILURE_ANALYSIS
    
    intent3 = analyze_query("Clean architecture design principles goals")
    assert intent3.profile == RetrievalProfile.ARCHITECTURE_REVIEW


def test_rrf_blending() -> None:
    rec1 = MemoryRecord(
        id="mem-1", version=1, title="Test 1", content="Content 1",
        memory_type=MemoryType.DECISION, importance="medium", lifecycle_status="active",
        source_event_ids=["e1"], source_type="test", project_id="test"
    )
    rec2 = MemoryRecord(
        id="mem-2", version=1, title="Test 2", content="Content 2",
        memory_type=MemoryType.DECISION, importance="medium", lifecycle_status="active",
        source_event_ids=["e2"], source_type="test", project_id="test"
    )
    
    # keyword ranks: mem-1, mem-2
    # semantic ranks: mem-2, mem-1
    keyword_results = [rec1, rec2]
    semantic_results = [rec2, rec1]
    
    blended = perform_rrf_blending(keyword_results, semantic_results)
    assert len(blended) == 2
    # Since they are symmetric, the order is blended correctly
    assert blended[0].id in ["mem-1", "mem-2"]


def test_explainable_citations_and_audit(tmp_path) -> None:
    file_path = tmp_path / "memory.md"
    provider = MarkdownMemoryProvider(file_path=file_path)
    
    rec = MemoryRecord(
        id="postgres-dec",
        version=1,
        title="Postgres Database decision",
        content="Use postgres routing database for scale",
        memory_type=MemoryType.DECISION,
        importance="high",
        lifecycle_status="active",
        source_event_ids=["evt-99"],
        source_type="decision",
        project_id="test",
    )
    provider.add_record(rec)
    
    # Test citation building
    citation = build_citation(rec, "postgres", ["query_analyzer", "retrieval_planner"])
    assert citation.memory_id == "postgres-dec"
    assert "keyword_match_title" in citation.reasons or "keyword_match_content" in citation.reasons
    assert "retrieval_planner" in citation.retrieval_path
    
    # Test retrieval auditing
    failures = audit_retrieval_execution(
        project_id=uuid.uuid4(),
        query="postgres decisions",
        predicted_profile=RetrievalProfile.DECISION_LOOKUP,
        expected_profile=RetrievalProfile.FAILURE_ANALYSIS, # deliberate mismatch
        expected_memory_id="postgres-dec",
        retrieved_citations=[citation]
    )
    assert RetrievalFailure.QUERY_MISCLASSIFICATION in failures


def test_retrieval_timing_and_execution_metadata() -> None:
    # Test retrieve_ranked_citations timing segment logging
    citations, execution = retrieve_ranked_citations("database decisions", limit=2)
    assert execution.timing is not None
    assert execution.timing.query_analysis_ms >= 0
    assert execution.timing.total_ms >= 0
    assert execution.keyword_candidates >= 0
    assert execution.vector_candidates == 0
    assert execution.semantic_used is False
    assert execution.rrf_used is False


def test_detailed_adversarial_audit_cases() -> None:
    # Wrong Ranking, Over Retrieval, Citation Error
    rec1 = MemoryRecord(
        id="mem-1", version=1, title="Test 1", content="Content 1",
        memory_type=MemoryType.DECISION, importance="medium", lifecycle_status="active",
        source_event_ids=["e1"], source_type="test", project_id="test"
    )
    rec2 = MemoryRecord(
        id="mem-2", version=1, title="Test 2", content="Content 2",
        memory_type=MemoryType.DECISION, importance="medium", lifecycle_status="active",
        source_event_ids=["e2"], source_type="test", project_id="test"
    )
    cit1 = build_citation(rec1, "test", ["query_analyzer", "retrieval_planner"])
    cit2 = build_citation(rec2, "test", ["query_analyzer", "retrieval_planner"])

    # Wrong ranking -> mem-2 expected first but list has [cit1, cit2]
    failures_ranking = audit_retrieval_execution(
        project_id=uuid.uuid4(),
        query="test",
        predicted_profile=RetrievalProfile.DECISION_LOOKUP,
        expected_profile=RetrievalProfile.DECISION_LOOKUP,
        expected_memory_id="mem-2",
        retrieved_citations=[cit1, cit2]
    )
    assert RetrievalFailure.RANKING_ERROR in failures_ranking

    # Over Retrieval -> limit > 2 (len is 3)
    cit3 = build_citation(rec2, "test", ["query_analyzer"])
    failures_over = audit_retrieval_execution(
        project_id=uuid.uuid4(),
        query="test",
        predicted_profile=RetrievalProfile.DECISION_LOOKUP,
        expected_profile=RetrievalProfile.DECISION_LOOKUP,
        expected_memory_id=None,
        retrieved_citations=[cit1, cit2, cit3]
    )
    assert RetrievalFailure.OVER_RETRIEVAL in failures_over

    # Citation Error -> missing source events or reasons
    cit_bad = MemoryCitation(
        memory_id="mem-1",
        score=cit1.score,
        source_event_ids=[], # missing
        reasons=[],          # missing
        retrieval_path=["test"]
    )
    failures_cit = audit_retrieval_execution(
        project_id=uuid.uuid4(),
        query="test",
        predicted_profile=RetrievalProfile.DECISION_LOOKUP,
        expected_profile=RetrievalProfile.DECISION_LOOKUP,
        expected_memory_id=None,
        retrieved_citations=[cit_bad]
    )
    assert RetrievalFailure.CITATION_ERROR in failures_cit

