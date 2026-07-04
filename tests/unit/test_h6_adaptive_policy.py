"""
H6 — Adaptive Policy Engine Tests.

PolicyTelemetry, AdjustmentRule, PolicyAdjustment, AdaptivePolicy,
TelemetryCollector, RuleEvaluator, AdaptivePolicyEngine.
"""
from __future__ import annotations

import time
import pytest
from typing import Any

from rationalevault.memory.adaptive_models import (
    AdaptivePolicy,
    AdjustmentDirection,
    AdjustmentRule,
    MetricType,
    PolicyAdjustment,
    PolicyDimension,
    PolicyTelemetry,
)
from rationalevault.memory.adaptive_engine import (
    AdaptivePolicyEngine,
    RuleEvaluator,
    TelemetryCollector,
)
from rationalevault.memory.policy_models import (
    MemoryPolicy,
    ProvenanceDepth,
    RetrievalStrategy,
)


# ── Helpers ───────────────────────────────────────────────────────────────

def _make_telemetry(
    metric_type: MetricType = MetricType.RETRIEVAL_PRECISION,
    value: float = 0.5,
) -> PolicyTelemetry:
    return PolicyTelemetry(
        telemetry_id=PolicyTelemetry.generate_telemetry_id(
            metric_type.value, value, str(time.time()),
        ),
        metric_type=metric_type,
        value=value,
        sample_count=10,
        metadata={"timestamp": str(time.time())},
    )


def _make_rule(
    metric_type: MetricType = MetricType.RETRIEVAL_PRECISION,
    direction: AdjustmentDirection = AdjustmentDirection.INCREASE,
    threshold: float = 0.3,
) -> AdjustmentRule:
    return AdjustmentRule(
        rule_id=AdjustmentRule.generate_rule_id(metric_type.value, "PROVENANCE"),
        metric_type=metric_type,
        dimension=PolicyDimension.PROVENANCE,
        direction=direction,
        threshold=threshold,
        adjustment_magnitude=0.2,
    )


# ── PolicyTelemetry ───────────────────────────────────────────────────────

class TestPolicyTelemetry:
    def test_frozen(self):
        t = _make_telemetry()
        with pytest.raises(AttributeError):
            t.value = 0.0

    def test_to_dict(self):
        t = _make_telemetry(MetricType.CACHE_HIT_RATE, 0.75)
        d = t.to_dict()
        assert d["metric_type"] == "CACHE_HIT_RATE"
        assert d["value"] == 0.75
        assert d["sample_count"] == 10

    def test_generate_id_deterministic(self):
        id1 = PolicyTelemetry.generate_telemetry_id("PRECISION", 0.5, "123")
        id2 = PolicyTelemetry.generate_telemetry_id("PRECISION", 0.5, "123")
        assert id1 == id2
        assert id1.startswith("TELE-")


# ── AdjustmentRule ─────────────────────────────────────────────────────────

class TestAdjustmentRule:
    def test_frozen(self):
        r = _make_rule()
        with pytest.raises(AttributeError):
            r.threshold = 0.5

    def test_to_dict(self):
        r = _make_rule()
        d = r.to_dict()
        assert d["metric_type"] == "RETRIEVAL_PRECISION"
        assert d["dimension"] == "PROVENANCE"
        assert d["direction"] == "INCREASE"
        assert d["threshold"] == 0.3

    def test_generate_id_deterministic(self):
        id1 = AdjustmentRule.generate_rule_id("PRECISION", "PROVENANCE")
        id2 = AdjustmentRule.generate_rule_id("PRECISION", "PROVENANCE")
        assert id1 == id2
        assert id1.startswith("ARUL-")


# ── PolicyAdjustment ──────────────────────────────────────────────────────

class TestPolicyAdjustment:
    def test_frozen(self):
        a = PolicyAdjustment(
            adjustment_id="PADJ-1", rule_id="ARUL-1",
            dimension=PolicyDimension.PROVENANCE,
            direction=AdjustmentDirection.INCREASE,
            current_value=0.5, recommended_value=0.7,
            metric_value=0.2, confidence=0.8,
        )
        with pytest.raises(AttributeError):
            a.confidence = 0.0

    def test_to_dict(self):
        a = PolicyAdjustment(
            adjustment_id="PADJ-1", rule_id="ARUL-1",
            dimension=PolicyDimension.CACHE,
            direction=AdjustmentDirection.DECREASE,
            current_value=0.8, recommended_value=0.6,
            metric_value=0.3, confidence=0.9,
            reason="Cache hit rate low",
        )
        d = a.to_dict()
        assert d["dimension"] == "CACHE"
        assert d["direction"] == "DECREASE"
        assert d["confidence"] == 0.9
        assert "Cache" in d["reason"]

    def test_generate_id_deterministic(self):
        id1 = PolicyAdjustment.generate_adjustment_id("ARUL-1", "PROVENANCE")
        id2 = PolicyAdjustment.generate_adjustment_id("ARUL-1", "PROVENANCE")
        assert id1 == id2
        assert id1.startswith("PADJ-")


# ── AdaptivePolicy ─────────────────────────────────────────────────────────

class TestAdaptivePolicy:
    def test_frozen(self):
        p = AdaptivePolicy(policy_id="APOL-1", name="test", base_policy_name="default")
        with pytest.raises(AttributeError):
            p.name = "hacked"

    def test_to_dict(self):
        p = AdaptivePolicy(
            policy_id="APOL-1", name="test", base_policy_name="default",
            rules=[_make_rule()],
        )
        d = p.to_dict()
        assert d["name"] == "test"
        assert len(d["rules"]) == 1

    def test_default_policy(self):
        p = AdaptivePolicy.default()
        assert p.name == "default"
        assert len(p.rules) == 3
        assert p.enabled is True

    def test_aggressive_policy(self):
        p = AdaptivePolicy.aggressive()
        assert p.name == "aggressive"
        assert len(p.rules) == 2

    def test_generate_id_deterministic(self):
        id1 = AdaptivePolicy.generate_policy_id("test")
        id2 = AdaptivePolicy.generate_policy_id("test")
        assert id1 == id2
        assert id1.startswith("APOL-")


# ── TelemetryCollector ─────────────────────────────────────────────────────

class TestTelemetryCollector:
    def test_initial_state(self):
        c = TelemetryCollector()
        assert c.record_count() == 0

    def test_record(self):
        c = TelemetryCollector()
        c.record(_make_telemetry(MetricType.RETRIEVAL_PRECISION, 0.8))
        c.record(_make_telemetry(MetricType.CACHE_HIT_RATE, 0.9))
        assert c.record_count() == 2

    def test_get_recent(self):
        c = TelemetryCollector()
        c.record(_make_telemetry(MetricType.RETRIEVAL_PRECISION, 0.8))
        c.record(_make_telemetry(MetricType.CACHE_HIT_RATE, 0.9))
        recent = c.get_recent(MetricType.RETRIEVAL_PRECISION)
        assert len(recent) == 1
        assert recent[0].value == 0.8

    def test_get_recent_all_types(self):
        c = TelemetryCollector()
        c.record(_make_telemetry(MetricType.RETRIEVAL_PRECISION, 0.8))
        c.record(_make_telemetry(MetricType.CACHE_HIT_RATE, 0.9))
        recent = c.get_recent()
        assert len(recent) == 2

    def test_aggregate(self):
        c = TelemetryCollector()
        c.record(_make_telemetry(MetricType.RETRIEVAL_PRECISION, 0.6))
        c.record(_make_telemetry(MetricType.RETRIEVAL_PRECISION, 0.8))
        avg = c.aggregate(MetricType.RETRIEVAL_PRECISION)
        assert avg is not None
        assert abs(avg - 0.7) < 0.01

    def test_aggregate_empty(self):
        c = TelemetryCollector()
        avg = c.aggregate(MetricType.RETRIEVAL_PRECISION)
        assert avg is None

    def test_aggregate_weighted(self):
        c = TelemetryCollector()
        c.record(PolicyTelemetry(
            telemetry_id="T1", metric_type=MetricType.RETRIEVAL_PRECISION,
            value=0.6, sample_count=10,
        ))
        c.record(PolicyTelemetry(
            telemetry_id="T2", metric_type=MetricType.RETRIEVAL_PRECISION,
            value=0.9, sample_count=20,
        ))
        avg = c.aggregate(MetricType.RETRIEVAL_PRECISION)
        expected = (0.6 * 10 + 0.9 * 20) / 30
        assert abs(avg - expected) < 0.01


# ── RuleEvaluator ──────────────────────────────────────────────────────────

class TestRuleEvaluator:
    def test_initial_state(self):
        e = RuleEvaluator()
        assert len(e._last_adjustment_time) == 0

    def test_evaluate_triggered(self):
        e = RuleEvaluator()
        collector = TelemetryCollector()
        collector.record(_make_telemetry(MetricType.RETRIEVAL_PRECISION, 0.2))

        rule = _make_rule(
            metric_type=MetricType.RETRIEVAL_PRECISION,
            direction=AdjustmentDirection.INCREASE,
            threshold=0.3,
        )

        current_values = {PolicyDimension.PROVENANCE: 0.5}
        adjustments = e.evaluate([rule], collector, current_values)
        assert len(adjustments) == 1
        assert adjustments[0].dimension == PolicyDimension.PROVENANCE
        assert adjustments[0].recommended_value == 0.7

    def test_evaluate_not_triggered(self):
        e = RuleEvaluator()
        collector = TelemetryCollector()
        collector.record(_make_telemetry(MetricType.RETRIEVAL_PRECISION, 0.8))

        rule = _make_rule(
            metric_type=MetricType.RETRIEVAL_PRECISION,
            direction=AdjustmentDirection.INCREASE,
            threshold=0.3,
        )

        current_values = {PolicyDimension.PROVENANCE: 0.5}
        adjustments = e.evaluate([rule], collector, current_values)
        assert len(adjustments) == 0

    def test_evaluate_cooldown(self):
        e = RuleEvaluator()
        collector = TelemetryCollector()
        collector.record(_make_telemetry(MetricType.RETRIEVAL_PRECISION, 0.2))

        rule = _make_rule(
            metric_type=MetricType.RETRIEVAL_PRECISION,
            direction=AdjustmentDirection.INCREASE,
            threshold=0.3,
        )
        rule = AdjustmentRule(
            rule_id=rule.rule_id,
            metric_type=rule.metric_type,
            dimension=rule.dimension,
            direction=rule.direction,
            threshold=rule.threshold,
            adjustment_magnitude=rule.adjustment_magnitude,
            cooldown_seconds=300,
        )

        current_values = {PolicyDimension.PROVENANCE: 0.5}

        # First evaluation triggers
        adj1 = e.evaluate([rule], collector, current_values)
        assert len(adj1) == 1

        # Second evaluation within cooldown
        adj2 = e.evaluate([rule], collector, current_values)
        assert len(adj2) == 0

    def test_evaluate_bounds(self):
        e = RuleEvaluator()
        collector = TelemetryCollector()
        collector.record(_make_telemetry(MetricType.RETRIEVAL_PRECISION, 0.2))

        rule = AdjustmentRule(
            rule_id="ARUL-1",
            metric_type=MetricType.RETRIEVAL_PRECISION,
            dimension=PolicyDimension.PROVENANCE,
            direction=AdjustmentDirection.INCREASE,
            threshold=0.3,
            adjustment_magnitude=0.2,
            min_bound=0.0,
            max_bound=0.6,  # Max bound
            cooldown_seconds=0,
        )

        current_values = {PolicyDimension.PROVENANCE: 0.5}
        adjustments = e.evaluate([rule], collector, current_values)
        assert len(adjustments) == 1
        assert adjustments[0].recommended_value == 0.6  # Capped at max

    def test_evaluate_decrease(self):
        e = RuleEvaluator()
        collector = TelemetryCollector()
        collector.record(_make_telemetry(MetricType.RETRIEVAL_LATENCY_MS, 800.0))

        rule = AdjustmentRule(
            rule_id="ARUL-1",
            metric_type=MetricType.RETRIEVAL_LATENCY_MS,
            dimension=PolicyDimension.RETRIEVAL,
            direction=AdjustmentDirection.DECREASE,
            threshold=500.0,
            adjustment_magnitude=0.2,
            cooldown_seconds=0,
        )

        current_values = {PolicyDimension.RETRIEVAL: 0.8}
        adjustments = e.evaluate([rule], collector, current_values)
        assert len(adjustments) == 1
        assert abs(adjustments[0].recommended_value - 0.6) < 0.01


# ── AdaptivePolicyEngine ───────────────────────────────────────────────────

class TestAdaptivePolicyEngine:
    def test_initial_state(self):
        engine = AdaptivePolicyEngine()
        assert engine.telemetry_count() == 0
        assert engine.rule_count() == 3

    def test_record_telemetry(self):
        engine = AdaptivePolicyEngine()
        engine.record_telemetry(_make_telemetry(MetricType.RETRIEVAL_PRECISION, 0.8))
        assert engine.telemetry_count() == 1

    def test_evaluate(self):
        engine = AdaptivePolicyEngine()
        engine.record_telemetry(_make_telemetry(MetricType.RETRIEVAL_PRECISION, 0.2))

        current_values = {PolicyDimension.PROVENANCE: 0.5}
        adjustments = engine.evaluate(current_values)
        assert len(adjustments) >= 1

    def test_evaluate_disabled(self):
        engine = AdaptivePolicyEngine(
            adaptive_policy=AdaptivePolicy(
                policy_id="APOL-1",
                name="disabled",
                base_policy_name="default",
                enabled=False,
            )
        )
        engine.record_telemetry(_make_telemetry(MetricType.RETRIEVAL_PRECISION, 0.2))

        current_values = {PolicyDimension.PROVENANCE: 0.5}
        adjustments = engine.evaluate(current_values)
        assert len(adjustments) == 0

    def test_apply_adjustments(self):
        engine = AdaptivePolicyEngine()
        base = MemoryPolicy.default()

        adjustments = [
            PolicyAdjustment(
                adjustment_id="PADJ-1", rule_id="ARUL-1",
                dimension=PolicyDimension.RETRIEVAL,
                direction=AdjustmentDirection.DECREASE,
                current_value=0.5, recommended_value=0.3,
                metric_value=0.8, confidence=0.9,
            ),
        ]

        adapted = engine.apply_adjustments(base, adjustments)
        assert adapted.name == "adaptive-default"
        assert adapted.retrieval.max_results == max(1, int(0.3 * 20))

    def test_apply_multiple_adjustments(self):
        engine = AdaptivePolicyEngine()
        base = MemoryPolicy.default()

        adjustments = [
            PolicyAdjustment(
                adjustment_id="PADJ-1", rule_id="ARUL-1",
                dimension=PolicyDimension.RETRIEVAL,
                direction=AdjustmentDirection.DECREASE,
                current_value=0.5, recommended_value=0.3,
                metric_value=0.8, confidence=0.9,
            ),
            PolicyAdjustment(
                adjustment_id="PADJ-2", rule_id="ARUL-2",
                dimension=PolicyDimension.CACHE,
                direction=AdjustmentDirection.INCREASE,
                current_value=0.5, recommended_value=0.8,
                metric_value=0.3, confidence=0.8,
            ),
        ]

        adapted = engine.apply_adjustments(base, adjustments)
        assert adapted.retrieval.max_results == max(1, int(0.3 * 20))
        assert adapted.cache.ttl_seconds == max(60, int(0.8 * 600))

    def test_get_metric_summary(self):
        engine = AdaptivePolicyEngine()
        engine.record_telemetry(_make_telemetry(MetricType.RETRIEVAL_PRECISION, 0.8))
        engine.record_telemetry(_make_telemetry(MetricType.CACHE_HIT_RATE, 0.9))

        summary = engine.get_metric_summary()
        assert summary["RETRIEVAL_PRECISION"] == 0.8
        assert summary["CACHE_HIT_RATE"] == 0.9

    def test_base_policy_not_modified(self):
        engine = AdaptivePolicyEngine()
        base = MemoryPolicy.default()
        original_max = base.retrieval.max_results

        adjustments = [
            PolicyAdjustment(
                adjustment_id="PADJ-1", rule_id="ARUL-1",
                dimension=PolicyDimension.RETRIEVAL,
                direction=AdjustmentDirection.DECREASE,
                current_value=0.5, recommended_value=0.3,
                metric_value=0.8, confidence=0.9,
            ),
        ]

        engine.apply_adjustments(base, adjustments)
        assert base.retrieval.max_results == original_max  # Unchanged
