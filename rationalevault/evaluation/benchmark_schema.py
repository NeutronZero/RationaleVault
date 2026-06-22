from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class HandoffBenchmark:
    benchmark_id: str
    benchmark_type: str  # synthetic | real_world
    expected_goal: str
    expected_tasks: list[str]
    expected_decisions: list[Any]
    expected_questions: list[str]
    expected_blockers: list[str]
    expected_next_action: str
    handoff_chain: list[str]
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HandoffBenchmark:
        return cls(
            benchmark_id=data["benchmark_id"],
            benchmark_type=data["benchmark_type"],
            expected_goal=data["expected_goal"],
            expected_tasks=data.get("expected_tasks") or [],
            expected_decisions=data.get("expected_decisions") or [],
            expected_questions=data.get("expected_questions") or [],
            expected_blockers=data.get("expected_blockers") or [],
            expected_next_action=data["expected_next_action"],
            handoff_chain=data.get("handoff_chain") or [],
            metadata=data.get("metadata") or {},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "benchmark_id": self.benchmark_id,
            "benchmark_type": self.benchmark_type,
            "expected_goal": self.expected_goal,
            "expected_tasks": self.expected_tasks,
            "expected_decisions": self.expected_decisions,
            "expected_questions": self.expected_questions,
            "expected_blockers": self.expected_blockers,
            "expected_next_action": self.expected_next_action,
            "handoff_chain": self.handoff_chain,
            "metadata": self.metadata,
        }
