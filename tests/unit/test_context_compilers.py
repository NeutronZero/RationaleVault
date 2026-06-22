"""Sprint I6: Agent Compiler Framework — Unit Tests."""
from __future__ import annotations

import pytest

from rationalevault.compilers.compiler_output import CompilerMetadata, CompilerOutput
from rationalevault.compilers.context_compiler_base import ContextPackageCompiler
from rationalevault.compilers.claude_context import ClaudeContextCompiler
from rationalevault.compilers.opencode_context import OpenCodeContextCompiler
from rationalevault.compilers.cursor_context import CursorContextCompiler
from rationalevault.compilers.registry import (
    get_context_compiler,
    available_agents,
    reset_registry,
)
from rationalevault.knowledge.context_compiler import ContextPackage
from rationalevault.knowledge.context_types import ContextCitation


# ── Helpers ────────────────────────────────────────────────────────────────


def _make_citation(
    source_type: str = "memory",
    source_id: str = "mem-001",
    title: str = "Test Memory",
    content: str = "Test content about SQLite",
    relevance_score: float = 0.9,
    confidence: float = 0.85,
    reasons: list[str] | None = None,
    source_event_ids: list[str] | None = None,
) -> ContextCitation:
    return ContextCitation(
        source_type=source_type,
        source_id=source_id,
        title=title,
        content=content,
        relevance_score=relevance_score,
        confidence=confidence,
        reasons=reasons or ["memory_type:DECISION"],
        source_event_ids=source_event_ids or ["evt-001"],
    )


def _make_package(
    query: str = "Why did we choose SQLite?",
    profile: str = "DECISION_LOOKUP",
    citations: list[ContextCitation] | None = None,
    source_counts: dict[str, int] | None = None,
    timing: dict[str, float] | None = None,
) -> ContextPackage:
    if citations is None:
        citations = []
    if source_counts is None:
        source_counts = {
            "events": sum(1 for c in citations if c.source_type == "event"),
            "memories": sum(1 for c in citations if c.source_type == "memory"),
            "knowledge": sum(1 for c in citations if c.source_type == "knowledge"),
        }
    if timing is None:
        timing = {"total_ms": 15.0}
    return ContextPackage(
        context_id="test-ctx-001",
        query=query,
        profile=profile,
        created_at="2024-01-01T00:00:00",
        citations=citations,
        source_counts=source_counts,
        timing=timing,
    )


def _make_knowledge_citation(
    knowledge_type: str = "DECISION_LINEAGE",
    title: str = "SQLite Decision",
    content: str = "We chose SQLite for local storage",
    knowledge_domain: str = "ARCHITECTURE",
    confidence: float = 0.9,
) -> ContextCitation:
    return ContextCitation(
        source_type="knowledge",
        source_id="k-001",
        title=title,
        content=content,
        relevance_score=0.95,
        confidence=confidence,
        reasons=[f"knowledge_type:{knowledge_type}", f"domain:{knowledge_domain}"],
        source_event_ids=["evt-001"],
    )


# ── CompilerOutput Tests ──────────────────────────────────────────────────


def test_compiler_output_serialization() -> None:
    """CompilerOutput must round-trip through dict."""
    output = CompilerOutput(
        query="test query",
        profile="DECISION_LOOKUP",
        agent="Claude",
        format_name="markdown",
        rendered_content="# Test\nHello",
        citation_count=5,
        source_counts={"events": 2, "memories": 2, "knowledge": 1},
        compile_time_ms=12.5,
        generated_at="2024-01-01T00:00:00",
    )
    d = output.to_dict()
    output2 = CompilerOutput.from_dict(d)
    assert output2.query == output.query
    assert output2.agent == output.agent
    assert output2.citation_count == output.citation_count
    assert output2.compile_time_ms == output.compile_time_ms


def test_compiler_output_fields() -> None:
    """CompilerOutput must have all required fields."""
    output = CompilerOutput(
        query="q",
        profile="p",
        agent="a",
        format_name="f",
        rendered_content="c",
        citation_count=0,
        source_counts={},
        compile_time_ms=0.0,
        generated_at="t",
    )
    assert output.query == "q"
    assert output.profile == "p"
    assert output.agent == "a"


# ── CompilerMetadata Tests ────────────────────────────────────────────────


def test_compiler_metadata_serialization() -> None:
    """CompilerMetadata must round-trip through dict."""
    meta = CompilerMetadata(
        agent="Claude",
        format_name="markdown",
        supports_provenance=True,
        supports_hierarchical_sections=True,
        max_context_size=100_000,
    )
    d = meta.to_dict()
    meta2 = CompilerMetadata.from_dict(d)
    assert meta2.agent == meta.agent
    assert meta2.supports_provenance == meta.supports_provenance
    assert meta2.max_context_size == meta.max_context_size


# ── ClaudeContextCompiler Tests ────────────────────────────────────────────


def test_claude_compiler_basic() -> None:
    """ClaudeContextCompiler must produce valid output."""
    citations = [
        _make_citation("memory", "m1", "Decision: SQLite", "Use SQLite", reasons=["memory_type:DECISION"]),
        _make_citation("event", "e1", "Event: Deploy", "Deployed v1"),
        _make_knowledge_citation("ARCHITECTURE_PRINCIPLE", "No ORM", "Direct SQL only"),
    ]
    package = _make_package(citations=citations)
    compiler = ClaudeContextCompiler()
    output = compiler.compile(package)

    assert output.agent == "Claude"
    assert output.format_name == "markdown"
    assert output.citation_count == 3
    assert "# " in output.rendered_content
    assert output.compile_time_ms >= 0


def test_claude_compiler_determinism() -> None:
    """ClaudeContextCompiler must be deterministic."""
    citations = [_make_citation("memory", "m1", "Title", "Content")]
    package = _make_package(citations=citations)
    compiler = ClaudeContextCompiler()

    output1 = compiler.compile(package)
    output2 = compiler.compile(package)

    assert output1.rendered_content == output2.rendered_content


def test_claude_compiler_max_citations() -> None:
    """ClaudeContextCompiler must respect max_citations."""
    citations = [_make_citation("memory", f"m{i}", f"Mem {i}", f"Content {i}") for i in range(50)]
    package = _make_package(citations=citations)
    compiler = ClaudeContextCompiler()
    output = compiler.compile(package)

    assert output.citation_count == 30  # default max_citations


def test_claude_compiler_critical_constraints() -> None:
    """ClaudeContextCompiler must surface PROJECT_INVARIANT as Critical Constraints."""
    citations = [
        _make_knowledge_citation("PROJECT_INVARIANT", "No Vector DB", "Never use vector DB"),
        _make_knowledge_citation("LESSON", "Some Lesson", "Learned something"),
    ]
    package = _make_package(citations=citations)
    compiler = ClaudeContextCompiler()
    output = compiler.compile(package)

    assert "Critical Constraints" in output.rendered_content
    assert "No Vector DB" in output.rendered_content


def test_claude_compiler_decisions_section() -> None:
    """ClaudeContextCompiler must group decisions separately."""
    citations = [
        _make_knowledge_citation("DECISION_LINEAGE", "SQLite Choice", "Used SQLite"),
        _make_citation("memory", "m1", "Lesson", "Do X", reasons=["memory_type:LESSON_LEARNED"]),
    ]
    package = _make_package(citations=citations)
    compiler = ClaudeContextCompiler()
    output = compiler.compile(package)

    assert "Decisions & Rationale" in output.rendered_content


def test_claude_compiler_empty_package() -> None:
    """ClaudeContextCompiler must handle empty packages gracefully."""
    package = _make_package(citations=[])
    compiler = ClaudeContextCompiler()
    output = compiler.compile(package)

    assert output.citation_count == 0
    assert "Project Context" in output.rendered_content


def test_claude_compiler_source_traceability() -> None:
    """ClaudeContextCompiler must include source traceability."""
    citations = [
        _make_citation("memory", "m1", "Title", "Content", source_event_ids=["evt-1", "evt-2"]),
    ]
    package = _make_package(citations=citations)
    compiler = ClaudeContextCompiler()
    output = compiler.compile(package)

    assert "Source Traceability" in output.rendered_content
    assert "evt-1" in output.rendered_content


def test_claude_compiler_metadata() -> None:
    """ClaudeContextCompiler must expose correct metadata."""
    compiler = ClaudeContextCompiler()
    meta = compiler.metadata

    assert meta.agent == "Claude"
    assert meta.format_name == "markdown"
    assert meta.supports_provenance is True


def test_claude_compiler_profile_adaptation() -> None:
    """ClaudeContextCompiler must adapt to different profiles."""
    citations = [
        _make_citation("memory", "m1", "Decision", "R", reasons=["memory_type:DECISION"]),
        _make_knowledge_citation("ARCHITECTURE_PRINCIPLE", "Arch", "Design"),
    ]

    pkg_decision = _make_package(profile="DECISION_LOOKUP", citations=citations)
    pkg_knowledge = _make_package(profile="KNOWLEDGE_REVIEW", citations=citations)

    compiler = ClaudeContextCompiler()
    out_decision = compiler.compile(pkg_decision)
    out_knowledge = compiler.compile(pkg_knowledge)

    # Both should compile successfully with different profiles
    assert out_decision.profile == "DECISION_LOOKUP"
    assert out_knowledge.profile == "KNOWLEDGE_REVIEW"
    assert len(out_decision.rendered_content) > 0
    assert len(out_knowledge.rendered_content) > 0


# ── OpenCodeContextCompiler Tests ──────────────────────────────────────────


def test_opencode_compiler_basic() -> None:
    """OpenCodeContextCompiler must produce valid output."""
    citations = [
        _make_citation("memory", "m1", "Decision", "Use SQLite", reasons=["memory_type:DECISION"]),
        _make_knowledge_citation("PROJECT_INVARIANT", "No ORM", "Direct SQL"),
    ]
    package = _make_package(citations=citations)
    compiler = OpenCodeContextCompiler()
    output = compiler.compile(package)

    assert output.agent == "OpenCode"
    assert output.format_name == "markdown"
    assert output.citation_count == 2
    assert "# Project Context" in output.rendered_content


def test_opencode_compiler_determinism() -> None:
    """OpenCodeContextCompiler must be deterministic."""
    citations = [_make_citation("memory", "m1", "Title", "Content")]
    package = _make_package(citations=citations)
    compiler = OpenCodeContextCompiler()

    output1 = compiler.compile(package)
    output2 = compiler.compile(package)

    assert output1.rendered_content == output2.rendered_content


def test_opencode_compiler_empty() -> None:
    """OpenCodeContextCompiler must handle empty packages."""
    package = _make_package(citations=[])
    compiler = OpenCodeContextCompiler()
    output = compiler.compile(package)

    assert output.citation_count == 0
    assert "# Project Context" in output.rendered_content


def test_opencode_compiler_sections() -> None:
    """OpenCodeContextCompiler must have all expected sections."""
    citations = [
        _make_knowledge_citation("DECISION_LINEAGE", "Decision", "Use X"),
        _make_knowledge_citation("PROJECT_INVARIANT", "Constraint", "Never Y"),
        _make_citation("event", "e1", "Event: Deploy", "Deployed v1"),
    ]
    package = _make_package(citations=citations)
    compiler = OpenCodeContextCompiler()
    output = compiler.compile(package)

    assert "## Decisions" in output.rendered_content
    assert "## Constraints" in output.rendered_content
    assert "## Recent Changes" in output.rendered_content
    assert "## References" in output.rendered_content


# ── CursorContextCompiler Tests ────────────────────────────────────────────


def test_cursor_compiler_basic() -> None:
    """CursorContextCompiler must produce valid YAML output."""
    citations = [
        _make_citation("memory", "mem-abc123", "Title", "Content", source_event_ids=["evt-001"]),
    ]
    package = _make_package(citations=citations)
    compiler = CursorContextCompiler()
    output = compiler.compile(package)

    assert output.agent == "Cursor"
    assert output.format_name == "yaml"
    assert output.citation_count == 1
    assert "citations:" in output.rendered_content


def test_cursor_compiler_determinism() -> None:
    """CursorContextCompiler must be deterministic."""
    citations = [_make_citation("memory", "m1", "Title", "Content")]
    package = _make_package(citations=citations)
    compiler = CursorContextCompiler()

    output1 = compiler.compile(package)
    output2 = compiler.compile(package)

    assert output1.rendered_content == output2.rendered_content


def test_cursor_compiler_provenance() -> None:
    """CursorContextCompiler must include source_events in YAML."""
    citations = [
        _make_citation(
            "memory", "m1", "Title", "Content",
            source_event_ids=["evt-001", "evt-002"],
        ),
    ]
    package = _make_package(citations=citations)
    compiler = CursorContextCompiler()
    output = compiler.compile(package)

    assert "source_events:" in output.rendered_content
    assert "evt-001" in output.rendered_content
    assert "evt-002" in output.rendered_content


def test_cursor_compiler_empty() -> None:
    """CursorContextCompiler must handle empty packages."""
    package = _make_package(citations=[])
    compiler = CursorContextCompiler()
    output = compiler.compile(package)

    assert output.citation_count == 0
    assert "citations:" in output.rendered_content
    assert "query:" in output.rendered_content


def test_cursor_compiler_yaml_structure() -> None:
    """CursorContextCompiler must produce valid YAML structure."""
    citations = [
        _make_citation("memory", "m1", "Title", "Content", confidence=0.95),
    ]
    package = _make_package(citations=citations)
    compiler = CursorContextCompiler()
    output = compiler.compile(package)

    assert 'query: "Why did we choose SQLite?"' in output.rendered_content
    assert 'profile: "DECISION_LOOKUP"' in output.rendered_content
    assert "source_counts:" in output.rendered_content
    assert "confidence: 0.95" in output.rendered_content


# ── Registry Tests ─────────────────────────────────────────────────────────


def test_registry_available_agents() -> None:
    """Registry must list all available agents."""
    agents = available_agents()
    assert "claude" in agents
    assert "opencode" in agents
    assert "cursor" in agents


def test_registry_get_claude() -> None:
    """Registry must return ClaudeContextCompiler for 'claude'."""
    reset_registry()
    compiler = get_context_compiler("claude")
    assert isinstance(compiler, ClaudeContextCompiler)


def test_registry_get_opencode() -> None:
    """Registry must return OpenCodeContextCompiler for 'opencode'."""
    reset_registry()
    compiler = get_context_compiler("opencode")
    assert isinstance(compiler, OpenCodeContextCompiler)


def test_registry_get_cursor() -> None:
    """Registry must return CursorContextCompiler for 'cursor'."""
    reset_registry()
    compiler = get_context_compiler("cursor")
    assert isinstance(compiler, CursorContextCompiler)


def test_registry_singleton() -> None:
    """Registry must return the same instance on repeated calls."""
    reset_registry()
    c1 = get_context_compiler("claude")
    c2 = get_context_compiler("claude")
    assert c1 is c2


def test_registry_unknown_agent() -> None:
    """Registry must raise ValueError for unknown agents."""
    reset_registry()
    with pytest.raises(ValueError, match="Unknown agent"):
        get_context_compiler("unknown")


def test_registry_reset() -> None:
    """Registry reset must clear all instances."""
    reset_registry()
    c1 = get_context_compiler("claude")
    reset_registry()
    c2 = get_context_compiler("claude")
    assert c1 is not c2


# ── ABC Compliance Tests ───────────────────────────────────────────────────


def test_claude_is_context_compiler() -> None:
    """ClaudeContextCompiler must be a ContextPackageCompiler."""
    assert issubclass(ClaudeContextCompiler, ContextPackageCompiler)


def test_opencode_is_context_compiler() -> None:
    """OpenCodeContextCompiler must be a ContextPackageCompiler."""
    assert issubclass(OpenCodeContextCompiler, ContextPackageCompiler)


def test_cursor_is_context_compiler() -> None:
    """CursorContextCompiler must be a ContextPackageCompiler."""
    assert issubclass(CursorContextCompiler, ContextPackageCompiler)


# ── Compiler Evaluator Tests ───────────────────────────────────────────────


def test_evaluator_basic() -> None:
    """CompilerEvaluator must evaluate a basic compilation."""
    from rationalevault.evaluation.compiler_evaluator import CompilerEvaluator
    citations = [_make_citation("memory", "m1", "Title", "Content")]
    package = _make_package(citations=citations)
    compiler = ClaudeContextCompiler()
    evaluator = CompilerEvaluator()
    result = evaluator.evaluate(compiler, package)

    assert result.output_valid
    assert result.citation_preservation == 1.0
    assert result.memory_preservation == 1.0
    assert result.source_counts_match
    assert result.determinism_score == 1.0
    assert result.passed


def test_evaluator_empty_package() -> None:
    """CompilerEvaluator must handle empty packages."""
    from rationalevault.evaluation.compiler_evaluator import CompilerEvaluator
    package = _make_package(citations=[])
    compiler = ClaudeContextCompiler()
    evaluator = CompilerEvaluator()
    result = evaluator.evaluate(compiler, package)

    assert result.output_valid
    assert result.citation_count_input == 0
    assert result.citation_preservation == 1.0


def test_evaluator_section_coverage() -> None:
    """CompilerEvaluator must check section coverage."""
    from rationalevault.evaluation.compiler_evaluator import CompilerEvaluator
    citations = [
        _make_citation("memory", "m1", "Decision", "R", reasons=["memory_type:DECISION"]),
        _make_knowledge_citation("PROJECT_INVARIANT", "Constraint", "Never X"),
    ]
    package = _make_package(citations=citations)
    compiler = ClaudeContextCompiler()

    evaluator = CompilerEvaluator(expected_sections=["Decisions & Rationale", "Critical Constraints"])
    result = evaluator.evaluate(compiler, package)

    assert result.section_coverage == 1.0


def test_evaluator_all_compilers() -> None:
    """CompilerEvaluator must work with all compiler types."""
    from rationalevault.evaluation.compiler_evaluator import CompilerEvaluator
    citations = [_make_citation("memory", "m1", "Title", "Content")]
    package = _make_package(citations=citations)
    evaluator = CompilerEvaluator()

    for cls in [ClaudeContextCompiler, OpenCodeContextCompiler, CursorContextCompiler]:
        compiler = cls()
        result = evaluator.evaluate(compiler, package)
        assert result.output_valid, f"{cls.__name__} output invalid"
        # All compilers should preserve the citation itself
        assert result.citation_preservation == 1.0, f"{cls.__name__} lost citations"
        assert result.memory_preservation == 1.0, f"{cls.__name__} lost memories"
        assert result.determinism_score == 1.0, f"{cls.__name__} not deterministic"


def test_check_compiler_gates() -> None:
    """check_compiler_gates must return correct results."""
    from rationalevault.evaluation.compiler_evaluator import CompilerEvaluator, check_compiler_gates
    citations = [_make_citation("memory", "m1", "Title", "Content")]
    package = _make_package(citations=citations)
    compiler = ClaudeContextCompiler()
    evaluator = CompilerEvaluator()
    result = evaluator.evaluate(compiler, package)

    passed, failures = check_compiler_gates(result)
    assert passed
    assert len(failures) == 0


def test_evaluator_memory_preservation() -> None:
    """CompilerEvaluator must compute memory preservation correctly."""
    from rationalevault.evaluation.compiler_evaluator import CompilerEvaluator
    citations = [
        _make_citation("memory", "mem-001", "Memory One", "Content A"),
        _make_citation("memory", "mem-002", "Memory Two", "Content B"),
    ]
    package = _make_package(citations=citations)
    compiler = ClaudeContextCompiler()
    evaluator = CompilerEvaluator()
    result = evaluator.evaluate(compiler, package)

    assert result.memory_count_input == 2
    assert result.memory_preservation == 1.0


def test_evaluator_knowledge_preservation() -> None:
    """CompilerEvaluator must compute knowledge preservation correctly."""
    from rationalevault.evaluation.compiler_evaluator import CompilerEvaluator
    citations = [
        _make_knowledge_citation("ARCHITECTURE_PRINCIPLE", "No ORM", "Direct SQL"),
        _make_knowledge_citation("PROJECT_INVARIANT", "No Vector DB", "Never"),
    ]
    package = _make_package(citations=citations)
    compiler = ClaudeContextCompiler()
    evaluator = CompilerEvaluator()
    result = evaluator.evaluate(compiler, package)

    assert result.knowledge_count_input == 2
    assert result.knowledge_preservation == 1.0


def test_evaluator_event_preservation() -> None:
    """CompilerEvaluator must compute event preservation correctly."""
    from rationalevault.evaluation.compiler_evaluator import CompilerEvaluator
    citations = [
        _make_citation("event", "evt-001", "Event One", "Deployed version one to production"),
        _make_citation("event", "evt-002", "Event Two", "Migrated database schema"),
    ]
    package = _make_package(citations=citations)
    compiler = ClaudeContextCompiler()
    evaluator = CompilerEvaluator()
    result = evaluator.evaluate(compiler, package)

    assert result.event_count_input == 2
    assert result.event_preservation == 1.0


def test_evaluator_source_event_preservation() -> None:
    """CompilerEvaluator must compute source event preservation correctly."""
    from rationalevault.evaluation.compiler_evaluator import CompilerEvaluator
    citations = [
        _make_citation("memory", "m1", "Title", "Content", source_event_ids=["src-001", "src-002"]),
        _make_citation("event", "e1", "Event Details", "Something happened here", source_event_ids=["src-003"]),
    ]
    package = _make_package(citations=citations)
    compiler = ClaudeContextCompiler()
    evaluator = CompilerEvaluator()
    result = evaluator.evaluate(compiler, package)

    assert result.source_events_input == 3
    assert result.source_event_preservation == 1.0


def test_evaluator_claude_source_event_preservation() -> None:
    """ClaudeContextCompiler must preserve source events in traceability section."""
    from rationalevault.evaluation.compiler_evaluator import CompilerEvaluator
    citations = [
        _make_citation("memory", "m1", "Memory Title", "Content here", source_event_ids=["evt-abc", "evt-def"]),
    ]
    package = _make_package(citations=citations)
    compiler = ClaudeContextCompiler()
    evaluator = CompilerEvaluator()
    result = evaluator.evaluate(compiler, package)

    assert result.source_events_input == 2
    assert result.source_event_preservation == 1.0
    assert "evt-abc" in compiler.compile(package).rendered_content


def test_evaluator_compression_ratio() -> None:
    """CompilerEvaluator must compute compression ratio correctly."""
    from rationalevault.evaluation.compiler_evaluator import CompilerEvaluator
    citations = [
        _make_citation("memory", "m1", "Short", "Hi"),
    ]
    package = _make_package(citations=citations)
    compiler = ClaudeContextCompiler()
    evaluator = CompilerEvaluator()
    result = evaluator.evaluate(compiler, package)

    assert result.input_content_chars > 0
    assert result.compression_ratio > 0


def test_evaluator_keyword_coverage() -> None:
    """CompilerEvaluator must compute keyword coverage correctly."""
    from rationalevault.evaluation.compiler_evaluator import CompilerEvaluator
    citations = [_make_citation("memory", "m1", "SQLite Decision", "Use SQLite for storage")]
    package = _make_package(citations=citations)
    compiler = ClaudeContextCompiler()

    evaluator = CompilerEvaluator(expected_keywords=["SQLite", "storage"])
    result = evaluator.evaluate(compiler, package)

    assert result.keyword_coverage == 1.0


def test_evaluator_determinism_check() -> None:
    """CompilerEvaluator must verify determinism across two compilations."""
    from rationalevault.evaluation.compiler_evaluator import CompilerEvaluator
    citations = [_make_citation("memory", "m1", "Title", "Content")]
    package = _make_package(citations=citations)
    compiler = ClaudeContextCompiler()
    evaluator = CompilerEvaluator()
    result = evaluator.evaluate(compiler, package)

    assert result.determinism_score == 1.0


def test_evaluator_mixed_sources() -> None:
    """CompilerEvaluator must handle mixed source types correctly."""
    from rationalevault.evaluation.compiler_evaluator import CompilerEvaluator
    citations = [
        _make_citation("memory", "m1", "Memory Title", "This is memory content"),
        _make_knowledge_citation("LESSON", "Lesson Learned", "Important lesson content here"),
        _make_citation("event", "e1", "Event Summary", "Something happened with details"),
    ]
    package = _make_package(citations=citations)
    compiler = ClaudeContextCompiler()
    evaluator = CompilerEvaluator()
    result = evaluator.evaluate(compiler, package)

    assert result.memory_count_input == 1
    assert result.knowledge_count_input == 1
    assert result.event_count_input == 1
    assert result.citation_count_input == 3
    assert result.passed


def test_evaluator_result_serialization() -> None:
    """CompilerEvalResult must be serializable."""
    from rationalevault.evaluation.compiler_evaluator import CompilerEvaluator
    citations = [_make_citation("memory", "m1", "Title", "Content")]
    package = _make_package(citations=citations)
    compiler = ClaudeContextCompiler()
    evaluator = CompilerEvaluator()
    result = evaluator.evaluate(compiler, package)

    d = result.to_dict()
    assert d["agent"] == "Claude"
    assert d["citation_preservation"] == 1.0
    assert d["memory_preservation"] == 1.0
    assert d["passed"] is True


def test_evaluator_benchmark_mode() -> None:
    """CompilerEvaluator must support benchmark-specific thresholds."""
    from rationalevault.evaluation.compiler_evaluator import CompilerEvaluator
    from rationalevault.evaluation.compiler_benchmark_schema import CompilerBenchmark
    citations = [_make_citation("memory", "m1", "Title", "Content")]
    package = _make_package(citations=citations)
    compiler = ClaudeContextCompiler()

    benchmark = CompilerBenchmark(
        benchmark_id="test-bench",
        min_citation_preservation=0.50,
        min_memory_preservation=0.50,
    )
    evaluator = CompilerEvaluator(benchmark_id="test-bench")
    result = evaluator.evaluate_benchmark(compiler, package, benchmark)

    assert result.benchmark_id == "test-bench"
    assert result.passed
