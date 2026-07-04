# ADR-019: Adaptive Policy Engine Architecture

**Status**: Accepted
**Date**: 2026-06-26
**Deciders**: RationaleVault team
**Technical Story**: How should memory policies evolve from runtime telemetry without manual intervention?

---

## Context

The Memory Policy Engine (v2.7) made memory behavior configurable through five policy dimensions. But policies were static — once set, they didn't change based on runtime behavior.

Meanwhile, the evaluation framework (Semantic Evaluation v2, Retrieval Audit, Context Utilization, Faithfulness Metrics) was collecting rich telemetry about system performance. This telemetry was useful for reporting but not for automatic optimization.

The missing piece was a feedback loop: evaluation → telemetry → policy adjustment → better results.

## Decision

Introduce an **Adaptive Policy Engine** that closes the loop between evaluation and runtime behavior.

### Architecture

```
Evaluation → Telemetry → Rule Evaluation → Policy Adjustment → Better Results
```

### Key Design Decisions

**1. Telemetry is append-only**

`PolicyTelemetry` data points are never mutated. They're collected, aggregated, and evaluated. This preserves audit trails and enables historical analysis.

**2. Adjustments are recommendations, not commands**

The `AdaptivePolicyEngine.evaluate()` returns `PolicyAdjustment` objects. The caller decides whether to apply them. This prevents runaway policy oscillation.

**3. Rules have cooldowns**

Each `AdjustmentRule` has a `cooldown_seconds` parameter. After an adjustment is recommended, the rule won't fire again until the cooldown expires. This prevents rapid oscillation.

**4. Adjustments are bounded**

Each rule has `min_bound` and `max_bound`. Adjustments can't exceed these limits, preventing extreme policy values.

**5. Confidence scoring**

Each adjustment includes a confidence score based on how far the metric is from the threshold. This lets callers prioritize high-confidence adjustments.

**6. Base policy is not modified**

`apply_adjustments()` is a pure function — it returns a new `MemoryPolicy` without modifying the base. This enables A/B testing and rollback.

### Preset Adaptive Policies

| Preset | Rules | Behavior |
|--------|-------|----------|
| `default` | 3 rules | Conservative: precision→provenance, latency→results, cache hit→TTL |
| `aggressive` | 2 rules | Responsive: precision→results, dedup rate→dedup threshold |

## Consequences

### Positive
- Evaluation metrics automatically improve runtime behavior
- Feedback loop enables continuous optimization
- Rules are tunable (thresholds, magnitudes, cooldowns)
- Bounded adjustments prevent oscillation
- Pure function application enables A/B testing

### Negative
- One more abstraction layer
- Requires telemetry collection infrastructure

## Alternatives Considered

### 1. Manual policy tuning
**Rejected**: Doesn't scale; humans can't monitor metrics continuously.

### 2. Machine learning-based adaptation
**Rejected**: Too complex for initial implementation; rule-based is sufficient and explainable.

### 3. Hardcoded feedback loops
**Rejected**: Inflexible; different scenarios need different rules.

## Relationships

- Depends on: Memory Policy Engine (v2.7), Evaluation Framework (existing)
- Extends: MemoryPolicy behavior
- Frozen: v2.8 (Adaptive Policy Engine Freeze)

---

*ADR-019 — Accepted 2026-06-26*
