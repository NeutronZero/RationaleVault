"""Projection Conformance Suite — executable verification of Projection Laws.

ADR-027 defines 8 Projection Laws. This suite turns them into generic,
projection-agnostic verification routines. It is a certification framework:
any projection must pass this suite to be considered platform-conformant.

Usage:
    suite = ConformanceSuite(projection, provider)
    report = suite.run()
    assert report.all_passed

The suite verifies projection behavior; it does not synthesize domain events.
"""
from __future__ import annotations

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
from rationalevault.projection_platform.conformance.suite import (
    ConformanceSuite,
)

__all__ = [
    "ConformanceReport",
    "ConformanceSuite",
    "LawResult",
    "ProjectionConformanceProvider",
    "verify_determinism",
    "verify_health_contract",
    "verify_incrementality",
    "verify_isolation",
    "verify_replay_equivalence",
    "verify_serialization_roundtrip",
    "verify_snapshot_roundtrip",
]
