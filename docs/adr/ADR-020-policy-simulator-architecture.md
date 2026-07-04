# ADR-020: Policy Simulator Architecture

**Status:** Accepted  
**Date:** 2026-06-28  
**Version:** v2.9  
**Decision Makers:** RationaleVault Architecture  
**Related:** ADR-018 (Memory Policy Engine), ADR-019 (Adaptive Policy Engine)

## Context

The Adaptive Policy Engine (v2.8) closes the loop between evaluation metrics and runtime behavior. It collects telemetry, evaluates rules, and recommends policy adjustments. However, it recommends adjustments based on threshold triggers, not predicted outcomes.

The platform needs a way to **estimate the impact** of a policy change before recommending it — a deterministic "dry run" that produces evidence for the adaptive engine.

## Decision

**The Policy Simulator replays observations, not the world.**

It accepts historical telemetry and two policies (current and candidate), replays the telemetry through both, and produces a `SimulationReport` with estimated metric deltas.

### Key Principles

1. **Deterministic replay** — no randomness, no external calls, no prediction
2. **Stateless** — no learning, no state between runs
3. **Pluggable estimators** — dimensions are independent components
4. **Advisory only** — simulation results inform decisions, they don't make them
5. **Separation of concerns** — the simulator never knows about thresholds, rules, or cooldowns

### Architecture

```
Telemetry
        ↓
PolicyReplayEngine
        ↓
DimensionEstimators (Retrieval, Cache, Provenance)
        ↓
SimulationResult (per policy)
        ↓
PolicySimulator
        ↓
SimulationReport
        ↓
Adaptive Policy Engine
```

### Contracts

| Contract | Prefix | Purpose |
|----------|--------|---------|
| `MetricEstimate` | — | Single estimated metric value with confidence |
| `SimulationResult` | PSIM-RES- | Estimated metrics for one policy |
| `SimulationScenario` | PSIM-SCN- | What is being simulated |
| `SimulationReport` | PSIM- | Complete comparison of two policies |

### Estimators

Each dimension has an independent estimator:

| Estimator | Dimension | Metrics |
|-----------|-----------|---------|
| `RetrievalEstimator` | retrieval | latency_ms, precision, result_count |
| `CacheEstimator` | cache | hit_rate, ttl_seconds |
| `ProvenanceEstimator` | provenance | coverage, cost |

New estimators (WriteEstimator, DedupEstimator, CostEstimator) can be added without modifying the replay engine.

### Confidence

Confidence is computed from four factors:
- **Sample factor**: `min(1.0, sample_count / 100)`
- **Metric factor**: `len(metrics_present) / len(all_metrics)`
- **Time factor**: temporal coverage of telemetry data
- **Policy distance**: penalty for large policy divergences

The policy distance factor prevents overstating certainty for large configuration changes.

### Explanation

Each report includes a human-readable explanation:

```
Top improvements:
  + retrieval.precision +8.0%
  + cache.hit_rate +6.0%
Top degradations:
  - provenance.cost +2.0%
Overall: positive (score=+0.170)
Confidence: 84%
```

## Consequences

### Positive
- Deterministic and reproducible
- Extensible through estimator plugins
- Explainable results with human-readable summaries
- Confidence degrades gracefully with policy distance
- Accepts `Iterable[PolicyTelemetry]` for portability

### Negative
- Heuristic estimation (not ground truth)
- Limited to observed telemetry scenarios
- Three dimensions only (Write and Dedup deferred)

## Alternatives Considered

1. **Predictive simulation** — Rejected: insufficient production data for ML-based prediction
2. **Monte Carlo sampling** — Rejected: introduces randomness, violates determinism
3. **Direct MemoryPolicyEngine integration** — Rejected: couples simulator to graph-backed stores

## Freeze

Frozen at v2.9:
- `MetricEstimate`, `SimulationResult`, `SimulationReport`, `SimulationScenario`
- `DimensionEstimator` protocol
- `PolicyReplayEngine`, `PolicySimulator`
- `PSIM` identifier prefix family
