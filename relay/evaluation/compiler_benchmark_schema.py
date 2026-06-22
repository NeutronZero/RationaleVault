"""Relay Compiler Benchmark Schema — Ground truth for compiler evaluation.

CompilerBenchmark defines expected preservation behavior for a specific
query + context package combination. Used by CompilerEvaluator to verify
that compilers preserve the right information.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CompilerBenchmark:
    """Ground truth for evaluating a ContextPackageCompiler.

    Defines what the compiler should preserve for a given query.
    """
    benchmark_id: str
    benchmark_version: int = 1
    query: str = ""
    agent: str = ""
    expected_profile: str = ""

    # Citation counts
    expected_total_citations: int = 0
    expected_memory_citations: int = 0
    expected_knowledge_citations: int = 0
    expected_event_citations: int = 0

    # Source IDs that must appear in output
    expected_source_ids: list[str] = field(default_factory=list)

    # Source event IDs that must appear in output
    expected_source_event_ids: list[str] = field(default_factory=list)

    # Keywords that must appear in rendered content
    expected_keywords: list[str] = field(default_factory=list)

    # Expected sections
    expected_sections: list[str] = field(default_factory=list)

    # Preservation thresholds
    min_citation_preservation: float = 0.80
    min_memory_preservation: float = 0.80
    min_knowledge_preservation: float = 0.80
    min_event_preservation: float = 0.80
    min_source_event_preservation: float = 0.80
    min_compression_ratio: float = 0.1  # output should be at least 10% of input

    def to_dict(self) -> dict[str, Any]:
        return {
            "benchmark_id": self.benchmark_id,
            "benchmark_version": self.benchmark_version,
            "query": self.query,
            "agent": self.agent,
            "expected_profile": self.expected_profile,
            "expected_total_citations": self.expected_total_citations,
            "expected_memory_citations": self.expected_memory_citations,
            "expected_knowledge_citations": self.expected_knowledge_citations,
            "expected_event_citations": self.expected_event_citations,
            "expected_source_ids": self.expected_source_ids,
            "expected_source_event_ids": self.expected_source_event_ids,
            "expected_keywords": self.expected_keywords,
            "expected_sections": self.expected_sections,
            "min_citation_preservation": self.min_citation_preservation,
            "min_memory_preservation": self.min_memory_preservation,
            "min_knowledge_preservation": self.min_knowledge_preservation,
            "min_event_preservation": self.min_event_preservation,
            "min_source_event_preservation": self.min_source_event_preservation,
            "min_compression_ratio": self.min_compression_ratio,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CompilerBenchmark:
        return cls(
            benchmark_id=data["benchmark_id"],
            benchmark_version=data.get("benchmark_version", 1),
            query=data.get("query", ""),
            agent=data.get("agent", ""),
            expected_profile=data.get("expected_profile", ""),
            expected_total_citations=data.get("expected_total_citations", 0),
            expected_memory_citations=data.get("expected_memory_citations", 0),
            expected_knowledge_citations=data.get("expected_knowledge_citations", 0),
            expected_event_citations=data.get("expected_event_citations", 0),
            expected_source_ids=data.get("expected_source_ids", []),
            expected_source_event_ids=data.get("expected_source_event_ids", []),
            expected_keywords=data.get("expected_keywords", []),
            expected_sections=data.get("expected_sections", []),
            min_citation_preservation=data.get("min_citation_preservation", 0.80),
            min_memory_preservation=data.get("min_memory_preservation", 0.80),
            min_knowledge_preservation=data.get("min_knowledge_preservation", 0.80),
            min_event_preservation=data.get("min_event_preservation", 0.80),
            min_source_event_preservation=data.get("min_source_event_preservation", 0.80),
            min_compression_ratio=data.get("min_compression_ratio", 0.1),
        )
