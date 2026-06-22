"""RationaleVault Continuity Benchmark Schema — Ground truth for context deliverability validation.

ExpectedArtifact provides alias-aware matching so recovery checks are
robust against paraphrasing while remaining fully deterministic.

ContinuityBenchmark defines what Agent B must recover from a ContextPackage
compiled for a specific query.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExpectedArtifact:
    """An artifact that Agent B must recover from context.

    Recovery is checked by matching canonical_value OR any alias
    against the rendered compiler output. Case-insensitive.
    """
    artifact_type: str          # "goal", "decision", "task", "question", "knowledge", "rationale"
    canonical_value: str        # primary text to match
    aliases: list[str] = field(default_factory=list)  # acceptable paraphrases
    severity: str = "medium"    # "low", "medium", "high", "critical"
    rationale: str = ""         # why this artifact matters (for rationale recall)

    def matches(self, text: str) -> bool:
        """Check if this artifact appears in text (case-insensitive)."""
        text_lower = text.lower()
        if self.canonical_value.lower() in text_lower:
            return True
        return any(alias.lower() in text_lower for alias in self.aliases)

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_type": self.artifact_type,
            "canonical_value": self.canonical_value,
            "aliases": self.aliases,
            "severity": self.severity,
            "rationale": self.rationale,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExpectedArtifact:
        return cls(
            artifact_type=data["artifact_type"],
            canonical_value=data["canonical_value"],
            aliases=data.get("aliases", []),
            severity=data.get("severity", "medium"),
            rationale=data.get("rationale", ""),
        )


@dataclass
class ContinuityBenchmark:
    """Ground truth for evaluating context deliverability.

    Defines what Agent A created and what Agent B must recover
    from a ContextPackage compiled for a specific query.
    """
    benchmark_id: str
    benchmark_version: int = 1
    scenario_name: str = ""
    description: str = ""

    # Query to compile context for
    query: str = ""

    # What Agent B must recover
    expected_goals: list[ExpectedArtifact] = field(default_factory=list)
    expected_decisions: list[ExpectedArtifact] = field(default_factory=list)
    expected_tasks: list[ExpectedArtifact] = field(default_factory=list)
    expected_questions: list[ExpectedArtifact] = field(default_factory=list)
    expected_knowledge: list[ExpectedArtifact] = field(default_factory=list)
    expected_rationales: list[ExpectedArtifact] = field(default_factory=list)

    # Continuity thresholds
    min_goal_recall: float = 1.0
    min_decision_recall: float = 1.0
    min_rationale_recall: float = 0.95
    min_task_recall: float = 0.95
    min_knowledge_recall: float = 0.80
    min_overall_continuity: float = 0.90
    min_context_gain: float = 0.10

    @property
    def all_expected(self) -> list[ExpectedArtifact]:
        """All expected artifacts across all categories."""
        return (
            self.expected_goals
            + self.expected_decisions
            + self.expected_tasks
            + self.expected_questions
            + self.expected_knowledge
            + self.expected_rationales
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "benchmark_id": self.benchmark_id,
            "benchmark_version": self.benchmark_version,
            "scenario_name": self.scenario_name,
            "description": self.description,
            "query": self.query,
            "expected_goals": [a.to_dict() for a in self.expected_goals],
            "expected_decisions": [a.to_dict() for a in self.expected_decisions],
            "expected_tasks": [a.to_dict() for a in self.expected_tasks],
            "expected_questions": [a.to_dict() for a in self.expected_questions],
            "expected_knowledge": [a.to_dict() for a in self.expected_knowledge],
            "expected_rationales": [a.to_dict() for a in self.expected_rationales],
            "min_goal_recall": self.min_goal_recall,
            "min_decision_recall": self.min_decision_recall,
            "min_rationale_recall": self.min_rationale_recall,
            "min_task_recall": self.min_task_recall,
            "min_knowledge_recall": self.min_knowledge_recall,
            "min_overall_continuity": self.min_overall_continuity,
            "min_context_gain": self.min_context_gain,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContinuityBenchmark:
        return cls(
            benchmark_id=data["benchmark_id"],
            benchmark_version=data.get("benchmark_version", 1),
            scenario_name=data.get("scenario_name", ""),
            description=data.get("description", ""),
            query=data.get("query", ""),
            expected_goals=[ExpectedArtifact.from_dict(a) for a in data.get("expected_goals", [])],
            expected_decisions=[ExpectedArtifact.from_dict(a) for a in data.get("expected_decisions", [])],
            expected_tasks=[ExpectedArtifact.from_dict(a) for a in data.get("expected_tasks", [])],
            expected_questions=[ExpectedArtifact.from_dict(a) for a in data.get("expected_questions", [])],
            expected_knowledge=[ExpectedArtifact.from_dict(a) for a in data.get("expected_knowledge", [])],
            expected_rationales=[ExpectedArtifact.from_dict(a) for a in data.get("expected_rationales", [])],
            min_goal_recall=data.get("min_goal_recall", 1.0),
            min_decision_recall=data.get("min_decision_recall", 1.0),
            min_rationale_recall=data.get("min_rationale_recall", 0.95),
            min_task_recall=data.get("min_task_recall", 0.95),
            min_knowledge_recall=data.get("min_knowledge_recall", 0.80),
            min_overall_continuity=data.get("min_overall_continuity", 0.90),
            min_context_gain=data.get("min_context_gain", 0.10),
        )
