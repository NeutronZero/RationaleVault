"""
H6.5 — Policy Simulator Tests.

MetricEstimate, SimulationResult, SimulationReport, SimulationScenario,
RetrievalEstimator, CacheEstimator, ProvenanceEstimator,
PolicyReplayEngine, PolicySimulator.
"""
from __future__ import annotations

import time
import pytest
from typing import Any

from rationalevault.memory.adaptive_models import MetricType, PolicyTelemetry
from rationalevault.memory.policy_models import (
    CachePolicy,
    MemoryPolicy,
    ProvenanceDepth,
    ProvenancePolicy,
    RetrievalPolicy,
)
from rationalevault.memory.simulation_models import (
    MetricEstimate,
    SimulationReport,
    SimulationResult,
    SimulationScenario,
)
from rationalevault.memory.simulation_engine import (
    CacheEstimator,
    PolicyReplayEngine,
    PolicySimulator,
    ProvenanceEstimator,
    RetrievalEstimator,
)


# ── Helpers ───────────────────────────────────────────────────────────────

def _make_telemetry(
    metric_type: MetricType = MetricType.RETRIEVAL_PRECISION,
    value: float = 0.5,
    **metadata: str,
) -> PolicyTelemetry:
    return PolicyTelemetry(
        telemetry_id=PolicyTelemetry.generate_telemetry_id(
            metric_type.value, value, str(time.time()),
        ),
        metric_type=metric_type,
        value=value,
        sample_count=10,
        metadata={"timestamp": str(time.time()), **metadata},
    )


def _make_telemetry_set() -> list[PolicyTelemetry]:
    """Create a realistic set of telemetry for simulation."""
    return [
        _make_telemetry(MetricType.RETRIEVAL_PRECISION, 0.6),
        _make_telemetry(MetricType.RETRIEVAL_LATENCY_MS, 300.0),
        _make_telemetry(MetricType.CACHE_HIT_RATE, 0.5),
        _make_telemetry(MetricType.PROVENANCE_COVERAGE, 0.7),
        _make_telemetry(MetricType.RESULT_COUNT_AVG, 8.0),
        _make_telemetry(MetricType.CONFIDENCE_SCORE_AVG, 0.75),
    ]


# ── MetricEstimate ───────────────────────────────────────────────────────

class TestMetricEstimate:
    def test_frozen(self):
        e = MetricEstimate(value=0.5, confidence=0.8)
        with pytest.raises(AttributeError):
            e.value = 0.0

    def test_to_dict(self):
        e = MetricEstimate(value=0.75, confidence=0.9)
        d = e.to_dict()
        assert d["value"] == 0.75
        assert d["confidence"] == 0.9

    def test_default_confidence(self):
        e = MetricEstimate(value=0.5)
        assert e.confidence == 1.0


# ── SimulationResult ──────────────────────────────────────────────────────

class TestSimulationResult:
    def test_frozen(self):
        r = SimulationResult(
            result_id="PSIM-RES-1", policy_name="test",
        )
        with pytest.raises(AttributeError):
            r.policy_name = "hacked"

    def test_to_dict(self):
        r = SimulationResult(
            result_id="PSIM-RES-1",
            policy_name="test",
            metrics={"latency": MetricEstimate(value=100.0, confidence=0.8)},
            sample_count=50,
            confidence=0.7,
        )
        d = r.to_dict()
        assert d["policy_name"] == "test"
        assert d["metrics"]["latency"]["value"] == 100.0
        assert d["sample_count"] == 50

    def test_get_metric(self):
        r = SimulationResult(
            result_id="PSIM-RES-1",
            policy_name="test",
            metrics={"latency": MetricEstimate(value=100.0)},
        )
        assert r.get("latency") == 100.0
        assert r.get("missing", 42.0) == 42.0

    def test_generate_id_deterministic(self):
        id1 = SimulationResult.generate_result_id("test")
        id2 = SimulationResult.generate_result_id("test")
        assert id1 == id2
        assert id1.startswith("PSIM-RES-")


# ── SimulationScenario ────────────────────────────────────────────────────

class TestSimulationScenario:
    def test_frozen(self):
        s = SimulationScenario(
            scenario_id="PSIM-SCN-1", name="test",
        )
        with pytest.raises(AttributeError):
            s.name = "hacked"

    def test_to_dict(self):
        s = SimulationScenario(
            scenario_id="PSIM-SCN-1",
            name="default → aggressive",
            description="Testing recall",
            current_policy_name="default",
            candidate_policy_name="aggressive",
        )
        d = s.to_dict()
        assert d["name"] == "default → aggressive"
        assert d["current_policy_name"] == "default"

    def test_auto_name(self):
        name = SimulationScenario.auto_name("default", "aggressive")
        assert name == "default → aggressive"

    def test_generate_id_deterministic(self):
        id1 = SimulationScenario.generate_scenario_id("a", "b")
        id2 = SimulationScenario.generate_scenario_id("a", "b")
        assert id1 == id2
        assert id1.startswith("PSIM-SCN-")


# ── SimulationReport ──────────────────────────────────────────────────────

class TestSimulationReport:
    def test_frozen(self):
        scenario = SimulationScenario(
            scenario_id="PSIM-SCN-1", name="test",
        )
        current = SimulationResult(
            result_id="PSIM-RES-1", policy_name="default",
        )
        candidate = SimulationResult(
            result_id="PSIM-RES-2", policy_name="aggressive",
        )
        r = SimulationReport(
            report_id="PSIM-1",
            scenario=scenario,
            current=current,
            candidate=candidate,
        )
        with pytest.raises(AttributeError):
            r.report_id = "hacked"

    def test_to_dict(self):
        scenario = SimulationScenario(
            scenario_id="PSIM-SCN-1", name="test",
        )
        current = SimulationResult(
            result_id="PSIM-RES-1", policy_name="default",
        )
        candidate = SimulationResult(
            result_id="PSIM-RES-2", policy_name="aggressive",
        )
        r = SimulationReport(
            report_id="PSIM-1",
            scenario=scenario,
            current=current,
            candidate=candidate,
            deltas={"retrieval.precision": 0.08},
            improvements=["retrieval.precision"],
            degradations=[],
            explanation="Positive overall",
            overall_delta_score=0.17,
            confidence=0.84,
        )
        d = r.to_dict()
        assert d["report_id"] == "PSIM-1"
        assert d["deltas"]["retrieval.precision"] == 0.08
        assert d["improvements"] == ["retrieval.precision"]
        assert d["confidence"] == 0.84

    def test_generate_id_deterministic(self):
        id1 = SimulationReport.generate_report_id("PSIM-SCN-1")
        id2 = SimulationReport.generate_report_id("PSIM-SCN-1")
        assert id1 == id2
        assert id1.startswith("PSIM-")


# ── RetrievalEstimator ────────────────────────────────────────────────────

class TestRetrievalEstimator:
    def test_dimension_name(self):
        e = RetrievalEstimator()
        assert e.dimension_name == "retrieval"

    def test_estimate_with_telemetry(self):
        e = RetrievalEstimator()
        telemetry = _make_telemetry_set()
        policy = MemoryPolicy.default()
        metrics = e.estimate(telemetry, policy)
        assert "retrieval.latency_ms" in metrics
        assert "retrieval.precision" in metrics
        assert "retrieval.result_count" in metrics
        assert metrics["retrieval.latency_ms"].value > 0
        assert 0.0 <= metrics["retrieval.precision"].value <= 1.0
        assert metrics["retrieval.result_count"].value > 0

    def test_estimate_without_telemetry(self):
        e = RetrievalEstimator()
        policy = MemoryPolicy.default()
        metrics = e.estimate([], policy)
        assert "retrieval.precision" in metrics
        # Without telemetry, precision uses heuristic default
        assert metrics["retrieval.precision"].value > 0

    def test_estimate_respects_max_results(self):
        from rationalevault.memory.policy_models import RetrievalPolicy
        e = RetrievalEstimator()
        policy = MemoryPolicy(
            policy_id="MPOL-1",
            name="small",
            retrieval=RetrievalPolicy(
                policy_id="MPOL-RET-1",
                max_results=3,
            ),
        )
        metrics = e.estimate([], policy)
        assert metrics["retrieval.result_count"].value <= 3.0


# ── CacheEstimator ────────────────────────────────────────────────────────

class TestCacheEstimator:
    def test_dimension_name(self):
        e = CacheEstimator()
        assert e.dimension_name == "cache"

    def test_estimate_with_telemetry(self):
        e = CacheEstimator()
        telemetry = _make_telemetry_set()
        policy = MemoryPolicy.default()
        metrics = e.estimate(telemetry, policy)
        assert "cache.hit_rate" in metrics
        assert "cache.ttl_seconds" in metrics
        assert 0.0 <= metrics["cache.hit_rate"].value <= 1.0
        assert metrics["cache.ttl_seconds"].value > 0

    def test_estimate_disabled_cache(self):
        e = CacheEstimator()
        from rationalevault.memory.policy_models import CachePolicy
        policy = MemoryPolicy(
            policy_id="MPOL-1",
            name="no-cache",
            cache=CachePolicy(
                policy_id="MPOL-CAC-1",
                enabled=False,
            ),
        )
        metrics = e.estimate([], policy)
        assert metrics["cache.hit_rate"].value == 0.0

    def test_estimate_long_ttl(self):
        e = CacheEstimator()
        from rationalevault.memory.policy_models import CachePolicy
        policy = MemoryPolicy(
            policy_id="MPOL-1",
            name="long-ttl",
            cache=CachePolicy(
                policy_id="MPOL-CAC-1",
                ttl_seconds=600,
                max_entries=200,
            ),
        )
        metrics = e.estimate([], policy)
        # Long TTL should produce higher hit rate estimate
        assert metrics["cache.hit_rate"].value > 0.3


# ── ProvenanceEstimator ───────────────────────────────────────────────────

class TestProvenanceEstimator:
    def test_dimension_name(self):
        e = ProvenanceEstimator()
        assert e.dimension_name == "provenance"

    def test_estimate_with_telemetry(self):
        e = ProvenanceEstimator()
        telemetry = _make_telemetry_set()
        policy = MemoryPolicy.default()
        metrics = e.estimate(telemetry, policy)
        assert "provenance.coverage" in metrics
        assert "provenance.cost" in metrics
        assert 0.0 <= metrics["provenance.coverage"].value <= 1.0
        assert 0.0 <= metrics["provenance.cost"].value <= 1.0

    def test_estimate_none_depth(self):
        e = ProvenanceEstimator()
        from rationalevault.memory.policy_models import ProvenancePolicy
        policy = MemoryPolicy(
            policy_id="MPOL-1",
            name="no-provenance",
            provenance=ProvenancePolicy(
                policy_id="MPOL-PRV-1",
                depth=ProvenanceDepth.NONE,
            ),
        )
        metrics = e.estimate([], policy)
        assert metrics["provenance.coverage"].value == 0.0

    def test_estimate_complete_depth(self):
        e = ProvenanceEstimator()
        from rationalevault.memory.policy_models import ProvenancePolicy
        policy = MemoryPolicy(
            policy_id="MPOL-1",
            name="full-provenance",
            provenance=ProvenancePolicy(
                policy_id="MPOL-PRV-1",
                depth=ProvenanceDepth.COMPLETE,
            ),
        )
        metrics = e.estimate([], policy)
        assert metrics["provenance.coverage"].value > 0.5


# ── PolicyReplayEngine ────────────────────────────────────────────────────

class TestPolicyReplayEngine:
    def test_initial_state(self):
        engine = PolicyReplayEngine()
        assert len(engine.estimators) == 3

    def test_replay_with_telemetry(self):
        engine = PolicyReplayEngine()
        telemetry = _make_telemetry_set()
        policy = MemoryPolicy.default()
        result = engine.replay(telemetry, policy)
        assert result.policy_name == "default"
        assert result.sample_count == 6
        assert len(result.metrics) > 0
        assert result.confidence > 0

    def test_replay_without_telemetry(self):
        engine = PolicyReplayEngine()
        policy = MemoryPolicy.default()
        result = engine.replay([], policy)
        assert result.policy_name == "default"
        assert result.sample_count == 0
        # Should still produce estimates from policy parameters
        assert len(result.metrics) > 0

    def test_replay_deterministic(self):
        engine = PolicyReplayEngine()
        telemetry = _make_telemetry_set()
        policy = MemoryPolicy.default()
        r1 = engine.replay(telemetry, policy)
        r2 = engine.replay(telemetry, policy)
        assert r1.metrics.keys() == r2.metrics.keys()
        for key in r1.metrics:
            assert r1.metrics[key].value == r2.metrics[key].value

    def test_replay_different_policies_different_results(self):
        engine = PolicyReplayEngine()
        # Provide total_candidates metadata so estimator uses it
        telemetry = _make_telemetry_set() + [
            PolicyTelemetry(
                telemetry_id="T-CAND",
                metric_type=MetricType.RESULT_COUNT_AVG,
                value=15.0,
                metadata={"total_candidates": "15"},
            ),
        ]
        default = MemoryPolicy.default()
        aggressive = MemoryPolicy.aggressive()
        r1 = engine.replay(telemetry, default)
        r2 = engine.replay(telemetry, aggressive)
        # Default max_results=10, aggressive max_results=20, total_candidates=15
        # Default: min(10, 15) = 10, Aggressive: min(20, 15) = 15
        assert r1.get("retrieval.result_count") != r2.get("retrieval.result_count")


# ── PolicySimulator ───────────────────────────────────────────────────────

class TestPolicySimulator:
    def test_initial_state(self):
        sim = PolicySimulator()
        assert sim.engine is not None

    def test_simulate_identical_policies(self):
        sim = PolicySimulator()
        telemetry = _make_telemetry_set()
        policy = MemoryPolicy.default()
        report = sim.simulate(telemetry, policy, policy)
        assert report.scenario.current_policy_name == "default"
        assert report.scenario.candidate_policy_name == "default"
        # Identical policies should produce near-zero deltas
        for delta in report.deltas.values():
            assert abs(delta) < 0.01
        assert len(report.improvements) == 0
        assert len(report.degradations) == 0

    def test_simulate_default_vs_aggressive(self):
        sim = PolicySimulator()
        telemetry = _make_telemetry_set()
        default = MemoryPolicy.default()
        aggressive = MemoryPolicy.aggressive()
        report = sim.simulate(telemetry, default, aggressive)
        assert report.scenario.name == "default → aggressive"
        assert report.overall_delta_score != 0.0
        assert report.confidence > 0

    def test_simulate_with_custom_scenario_name(self):
        sim = PolicySimulator()
        telemetry = _make_telemetry_set()
        default = MemoryPolicy.default()
        aggressive = MemoryPolicy.aggressive()
        report = sim.simulate(
            telemetry, default, aggressive,
            scenario_name="benchmark-1",
            scenario_description="Performance test",
        )
        assert report.scenario.name == "benchmark-1"
        assert report.scenario.description == "Performance test"

    def test_simulate_no_telemetry(self):
        sim = PolicySimulator()
        default = MemoryPolicy.default()
        aggressive = MemoryPolicy.aggressive()
        report = sim.simulate([], default, aggressive)
        # Should still produce a report, just with lower confidence
        assert report.confidence < 1.0
        assert report.current.sample_count == 0

    def test_simulate_has_explanation(self):
        sim = PolicySimulator()
        telemetry = _make_telemetry_set()
        default = MemoryPolicy.default()
        aggressive = MemoryPolicy.aggressive()
        report = sim.simulate(telemetry, default, aggressive)
        assert len(report.explanation) > 0
        assert "Confidence" in report.explanation

    def test_simulate_deterministic(self):
        sim = PolicySimulator()
        telemetry = _make_telemetry_set()
        default = MemoryPolicy.default()
        aggressive = MemoryPolicy.aggressive()
        r1 = sim.simulate(telemetry, default, aggressive)
        r2 = sim.simulate(telemetry, default, aggressive)
        assert r1.overall_delta_score == r2.overall_delta_score
        assert r1.confidence == r2.confidence
        assert r1.deltas == r2.deltas

    def test_simulate_policy_distance_affects_confidence(self):
        sim = PolicySimulator()
        telemetry = _make_telemetry_set()
        default = MemoryPolicy.default()
        # Small change
        small_change = MemoryPolicy(
            policy_id="MPOL-1",
            name="small-change",
            retrieval=RetrievalPolicy(
                policy_id="MPOL-RET-1",
                max_results=12,  # Default is 10
            ),
        )
        # Large change
        strict = MemoryPolicy.strict()
        r_small = sim.simulate(telemetry, default, small_change)
        r_large = sim.simulate(telemetry, default, strict)
        # Large policy change should have lower confidence
        assert r_large.confidence <= r_small.confidence

    def test_simulate_improvements_and_degradations(self):
        sim = PolicySimulator()
        telemetry = _make_telemetry_set()
        default = MemoryPolicy.default()
        aggressive = MemoryPolicy.aggressive()
        report = sim.simulate(telemetry, default, aggressive)
        # Should have some classification
        assert isinstance(report.improvements, list)
        assert isinstance(report.degradations, list)

    def test_simulate_report_has_ids(self):
        sim = PolicySimulator()
        telemetry = _make_telemetry_set()
        default = MemoryPolicy.default()
        aggressive = MemoryPolicy.aggressive()
        report = sim.simulate(telemetry, default, aggressive)
        assert report.report_id.startswith("PSIM-")
        assert report.scenario.scenario_id.startswith("PSIM-SCN-")
        assert report.current.result_id.startswith("PSIM-RES-")
        assert report.candidate.result_id.startswith("PSIM-RES-")


# ── Integration ───────────────────────────────────────────────────────────

class TestSimulationIntegration:
    def test_end_to_end_flow(self):
        """Full simulation flow: telemetry → replay → report."""
        sim = PolicySimulator()
        telemetry = _make_telemetry_set()
        current = MemoryPolicy.default()
        candidate = MemoryPolicy(
            policy_id="MPOL-CUSTOM",
            name="custom",
            description="Custom policy for testing",
            retrieval=RetrievalPolicy(
                policy_id="MPOL-RET-CUSTOM",
                max_results=15,
                boost_critical=2.0,
            ),
        )
        report = sim.simulate(telemetry, current, candidate)

        # Report is complete
        assert report.report_id
        assert report.scenario
        assert report.current
        assert report.candidate
        assert report.deltas
        assert report.explanation
        assert report.confidence > 0

        # Can serialize to dict
        d = report.to_dict()
        assert d["report_id"] == report.report_id
        assert d["scenario"]["name"] == "default → custom"

    def test_simulate_produces_evidence(self):
        """Simulation produces evidence that can inform decisions."""
        sim = PolicySimulator()
        telemetry = _make_telemetry_set()
        current = MemoryPolicy.default()
        candidate = MemoryPolicy.strict()
        report = sim.simulate(telemetry, current, candidate)

        # Evidence is structured
        assert len(report.improvements) + len(report.degradations) > 0
        assert report.overall_delta_score != 0.0
        assert 0.0 <= report.confidence <= 1.0

    def test_simulate_with_custom_estimators(self):
        """Custom estimators can be plugged in."""
        from rationalevault.memory.simulation_models import MetricEstimate

        class CustomEstimator:
            @property
            def dimension_name(self):
                return "custom"

            def estimate(self, telemetry, policy):
                return {
                    "custom.metric": MetricEstimate(value=42.0, confidence=1.0),
                }

        engine = PolicyReplayEngine(estimators=[CustomEstimator()])
        sim = PolicySimulator(engine=engine)
        telemetry = _make_telemetry_set()
        policy = MemoryPolicy.default()
        result = engine.replay(telemetry, policy)
        assert result.get("custom.metric") == 42.0
