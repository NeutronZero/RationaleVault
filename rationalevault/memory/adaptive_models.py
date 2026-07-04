"""
RationaleVault Adaptive Policy Engine — Contracts for telemetry-driven policy adjustment.

The Adaptive Policy Engine closes the loop between evaluation metrics and
runtime memory behavior. It collects telemetry, evaluates it against thresholds,
and recommends policy adjustments.

Design rules:
  - Telemetry is append-only (never mutated).
  - Policy adjustments are recommendations, not commands.
  - The adaptive layer wraps, not replaces, the static MemoryPolicy.
  - Adjustments are bounded (min/max) to prevent oscillation.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# =====================================================================
# Enums
# =====================================================================

class AdjustmentDirection(str, Enum):
    """Direction of policy adjustment."""
    INCREASE = "INCREASE"
    DECREASE = "DECREASE"
    MAINTAIN = "MAINTAIN"


class MetricType(str, Enum):
    """Types of telemetry metrics."""
    RETRIEVAL_PRECISION = "RETRIEVAL_PRECISION"
    RETRIEVAL_LATENCY_MS = "RETRIEVAL_LATENCY_MS"
    CACHE_HIT_RATE = "CACHE_HIT_RATE"
    DEDUP_RATE = "DEDUP_RATE"
    PROVENANCE_COVERAGE = "PROVENANCE_COVERAGE"
    WRITE_SUCCESS_RATE = "WRITE_SUCCESS_RATE"
    RESULT_COUNT_AVG = "RESULT_COUNT_AVG"
    CONFIDENCE_SCORE_AVG = "CONFIDENCE_SCORE_AVG"


class PolicyDimension(str, Enum):
    """Which policy dimension to adjust."""
    RETRIEVAL = "RETRIEVAL"
    CACHE = "CACHE"
    PROVENANCE = "PROVENANCE"
    WRITE = "WRITE"
    DEDUP = "DEDUP"


# =====================================================================
# Telemetry
# =====================================================================

@dataclass(frozen=True)
class PolicyTelemetry:
    """
    A single telemetry data point.

    TELE-[hash] — immutable telemetry identifier.
    """
    telemetry_id: str               # TELE-[hash]
    metric_type: MetricType
    value: float
    sample_count: int = 1
    window_seconds: int = 300       # 5 minute window
    metadata: dict[str, str] = field(default_factory=dict)

    @staticmethod
    def generate_telemetry_id(metric_type: str, value: float, timestamp: str) -> str:
        data = f"telemetry:{metric_type}:{value}:{timestamp}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"TELE-{h}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "telemetry_id": self.telemetry_id,
            "metric_type": self.metric_type.value,
            "value": self.value,
            "sample_count": self.sample_count,
            "window_seconds": self.window_seconds,
        }


# =====================================================================
# Adjustment Rule
# =====================================================================

@dataclass(frozen=True)
class AdjustmentRule:
    """
    Defines when and how a policy dimension should be adjusted.

    ARUL-[hash] — immutable rule identifier.
    """
    rule_id: str                    # ARUL-[hash]
    metric_type: MetricType
    dimension: PolicyDimension
    direction: AdjustmentDirection
    threshold: float                # Metric value that triggers adjustment
    adjustment_magnitude: float     # How much to adjust (0.0-1.0 scale)
    min_bound: float = 0.0          # Minimum allowed value
    max_bound: float = 1.0          # Maximum allowed value
    cooldown_seconds: int = 60      # Minimum time between adjustments
    description: str = ""

    @staticmethod
    def generate_rule_id(metric_type: str, dimension: str) -> str:
        data = f"adjustment_rule:{metric_type}:{dimension}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"ARUL-{h}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "metric_type": self.metric_type.value,
            "dimension": self.dimension.value,
            "direction": self.direction.value,
            "threshold": self.threshold,
            "adjustment_magnitude": self.adjustment_magnitude,
            "min_bound": self.min_bound,
            "max_bound": self.max_bound,
            "cooldown_seconds": self.cooldown_seconds,
            "description": self.description,
        }


# =====================================================================
# Policy Adjustment
# =====================================================================

@dataclass(frozen=True)
class PolicyAdjustment:
    """
    A recommended policy adjustment.

    PADJ-[hash] — immutable adjustment identifier.
    """
    adjustment_id: str              # PADJ-[hash]
    rule_id: str
    dimension: PolicyDimension
    direction: AdjustmentDirection
    current_value: float
    recommended_value: float
    metric_value: float
    confidence: float               # 0.0-1.0, how confident in this adjustment
    reason: str = ""

    @staticmethod
    def generate_adjustment_id(rule_id: str, dimension: str) -> str:
        data = f"policy_adjustment:{rule_id}:{dimension}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"PADJ-{h}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "adjustment_id": self.adjustment_id,
            "rule_id": self.rule_id,
            "dimension": self.dimension.value,
            "direction": self.direction.value,
            "current_value": self.current_value,
            "recommended_value": self.recommended_value,
            "metric_value": self.metric_value,
            "confidence": self.confidence,
            "reason": self.reason,
        }


# =====================================================================
# Adaptive Policy
# =====================================================================

@dataclass(frozen=True)
class AdaptivePolicy:
    """
    Wraps a static MemoryPolicy with adjustment rules.

    APOL-[hash] — immutable adaptive policy identifier.
    """
    policy_id: str                  # APOL-[hash]
    name: str
    base_policy_name: str           # Reference to MemoryPolicy name
    rules: list[AdjustmentRule] = field(default_factory=list)
    enabled: bool = True
    max_adjustments_per_window: int = 3
    evaluation_window_seconds: int = 300
    metadata: dict[str, str] = field(default_factory=dict)

    @staticmethod
    def generate_policy_id(name: str) -> str:
        data = f"adaptive_policy:{name}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"APOL-{h}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "name": self.name,
            "base_policy_name": self.base_policy_name,
            "rules": [r.to_dict() for r in self.rules],
            "enabled": self.enabled,
            "max_adjustments_per_window": self.max_adjustments_per_window,
            "evaluation_window_seconds": self.evaluation_window_seconds,
        }

    @staticmethod
    def default() -> AdaptivePolicy:
        """Default adaptive policy with conservative rules."""
        return AdaptivePolicy(
            policy_id=AdaptivePolicy.generate_policy_id("default"),
            name="default",
            base_policy_name="default",
            rules=[
                # If precision drops below 0.3, increase provenance depth
                AdjustmentRule(
                    rule_id=AdjustmentRule.generate_rule_id("RETRIEVAL_PRECISION", "PROVENANCE"),
                    metric_type=MetricType.RETRIEVAL_PRECISION,
                    dimension=PolicyDimension.PROVENANCE,
                    direction=AdjustmentDirection.INCREASE,
                    threshold=0.3,
                    adjustment_magnitude=0.2,
                    min_bound=0.0,
                    max_bound=1.0,
                    description="Increase provenance when precision is low",
                ),
                # If latency exceeds 500ms, decrease max results
                AdjustmentRule(
                    rule_id=AdjustmentRule.generate_rule_id("RETRIEVAL_LATENCY_MS", "RETRIEVAL"),
                    metric_type=MetricType.RETRIEVAL_LATENCY_MS,
                    dimension=PolicyDimension.RETRIEVAL,
                    direction=AdjustmentDirection.DECREASE,
                    threshold=500.0,
                    adjustment_magnitude=0.2,
                    min_bound=0.1,
                    max_bound=1.0,
                    description="Reduce result count when latency is high",
                ),
                # If cache hit rate drops below 0.5, increase TTL
                AdjustmentRule(
                    rule_id=AdjustmentRule.generate_rule_id("CACHE_HIT_RATE", "CACHE"),
                    metric_type=MetricType.CACHE_HIT_RATE,
                    dimension=PolicyDimension.CACHE,
                    direction=AdjustmentDirection.INCREASE,
                    threshold=0.5,
                    adjustment_magnitude=0.3,
                    min_bound=0.0,
                    max_bound=1.0,
                    description="Increase cache TTL when hit rate is low",
                ),
            ],
        )

    @staticmethod
    def aggressive() -> AdaptivePolicy:
        """Aggressive adaptive policy with more responsive rules."""
        return AdaptivePolicy(
            policy_id=AdaptivePolicy.generate_policy_id("aggressive"),
            name="aggressive",
            base_policy_name="aggressive",
            rules=[
                AdjustmentRule(
                    rule_id=AdjustmentRule.generate_rule_id("RETRIEVAL_PRECISION", "RETRIEVAL"),
                    metric_type=MetricType.RETRIEVAL_PRECISION,
                    dimension=PolicyDimension.RETRIEVAL,
                    direction=AdjustmentDirection.INCREASE,
                    threshold=0.4,
                    adjustment_magnitude=0.3,
                    min_bound=0.1,
                    max_bound=1.0,
                    cooldown_seconds=30,
                ),
                AdjustmentRule(
                    rule_id=AdjustmentRule.generate_rule_id("DEDUP_RATE", "DEDUP"),
                    metric_type=MetricType.DEDUP_RATE,
                    dimension=PolicyDimension.DEDUP,
                    direction=AdjustmentDirection.DECREASE,
                    threshold=0.3,
                    adjustment_magnitude=0.2,
                    min_bound=0.1,
                    max_bound=1.0,
                    cooldown_seconds=30,
                ),
            ],
        )
