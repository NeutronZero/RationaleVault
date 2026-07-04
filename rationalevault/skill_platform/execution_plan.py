"""
RationaleVault Skill Platform — ExecutionPlan.

Immutable plan for skill execution. Carries the candidate, context,
and execution constraints. Produced by the bridge, consumed by the executor.

Design rules:
  - ExecutionPlan is frozen — immutable after creation.
  - Carries retry policy, priority, confirmation requirement.
  - Execution constraints (timeout, memory) belong to the plan,
    not the runtime.
  - The scheduler (C5) uses plan fields without modifying the runtime.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rationalevault.skill_platform.bridge import SkillCandidate
from rationalevault.skill_platform.context import ExecutionContext


@dataclass(frozen=True)
class ExecutionPlan:
    """
    Immutable plan for skill execution.

    Produced by the bridge's create_execution_plans().
    Consumed by the executor. The scheduler (C5) uses plan fields
    for ordering and parallelism without modifying the runtime.
    """
    candidate: SkillCandidate
    context: ExecutionContext
    version: str = "1.0"
    retry_policy: str = "none"             # "none" | "transient" | "always"
    priority: int = 0                      # execution order (lower = higher priority)
    confirmation_required: bool = False
    timeout_seconds: int = 30
    max_memory_mb: int | None = None
    allow_parallel: bool = False
    expected_duration: str = "short"       # "short" | "medium" | "long"

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "decision_id": self.candidate.decision.decision_id,
            "skill_id": self.candidate.manifest.skill_id,
            "skill_name": self.candidate.manifest.name,
            "blocked": self.candidate.blocked,
            "blocked_reason": self.candidate.blocked_reason,
            "retry_policy": self.retry_policy,
            "priority": self.priority,
            "confirmation_required": self.confirmation_required,
            "timeout_seconds": self.timeout_seconds,
            "max_memory_mb": self.max_memory_mb,
            "allow_parallel": self.allow_parallel,
            "expected_duration": self.expected_duration,
        }
