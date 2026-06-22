"""Sprint I4.5: Knowledge Evaluation — Unit Tests."""
from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from rationalevault.knowledge.benchmark_schema import KnowledgeBenchmark
from rationalevault.knowledge.evaluator import (
    KnowledgeEvalResult,
    KnowledgeEvaluator,
    KnowledgeEvaluationThresholds,
    KnowledgeIdentityStatus,
    KnowledgeSemanticStatus,
    check_knowledge_gates,
)
from rationalevault.knowledge.models import (
    KnowledgeConfidence,
    KnowledgeDomain,
    KnowledgeLifecycle,
    KnowledgeObject,
    KnowledgeType,
    ProvenanceChain,
)


# ── Helper Functions ──────────────────────────────────────────────────────────


def _make_knowledge(
    k_id: str,
    title: str,
    content: str,
    knowledge_type: KnowledgeType = KnowledgeType.ARCHITECTURE_PRINCIPLE,
    knowledge_domain: KnowledgeDomain = KnowledgeDomain.ARCHITECTURE,
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
        importance="high",
        provenance=provenance,
        supporting_memory_ids=["mem-1", "mem-2"],
    )


def _make_benchmark(
    benchmark_id: str = "test_benchmark",
    expected_knowledge: list[dict] | None = None,
    expected_contradictions: list[tuple[str, str]] | None = None,
    expected_knowledge_types: list[str] | None = None,
) -> KnowledgeBenchmark:
    if expected_knowledge is None:
        expected_knowledge = []
    if expected_contradictions is None:
        expected_contradictions = []
    if expected_knowledge_types is None:
        expected_knowledge_types = []

    return KnowledgeBenchmark(
        benchmark_id=benchmark_id,
        benchmark_type="synthetic",
        benchmark_version=1,
        expected_architecture_principles=[
            k for k in expected_knowledge if k.get("type") == "ARCHITECTURE_PRINCIPLE"
        ],
        expected_project_invariants=[
            k for k in expected_knowledge if k.get("type") == "PROJECT_INVARIANT"
        ],
        expected_lessons=[
            k for k in expected_knowledge if k.get("type") == "LESSON"
        ],
        expected_failure_patterns=[
            k for k in expected_knowledge if k.get("type") == "FAILURE_PATTERN"
        ],
        expected_workflow_patterns=[
            k for k in expected_knowledge if k.get("type") == "WORKFLOW_PATTERN"
        ],
        expected_research_findings=[
            k for k in expected_knowledge if k.get("type") == "RESEARCH_FINDING"
        ],
        expected_decision_lineages=[
            k for k in expected_knowledge if k.get("type") == "DECISION_LINEAGE"
        ],
        expected_contradictions=expected_contradictions,
        expected_knowledge_types=expected_knowledge_types,
    )


# ── Benchmark Schema Tests ────────────────────────────────────────────────────


def test_benchmark_serialization() -> None:
    """KnowledgeBenchmark must round-trip through dict."""
    benchmark = _make_benchmark(
        benchmark_id="test_1",
        expected_knowledge=[
            {"title": "SQLite First", "content": "Use SQLite", "type": "ARCHITECTURE_PRINCIPLE"},
        ],
    )

    d = benchmark.to_dict()
    benchmark2 = KnowledgeBenchmark.from_dict(d)

    assert benchmark2.benchmark_id == "test_1"
    assert benchmark2.benchmark_version == 1
    assert len(benchmark2.expected_architecture_principles) == 1


def test_benchmark_version() -> None:
    """benchmark_version defaults to 1."""
    benchmark = KnowledgeBenchmark(
        benchmark_id="test",
        benchmark_type="synthetic",
    )
    assert benchmark.benchmark_version == 1


def test_benchmark_all_expected_knowledge() -> None:
    """all_expected_knowledge flattens all expected lists."""
    benchmark = _make_benchmark(
        expected_knowledge=[
            {"title": "Principle 1", "content": "P1", "type": "ARCHITECTURE_PRINCIPLE"},
            {"title": "Invariant 1", "content": "I1", "type": "PROJECT_INVARIANT"},
            {"title": "Lesson 1", "content": "L1", "type": "LESSON"},
        ],
    )

    all_expected = benchmark.all_expected_knowledge
    assert len(all_expected) == 3
    titles = {k["title"] for k in all_expected}
    assert "Principle 1" in titles
    assert "Invariant 1" in titles
    assert "Lesson 1" in titles


# ── Evaluator Tests ───────────────────────────────────────────────────────────


def test_evaluator_identity_recall() -> None:
    """Identity recall must count exact title matches."""
    benchmark = _make_benchmark(
        expected_knowledge=[
            {"title": "SQLite First", "content": "Use SQLite", "type": "ARCHITECTURE_PRINCIPLE"},
            {"title": "Derived State", "content": "State derived from events", "type": "ARCHITECTURE_PRINCIPLE"},
        ],
    )

    synthesized = [
        _make_knowledge("k1", "SQLite First", "Use SQLite"),
    ]

    evaluator = KnowledgeEvaluator(benchmark)
    result = evaluator.evaluate(synthesized)

    assert result.identity_preserved == 1
    assert result.identity_lost == 1
    assert result.identity_recall == 0.5


def test_evaluator_semantic_recall() -> None:
    """Semantic recall must count content similarity matches."""
    benchmark = _make_benchmark(
        expected_knowledge=[
            {"title": "SQLite First", "content": "Use SQLite for local-first storage", "type": "ARCHITECTURE_PRINCIPLE"},
        ],
    )

    # Synthesized has different title but similar content
    synthesized = [
        _make_knowledge("k1", "Local SQLite Default", "Use SQLite as default local storage"),
    ]

    evaluator = KnowledgeEvaluator(benchmark)
    result = evaluator.evaluate(synthesized)

    # Identity should miss (different title)
    assert result.identity_preserved == 0
    # Semantic should hit (similar content)
    assert result.semantic_consistent >= 1 or result.semantic_drifted >= 1


def test_evaluator_precision() -> None:
    """Precision must detect false positives."""
    benchmark = _make_benchmark(
        expected_knowledge=[
            {"title": "SQLite First", "content": "Use SQLite", "type": "ARCHITECTURE_PRINCIPLE"},
        ],
    )

    synthesized = [
        _make_knowledge("k1", "SQLite First", "Use SQLite"),
        _make_knowledge("k2", "Unexpected Knowledge", "This was not expected"),
    ]

    evaluator = KnowledgeEvaluator(benchmark)
    result = evaluator.evaluate(synthesized)

    assert result.precision == 0.5
    assert result.false_positives == 1


def test_evaluator_f1_score() -> None:
    """F1 = 2 * P * R / (P + R)."""
    benchmark = _make_benchmark(
        expected_knowledge=[
            {"title": "SQLite First", "content": "Use SQLite", "type": "ARCHITECTURE_PRINCIPLE"},
        ],
    )

    synthesized = [
        _make_knowledge("k1", "SQLite First", "Use SQLite"),
    ]

    evaluator = KnowledgeEvaluator(benchmark)
    result = evaluator.evaluate(synthesized)

    # P=1.0, R=1.0 -> F1=1.0
    assert result.f1_score == 1.0


def test_evaluator_determinism_score() -> None:
    """Determinism = same ID + type + provenance across runs."""
    benchmark = _make_benchmark(
        expected_knowledge=[
            {"title": "SQLite First", "content": "Use SQLite", "type": "ARCHITECTURE_PRINCIPLE"},
        ],
    )

    synthesized_run1 = [
        _make_knowledge("k1", "SQLite First", "Use SQLite"),
    ]
    synthesized_run2 = [
        _make_knowledge("k1", "SQLite First", "Use SQLite"),
    ]

    evaluator = KnowledgeEvaluator(benchmark)
    result = evaluator.evaluate(synthesized_run1, previous_synthesis=synthesized_run2)

    assert result.determinism_score == 1.0


def test_evaluator_determinism_score_low() -> None:
    """Determinism < 1 when runs produce different knowledge."""
    benchmark = _make_benchmark(
        expected_knowledge=[
            {"title": "SQLite First", "content": "Use SQLite", "type": "ARCHITECTURE_PRINCIPLE"},
        ],
    )

    synthesized_run1 = [
        _make_knowledge("k1", "SQLite First", "Use SQLite"),
    ]
    synthesized_run2 = [
        _make_knowledge("k2", "Different Knowledge", "Something else"),
    ]

    evaluator = KnowledgeEvaluator(benchmark)
    result = evaluator.evaluate(synthesized_run1, previous_synthesis=synthesized_run2)

    assert result.determinism_score == 0.0


def test_evaluator_provenance_depth() -> None:
    """Provenance depth = memories + events per knowledge."""
    benchmark = _make_benchmark(
        expected_knowledge=[
            {"title": "SQLite First", "content": "Use SQLite", "type": "ARCHITECTURE_PRINCIPLE"},
        ],
    )

    synthesized = [
        _make_knowledge("k1", "SQLite First", "Use SQLite"),
    ]

    evaluator = KnowledgeEvaluator(benchmark)
    result = evaluator.evaluate(synthesized)

    # Each knowledge has 2 memories + 3 events = 5
    assert result.average_provenance_depth == 5.0


def test_evaluator_contradictions() -> None:
    """Contradiction detection quality."""
    benchmark = _make_benchmark(
        expected_knowledge=[
            {"title": "Use SQLite", "content": "Use SQLite for storage", "type": "ARCHITECTURE_PRINCIPLE"},
            {"title": "Use Postgres", "content": "Use PostgreSQL for storage", "type": "ARCHITECTURE_PRINCIPLE"},
        ],
        expected_contradictions=[],  # No expected contradictions for this test
    )

    synthesized = [
        _make_knowledge("k1", "Use SQLite", "Use SQLite for storage"),
        _make_knowledge("k2", "Use Postgres", "Use PostgreSQL for storage"),
    ]

    evaluator = KnowledgeEvaluator(benchmark)
    result = evaluator.evaluate(synthesized)

    # SQLite vs PostgreSQL should be detected as contradiction
    assert result.contradictions_detected >= 1
    # Since no expected contradictions, true_contradictions = 0, false = detected
    assert result.true_contradictions == 0
    assert result.false_contradictions >= 1


def test_evaluator_coverage_benchmark_relative() -> None:
    """Coverage should be benchmark-relative when expected_knowledge_types specified."""
    benchmark = _make_benchmark(
        expected_knowledge=[
            {"title": "SQLite First", "content": "Use SQLite", "type": "ARCHITECTURE_PRINCIPLE"},
        ],
        expected_knowledge_types=["ARCHITECTURE_PRINCIPLE", "LESSON"],
    )

    synthesized = [
        _make_knowledge("k1", "SQLite First", "Use SQLite"),
    ]

    evaluator = KnowledgeEvaluator(benchmark)
    result = evaluator.evaluate(synthesized)

    # Only ARCHITECTURE_PRINCIPLE covered, not LESSON -> 50%
    assert result.type_coverage == 0.5


# ── Gate Tests ────────────────────────────────────────────────────────────────


def test_knowledge_gates_pass() -> None:
    """Gates should pass when metrics are above thresholds."""
    result = KnowledgeEvalResult(
        benchmark_id="test",
        benchmark_version=1,
        expected_count=1,
        synthesized_count=1,
        identity_recall=1.0,
        identity_preserved=1,
        identity_aliased=0,
        identity_lost=0,
        semantic_recall=1.0,
        semantic_consistent=1,
        semantic_drifted=0,
        semantic_contradicted=0,
        precision=1.0,
        false_positives=0,
        f1_score=1.0,
        determinism_score=1.0,
        provenance_pct=1.0,
        average_provenance_depth=5.0,
        contradictions_detected=0,
        contradictions_expected=0,
        true_contradictions=0,
        false_contradictions=0,
        contradiction_precision=1.0,
        type_coverage=1.0,
    )

    thresholds = KnowledgeEvaluationThresholds()
    passed, failures = check_knowledge_gates(result, thresholds)

    assert passed
    assert len(failures) == 0


def test_knowledge_gates_fail_precision() -> None:
    """Gates should fail when precision is below threshold."""
    result = KnowledgeEvalResult(
        benchmark_id="test",
        benchmark_version=1,
        expected_count=1,
        synthesized_count=5,
        identity_recall=1.0,
        identity_preserved=1,
        identity_aliased=0,
        identity_lost=0,
        semantic_recall=1.0,
        semantic_consistent=1,
        semantic_drifted=0,
        semantic_contradicted=0,
        precision=0.5,  # Below threshold
        false_positives=0,
        f1_score=0.67,
        determinism_score=1.0,
        provenance_pct=1.0,
        average_provenance_depth=5.0,
        contradictions_detected=0,
        contradictions_expected=0,
        true_contradictions=0,
        false_contradictions=0,
        contradiction_precision=1.0,
        type_coverage=1.0,
    )

    thresholds = KnowledgeEvaluationThresholds()
    passed, failures = check_knowledge_gates(result, thresholds)

    assert not passed
    assert "precision" in failures


def test_knowledge_gates_fail_determinism() -> None:
    """Gates should fail when determinism is below threshold."""
    result = KnowledgeEvalResult(
        benchmark_id="test",
        benchmark_version=1,
        expected_count=1,
        synthesized_count=1,
        identity_recall=1.0,
        identity_preserved=1,
        identity_aliased=0,
        identity_lost=0,
        semantic_recall=1.0,
        semantic_consistent=1,
        semantic_drifted=0,
        semantic_contradicted=0,
        precision=1.0,
        false_positives=0,
        f1_score=1.0,
        determinism_score=0.5,  # Below threshold
        provenance_pct=1.0,
        average_provenance_depth=5.0,
        contradictions_detected=0,
        contradictions_expected=0,
        true_contradictions=0,
        false_contradictions=0,
        contradiction_precision=1.0,
        type_coverage=1.0,
    )

    thresholds = KnowledgeEvaluationThresholds()
    passed, failures = check_knowledge_gates(result, thresholds)

    assert not passed
    assert "determinism_score" in failures


def test_knowledge_gates_fail_false_contradictions() -> None:
    """Gates should fail when false contradictions > 0."""
    result = KnowledgeEvalResult(
        benchmark_id="test",
        benchmark_version=1,
        expected_count=1,
        synthesized_count=1,
        identity_recall=1.0,
        identity_preserved=1,
        identity_aliased=0,
        identity_lost=0,
        semantic_recall=1.0,
        semantic_consistent=1,
        semantic_drifted=0,
        semantic_contradicted=0,
        precision=1.0,
        false_positives=0,
        f1_score=1.0,
        determinism_score=1.0,
        provenance_pct=1.0,
        average_provenance_depth=5.0,
        contradictions_detected=2,
        contradictions_expected=1,
        true_contradictions=1,
        false_contradictions=1,  # Above threshold
        contradiction_precision=0.5,
        type_coverage=1.0,
    )

    thresholds = KnowledgeEvaluationThresholds()
    passed, failures = check_knowledge_gates(result, thresholds)

    assert not passed
    assert "false_contradictions" in failures


# ── Edge Case Tests ───────────────────────────────────────────────────────────


def test_evaluator_empty_synthesis() -> None:
    """Graceful handling of empty synthesis."""
    benchmark = _make_benchmark(
        expected_knowledge=[
            {"title": "SQLite First", "content": "Use SQLite", "type": "ARCHITECTURE_PRINCIPLE"},
        ],
    )

    evaluator = KnowledgeEvaluator(benchmark)
    result = evaluator.evaluate([])

    assert result.expected_count == 1
    assert result.synthesized_count == 0
    assert result.identity_recall == 0.0
    assert result.semantic_recall == 0.0


def test_evaluator_empty_benchmark() -> None:
    """Graceful handling of empty benchmark."""
    benchmark = _make_benchmark(expected_knowledge=[])

    synthesized = [
        _make_knowledge("k1", "SQLite First", "Use SQLite"),
    ]

    evaluator = KnowledgeEvaluator(benchmark)
    result = evaluator.evaluate(synthesized)

    assert result.expected_count == 0
    assert result.synthesized_count == 1
    assert result.precision == 0.0


def test_evaluator_semantic_recall_containment() -> None:
    """Semantic recall must use containment (max) logic."""
    benchmark = _make_benchmark(
        expected_knowledge=[
            {"title": "A", "content": "Use SQLite for local storage", "type": "ARCHITECTURE_PRINCIPLE"},
        ],
    )

    synthesized = [
        _make_knowledge("k1", "B", "Use SQLite for local storage and caching"),
    ]

    evaluator = KnowledgeEvaluator(benchmark)
    result = evaluator.evaluate(synthesized)

    # Semantic should match even though title is different
    assert result.semantic_recall >= 0.5
