# ADR-009: Knowledge Promotion Pipeline

**Status:** Accepted  
**Date:** 2026-06-26  
**Deciders:** RationaleVault Architecture  
**Related:** ADR-008 (Reflection Event Hierarchy), ADR-007 (Three-Track Roadmap)

---

## Context

Program F requires a deterministic pipeline to promote reflection insights into durable knowledge. The execution pipeline already established the pattern:

```
ExecutionEvaluation → GateResult → PromotionDecision → ArtifactCandidate → Artifact
```

Knowledge promotion needs the same rigor: measurement → policy → decision → materialization. Each stage must have a distinct responsibility, immutable frozen dataclasses, and full event-sourced traceability.

## Decision

Implement the Knowledge Promotion Pipeline as four deterministic stages:

```text
PromotionCandidate
        ↓
    [Assess]     PromotionAssessor — compute facts and scores
        ↓
    [Gate]       PromotionGate — apply PromotionGatePolicy
        ↓
    [Decide]     PromotionDecider — record business decision
        ↓
    [Materialize] KnowledgeMaterializer — KnowledgeCandidate → KnowledgeObject
```

### Stage Responsibilities

| Stage | Input | Output | Responsibility |
|-------|-------|--------|----------------|
| Assess | PromotionCandidate | PromotionAssessment | Compute evidence ratio, confidence, contradictions — no policy decisions |
| Gate | PromotionAssessment + Policy | PromotionGateResult | Apply threshold rules, produce violations list |
| Decide | All above | KnowledgePromotionDecision + KnowledgeCandidate | Record business decision (approve/reject/defer), create KnowledgeCandidate if approved |
| Materialize | KnowledgeCandidate | KnowledgeObject | Map to full KnowledgeObject with ProvenanceChain, KnowledgeConfidence, initial EpistemicStatus |

### Event Hierarchy

```
KNOWLEDGE_PROMOTION_CANDIDATE
        ↓
KNOWLEDGE_PROMOTION_ASSESSED
        ↓
KNOWLEDGE_PROMOTION_GATED
        ↓
KNOWLEDGE_PROMOTION_APPROVED / KNOWLEDGE_PROMOTION_REJECTED
```

### Design Rules

1. **Deterministic** — no randomness, no I/O, no AI calls in any stage.
2. **Frozen dataclasses** — all intermediate objects are immutable.
3. **Separation of concerns** — domain models ≠ event payloads.
4. **AI advisory only** — AI never writes to the pipeline.
5. **PromotionGatePolicy is append-only** — v1 → v2 → v3, never mutated.
6. **Pipeline symmetry** — mirrors execution pipeline pattern exactly.

### Initial Epistemic Status Classification

New knowledge receives its initial epistemic status deterministically:
- High confidence (≥0.8) + 3+ supporting + no contradictions → `VALIDATED`
- Medium confidence + no contradictions → `PROPOSED`
- Any contradictions → `CONFLICTED`

## Consequences

### Positive
- Each stage is independently testable and replaceable.
- Full event-sourced traceability from candidate to materialized knowledge.
- Policy thresholds are configurable via PromotionGatePolicy without code changes.
- Pipeline is composable with the existing reflection pipeline.

### Negative
- Four-stage pipeline adds complexity over a simpler approve/reject pattern.
- PromotionGatePolicy versioning requires governance (append-only).

### Mitigations
- Comprehensive test suite (69 tests across Phase 2A/2B/2C).
- PromotionReport aggregates all intermediate results for debugging.

## Alternatives Considered

### 1. Monolithic Promotion Function
Single function that takes a candidate and returns a KnowledgeObject.
- Rejected: violates single-responsibility, hard to test stages independently.

### 2. Stateful Promotion Pipeline
Pipeline maintains internal state between stages.
- Rejected: violates deterministic replay guarantee. Each stage must be a pure function.

### 3. AI-Driven Promotion
Let AI decide which candidates to promote.
- Rejected: violates the principle that AI is advisory only. Human/AI review produces AdvisoryReport objects, never writes to the pipeline.

## Freeze Level Impact

**L1 Freeze (v1.9):**
- `PromotionCandidate`, `PromotionAssessment`, `PromotionGatePolicy`, `PromotionGateResult`, `KnowledgePromotionDecision`, `KnowledgeCandidate`, `PromotionReport`
- Event payloads: `PromotionCandidateCreatedPayload`, `PromotionAssessedPayload`, `PromotionGatedPayload`, `PromotionDecisionPayload`
- Event types: `KNOWLEDGE_PROMOTION_CANDIDATE`, `KNOWLEDGE_PROMOTION_ASSESSED`, `KNOWLEDGE_PROMOTION_GATED`, `KNOWLEDGE_PROMOTION_APPROVED`, `KNOWLEDGE_PROMOTION_REJECTED`
- Pipeline classes: `PromotionAssessor`, `PromotionGate`, `PromotionDecider`, `PromotionPipeline`, `KnowledgeMaterializer`

## References

- `rationalevault/knowledge/promotion_models.py` — Phase 2A contracts
- `rationalevault/knowledge/promotion_events.py` — Event payloads
- `rationalevault/knowledge/promotion_pipeline.py` — Pipeline logic (Assess, Gate, Decide)
- `rationalevault/knowledge/promotion_materializer.py` — KnowledgeCandidate → KnowledgeObject
- `rationalevault/skill_platform/gate.py` — Execution pipeline pattern (reference)
- `tests/unit/test_phase2a_knowledge_promotion.py` — 31 tests
- `tests/unit/test_phase2b_promotion_pipeline.py` — 23 tests
- `tests/unit/test_phase2c_materialization.py` — 15 tests
