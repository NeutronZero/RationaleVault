"""
RationaleVault Policy Simulator — Contracts for deterministic replay-based simulation.

The Policy Simulator replays historical telemetry through candidate policies
and estimates the outcome. It is a stateless, deterministic "dry run" that
produces evidence for the Adaptive Policy Engine.

Design rules:
  - The simulator replays observations, not the world.
  - Estimators are pluggable components (one per policy dimension).
  - The simulator never knows about recommendation thresholds, rules, or cooldowns.
  - Simulation reports are advisory evidence, not directives.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any



# =====================================================================
# Metric Estimate
# =====================================================================

@dataclass(frozen=True)
class MetricEstimate:
    """
    A single estimated metric value with confidence.

    Extensible — new metrics are added as new keys in SimulationResult.metrics
    without changing this contract.
    """
    value: float
    confidence: float = 1.0    # 0.0-1.0, how reliable this estimate is

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "confidence": self.confidence,
        }


# =====================================================================
# Simulation Result
# =====================================================================

@dataclass(frozen=True)
class SimulationResult:
    """
    Estimated metrics for a single policy under replay.

    PSIM-RES-[hash] — immutable result identifier.

    Metrics are stored in a dict for forward compatibility. New dimensions
    (token cost, graph depth, connector latency) can be added without
    changing this contract.
    """
    result_id: str                  # PSIM-RES-[hash]
    policy_name: str
    metrics: dict[str, MetricEstimate] = field(default_factory=dict)
    sample_count: int = 0
    confidence: float = 0.0        # Overall confidence in this result

    @staticmethod
    def generate_result_id(policy_name: str) -> str:
        data = f"simulation_result:{policy_name}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"PSIM-RES-{h}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_id": self.result_id,
            "policy_name": self.policy_name,
            "metrics": {k: v.to_dict() for k, v in self.metrics.items()},
            "sample_count": self.sample_count,
            "confidence": self.confidence,
        }

    def get(self, metric_name: str, default: float = 0.0) -> float:
        """Get a metric value by name, with a default."""
        est = self.metrics.get(metric_name)
        return est.value if est else default


# =====================================================================
# Simulation Scenario
# =====================================================================

@dataclass(frozen=True)
class SimulationScenario:
    """
    Defines what is being simulated.

    PSIM-SCN-[hash] — immutable scenario identifier.

    Identity (scenario_id) is separate from presentation (name).
    """
    scenario_id: str                # PSIM-SCN-[hash]
    name: str                       # Human-readable label
    description: str = ""
    current_policy_name: str = ""
    candidate_policy_name: str = ""
    metadata: dict[str, str] = field(default_factory=dict)

    @staticmethod
    def generate_scenario_id(current_name: str, candidate_name: str) -> str:
        data = f"simulation_scenario:{current_name}:{candidate_name}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"PSIM-SCN-{h}"

    @staticmethod
    def auto_name(current_name: str, candidate_name: str) -> str:
        """Generate a default scenario name from policy names."""
        return f"{current_name} → {candidate_name}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "name": self.name,
            "description": self.description,
            "current_policy_name": self.current_policy_name,
            "candidate_policy_name": self.candidate_policy_name,
        }


# =====================================================================
# Simulation Report
# =====================================================================

@dataclass(frozen=True)
class SimulationReport:
    """
    Complete simulation report comparing two policies.

    PSIM-[hash] — immutable report identifier.

    The report includes:
      - Per-policy estimated metrics
      - Dimension-level deltas
      - Human-readable explanation
      - Overall delta score and confidence
    """
    report_id: str                  # PSIM-[hash]
    scenario: SimulationScenario
    current: SimulationResult
    candidate: SimulationResult
    deltas: dict[str, float] = field(default_factory=dict)
    improvements: list[str] = field(default_factory=list)
    degradations: list[str] = field(default_factory=list)
    explanation: str = ""           # Human-readable summary
    overall_delta_score: float = 0.0
    confidence: float = 0.0

    @staticmethod
    def generate_report_id(scenario_id: str) -> str:
        data = f"simulation_report:{scenario_id}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"PSIM-{h}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "scenario": self.scenario.to_dict(),
            "current": self.current.to_dict(),
            "candidate": self.candidate.to_dict(),
            "deltas": self.deltas,
            "improvements": self.improvements,
            "degradations": self.degradations,
            "explanation": self.explanation,
            "overall_delta_score": self.overall_delta_score,
            "confidence": self.confidence,
        }
