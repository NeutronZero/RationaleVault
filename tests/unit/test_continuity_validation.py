"""Sprint I7: Multi-Agent Cognitive Continuity Validation — Unit Tests."""
from __future__ import annotations

import json
import pytest

from rationalevault.evaluation.continuity_benchmark_schema import (
    ContinuityBenchmark,
    ExpectedArtifact,
)
from rationalevault.evaluation.continuity_evaluator import (
    ContinuityEvaluator,
    ContinuityResult,
    check_continuity_gates,
)
from rationalevault.compilers.compiler_output import CompilerOutput


# ── Helpers ────────────────────────────────────────────────────────────────


def _make_artifact(
    artifact_type: str = "decision",
    canonical_value: str = "Use SQLite",
    aliases: list[str] | None = None,
    rationale: str = "",
    severity: str = "medium",
) -> ExpectedArtifact:
    return ExpectedArtifact(
        artifact_type=artifact_type,
        canonical_value=canonical_value,
        aliases=aliases or [],
        severity=severity,
        rationale=rationale,
    )


def _make_benchmark(
    benchmark_id: str = "test_benchmark",
    query: str = "test query",
    goals: list[ExpectedArtifact] | None = None,
    decisions: list[ExpectedArtifact] | None = None,
    rationales: list[ExpectedArtifact] | None = None,
    tasks: list[ExpectedArtifact] | None = None,
    knowledge: list[ExpectedArtifact] | None = None,
    questions: list[ExpectedArtifact] | None = None,
) -> ContinuityBenchmark:
    return ContinuityBenchmark(
        benchmark_id=benchmark_id,
        query=query,
        expected_goals=goals or [],
        expected_decisions=decisions or [],
        expected_rationales=rationales or [],
        expected_tasks=tasks or [],
        expected_knowledge=knowledge or [],
        expected_questions=questions or [],
    )


def _make_output(
    rendered_content: str = "",
    agent: str = "Claude",
    citation_count: int = 0,
) -> CompilerOutput:
    return CompilerOutput(
        query="test query",
        profile="GENERAL_SEARCH",
        agent=agent,
        format_name="markdown",
        rendered_content=rendered_content,
        citation_count=citation_count,
        source_counts={"events": 0, "memories": 0, "knowledge": 0},
        compile_time_ms=10.0,
        generated_at="2024-01-01T00:00:00",
    )


# ── ExpectedArtifact Tests ─────────────────────────────────────────────────


def test_artifact_matches_canonical() -> None:
    """ExpectedArtifact must match canonical value."""
    a = _make_artifact(canonical_value="Use SQLite")
    assert a.matches("We decided to Use SQLite for storage")
    assert not a.matches("We chose PostgreSQL")


def test_artifact_matches_alias() -> None:
    """ExpectedArtifact must match aliases."""
    a = _make_artifact(
        canonical_value="Use SQLite",
        aliases=["SQLite First", "SQLite database"],
    )
    assert a.matches("We went with SQLite First")
    assert a.matches("The SQLite database is ready")
    assert not a.matches("We chose PostgreSQL")


def test_artifact_case_insensitive() -> None:
    """ExpectedArtifact matching must be case-insensitive."""
    a = _make_artifact(canonical_value="USE SQLITE")
    assert a.matches("we decided to use sqlite")


def test_artifact_serialization() -> None:
    """ExpectedArtifact must round-trip through dict."""
    a = _make_artifact(
        canonical_value="Test",
        aliases=["Alias1", "Alias2"],
        rationale="Because",
    )
    d = a.to_dict()
    a2 = ExpectedArtifact.from_dict(d)
    assert a2.canonical_value == a.canonical_value
    assert a2.aliases == a.aliases
    assert a2.rationale == a.rationale


# ── ContinuityBenchmark Tests ──────────────────────────────────────────────


def test_benchmark_serialization() -> None:
    """ContinuityBenchmark must round-trip through dict."""
    b = _make_benchmark(
        goals=[_make_artifact("goal", "Ship product")],
        decisions=[_make_artifact("decision", "Use Redis")],
    )
    d = b.to_dict()
    b2 = ContinuityBenchmark.from_dict(d)
    assert b2.benchmark_id == b.benchmark_id
    assert len(b2.expected_goals) == 1
    assert len(b2.expected_decisions) == 1


def test_benchmark_all_expected() -> None:
    """ContinuityBenchmark.all_expected must return all artifacts."""
    b = _make_benchmark(
        goals=[_make_artifact("goal", "G1")],
        decisions=[_make_artifact("decision", "D1")],
        tasks=[_make_artifact("task", "T1")],
    )
    assert len(b.all_expected) == 3


def test_benchmark_from_json() -> None:
    """ContinuityBenchmark must load from JSON file format."""
    data = {
        "benchmark_id": "test",
        "query": "test query",
        "expected_goals": [
            {"artifact_type": "goal", "canonical_value": "Ship", "aliases": ["Launch"], "severity": "high"}
        ],
        "expected_decisions": [
            {"artifact_type": "decision", "canonical_value": "Use X", "aliases": [], "severity": "medium", "rationale": "Because"}
        ],
    }
    b = ContinuityBenchmark.from_dict(data)
    assert b.benchmark_id == "test"
    assert len(b.expected_goals) == 1
    assert b.expected_goals[0].canonical_value == "Ship"
    assert b.expected_decisions[0].rationale == "Because"


# ── ContinuityEvaluator Tests ──────────────────────────────────────────────


def test_evaluator_perfect_recovery() -> None:
    """ContinuityEvaluator must score 1.0 when all artifacts are recovered."""
    benchmark = _make_benchmark(
        goals=[_make_artifact("goal", "Ship product")],
        decisions=[_make_artifact("decision", "Use SQLite", rationale="It is fast")],
        tasks=[_make_artifact("task", "Build API")],
    )
    output = _make_output(
        rendered_content="Goal: Ship product. Decision: Use SQLite. Because It is fast. Task: Build API."
    )
    evaluator = ContinuityEvaluator(benchmark)
    result = evaluator.evaluate(output)

    assert result.goal_recall == 1.0
    assert result.decision_recall == 1.0
    assert result.rationale_recall == 1.0
    assert result.task_recall == 1.0
    assert result.overall_continuity == 1.0
    assert result.passed


def test_evaluator_partial_recovery() -> None:
    """ContinuityEvaluator must detect missing artifacts."""
    benchmark = _make_benchmark(
        decisions=[
            _make_artifact("decision", "Use SQLite"),
            _make_artifact("decision", "Use Redis"),
        ],
    )
    output = _make_output(rendered_content="Decision: Use SQLite.")
    evaluator = ContinuityEvaluator(benchmark)
    result = evaluator.evaluate(output)

    assert result.decision_recall == 0.5
    assert result.decision_recovered == 1
    assert result.decision_expected == 2
    assert len(result.missed_artifacts) == 1
    assert result.missed_artifacts[0]["canonical_value"] == "Use Redis"


def test_evaluator_empty_benchmark() -> None:
    """ContinuityEvaluator must handle empty benchmarks."""
    benchmark = _make_benchmark()
    output = _make_output(rendered_content="Some content")
    evaluator = ContinuityEvaluator(benchmark)
    result = evaluator.evaluate(output)

    assert result.overall_continuity == 1.0
    assert result.passed


def test_evaluator_alias_matching() -> None:
    """ContinuityEvaluator must use alias matching."""
    benchmark = _make_benchmark(
        decisions=[
            _make_artifact("decision", "Use SQLite", aliases=["SQLite First", "SQLite DB"]),
        ],
    )
    output = _make_output(rendered_content="We went with SQLite First.")
    evaluator = ContinuityEvaluator(benchmark)
    result = evaluator.evaluate(output)

    assert result.decision_recall == 1.0


def test_evaluator_rationale_recall() -> None:
    """ContinuityEvaluator must compute rationale recall."""
    benchmark = _make_benchmark(
        rationales=[
            _make_artifact("rationale", "ACID compliance", rationale=""),
            _make_artifact("rationale", "Low latency", rationale=""),
        ],
    )
    output = _make_output(rendered_content="Because ACID compliance is needed.")
    evaluator = ContinuityEvaluator(benchmark)
    result = evaluator.evaluate(output)

    assert result.rationale_recall == 0.5
    assert result.rationale_recovered == 1


def test_evaluator_context_gain() -> None:
    """ContinuityEvaluator must compute context gain over head baseline."""
    benchmark = _make_benchmark(
        goals=[_make_artifact("goal", "Ship product")],
        decisions=[
            _make_artifact("decision", "Use SQLite"),
            _make_artifact("decision", "Use Redis"),
        ],
    )
    # Context output has everything
    context_output = _make_output(
        rendered_content="Goal: Ship product. Decision: Use SQLite. Decision: Use Redis."
    )
    # Head baseline only has partial info
    head_text = "Goal: Ship product. Decision: Use SQLite."

    evaluator = ContinuityEvaluator(benchmark)
    result = evaluator.evaluate_with_head_baseline(context_output, head_text)

    assert result.overall_continuity == 1.0
    assert result.context_gain > 0.0


def test_evaluator_gate_failure() -> None:
    """ContinuityEvaluator must detect gate failures."""
    benchmark = _make_benchmark(
        goals=[_make_artifact("goal", "Ship product")],
    )
    output = _make_output(rendered_content="No goals here.")
    evaluator = ContinuityEvaluator(benchmark)
    result = evaluator.evaluate(output)

    assert not result.passed
    assert "goal_recall" in result.gate_failures


def test_evaluator_recovered_and_missed() -> None:
    """ContinuityEvaluator must track recovered and missed artifacts."""
    benchmark = _make_benchmark(
        decisions=[
            _make_artifact("decision", "Use SQLite"),
            _make_artifact("decision", "Use Redis"),
        ],
        tasks=[
            _make_artifact("task", "Build API"),
        ],
    )
    output = _make_output(rendered_content="Decision: Use SQLite. Task: Build API.")
    evaluator = ContinuityEvaluator(benchmark)
    result = evaluator.evaluate(output)

    recovered_values = {a["canonical_value"] for a in result.recovered_artifacts}
    missed_values = {a["canonical_value"] for a in result.missed_artifacts}

    assert "Use SQLite" in recovered_values
    assert "Build API" in recovered_values
    assert "Use Redis" in missed_values


def test_evaluator_result_serialization() -> None:
    """ContinuityResult must be serializable."""
    benchmark = _make_benchmark(
        goals=[_make_artifact("goal", "Ship")],
    )
    output = _make_output(rendered_content="Goal: Ship.")
    evaluator = ContinuityEvaluator(benchmark)
    result = evaluator.evaluate(output)

    d = result.to_dict()
    assert d["benchmark_id"] == "test_benchmark"
    assert d["goal_recall"] == 1.0
    assert d["passed"] is True


def test_check_continuity_gates() -> None:
    """check_continuity_gates must return correct results."""
    benchmark = _make_benchmark(
        goals=[_make_artifact("goal", "Ship")],
    )
    output = _make_output(rendered_content="Goal: Ship.")
    evaluator = ContinuityEvaluator(benchmark)
    result = evaluator.evaluate(output)

    passed, failures = check_continuity_gates(result)
    assert passed
    assert len(failures) == 0


def test_check_continuity_gates_failure() -> None:
    """check_continuity_gates must detect failures."""
    benchmark = _make_benchmark(
        goals=[_make_artifact("goal", "Ship")],
    )
    output = _make_output(rendered_content="Nothing here.")
    evaluator = ContinuityEvaluator(benchmark)
    result = evaluator.evaluate(output)

    passed, failures = check_continuity_gates(result)
    assert not passed
    assert "goal_recall" in failures


# ── Benchmark File Loading Tests ───────────────────────────────────────────


def test_load_all_benchmarks() -> None:
    """All benchmark JSON files must load and be valid."""
    from pathlib import Path
    benchmark_dir = Path(__file__).parent.parent.parent / "rationalevault" / "evaluation" / "continuity_benchmarks"
    if not benchmark_dir.exists():
        pytest.skip("continuity_benchmarks directory not found")

    for p in benchmark_dir.glob("*.json"):
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        benchmark = ContinuityBenchmark.from_dict(data)
        assert benchmark.benchmark_id, f"Missing benchmark_id in {p.name}"
        assert benchmark.query, f"Missing query in {p.name}"
        assert len(benchmark.all_expected) > 0, f"No expected artifacts in {p.name}"


def test_all_benchmarks_compile() -> None:
    """All benchmarks must produce valid evaluations with Claude compiler."""
    from pathlib import Path
    from rationalevault.compilers.claude_context import ClaudeContextCompiler
    from rationalevault.knowledge.context_compiler import ContextPackage
    from rationalevault.knowledge.context_types import ContextCitation

    benchmark_dir = Path(__file__).parent.parent.parent / "rationalevault" / "evaluation" / "continuity_benchmarks"
    if not benchmark_dir.exists():
        pytest.skip("continuity_benchmarks directory not found")

    compiler = ClaudeContextCompiler()

    for p in benchmark_dir.glob("*.json"):
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        benchmark = ContinuityBenchmark.from_dict(data)

        # Create a mock package with relevant citations
        citations = []
        for artifact in benchmark.all_expected:
            citations.append(ContextCitation(
                source_type="memory",
                source_id=f"mem-{artifact.canonical_value[:8]}",
                title=artifact.canonical_value,
                content=artifact.canonical_value,
                relevance_score=0.9,
                confidence=0.9,
                reasons=[f"artifact_type:{artifact.artifact_type}"],
                source_event_ids=["evt-001"],
            ))

        package = ContextPackage(
            context_id="test",
            query=benchmark.query,
            profile="CONTEXT_CONSTRUCTION",
            created_at="2024-01-01T00:00:00",
            citations=citations,
            source_counts={"events": 0, "memories": len(citations), "knowledge": 0},
            timing={"total_ms": 10.0},
        )

        output = compiler.compile(package)
        evaluator = ContinuityEvaluator(benchmark)
        result = evaluator.evaluate(output)

        # All artifacts should be recoverable since we put them in the citations
        assert result.overall_continuity == 1.0, (
            f"{benchmark.benchmark_id}: overall_continuity={result.overall_continuity:.2f}, "
            f"missed={[a['canonical_value'] for a in result.missed_artifacts]}"
        )
