"""RationaleVault Context Benchmark Schema — Ground truth for context evaluation.

Defines the expected context composition for a given query, used by
ContextEvaluator to measure context quality metrics.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ContextBenchmark:
    """Ground truth for context evaluation.

    Defines what a perfect ContextPackage should contain for a given query.
    """
    benchmark_id: str
    benchmark_version: int = 1
    benchmark_type: str = "synthetic"  # synthetic | real_world

    # Query context
    query: str = ""
    expected_profile: str = ""

    # Expected source composition
    expected_event_count: int = 0
    expected_memory_count: int = 0
    expected_knowledge_count: int = 0

    # Expected content (titles or keywords that should appear)
    expected_event_types: list[str] = field(default_factory=list)
    expected_memory_titles: list[str] = field(default_factory=list)
    expected_knowledge_titles: list[str] = field(default_factory=list)

    # Expected keywords that should appear in citations
    expected_keywords: list[str] = field(default_factory=list)

    # Quality expectations
    expected_min_completeness: float = 0.67
    expected_min_precision: float = 0.70
    expected_max_redundancy: float = 0.25

    # Metadata
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "benchmark_id": self.benchmark_id,
            "benchmark_version": self.benchmark_version,
            "benchmark_type": self.benchmark_type,
            "query": self.query,
            "expected_profile": self.expected_profile,
            "expected_event_count": self.expected_event_count,
            "expected_memory_count": self.expected_memory_count,
            "expected_knowledge_count": self.expected_knowledge_count,
            "expected_event_types": self.expected_event_types,
            "expected_memory_titles": self.expected_memory_titles,
            "expected_knowledge_titles": self.expected_knowledge_titles,
            "expected_keywords": self.expected_keywords,
            "expected_min_completeness": self.expected_min_completeness,
            "expected_min_precision": self.expected_min_precision,
            "expected_max_redundancy": self.expected_max_redundancy,
            "description": self.description,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ContextBenchmark:
        return cls(
            benchmark_id=d["benchmark_id"],
            benchmark_version=d.get("benchmark_version", 1),
            benchmark_type=d.get("benchmark_type", "synthetic"),
            query=d.get("query", ""),
            expected_profile=d.get("expected_profile", ""),
            expected_event_count=d.get("expected_event_count", 0),
            expected_memory_count=d.get("expected_memory_count", 0),
            expected_knowledge_count=d.get("expected_knowledge_count", 0),
            expected_event_types=d.get("expected_event_types", []),
            expected_memory_titles=d.get("expected_memory_titles", []),
            expected_knowledge_titles=d.get("expected_knowledge_titles", []),
            expected_keywords=d.get("expected_keywords", []),
            expected_min_completeness=d.get("expected_min_completeness", 0.67),
            expected_min_precision=d.get("expected_min_precision", 0.70),
            expected_max_redundancy=d.get("expected_max_redundancy", 0.25),
            description=d.get("description", ""),
            metadata=d.get("metadata", {}),
        )
