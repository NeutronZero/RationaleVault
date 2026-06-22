"""RationaleVault Knowledge Benchmark Schema — Ground truth for knowledge synthesis evaluation.

Versioned to track changes in synthesis rules over time.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class KnowledgeBenchmark:
    """Ground truth for knowledge synthesis evaluation.

    Versioned to track changes in synthesis rules over time.
    Each benchmark represents expected knowledge output for a given input corpus.
    """
    benchmark_id: str
    benchmark_type: str  # synthetic | real_world
    benchmark_version: int = 1

    # Expected knowledge objects (what synthesis should produce)
    expected_architecture_principles: list[dict[str, Any]] = field(default_factory=list)
    expected_project_invariants: list[dict[str, Any]] = field(default_factory=list)
    expected_lessons: list[dict[str, Any]] = field(default_factory=list)
    expected_failure_patterns: list[dict[str, Any]] = field(default_factory=list)
    expected_workflow_patterns: list[dict[str, Any]] = field(default_factory=list)
    expected_research_findings: list[dict[str, Any]] = field(default_factory=list)
    expected_decision_lineages: list[dict[str, Any]] = field(default_factory=list)

    # Expected relations
    expected_contradictions: list[tuple[str, str]] = field(default_factory=list)
    expected_supports: list[tuple[str, str]] = field(default_factory=list)

    # Source memories (what memories should be present)
    expected_memory_count: int = 0
    expected_memory_types: list[str] = field(default_factory=list)

    # Expected knowledge types (for benchmark-relative coverage)
    expected_knowledge_types: list[str] = field(default_factory=list)

    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KnowledgeBenchmark:
        return cls(
            benchmark_id=data["benchmark_id"],
            benchmark_type=data["benchmark_type"],
            benchmark_version=data.get("benchmark_version", 1),
            expected_architecture_principles=data.get("expected_architecture_principles") or [],
            expected_project_invariants=data.get("expected_project_invariants") or [],
            expected_lessons=data.get("expected_lessons") or [],
            expected_failure_patterns=data.get("expected_failure_patterns") or [],
            expected_workflow_patterns=data.get("expected_workflow_patterns") or [],
            expected_research_findings=data.get("expected_research_findings") or [],
            expected_decision_lineages=data.get("expected_decision_lineages") or [],
            expected_contradictions=[tuple(c) for c in data.get("expected_contradictions") or []],
            expected_supports=[tuple(s) for s in data.get("expected_supports") or []],
            expected_memory_count=data.get("expected_memory_count", 0),
            expected_memory_types=data.get("expected_memory_types") or [],
            expected_knowledge_types=data.get("expected_knowledge_types") or [],
            metadata=data.get("metadata") or {},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "benchmark_id": self.benchmark_id,
            "benchmark_type": self.benchmark_type,
            "benchmark_version": self.benchmark_version,
            "expected_architecture_principles": self.expected_architecture_principles,
            "expected_project_invariants": self.expected_project_invariants,
            "expected_lessons": self.expected_lessons,
            "expected_failure_patterns": self.expected_failure_patterns,
            "expected_workflow_patterns": self.expected_workflow_patterns,
            "expected_research_findings": self.expected_research_findings,
            "expected_decision_lineages": self.expected_decision_lineages,
            "expected_contradictions": self.expected_contradictions,
            "expected_supports": self.expected_supports,
            "expected_memory_count": self.expected_memory_count,
            "expected_memory_types": self.expected_memory_types,
            "expected_knowledge_types": self.expected_knowledge_types,
            "metadata": self.metadata,
        }

    @property
    def all_expected_knowledge(self) -> list[dict[str, Any]]:
        """Flatten all expected knowledge into a single list."""
        return (
            self.expected_architecture_principles
            + self.expected_project_invariants
            + self.expected_lessons
            + self.expected_failure_patterns
            + self.expected_workflow_patterns
            + self.expected_research_findings
            + self.expected_decision_lineages
        )
