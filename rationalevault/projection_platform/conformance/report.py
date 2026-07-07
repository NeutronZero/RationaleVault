"""Conformance report data structures."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LawResult:
    """Result of a single Projection Law verification."""

    passed: bool
    duration_ms: float = 0.0
    message: Optional[str] = None


@dataclass
class ConformanceReport:
    """Structured report from the Projection Conformance Suite.

    Suitable for CI reporting and certification workflows.
    """

    projection_id: str
    law_results: dict[str, LawResult] = field(default_factory=dict)

    @property
    def all_passed(self) -> bool:
        return all(r.passed for r in self.law_results.values())

    @property
    def failed_laws(self) -> list[str]:
        return [name for name, r in self.law_results.items() if not r.passed]

    def summary(self) -> str:
        """Human-readable summary of the conformance run."""
        total = len(self.law_results)
        passed = sum(1 for r in self.law_results.values() if r.passed)
        status = "PASS" if self.all_passed else "FAIL"
        lines = [
            f"[conformance] {self.projection_id}: {status} "
            f"({passed}/{total} laws)",
        ]
        for name, result in self.law_results.items():
            marker = "PASS" if result.passed else "FAIL"
            line = f"  [{marker}] {name}"
            if result.message:
                line += f" — {result.message}"
            if result.duration_ms > 0:
                line += f" ({result.duration_ms:.1f}ms)"
            lines.append(line)
        return "\n".join(lines)
