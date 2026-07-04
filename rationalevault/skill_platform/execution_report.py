"""
RationaleVault Skill Platform — ExecutionReport.

Immutable report of a complete execution cycle. Wraps a list of
SkillResult objects with summary metrics.

Design rules:
  - ExecutionReport is frozen — immutable after creation.
  - version enables serialisation evolution.
  - Natural input to the Reflection Engine (Cognitive Improvement loop).
  - Starts as a simple wrapper; grows later.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rationalevault.skill_platform.result import SkillResult, SkillResultStatus


@dataclass(frozen=True)
class ExecutionReport:
    """
    Immutable report of a complete execution cycle.

    Wraps SkillResult objects with summary metrics. Natural input
    to the Reflection Engine in the Cognitive Improvement loop.
    """
    version: str = "1.0"
    results: list[SkillResult] = field(default_factory=list)
    failures: list[SkillResult] = field(default_factory=list)
    total_duration_ms: int = 0
    total_executions: int = 0
    total_completed: int = 0
    total_failed: int = 0
    total_timeout: int = 0
    total_denied: int = 0
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "results": [r.to_dict() for r in self.results],
            "failures": [r.to_dict() for r in self.failures],
            "total_duration_ms": self.total_duration_ms,
            "total_executions": self.total_executions,
            "total_completed": self.total_completed,
            "total_failed": self.total_failed,
            "total_timeout": self.total_timeout,
            "total_denied": self.total_denied,
            "summary": self.summary,
        }

    @classmethod
    def from_results(cls, results: list[SkillResult]) -> "ExecutionReport":
        """Build an ExecutionReport from a list of SkillResult objects."""
        completed = [r for r in results if r.status == SkillResultStatus.COMPLETED]
        failed = [r for r in results if r.status != SkillResultStatus.COMPLETED]
        total_duration = sum(r.duration_ms for r in results)

        summary_parts = [
            f"{len(results)} total",
            f"{len(completed)} completed",
            f"{len(failed)} failed",
            f"{total_duration}ms total duration",
        ]

        return cls(
            results=results,
            failures=failed,
            total_duration_ms=total_duration,
            total_executions=len(results),
            total_completed=len(completed),
            total_failed=len([r for r in results if r.status == SkillResultStatus.FAILED]),
            total_timeout=len([r for r in results if r.status == SkillResultStatus.TIMEOUT]),
            total_denied=len([r for r in results if r.status == SkillResultStatus.DENIED]),
            summary=", ".join(summary_parts),
        )
