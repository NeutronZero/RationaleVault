"""Parametrized compliance tests for RP-01 through RP-09."""

from __future__ import annotations

import pytest

from rationalevault.replay.compliance.validator import ReplayComplianceValidator, REQUIRES_SNAPSHOT
from rationalevault.replay.compliance.vectors import load_vectors
from rationalevault.replay.engine.default import DefaultReplayer
from rationalevault.replay.registry import ProjectionRegistry

VECTORS = load_vectors()


def _engine_factory(registry: ProjectionRegistry) -> DefaultReplayer:
    return DefaultReplayer(registry)


@pytest.mark.parametrize("vector_name", sorted(VECTORS.keys()))
def test_compliance(vector_name):
    vector = VECTORS[vector_name]
    validator = ReplayComplianceValidator(_engine_factory)
    results = validator.validate(vector)
    failures = [r for r in results if not r.passed]
    assert not failures, (
        f"Failed {vector_name}: "
        + "; ".join(f"{r.message}" for r in failures)
    )


def test_all_vectors_loaded():
    assert "rp-01-empty-ledger" in VECTORS
    assert "rp-02-single-event" in VECTORS
    assert "rp-09-interrupted-replay" in VECTORS
    assert len(VECTORS) >= 7
