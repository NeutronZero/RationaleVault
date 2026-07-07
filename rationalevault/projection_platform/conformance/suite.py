"""ConformanceSuite — orchestrates all law verifications."""
from __future__ import annotations

import time
from typing import Callable

from rationalevault.projection_platform.conformance.laws import (
    verify_determinism,
    verify_health_contract,
    verify_incrementality,
    verify_isolation,
    verify_replay_equivalence,
    verify_serialization_roundtrip,
    verify_snapshot_roundtrip,
)
from rationalevault.projection_platform.conformance.providers import (
    ProjectionConformanceProvider,
)
from rationalevault.projection_platform.conformance.report import (
    ConformanceReport,
    LawResult,
)
from rationalevault.projection_platform.protocols import Projection


class ConformanceSuite:
    """Runs all Projection Law verifications against a projection.

    The suite is generic — it contains no projection-specific logic.
    Projection-specific knowledge is supplied through the provider.

    Usage:
        suite = ConformanceSuite(projection, provider)
        report = suite.run()
        assert report.all_passed
    """

    def __init__(
        self,
        projection: Projection,
        provider: ProjectionConformanceProvider,
    ) -> None:
        self.projection = projection
        self.provider = provider

    def run(self) -> ConformanceReport:
        """Execute all law tests and return a structured report."""
        results: dict[str, LawResult] = {}

        for name, law_fn in self._law_tests():
            start = time.monotonic()
            try:
                law_fn(self.projection, self.provider)
                duration = (time.monotonic() - start) * 1000
                results[name] = LawResult(
                    passed=True, duration_ms=duration,
                )
            except (AssertionError, Exception) as e:
                duration = (time.monotonic() - start) * 1000
                results[name] = LawResult(
                    passed=False,
                    duration_ms=duration,
                    message=str(e),
                )

        return ConformanceReport(
            projection_id=self.projection.metadata.id,
            law_results=results,
        )

    def _law_tests(self) -> list[tuple[str, Callable]]:
        """Return ordered list of (name, law_test) pairs."""
        return [
            ("determinism", verify_determinism),
            ("incrementality", verify_incrementality),
            ("snapshot_roundtrip", verify_snapshot_roundtrip),
            ("replay_equivalence", verify_replay_equivalence),
            ("serialization_roundtrip", verify_serialization_roundtrip),
            ("health_contract", verify_health_contract),
            ("isolation", verify_isolation),
        ]
