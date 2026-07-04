from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class ReasoningConfig:
    """Configuration parameters for the cognitive reasoning engine."""
    version: str = "BeliefEngine v1"
    attenuation: float = 0.8
    agreement_weight: float = 0.1
    corroboration_weight: float = 0.05
    contradiction_penalty_weight: float = 0.3
    staleness_penalty_weight: float = 0.01
