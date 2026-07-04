"""RationaleVault Compiler Evaluator — Comprehensive evaluation for ContextPackageCompiler outputs.

Evaluates CompilerOutput for preservation quality metrics:
  - output_valid: rendered_content is non-empty
  - citation_preservation: % of input citations represented in output
  - memory_preservation: % of memory citations in output
  - knowledge_preservation: % of knowledge citations in output
  - event_preservation: % of event citations in output
  - source_event_preservation: % of source_event_ids in output
  - compression_ratio: output size / input content size
  - keyword_coverage: % of expected keywords in output
  - section_coverage: expected sections present
  - compile_latency_ms: within budget
  - determinism: same input → same output

Gate thresholds:
  - MIN_CITATION_PRESERVATION = 0.80
  - MIN_SOURCE_EVENT_PRESERVATION = 0.80
  - MAX_COMPILE_LATENCY_MS = 100.0
  - MIN_DETERMINISM_SCORE = 1.0
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from rationalevault.compilers.context_compiler_base import ContextPackageCompiler

if TYPE_CHECKING:
    from rationalevault.evaluation.compiler_benchmark_schema import CompilerBenchmark
    from rationalevault.knowledge.context_compiler import ContextPackage
    from rationalevault.knowledge.context_types import ContextCitation


# ── Gate Thresholds ────────────────────────────────────────────────────────

MIN_CITATION_PRESERVATION = 0.80
MIN_MEMORY_PRESERVATION = 0.80
MIN_KNOWLEDGE_PRESERVATION = 0.80
MIN_EVENT_PRESERVATION = 0.80
MIN_SOURCE_EVENT_PRESERVATION = 0.80
MAX_COMPILE_LATENCY_MS = 100.0
MAX_RENDERED_CHARS = 500_000
MIN_DETERMINISM_SCORE = 1.0
MIN_KEYWORD_COVERAGE = 0.50
MIN_SECTION_COVERAGE = 0.67


# ── Evaluation Result ──────────────────────────────────────────────────────


@dataclass
class CompilerEvalResult:
    """Evaluation result for a single compiler output."""
    agent: str
    format_name: str
    benchmark_id: str

    # Output metrics
    output_valid: bool
    rendered_chars: int
    rendered_lines: int

    # Citation preservation
    citation_count_input: int
    citation_count_output: int
    citation_preservation: float

    # Source-type preservation
    memory_count_input: int
    memory_preservation: float
    knowledge_count_input: int
    knowledge_preservation: float
    event_count_input: int
    event_preservation: float

    # Source event preservation
    source_events_input: int
    source_events_in_output: int
    source_event_preservation: float

    # Compression
    input_content_chars: int
    compression_ratio: float

    # Section and keyword coverage
    section_coverage: float
    keyword_coverage: float

    # Source counts metadata
    source_counts_match: bool

    # Performance
    compile_latency_ms: float
    determinism_score: float
    within_latency_budget: bool
    within_size_budget: bool

    # Gate status
    passed: bool = False
    gate_failures: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, any]:
        return {
            "agent": self.agent,
            "format_name": self.format_name,
            "benchmark_id": self.benchmark_id,
            "output_valid": self.output_valid,
            "rendered_chars": self.rendered_chars,
            "rendered_lines": self.rendered_lines,
            "citation_count_input": self.citation_count_input,
            "citation_count_output": self.citation_count_output,
            "citation_preservation": self.citation_preservation,
            "memory_count_input": self.memory_count_input,
            "memory_preservation": self.memory_preservation,
            "knowledge_count_input": self.knowledge_count_input,
            "knowledge_preservation": self.knowledge_preservation,
            "event_count_input": self.event_count_input,
            "event_preservation": self.event_preservation,
            "source_events_input": self.source_events_input,
            "source_events_in_output": self.source_events_in_output,
            "source_event_preservation": self.source_event_preservation,
            "input_content_chars": self.input_content_chars,
            "compression_ratio": self.compression_ratio,
            "section_coverage": self.section_coverage,
            "keyword_coverage": self.keyword_coverage,
            "source_counts_match": self.source_counts_match,
            "compile_latency_ms": self.compile_latency_ms,
            "determinism_score": self.determinism_score,
            "within_latency_budget": self.within_latency_budget,
            "within_size_budget": self.within_size_budget,
            "passed": self.passed,
            "gate_failures": self.gate_failures,
        }


# ── Preservation Helpers ───────────────────────────────────────────────────


def _count_by_type(citations: list[ContextCitation], source_type: str) -> int:
    return sum(1 for c in citations if c.source_type == source_type)


def _count_source_events(citations: list[ContextCitation]) -> set[str]:
    events: set[str] = set()
    for c in citations:
        events.update(c.source_event_ids)
    return events


def _citation_is_preserved(citation: ContextCitation, rendered: str) -> bool:
    """Check if a citation is represented in rendered output.

    A citation is considered preserved if:
    - Its source_id appears in output, OR
    - Its title appears in output (for events, titles are rendered directly), OR
    - A significant substring of its content appears in output
    """
    if citation.source_id and citation.source_id in rendered:
        return True
    if citation.title and len(citation.title) >= 3 and citation.title in rendered:
        return True
    if citation.content and len(citation.content) >= 10:
        if citation.content[:20] in rendered:
            return True
    return False


def _count_source_ids_in_output(citations: list[ContextCitation], rendered: str) -> int:
    """Count how many citations are represented in rendered output."""
    return sum(1 for c in citations if _citation_is_preserved(c, rendered))


def _count_source_events_in_output(citations: list[ContextCitation], rendered: str) -> int:
    """Count how many unique source_event_ids appear in rendered output."""
    all_events = _count_source_events(citations)
    found = sum(1 for eid in all_events if eid in rendered)
    return found


def _compute_input_content_chars(citations: list[ContextCitation]) -> int:
    """Compute total content characters in input citations."""
    return sum(len(c.title) + len(c.content) for c in citations)


# ── Evaluator ──────────────────────────────────────────────────────────────


class CompilerEvaluator:
    """Evaluates ContextPackageCompiler outputs against preservation gates."""

    def __init__(
        self,
        expected_sections: list[str] | None = None,
        expected_keywords: list[str] | None = None,
        citation_latency_budget_ms: float = MAX_COMPILE_LATENCY_MS,
        benchmark_id: str = "unnamed",
    ) -> None:
        self.expected_sections = expected_sections or []
        self.expected_keywords = expected_keywords or []
        self.citation_latency_budget_ms = citation_latency_budget_ms
        self.benchmark_id = benchmark_id

    def evaluate(
        self,
        compiler: ContextPackageCompiler,
        package: ContextPackage,
    ) -> CompilerEvalResult:
        """Run a compiler and evaluate the output.

        Args:
            compiler: The ContextPackageCompiler to test.
            package: The ContextPackage to compile.

        Returns:
            CompilerEvalResult with all metrics and gate status.
        """
        # Compile twice for determinism check
        output1 = compiler.compile(package)
        output2 = compiler.compile(package)

        rendered = output1.rendered_content
        citations = package.citations

        # Basic validity
        output_valid = bool(rendered.strip())
        rendered_chars = len(rendered)
        rendered_lines = rendered.count("\n") + 1

        # Citation preservation (by source_id in output)
        citation_count_input = len(citations)
        citation_count_output = output1.citation_count
        source_ids_found = _count_source_ids_in_output(citations, rendered)
        if citation_count_input > 0:
            citation_preservation = source_ids_found / citation_count_input
        else:
            citation_preservation = 1.0

        # Source-type preservation
        memory_input = _count_by_type(citations, "memory")
        memory_in_output = _count_source_ids_in_output(
            [c for c in citations if c.source_type == "memory"], rendered
        )
        memory_preservation = memory_in_output / memory_input if memory_input > 0 else 1.0

        knowledge_input = _count_by_type(citations, "knowledge")
        knowledge_in_output = _count_source_ids_in_output(
            [c for c in citations if c.source_type == "knowledge"], rendered
        )
        knowledge_preservation = knowledge_in_output / knowledge_input if knowledge_input > 0 else 1.0

        event_input = _count_by_type(citations, "event")
        event_in_output = _count_source_ids_in_output(
            [c for c in citations if c.source_type == "event"], rendered
        )
        event_preservation = event_in_output / event_input if event_input > 0 else 1.0

        # Source event preservation
        all_source_events = _count_source_events(citations)
        source_events_in_output = _count_source_events_in_output(citations, rendered)
        source_event_preservation = (
            source_events_in_output / len(all_source_events)
            if all_source_events else 1.0
        )

        # Compression ratio
        input_content_chars = _compute_input_content_chars(citations)
        compression_ratio = rendered_chars / input_content_chars if input_content_chars > 0 else 1.0

        # Section coverage
        if self.expected_sections:
            sections_found = sum(
                1 for s in self.expected_sections if s in rendered
            )
            section_coverage = sections_found / len(self.expected_sections)
        else:
            section_coverage = 1.0

        # Keyword coverage
        if self.expected_keywords:
            keywords_found = sum(
                1 for kw in self.expected_keywords if kw.lower() in rendered.lower()
            )
            keyword_coverage = keywords_found / len(self.expected_keywords)
        else:
            keyword_coverage = 1.0

        # Source counts match
        source_counts_match = output1.source_counts == package.source_counts

        # Latency
        compile_latency_ms = output1.compile_time_ms
        within_latency = compile_latency_ms <= self.citation_latency_budget_ms

        # Size budget
        within_size = rendered_chars <= MAX_RENDERED_CHARS

        # Determinism
        determinism_score = 1.0 if rendered == output2.rendered_content else 0.0

        # Gates
        failures = []
        if not output_valid:
            failures.append("output_invalid")
        if citation_preservation < MIN_CITATION_PRESERVATION:
            failures.append("citation_preservation")
        if memory_preservation < MIN_MEMORY_PRESERVATION:
            failures.append("memory_preservation")
        if knowledge_preservation < MIN_KNOWLEDGE_PRESERVATION:
            failures.append("knowledge_preservation")
        if event_preservation < MIN_EVENT_PRESERVATION:
            failures.append("event_preservation")
        if source_event_preservation < MIN_SOURCE_EVENT_PRESERVATION:
            failures.append("source_event_preservation")
        if not source_counts_match:
            failures.append("source_counts_mismatch")
        if not within_latency:
            failures.append("compile_latency")
        if not within_size:
            failures.append("rendered_size")
        if determinism_score < MIN_DETERMINISM_SCORE:
            failures.append("determinism")
        if keyword_coverage < MIN_KEYWORD_COVERAGE:
            failures.append("keyword_coverage")
        if section_coverage < MIN_SECTION_COVERAGE:
            failures.append("section_coverage")

        return CompilerEvalResult(
            agent=compiler.agent_name,
            format_name=compiler.format_name,
            benchmark_id=self.benchmark_id,
            output_valid=output_valid,
            rendered_chars=rendered_chars,
            rendered_lines=rendered_lines,
            citation_count_input=citation_count_input,
            citation_count_output=citation_count_output,
            citation_preservation=citation_preservation,
            memory_count_input=memory_input,
            memory_preservation=memory_preservation,
            knowledge_count_input=knowledge_input,
            knowledge_preservation=knowledge_preservation,
            event_count_input=event_input,
            event_preservation=event_preservation,
            source_events_input=len(all_source_events),
            source_events_in_output=source_events_in_output,
            source_event_preservation=source_event_preservation,
            input_content_chars=input_content_chars,
            compression_ratio=compression_ratio,
            section_coverage=section_coverage,
            keyword_coverage=keyword_coverage,
            source_counts_match=source_counts_match,
            compile_latency_ms=compile_latency_ms,
            determinism_score=determinism_score,
            within_latency_budget=within_latency,
            within_size_budget=within_size,
            passed=len(failures) == 0,
            gate_failures=failures,
        )

    def evaluate_benchmark(
        self,
        compiler: ContextPackageCompiler,
        package: ContextPackage,
        benchmark: CompilerBenchmark,
    ) -> CompilerEvalResult:
        """Evaluate using benchmark-specific thresholds.

        Uses the benchmark's custom preservation thresholds instead of defaults.
        """
        result = self.evaluate(compiler, package)

        # Override gate failures with benchmark-specific thresholds
        failures = list(result.gate_failures)

        # Remove default preservation failures and recheck with benchmark thresholds
        for gate in ["citation_preservation", "memory_preservation",
                      "knowledge_preservation", "event_preservation",
                      "source_event_preservation"]:
            if gate in failures:
                failures.remove(gate)

        if result.citation_preservation < benchmark.min_citation_preservation:
            failures.append("citation_preservation")
        if result.memory_preservation < benchmark.min_memory_preservation:
            failures.append("memory_preservation")
        if result.knowledge_preservation < benchmark.min_knowledge_preservation:
            failures.append("knowledge_preservation")
        if result.event_preservation < benchmark.min_event_preservation:
            failures.append("event_preservation")
        if result.source_event_preservation < benchmark.min_source_event_preservation:
            failures.append("source_event_preservation")

        result.gate_failures = failures
        result.passed = len(failures) == 0
        result.benchmark_id = benchmark.benchmark_id

        return result


def check_compiler_gates(result: CompilerEvalResult) -> tuple[bool, list[str]]:
    """Check if a CompilerEvalResult passes all gates.

    Returns:
        (passed, list_of_failed_gate_names)
    """
    return result.passed, list(result.gate_failures)
