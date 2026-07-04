"""
RationaleVault Policy Simulator Runtime.

The simulator replays historical telemetry through candidate policies and
estimates the outcome. It is stateless, deterministic, and produces evidence
for the Adaptive Policy Engine.

Architecture:
  - Estimators are pluggable components (one per policy dimension).
  - PolicyReplayEngine orchestrates estimators across telemetry.
  - PolicySimulator produces SimulationReports from two policies.
  - The simulator never knows about thresholds, rules, or cooldowns.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from rationalevault.memory.adaptive_models import PolicyTelemetry
from rationalevault.memory.policy_models import (
    CacheInvalidation,
    MemoryPolicy,
    ProvenanceDepth,
)
from rationalevault.memory.simulation_models import (
    MetricEstimate,
    SimulationReport,
    SimulationResult,
    SimulationScenario,
)


# =====================================================================
# Estimator Protocol
# =====================================================================

class DimensionEstimator(Protocol):
    """
    Protocol for pluggable dimension estimators.

    Each estimator analyzes telemetry through a policy and produces
    metric estimates for its dimension.
    """
    @property
    def dimension_name(self) -> str: ...

    def estimate(
        self,
        telemetry: list[PolicyTelemetry],
        policy: MemoryPolicy,
    ) -> dict[str, MetricEstimate]: ...


# =====================================================================
# Retrieval Estimator
# =====================================================================

@dataclass
class RetrievalEstimator:
    """
    Estimates retrieval metrics from policy parameters and telemetry.

    Metrics produced:
      - retrieval.latency_ms
      - retrieval.precision
      - retrieval.result_count
    """
    base_latency_ms: float = 50.0

    @property
    def dimension_name(self) -> str:
        return "retrieval"

    def estimate(
        self,
        telemetry: list[PolicyTelemetry],
        policy: MemoryPolicy,
    ) -> dict[str, MetricEstimate]:
        rp = policy.retrieval
        total_candidates = self._total_candidates(telemetry)
        avg_latency = self._avg_latency(telemetry)
        avg_precision = self._avg_precision(telemetry)
        has_critical = self._has_critical(telemetry)

        # Result count: bounded by max_results and available candidates
        est_result_count = float(min(rp.max_results, max(1, total_candidates)))
        result_count_conf = min(1.0, total_candidates / max(1, rp.max_results)) if rp.max_results > 0 else 0.5

        # Latency: scales with result count and provenance depth
        provenance_factor = self._provenance_factor(policy)
        latency_scale = est_result_count / 10.0
        est_latency = self.base_latency_ms * latency_scale * (1.0 + provenance_factor * 0.3)
        if avg_latency > 0:
            # Blend heuristic with observed latency
            est_latency = (est_latency + avg_latency) / 2.0
        latency_conf = 0.7 if avg_latency > 0 else 0.4

        # Precision: boosted by type weights and critical importance
        avg_type_weight = self._avg_type_weight(rp.type_weights)
        critical_boost = rp.boost_critical if has_critical else 1.0
        est_precision = min(1.0, avg_precision * avg_type_weight * critical_boost) if avg_precision > 0 else 0.5
        precision_conf = 0.8 if avg_precision > 0 else 0.3

        return {
            "retrieval.latency_ms": MetricEstimate(value=est_latency, confidence=latency_conf),
            "retrieval.precision": MetricEstimate(value=est_precision, confidence=precision_conf),
            "retrieval.result_count": MetricEstimate(value=est_result_count, confidence=result_count_conf),
        }

    def _total_candidates(self, telemetry: list[PolicyTelemetry]) -> int:
        """Extract total candidate count from telemetry metadata."""
        for t in telemetry:
            count_str = t.metadata.get("total_candidates")
            if count_str:
                try:
                    return int(count_str)
                except (ValueError, TypeError):
                    pass
        return 10  # Default

    def _avg_latency(self, telemetry: list[PolicyTelemetry]) -> float:
        latencies = [
            t.value for t in telemetry
            if t.metric_type.value == "RETRIEVAL_LATENCY_MS"
        ]
        return sum(latencies) / len(latencies) if latencies else 0.0

    def _avg_precision(self, telemetry: list[PolicyTelemetry]) -> float:
        precisions = [
            t.value for t in telemetry
            if t.metric_type.value == "RETRIEVAL_PRECISION"
        ]
        return sum(precisions) / len(precisions) if precisions else 0.0

    def _has_critical(self, telemetry: list[PolicyTelemetry]) -> bool:
        for t in telemetry:
            if t.metadata.get("importance") == "critical":
                return True
        return False

    def _avg_type_weight(self, type_weights: dict[str, float]) -> float:
        if not type_weights:
            return 1.0
        return sum(type_weights.values()) / len(type_weights)

    def _provenance_factor(self, policy: MemoryPolicy) -> float:
        depth = policy.provenance.depth
        if depth == ProvenanceDepth.COMPLETE:
            return 1.0
        if depth == ProvenanceDepth.FULL:
            return 0.7
        if depth == ProvenanceDepth.SHALLOW:
            return 0.3
        return 0.0


# =====================================================================
# Cache Estimator
# =====================================================================

@dataclass
class CacheEstimator:
    """
    Estimates cache metrics from policy parameters and telemetry.

    Metrics produced:
      - cache.hit_rate
      - cache.ttl_seconds
    """

    @property
    def dimension_name(self) -> str:
        return "cache"

    def estimate(
        self,
        telemetry: list[PolicyTelemetry],
        policy: MemoryPolicy,
    ) -> dict[str, MetricEstimate]:
        cp = policy.cache
        observed_hit_rate = self._observed_hit_rate(telemetry)

        if not cp.enabled:
            return {
                "cache.hit_rate": MetricEstimate(value=0.0, confidence=1.0),
                "cache.ttl_seconds": MetricEstimate(value=0.0, confidence=1.0),
            }

        # TTL effectiveness: longer TTL → higher hit rate (diminishing returns)
        ttl_ratio = min(1.0, cp.ttl_seconds / 600.0)

        # Invalidation strategy factor
        inv_factor = {
            CacheInvalidation.TTL: 1.0,
            CacheInvalidation.LRU: 0.9,
            CacheInvalidation.EVENT_DRIVEN: 0.7,
            CacheInvalidation.MANUAL: 0.5,
        }.get(cp.invalidation, 1.0)

        # Max entries factor: more entries → higher hit rate (diminishing)
        entries_factor = min(1.0, cp.max_entries / 200.0)

        est_hit_rate = ttl_ratio * inv_factor * entries_factor
        est_hit_rate = max(0.0, min(1.0, est_hit_rate))

        # Blend with observed if available
        if observed_hit_rate > 0:
            est_hit_rate = (est_hit_rate + observed_hit_rate) / 2.0
            conf = 0.8
        else:
            conf = 0.4

        return {
            "cache.hit_rate": MetricEstimate(value=est_hit_rate, confidence=conf),
            "cache.ttl_seconds": MetricEstimate(value=float(cp.ttl_seconds), confidence=1.0),
        }

    def _observed_hit_rate(self, telemetry: list[PolicyTelemetry]) -> float:
        rates = [
            t.value for t in telemetry
            if t.metric_type.value == "CACHE_HIT_RATE"
        ]
        return sum(rates) / len(rates) if rates else 0.0


# =====================================================================
# Provenance Estimator
# =====================================================================

@dataclass
class ProvenanceEstimator:
    """
    Estimates provenance metrics from policy parameters and telemetry.

    Metrics produced:
      - provenance.coverage
      - provenance.cost
    """

    @property
    def dimension_name(self) -> str:
        return "provenance"

    def estimate(
        self,
        telemetry: list[PolicyTelemetry],
        policy: MemoryPolicy,
    ) -> dict[str, MetricEstimate]:
        pp = policy.provenance
        observed_coverage = self._observed_coverage(telemetry)

        # Depth factor
        depth_factor = {
            ProvenanceDepth.NONE: 0.0,
            ProvenanceDepth.SHALLOW: 0.4,
            ProvenanceDepth.FULL: 0.8,
            ProvenanceDepth.COMPLETE: 1.0,
        }.get(pp.depth, 0.5)

        # Chain satisfaction: how likely chains meet min/max requirements
        chain_satisfaction = self._chain_satisfaction(pp)

        est_coverage = depth_factor * chain_satisfaction
        est_coverage = max(0.0, min(1.0, est_coverage))

        # Blend with observed if available
        if observed_coverage > 0:
            est_coverage = (est_coverage + observed_coverage) / 2.0
            conf = 0.8
        else:
            conf = 0.4

        # Cost: deeper provenance = higher cost
        est_cost = depth_factor * 0.8 + (1.0 - chain_satisfaction) * 0.2

        return {
            "provenance.coverage": MetricEstimate(value=est_coverage, confidence=conf),
            "provenance.cost": MetricEstimate(value=est_cost, confidence=conf),
        }

    def _observed_coverage(self, telemetry: list[PolicyTelemetry]) -> float:
        coverages = [
            t.value for t in telemetry
            if t.metric_type.value == "PROVENANCE_COVERAGE"
        ]
        return sum(coverages) / len(coverages) if coverages else 0.0

    def _chain_satisfaction(self, pp: Any) -> float:
        """Estimate probability that provenance chains meet requirements."""
        if pp.min_chain_length == 0:
            return 1.0
        # Heuristic: deeper depth → higher satisfaction probability
        depth_score = {
            ProvenanceDepth.NONE: 0.0,
            ProvenanceDepth.SHALLOW: 0.3,
            ProvenanceDepth.FULL: 0.7,
            ProvenanceDepth.COMPLETE: 1.0,
        }.get(pp.depth, 0.5)
        return depth_score


# =====================================================================
# Policy Replay Engine
# =====================================================================

@dataclass
class PolicyReplayEngine:
    """
    Replays observations through a policy and produces estimated metrics.

    The engine is stateless — it accepts telemetry and a policy, and returns
    a SimulationResult. It never knows about rules, thresholds, or cooldowns.
    """
    estimators: list[DimensionEstimator] = field(default_factory=lambda: [
        RetrievalEstimator(),
        CacheEstimator(),
        ProvenanceEstimator(),
    ])

    def replay(
        self,
        telemetry: list[PolicyTelemetry],
        policy: MemoryPolicy,
    ) -> SimulationResult:
        """
        Replay telemetry through a policy and estimate all metrics.

        Returns a SimulationResult with metric estimates and confidence.
        """
        all_metrics: dict[str, MetricEstimate] = {}
        confidences: list[float] = []

        for estimator in self.estimators:
            metrics = estimator.estimate(telemetry, policy)
            all_metrics.update(metrics)
            for me in metrics.values():
                confidences.append(me.confidence)

        # Overall confidence: average of all metric confidences
        overall_confidence = (
            sum(confidences) / len(confidences) if confidences else 0.0
        )

        return SimulationResult(
            result_id=SimulationResult.generate_result_id(policy.name),
            policy_name=policy.name,
            metrics=all_metrics,
            sample_count=len(telemetry),
            confidence=overall_confidence,
        )


# =====================================================================
# Policy Simulator
# =====================================================================

# Weights for computing overall delta score
_DIMENSION_WEIGHTS: dict[str, float] = {
    "retrieval.precision": 0.35,      # Higher is better
    "retrieval.latency_ms": -0.25,    # Lower is better (negative weight)
    "retrieval.result_count": 0.10,   # Moderate is best
    "cache.hit_rate": 0.20,           # Higher is better
    "provenance.coverage": 0.15,      # Higher is better
    "provenance.cost": -0.10,         # Lower is better (negative weight)
}

# Dimensions where higher values are better
_HIGHER_IS_BETTER = {
    "retrieval.precision",
    "cache.hit_rate",
    "provenance.coverage",
    "retrieval.result_count",
}

# Dimensions where lower values are better
_LOWER_IS_BETTER = {
    "retrieval.latency_ms",
    "provenance.cost",
}


@dataclass
class PolicySimulator:
    """
    Produces SimulationReports by comparing two policies.

    The simulator is stateless and deterministic. It accepts a
    PolicyReplayEngine and produces reports from telemetry and policies.
    """
    engine: PolicyReplayEngine = field(default_factory=PolicyReplayEngine)

    def simulate(
        self,
        telemetry: list[PolicyTelemetry],
        current_policy: MemoryPolicy,
        candidate_policy: MemoryPolicy,
        scenario_name: str | None = None,
        scenario_description: str = "",
    ) -> SimulationReport:
        """
        Run deterministic simulation comparing two policies.

        Returns a SimulationReport with estimated deltas and explanation.
        """
        # Create scenario
        auto_name = SimulationScenario.auto_name(
            current_policy.name, candidate_policy.name,
        )
        name = scenario_name if scenario_name else auto_name

        scenario = SimulationScenario(
            scenario_id=SimulationScenario.generate_scenario_id(
                current_policy.name, candidate_policy.name,
            ),
            name=name,
            description=scenario_description,
            current_policy_name=current_policy.name,
            candidate_policy_name=candidate_policy.name,
        )

        # Replay through both policies
        current_result = self.engine.replay(telemetry, current_policy)
        candidate_result = self.engine.replay(telemetry, candidate_policy)

        # Compute deltas
        deltas = self._compute_deltas(current_result, candidate_result)

        # Classify improvements and degradations
        improvements, degradations = self._classify(deltas)

        # Compute overall delta score
        overall_score = self._overall_score(deltas)

        # Compute confidence with policy distance factor
        policy_distance = self._policy_distance(current_policy, candidate_policy)
        base_confidence = (
            current_result.confidence + candidate_result.confidence
        ) / 2.0
        # Reduce confidence as policies diverge
        distance_penalty = policy_distance * 0.3
        confidence = max(0.1, min(1.0, base_confidence - distance_penalty))

        # Generate explanation
        explanation = self._explain(
            current_result, candidate_result, deltas,
            improvements, degradations, overall_score, confidence,
        )

        return SimulationReport(
            report_id=SimulationReport.generate_report_id(scenario.scenario_id),
            scenario=scenario,
            current=current_result,
            candidate=candidate_result,
            deltas=deltas,
            improvements=improvements,
            degradations=degradations,
            explanation=explanation,
            overall_delta_score=overall_score,
            confidence=confidence,
        )

    def _compute_deltas(
        self,
        current: SimulationResult,
        candidate: SimulationResult,
    ) -> dict[str, float]:
        """Compute deltas for all shared metrics."""
        deltas = {}
        all_keys = set(current.metrics.keys()) | set(candidate.metrics.keys())
        for key in all_keys:
            c_val = current.get(key)
            d_val = candidate.get(key)
            deltas[key] = d_val - c_val
        return deltas

    def _classify(
        self,
        deltas: dict[str, float],
    ) -> tuple[list[str], list[str]]:
        """Classify deltas as improvements or degradations."""
        improvements = []
        degradations = []
        for key, delta in deltas.items():
            if abs(delta) < 1e-6:
                continue
            if key in _HIGHER_IS_BETTER:
                if delta > 0:
                    improvements.append(key)
                else:
                    degradations.append(key)
            elif key in _LOWER_IS_BETTER:
                if delta < 0:
                    improvements.append(key)
                else:
                    degradations.append(key)
            else:
                # Unknown dimension — any change is an improvement
                if delta > 0:
                    improvements.append(key)
        return improvements, degradations

    def _overall_score(self, deltas: dict[str, float]) -> float:
        """Compute weighted overall delta score."""
        total_weight = 0.0
        weighted_sum = 0.0
        for key, delta in deltas.items():
            weight = _DIMENSION_WEIGHTS.get(key, 0.0)
            if weight != 0.0:
                weighted_sum += delta * weight
                total_weight += abs(weight)
        if total_weight == 0.0:
            return 0.0
        return weighted_sum / total_weight

    def _policy_distance(
        self,
        current: MemoryPolicy,
        candidate: MemoryPolicy,
    ) -> float:
        """
        Compute normalized distance between two policies (0.0-1.0).

        Used as a confidence penalty — large policy changes reduce confidence
        in simulation accuracy.
        """
        diffs = []

        # Retrieval distance
        max_results_diff = abs(candidate.retrieval.max_results - current.retrieval.max_results) / 20.0
        diffs.append(max_results_diff)

        # Cache distance
        ttl_diff = abs(candidate.cache.ttl_seconds - current.cache.ttl_seconds) / 600.0
        diffs.append(ttl_diff)

        # Provenance distance
        depth_order = {
            ProvenanceDepth.NONE: 0,
            ProvenanceDepth.SHALLOW: 1,
            ProvenanceDepth.FULL: 2,
            ProvenanceDepth.COMPLETE: 3,
        }
        depth_diff = abs(
            depth_order.get(candidate.provenance.depth, 0)
            - depth_order.get(current.provenance.depth, 0)
        ) / 3.0
        diffs.append(depth_diff)

        if not diffs:
            return 0.0
        return sum(diffs) / len(diffs)

    def _explain(
        self,
        current: SimulationResult,
        candidate: SimulationResult,
        deltas: dict[str, float],
        improvements: list[str],
        degradations: list[str],
        overall_score: float,
        confidence: float,
    ) -> str:
        """Generate a human-readable explanation of the simulation."""
        lines = []

        # Top contributors
        if improvements:
            lines.append("Top improvements:")
            for key in sorted(improvements, key=lambda k: abs(deltas.get(k, 0)), reverse=True)[:3]:
                delta_val = deltas.get(key, 0)
                lines.append(f"  + {key} {delta_val:+.1%}")

        if degradations:
            lines.append("Top degradations:")
            for key in sorted(degradations, key=lambda k: abs(deltas.get(k, 0)), reverse=True)[:3]:
                delta_val = deltas.get(key, 0)
                lines.append(f"  - {key} {delta_val:+.1%}")

        if not improvements and not degradations:
            lines.append("No significant differences detected.")

        # Overall assessment
        direction = "positive" if overall_score > 0.01 else "negative" if overall_score < -0.01 else "neutral"
        lines.append(f"Overall: {direction} (score={overall_score:+.3f})")
        lines.append(f"Confidence: {confidence:.0%}")

        return "\n".join(lines)
