# ADR-003: Cognitive Pipeline Architecture

> **Status:** Accepted
> **Date:** 2026-06-26
> **Deciders:** Core architecture team
> **Relates to:** v1.2.0 architecture freeze, Epic B completion, `docs/v1.2.0_architecture_freeze.md`

---

## Context

With the event ledger and projection layer established, the next challenge is turning retrieved knowledge into consistent, conflict-resolved reasoning and actionable decisions. This requires a cognitive pipeline that can:

1. Aggregate evidence from multiple projections.
2. Assess confidence based on evidence quality.
3. Construct beliefs with deterministic IDs.
4. Resolve contradictions between beliefs.
5. Synthesize beliefs into actionable categories.
6. Gate decisions based on policy.

The pipeline must be pure functional (no I/O, no side effects), fully replayable, and explainable.

---

## Decision

The cognitive pipeline is structured as seven pure functional layers, each consuming only the output of the layer directly above it:

```
Event Ledger
      ↓
Projection Layer
      ↓
Retrieval Intelligence
      ↓
Evidence Layer → EvidenceBundle
      ↓
Assessment Layer → EvidenceAssessment
      ↓
Belief Layer → Belief (BEL-[hash])
      ↓
ReasoningReport → ReasoningReport
      ↓
Synthesis Layer → SynthesisReport (SYN-[hash])
      ↓
Decision Gate → DecisionSet (DEC-[hash])
```

Each layer:
- Consumes immutable input.
- Produces immutable output with a stable deterministic ID (SHA-256 hash, first 8 hex characters).
- Never imports or depends on layers below it in the pipeline.
- Never imports runtime, delivery, or consumer outputs.

The entire pipeline is a pure function: `(Event Ledger, Policy) → DecisionSet`.

### Three-Phase Decision Pipeline

The final three layers (Synthesis through Decision Gate) form a distinct three-phase decision pipeline that consumes `ReasoningReport` and produces `DecisionSet`:

```
ReasoningReport
      ↓
Phase 1 — Candidate Generation (CandidateGenerator)
      Each Belief → DecisionCandidate (CAND-[hash])
      Classifies belief into SynthesisCategory (AFFIRM/CHALLENGE/RESOLVE/DEFER/MONITOR)
      Computes priority from impact × confidence
      Attaches DecisionReason explainers
      ↓
Phase 2 — Synthesis (SynthesisEngine)
      list[DecisionCandidate] → SynthesisReport (SYN-[hash])
      Wraps each candidate with stable synthesis ID
      Sorts by priority (CRITICAL→LOW) then confidence descending
      Groups summary counts by category and priority
      ↓
Phase 3 — Decision Gate (DecisionGate)
      SynthesisReport + DecisionGatePolicy → DecisionSet (DEC-[hash])
      Evaluates policy only — see "Gate Never Re-Scores" below
      Blocks DEFER items, contradicted items (per policy), items below confidence floor
      Enforces max_decisions cap
```

### Gate Never Re-Scores

The Decision Gate is a **policy filter**, not a reasoning step. It evaluates whether a synthesis item satisfies the current policy thresholds. It **never** modifies:

- **Confidence** — frozen from `Belief.final_confidence` through synthesis
- **Priority** — frozen from `CandidateGenerator._derive_priority()`
- **Category** — frozen from `CandidateGenerator._classify()`
- **Rationale** — frozen from `DecisionReason` annotations

This invariant is foundational: it means `DecisionSet` is a deterministic, explainable snapshot of what the current policy approves. Different policies produce different `DEC-` IDs for identical synthesis artifacts, making policy changes fully traceable.

This also means Epic C (Skill Platform) can safely consume `DecisionSet` as read-only input without reintroducing reasoning — the reasoning is already complete.

---

## Consequences

### Positive

- **Deterministic replay**: Same events + same policy → identical DecisionSet, always.
- **Explainability**: Every decision carries BEL-, CONTR-, CAND-, SYN-, and DEC- IDs traceable to source evidence.
- **Testability**: Each layer can be tested independently with deterministic inputs.
- **Extensibility**: New layers can be inserted between existing layers without modifying those layers (per extension rules in v1.2.0 freeze).

### Negative

- **Complexity**: Seven layers is more complex than a monolithic reasoning step.
- **ID coupling**: CAND- and SYN- IDs are coupled to `SynthesisConfig.version`; DEC- IDs are coupled to `DecisionGatePolicy.version`. Policy changes produce new IDs for identical beliefs.

### Risks

- If the pipeline grows beyond ~10 layers, the ID chain may become unwieldy. This is a future concern, not a current risk.

---

## Alternatives Considered

1. **Monolithic reasoning function**: Rejected — harder to test, harder to explain, harder to extend.
2. **LLM-in-the-loop reasoning**: Rejected — introduces non-determinism, external dependency, and violates the "no LLM dependency" invariant.
3. **Rule engine with forward chaining**: Rejected — over-engineered for the current scope; pure functional layers are sufficient.

---

## Freeze Level Impact

The cognitive pipeline is **Frozen** as of v1.2.0 (Sprint B3 completion). Layer definitions, invariant contracts, stable IDs, and determinism guarantees are frozen. Extension rules are defined in `docs/v1.2.0_architecture_freeze.md`.

---

## References

- `docs/v1.2.0_architecture_freeze.md` — Authoritative freeze document
- `rationalevault/cognitive_head/` — Implementation
- `tests/unit/test_decision_synthesis.py` — Regression baseline (50 tests)
