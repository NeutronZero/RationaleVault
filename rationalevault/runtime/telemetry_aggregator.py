"""
RationaleVault Cross-Node Telemetry — Contracts for distributed telemetry aggregation.

Telemetry from multiple runtime nodes is aggregated into CrossNodeTelemetry
records. Aggregation strategies are pluggable components.

Design rules:
  - Aggregation strategies are extensible (like DimensionEstimators).
  - CrossNodeTelemetry is immutable.
  - Aggregation is deterministic.
  - The Event Ledger remains the source of truth for raw telemetry.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol


# =====================================================================
# Enums
# =====================================================================

class AggregationMethod(str, Enum):
    """Built-in aggregation methods."""
    AVERAGE = "AVERAGE"
    SUM = "SUM"
    MIN = "MIN"
    MAX = "MAX"
    P95 = "P95"


# =====================================================================
# Cross-Node Telemetry
# =====================================================================

@dataclass(frozen=True)
class CrossNodeTelemetry:
    """
    Telemetry aggregated from multiple runtime nodes.

    RSES-XTEL-[hash] — immutable aggregation identifier.
    """
    aggregation_id: str         # RSES-XTEL-[hash]
    source_node_ids: list[str]  # Which nodes contributed
    metric_type: str            # MetricType value
    value: float
    sample_count: int
    aggregation_method: str     # AggregationMethod value
    window_seconds: int = 300
    metadata: dict[str, str] = field(default_factory=dict)

    @staticmethod
    def generate_aggregation_id(
        metric_type: str, method: str, timestamp: str,
    ) -> str:
        data = f"cross_node_telemetry:{metric_type}:{method}:{timestamp}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"RSES-XTEL-{h}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "aggregation_id": self.aggregation_id,
            "source_node_ids": self.source_node_ids,
            "metric_type": self.metric_type,
            "value": self.value,
            "sample_count": self.sample_count,
            "aggregation_method": self.aggregation_method,
            "window_seconds": self.window_seconds,
        }


# =====================================================================
# Aggregation Strategy Protocol
# =====================================================================

class AggregationStrategy(Protocol):
    """
    Protocol for pluggable aggregation strategies.

    Each strategy implements a different way to combine telemetry
    values from multiple nodes.
    """
    @property
    def method_name(self) -> str: ...

    def aggregate(self, values: list[float]) -> float: ...


# =====================================================================
# Built-in Aggregation Strategies
# =====================================================================

@dataclass
class AverageAggregation:
    """Simple average of values."""
    @property
    def method_name(self) -> str:
        return "AVERAGE"

    def aggregate(self, values: list[float]) -> float:
        if not values:
            return 0.0
        return sum(values) / len(values)


@dataclass
class SumAggregation:
    """Sum of values."""
    @property
    def method_name(self) -> str:
        return "SUM"

    def aggregate(self, values: list[float]) -> float:
        return sum(values)


@dataclass
class MinAggregation:
    """Minimum value."""
    @property
    def method_name(self) -> str:
        return "MIN"

    def aggregate(self, values: list[float]) -> float:
        if not values:
            return 0.0
        return min(values)


@dataclass
class MaxAggregation:
    """Maximum value."""
    @property
    def method_name(self) -> str:
        return "MAX"

    def aggregate(self, values: list[float]) -> float:
        if not values:
            return 0.0
        return max(values)


@dataclass
class P95Aggregation:
    """95th percentile of values."""
    @property
    def method_name(self) -> str:
        return "P95"

    def aggregate(self, values: list[float]) -> float:
        if not values:
            return 0.0
        sorted_vals = sorted(values)
        idx = int(len(sorted_vals) * 0.95) - 1
        idx = max(0, min(idx, len(sorted_vals) - 1))
        return sorted_vals[idx]


# =====================================================================
# Node Telemetry Aggregator
# =====================================================================

@dataclass
class NodeTelemetryAggregator:
    """
    Aggregates telemetry from multiple nodes into CrossNodeTelemetry.

    The aggregator is pluggable — aggregation strategies can be
    added or replaced without modifying the aggregator.
    """
    strategies: dict[str, AggregationStrategy] = field(
        default_factory=lambda: {
            "AVERAGE": AverageAggregation(),
            "SUM": SumAggregation(),
            "MIN": MinAggregation(),
            "MAX": MaxAggregation(),
            "P95": P95Aggregation(),
        }
    )

    def aggregate(
        self,
        node_telemetry: dict[str, list[tuple[str, float]]],
        metric_type: str,
        method: str = "AVERAGE",
        window_seconds: int = 300,
    ) -> CrossNodeTelemetry:
        """
        Aggregate telemetry from multiple nodes.

        Args:
            node_telemetry: {node_id: [(metric_type, value), ...]}
            metric_type: The metric type to aggregate.
            method: Aggregation method name.
            window_seconds: Time window.

        Returns:
            CrossNodeTelemetry with aggregated value.
        """
        # Collect values from all nodes for the specified metric
        values = []
        source_node_ids = []
        total_samples = 0

        for node_id, metrics in node_telemetry.items():
            node_values = [v for mt, v in metrics if mt == metric_type]
            if node_values:
                source_node_ids.append(node_id)
                values.extend(node_values)
                total_samples += len(node_values)

        # Apply aggregation strategy
        strategy = self.strategies.get(method)
        if strategy is None:
            strategy = self.strategies["AVERAGE"]
            method = "AVERAGE"

        aggregated_value = strategy.aggregate(values) if values else 0.0

        return CrossNodeTelemetry(
            aggregation_id=CrossNodeTelemetry.generate_aggregation_id(
                metric_type, method, str(hash(tuple(sorted(values)))),
            ),
            source_node_ids=sorted(source_node_ids),
            metric_type=metric_type,
            value=aggregated_value,
            sample_count=total_samples,
            aggregation_method=method,
            window_seconds=window_seconds,
        )

    def aggregate_all(
        self,
        node_telemetry: dict[str, list[tuple[str, float]]],
        method: str = "AVERAGE",
        window_seconds: int = 300,
    ) -> list[CrossNodeTelemetry]:
        """
        Aggregate all metric types from multiple nodes.

        Returns one CrossNodeTelemetry per metric type.
        """
        # Discover all metric types
        metric_types = set()
        for metrics in node_telemetry.values():
            for mt, _ in metrics:
                metric_types.add(mt)

        return [
            self.aggregate(node_telemetry, mt, method, window_seconds)
            for mt in sorted(metric_types)
        ]
