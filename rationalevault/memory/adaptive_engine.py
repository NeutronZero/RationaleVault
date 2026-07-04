"""
RationaleVault Adaptive Policy Engine Runtime.

The AdaptivePolicyEngine collects telemetry, evaluates rules, and recommends
policy adjustments. It does not apply adjustments — that's the caller's decision.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from rationalevault.memory.adaptive_models import (
    AdaptivePolicy,
    AdjustmentDirection,
    AdjustmentRule,
    MetricType,
    PolicyAdjustment,
    PolicyDimension,
    PolicyTelemetry,
)
from rationalevault.memory.policy_models import (
    CachePolicy,
    DedupPolicy,
    MemoryPolicy,
    ProvenancePolicy,
    ProvenanceDepth,
    RetrievalPolicy,
    WritePolicy,
)


# =====================================================================
# Telemetry Collector
# =====================================================================

@dataclass
class TelemetryCollector:
    """
    Collects and stores telemetry data points.

    TELE data is append-only.
    """
    _telemetry: list[PolicyTelemetry] = field(default_factory=list)
    _last_emit_time: dict[str, float] = field(default_factory=dict)

    def record(self, telemetry: PolicyTelemetry) -> None:
        """Record a telemetry data point."""
        self._telemetry.append(telemetry)

    def get_recent(
        self,
        metric_type: MetricType | None = None,
        window_seconds: int = 300,
    ) -> list[PolicyTelemetry]:
        """Get recent telemetry within a time window."""
        now = time.time()
        cutoff = now - window_seconds
        result = []
        for t in self._telemetry:
            # Parse timestamp from metadata if available
            ts_str = t.metadata.get("timestamp")
            if ts_str:
                try:
                    ts = float(ts_str)
                    if ts >= cutoff:
                        if metric_type is None or t.metric_type == metric_type:
                            result.append(t)
                except (ValueError, TypeError):
                    pass
            else:
                # Include if no timestamp (backward compatible)
                if metric_type is None or t.metric_type == metric_type:
                    result.append(t)
        return result

    def aggregate(
        self,
        metric_type: MetricType,
        window_seconds: int = 300,
    ) -> float | None:
        """Aggregate recent telemetry for a metric (average)."""
        recent = self.get_recent(metric_type, window_seconds)
        if not recent:
            return None
        total = sum(t.value * t.sample_count for t in recent)
        count = sum(t.sample_count for t in recent)
        return total / count if count > 0 else None

    def record_count(self) -> int:
        return len(self._telemetry)


# =====================================================================
# Rule Evaluator
# =====================================================================

@dataclass
class RuleEvaluator:
    """
    Evaluates adjustment rules against telemetry.

    Returns recommended adjustments.
    """
    _last_adjustment_time: dict[str, float] = field(default_factory=dict)

    def evaluate(
        self,
        rules: list[AdjustmentRule],
        collector: TelemetryCollector,
        current_values: dict[PolicyDimension, float],
    ) -> list[PolicyAdjustment]:
        """
        Evaluate rules against collected telemetry.

        Returns list of recommended adjustments.
        """
        adjustments = []
        now = time.time()

        for rule in rules:
            # Check cooldown
            last_time = self._last_adjustment_time.get(rule.rule_id, 0.0)
            if now - last_time < rule.cooldown_seconds:
                continue

            # Get metric value
            metric_value = collector.aggregate(rule.metric_type)
            if metric_value is None:
                continue

            # Check threshold
            triggered = False
            if rule.direction == AdjustmentDirection.INCREASE:
                triggered = metric_value < rule.threshold
            elif rule.direction == AdjustmentDirection.DECREASE:
                triggered = metric_value > rule.threshold

            if not triggered:
                continue

            # Calculate adjustment
            current = current_values.get(rule.dimension, 0.5)
            if rule.direction == AdjustmentDirection.INCREASE:
                recommended = min(
                    current + rule.adjustment_magnitude,
                    rule.max_bound,
                )
            else:
                recommended = max(
                    current - rule.adjustment_magnitude,
                    rule.min_bound,
                )

            # Confidence based on how far metric is from threshold
            distance = abs(metric_value - rule.threshold)
            confidence = min(1.0, distance / rule.threshold) if rule.threshold > 0 else 0.5

            adjustment = PolicyAdjustment(
                adjustment_id=PolicyAdjustment.generate_adjustment_id(
                    rule.rule_id, rule.dimension.value,
                ),
                rule_id=rule.rule_id,
                dimension=rule.dimension,
                direction=rule.direction,
                current_value=current,
                recommended_value=recommended,
                metric_value=metric_value,
                confidence=confidence,
                reason=f"Metric {rule.metric_type.value}={metric_value:.3f} "
                       f"{'<' if rule.direction == AdjustmentDirection.INCREASE else '>'} "
                       f"threshold={rule.threshold}",
            )
            adjustments.append(adjustment)

            # Record adjustment time for cooldown
            self._last_adjustment_time[rule.rule_id] = now

        return adjustments


# =====================================================================
# Adaptive Policy Engine
# =====================================================================

@dataclass
class AdaptivePolicyEngine:
    """
    Orchestrates telemetry collection, rule evaluation, and policy adjustment.

    The engine does NOT apply adjustments automatically.
    It recommends adjustments that the caller can review and apply.
    """
    adaptive_policy: AdaptivePolicy = field(default_factory=AdaptivePolicy.default)
    collector: TelemetryCollector = field(default_factory=TelemetryCollector)
    evaluator: RuleEvaluator = field(default_factory=RuleEvaluator)

    def record_telemetry(self, telemetry: PolicyTelemetry) -> None:
        """Record a telemetry data point."""
        self.collector.record(telemetry)

    def evaluate(
        self,
        current_policy_values: dict[PolicyDimension, float],
    ) -> list[PolicyAdjustment]:
        """
        Evaluate all rules against collected telemetry.

        Returns recommended adjustments.
        """
        if not self.adaptive_policy.enabled:
            return []

        return self.evaluator.evaluate(
            self.adaptive_policy.rules,
            self.collector,
            current_policy_values,
        )

    def apply_adjustments(
        self,
        base_policy: MemoryPolicy,
        adjustments: list[PolicyAdjustment],
    ) -> MemoryPolicy:
        """
        Apply recommended adjustments to a base policy.

        Returns a new MemoryPolicy with adjusted values.
        This is a pure function — the base policy is not modified.
        """
        # Extract current values from base policy
        current_values = {
            PolicyDimension.RETRIEVAL: base_policy.retrieval.max_results / 20.0,
            PolicyDimension.CACHE: base_policy.cache.ttl_seconds / 600.0,
            PolicyDimension.PROVENANCE: 1.0 if base_policy.provenance.depth != ProvenanceDepth.NONE else 0.0,
            PolicyDimension.WRITE: 1.0 if base_policy.write.validation.value == "FULL" else 0.5,
            PolicyDimension.DEDUP: base_policy.dedup.similarity_threshold,
        }

        # Apply adjustments
        for adj in adjustments:
            current_values[adj.dimension] = adj.recommended_value

        # Reconstruct policy with adjusted values
        return MemoryPolicy(
            policy_id=MemoryPolicy.generate_policy_id(f"adaptive-{base_policy.name}"),
            name=f"adaptive-{base_policy.name}",
            description=f"Adaptively adjusted from {base_policy.name}",
            retrieval=RetrievalPolicy(
                policy_id=base_policy.retrieval.policy_id,
                strategy=base_policy.retrieval.strategy,
                max_results=max(1, int(current_values[PolicyDimension.RETRIEVAL] * 20)),
                min_score=base_policy.retrieval.min_score,
                boost_critical=base_policy.retrieval.boost_critical,
                type_weights=base_policy.retrieval.type_weights,
            ),
            cache=CachePolicy(
                policy_id=base_policy.cache.policy_id,
                enabled=base_policy.cache.enabled,
                invalidation=base_policy.cache.invalidation,
                ttl_seconds=max(60, int(current_values[PolicyDimension.CACHE] * 600)),
                max_entries=base_policy.cache.max_entries,
            ),
            provenance=ProvenancePolicy(
                policy_id=base_policy.provenance.policy_id,
                depth=ProvenanceDepth.FULL if current_values[PolicyDimension.PROVENANCE] > 0.5 else ProvenanceDepth.SHALLOW,
                require_source_events=base_policy.provenance.require_source_events,
                min_chain_length=base_policy.provenance.min_chain_length,
            ),
            write=WritePolicy(
                policy_id=base_policy.write.policy_id,
                validation=base_policy.write.validation,
                min_importance=base_policy.write.min_importance,
                require_project_id=base_policy.write.require_project_id,
            ),
            dedup=DedupPolicy(
                policy_id=base_policy.dedup.policy_id,
                strategy=base_policy.dedup.strategy,
                similarity_threshold=current_values[PolicyDimension.DEDUP],
                merge_on_dedup=base_policy.dedup.merge_on_dedup,
            ),
        )

    def get_metric_summary(self) -> dict[str, float | None]:
        """Get a summary of current metric values."""
        summary = {}
        for mt in MetricType:
            summary[mt.value] = self.collector.aggregate(mt)
        return summary

    def telemetry_count(self) -> int:
        return self.collector.record_count()

    def rule_count(self) -> int:
        return len(self.adaptive_policy.rules)
