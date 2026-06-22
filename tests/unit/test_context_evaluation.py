"""Sprint I5.5: Context Evaluation & Context Benchmarks — Unit Tests."""
from __future__ import annotations

import pytest

from relay.evaluation.context_benchmark_schema import ContextBenchmark
from relay.evaluation.context_evaluator import (
    ContextEvaluator,
    ContextEvalResult,
    ContextEvaluationThresholds,
    check_context_gates,
    _compute_f1,
    _compute_count_recall,
)
from relay.knowledge.context_compiler import ContextPackage
from relay.knowledge.context_types import ContextCitation


# ── Helpers ────────────────────────────────────────────────────────────────


def _make_benchmark(
    benchmark_id: str = "test_benchmark",
    query: str = "test query",
    expected_profile: str = "",
    expected_event_count: int = 2,
    expected_memory_count: int = 2,
    expected_knowledge_count: int = 2,
    expected_keywords: list[str] | None = None,
) -> ContextBenchmark:
    return ContextBenchmark(
        benchmark_id=benchmark_id,
        query=query,
        expected_profile=expected_profile,
        expected_event_count=expected_event_count,
        expected_memory_count=expected_memory_count,
        expected_knowledge_count=expected_knowledge_count,
        expected_keywords=expected_keywords or ["test", "content"],
    )


def _make_citation(
    source_type: str,
    source_id: str,
    title: str = "",
    content: str = "",
    relevance_score: float = 1.0,
) -> ContextCitation:
    return ContextCitation(
        source_type=source_type,
        source_id=source_id,
        title=title,
        content=content,
        relevance_score=relevance_score,
        confidence=1.0,
        reasons=["test"],
        source_event_ids=["evt-1"],
    )


def _make_package(
    query: str = "test query",
    profile: str = "GENERAL_SEARCH",
    citations: list[ContextCitation] | None = None,
    timing_ms: float = 10.0,
) -> ContextPackage:
    if citations is None:
        citations = []
    source_counts = {
        "events": sum(1 for c in citations if c.source_type == "event"),
        "memories": sum(1 for c in citations if c.source_type == "memory"),
        "knowledge": sum(1 for c in citations if c.source_type == "knowledge"),
    }
    return ContextPackage(
        context_id="test_context",
        query=query,
        profile=profile,
        created_at="2024-01-01T00:00:00",
        citations=citations,
        source_counts=source_counts,
        timing={"total_ms": timing_ms},
    )


# ── Benchmark Schema Tests ────────────────────────────────────────────────


def test_benchmark_serialization() -> None:
    """ContextBenchmark must round-trip through dict."""
    b = _make_benchmark()
    d = b.to_dict()
    b2 = ContextBenchmark.from_dict(d)
    assert b2.benchmark_id == b.benchmark_id
    assert b2.query == b.query
    assert b2.expected_event_count == b.expected_event_count


def test_benchmark_version() -> None:
    """ContextBenchmark must support versioning."""
    b = ContextBenchmark(benchmark_id="v1", benchmark_version=1)
    b2 = ContextBenchmark(benchmark_id="v1", benchmark_version=2)
    assert b.benchmark_version != b2.benchmark_version


# ── Helper Function Tests ─────────────────────────────────────────────────


def test_compute_f1() -> None:
    """F1 must compute correctly."""
    assert _compute_f1(1.0, 1.0) == 1.0
    assert _compute_f1(0.0, 0.0) == 0.0
    assert abs(_compute_f1(0.5, 1.0) - 0.6667) < 0.01


def test_compute_count_recall() -> None:
    """Count recall must compute correctly."""
    assert _compute_count_recall(0, 0) == 1.0
    assert _compute_count_recall(0, 5) == 0.5
    assert _compute_count_recall(5, 5) == 1.0
    assert _compute_count_recall(5, 3) == 0.6


# ── Evaluator Tests ───────────────────────────────────────────────────────


def test_evaluator_basic() -> None:
    """ContextEvaluator must compute basic metrics."""
    benchmark = _make_benchmark(
        expected_event_count=1,
        expected_memory_count=1,
        expected_knowledge_count=1,
        expected_keywords=["sqlite"],
    )
    citations = [
        _make_citation("event", "e1", content="sqlite decision"),
        _make_citation("memory", "m1", content="sqlite storage"),
        _make_citation("knowledge", "k1", content="sqlite first"),
    ]
    package = _make_package(citations=citations)

    evaluator = ContextEvaluator(benchmark)
    result = evaluator.evaluate(package)

    assert result.completeness == 1.0
    assert result.event_recall == 1.0
    assert result.memory_recall == 1.0
    assert result.knowledge_recall == 1.0
    assert result.precision > 0.0
    assert result.f1_score > 0.0


def test_evaluator_empty_package() -> None:
    """ContextEvaluator must handle empty packages."""
    benchmark = _make_benchmark(expected_event_count=2, expected_memory_count=2)
    package = _make_package(citations=[])

    evaluator = ContextEvaluator(benchmark)
    result = evaluator.evaluate(package)

    assert result.completeness == 0.0
    assert result.actual_total == 0
    assert result.redundancy == 0.0


def test_evaluator_determinism() -> None:
    """ContextEvaluator must check determinism across runs."""
    benchmark = _make_benchmark()
    citations = [_make_citation("memory", "m1")]
    pkg1 = _make_package(citations=citations)
    pkg2 = _make_package(citations=citations)

    evaluator = ContextEvaluator(benchmark)
    result = evaluator.evaluate(pkg1, previous_package=pkg2)

    assert result.determinism_score == 1.0


def test_evaluator_determinism_failure() -> None:
    """ContextEvaluator must detect non-deterministic output."""
    benchmark = _make_benchmark()
    pkg1 = _make_package(citations=[_make_citation("memory", "m1")])
    pkg2 = _make_package(citations=[_make_citation("memory", "m2")])

    evaluator = ContextEvaluator(benchmark)
    result = evaluator.evaluate(pkg1, previous_package=pkg2)

    assert result.determinism_score == 0.0


def test_evaluator_redundancy() -> None:
    """ContextEvaluator must detect redundant content."""
    benchmark = _make_benchmark()
    citations = [
        _make_citation("memory", "m1", title="Same", content="Same content"),
        _make_citation("knowledge", "k1", title="Same", content="Same content"),
        _make_citation("event", "e1", title="Different", content="Different content"),
    ]
    package = _make_package(citations=citations)

    evaluator = ContextEvaluator(benchmark)
    result = evaluator.evaluate(package)

    assert result.redundancy > 0.0
    assert result.unique_content_hashes < result.content_hashes


def test_evaluator_profile_accuracy() -> None:
    """ContextEvaluator must check profile accuracy."""
    benchmark = _make_benchmark(expected_profile="DECISION_LOOKUP")
    pkg_correct = _make_package(profile="DECISION_LOOKUP")
    pkg_wrong = _make_package(profile="GENERAL_SEARCH")

    evaluator = ContextEvaluator(benchmark)

    result_correct = evaluator.evaluate(pkg_correct)
    assert result_correct.profile_correct

    result_wrong = evaluator.evaluate(pkg_wrong)
    assert not result_wrong.profile_correct


def test_evaluator_timing_budget() -> None:
    """ContextEvaluator must enforce timing budget."""
    benchmark = _make_benchmark()
    pkg_fast = _make_package(timing_ms=10.0)
    pkg_slow = _make_package(timing_ms=1000.0)

    evaluator = ContextEvaluator(benchmark)

    result_fast = evaluator.evaluate(pkg_fast)
    assert result_fast.within_timing_budget

    result_slow = evaluator.evaluate(pkg_slow)
    assert not result_slow.within_timing_budget


# ── Gate Tests ─────────────────────────────────────────────────────────────


def test_check_context_gates_pass() -> None:
    """check_context_gates must pass when all metrics are good."""
    result = ContextEvalResult(
        benchmark_id="test",
        benchmark_version=1,
        expected_total=6,
        actual_total=6,
        source_types_present=3,
        source_types_possible=3,
        completeness=1.0,
        expected_event_count=2,
        actual_event_count=2,
        event_recall=1.0,
        expected_memory_count=2,
        actual_memory_count=2,
        memory_recall=1.0,
        expected_knowledge_count=2,
        actual_knowledge_count=2,
        knowledge_recall=1.0,
        expected_keywords=3,
        matched_keywords=3,
        keyword_recall=1.0,
        citations_with_keyword_match=6,
        precision=1.0,
        f1_score=1.0,
        content_hashes=6,
        unique_content_hashes=6,
        redundancy=0.0,
        source_balance=1.0,
        determinism_score=1.0,
        total_ms=10.0,
        within_timing_budget=True,
        profile_correct=True,
    )
    passed, failures = check_context_gates(result)
    assert passed
    assert len(failures) == 0


def test_check_context_gates_fail() -> None:
    """check_context_gates must detect failures."""
    result = ContextEvalResult(
        benchmark_id="test",
        benchmark_version=1,
        expected_total=6,
        actual_total=2,
        source_types_present=1,
        source_types_possible=3,
        completeness=0.33,
        expected_event_count=2,
        actual_event_count=0,
        event_recall=0.0,
        expected_memory_count=2,
        actual_memory_count=1,
        memory_recall=0.5,
        expected_knowledge_count=2,
        actual_knowledge_count=1,
        knowledge_recall=0.5,
        expected_keywords=3,
        matched_keywords=0,
        keyword_recall=0.0,
        citations_with_keyword_match=0,
        precision=0.0,
        f1_score=0.0,
        content_hashes=2,
        unique_content_hashes=1,
        redundancy=0.5,
        source_balance=0.1,
        determinism_score=0.5,
        total_ms=1000.0,
        within_timing_budget=False,
        profile_correct=False,
    )
    passed, failures = check_context_gates(result)
    assert not passed
    assert "completeness" in failures
    assert "source_balance" in failures
    assert "precision" in failures
    assert "f1_score" in failures
    assert "redundancy" in failures
    assert "determinism" in failures
    assert "timing_budget" in failures


def test_check_context_gates_custom_thresholds() -> None:
    """check_context_gates must respect custom thresholds."""
    result = ContextEvalResult(
        benchmark_id="test",
        benchmark_version=1,
        expected_total=6,
        actual_total=6,
        source_types_present=3,
        source_types_possible=3,
        completeness=0.80,
        expected_event_count=2,
        actual_event_count=2,
        event_recall=1.0,
        expected_memory_count=2,
        actual_memory_count=2,
        memory_recall=1.0,
        expected_knowledge_count=2,
        actual_knowledge_count=2,
        knowledge_recall=1.0,
        expected_keywords=3,
        matched_keywords=3,
        keyword_recall=1.0,
        citations_with_keyword_match=6,
        precision=0.80,
        f1_score=0.80,
        content_hashes=6,
        unique_content_hashes=6,
        redundancy=0.0,
        source_balance=1.0,
        determinism_score=1.0,
        total_ms=10.0,
        within_timing_budget=True,
        profile_correct=True,
    )
    # With default thresholds, this passes
    passed_default, _ = check_context_gates(result)
    assert passed_default

    # With stricter thresholds, this fails
    strict = ContextEvaluationThresholds(
        MIN_CONTEXT_PRECISION=0.90,
    )
    passed_strict, failures_strict = check_context_gates(result, strict)
    assert not passed_strict
    assert "precision" in failures_strict


# ── EvalResult Serialization Tests ────────────────────────────────────────


def test_eval_result_serialization() -> None:
    """ContextEvalResult must round-trip through dict."""
    result = ContextEvalResult(
        benchmark_id="test",
        benchmark_version=1,
        expected_total=6,
        actual_total=6,
        source_types_present=3,
        source_types_possible=3,
        completeness=1.0,
        expected_event_count=2,
        actual_event_count=2,
        event_recall=1.0,
        expected_memory_count=2,
        actual_memory_count=2,
        memory_recall=1.0,
        expected_knowledge_count=2,
        actual_knowledge_count=2,
        knowledge_recall=1.0,
        expected_keywords=3,
        matched_keywords=3,
        keyword_recall=1.0,
        citations_with_keyword_match=6,
        precision=1.0,
        f1_score=1.0,
        content_hashes=6,
        unique_content_hashes=6,
        redundancy=0.0,
        source_balance=1.0,
        determinism_score=1.0,
        total_ms=10.0,
        within_timing_budget=True,
        profile_correct=True,
    )
    d = result.to_dict()
    result2 = ContextEvalResult.from_dict(d)
    assert result2.benchmark_id == result.benchmark_id
    assert result2.completeness == result.completeness
    assert result2.f1_score == result.f1_score


# ── Thresholds Tests ──────────────────────────────────────────────────────


def test_context_evaluation_thresholds() -> None:
    """ContextEvaluationThresholds must have correct defaults."""
    t = ContextEvaluationThresholds()
    assert t.MIN_CONTEXT_COMPLETENESS == 0.67
    assert t.MIN_SOURCE_BALANCE == 0.15
    assert t.MIN_CONTEXT_PRECISION == 0.70
    assert t.MIN_CONTEXT_RECALL == 0.50
    assert t.MIN_CONTEXT_F1 == 0.60
    assert t.MAX_CONTEXT_REDUNDANCY == 0.25
    assert t.MIN_BLENDING_DETERMINISM == 1.0
    assert t.MAX_CONTEXT_COMPILE_MS == 500.0


def test_global_thresholds_include_context() -> None:
    """Global EvaluationThresholds must include context thresholds."""
    from relay.evaluation.thresholds import EvaluationThresholds
    t = EvaluationThresholds()
    assert t.MIN_CONTEXT_COMPLETENESS == 0.67
    assert t.MIN_CONTEXT_PRECISION == 0.70
    assert t.MAX_CONTEXT_REDUNDANCY == 0.25
