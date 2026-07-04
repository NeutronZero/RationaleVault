# ADR-006: Separation of Decision from Execution

> **Status:** Accepted
> **Date:** 2026-06-26
> **Deciders:** Core architecture team
> **Relates to:** v1.2.0 architecture freeze, Epic B completion, Epic C planning, `docs/v1.2.0_architecture_freeze.md`

---

## Context

The cognitive pipeline (Epic B) produces a `DecisionSet` — approved decisions with stable DEC- IDs, priority levels, categories, and full explainability. The natural next question is: what happens to these decisions?

Many agent frameworks blur the line between reasoning and execution — the same system that decides what to do also does it. This creates problems:
- Execution failures can corrupt reasoning state.
- Reasoning logic becomes entangled with runtime concerns.
- Replay becomes impossible if execution has side effects on reasoning.

---

## Decision

DecisionSet is a diagnostic-only output. It states which items satisfy the current policy. It does not execute anything.

Execution belongs entirely to the Skill Platform (Epic C). The Skill Platform consumes `DecisionSet` as input and answers only: *"How do we execute an already-approved decision safely and reproducibly?"*

The flow is:

```
DecisionSet (from Epic B)
      ↓
Decision → Skill Bridge (maps DEC- items to skill invocations)
      ↓
Skill Selection (matches decision category to appropriate skill)
      ↓
Sandbox Runtime (executes skill with input/output tracking)
      ↓
Execution Result (with provenance trace back to DEC- ID)
      ↓
Event Ledger (execution result is appended as a new event)
```

Skills do not re-reason. They do not reinterpret decisions. They execute what has already been decided.

---

## Consequences

### Positive

- **Clean separation of concerns**: Reasoning (Epic B) and execution (Epic C) are independent, testable, and replaceable.
- **Deterministic replay**: Execution results are appended as events, so the full history (decision → execution → outcome) is replayable.
- **Provenance**: Every execution result traces back to a specific DEC- ID, ContextPackage, and event IDs.
- **Safety**: Execution failures cannot corrupt reasoning state — they are separate layers.

### Negative

- **Indirection**: The Decision→Skill Bridge adds a mapping layer between decision and action.
- **Skill catalog management**: The platform must maintain a registry of available skills and their capabilities.

### Risks

- If the Decision→Skill Bridge mapping is incomplete, some decisions may not have corresponding skills. Mitigated by explicit gap analysis in Epic C planning.

---

## Alternatives Considered

1. **Integrated reasoning + execution**: Rejected — violates the pure functional invariant of the cognitive pipeline; makes replay impossible.
2. **Event-driven execution triggers**: Considered for future — execution could be triggered automatically by DecisionSet events, but this is deferred to Epic C.
3. **LLM-mediated execution**: Rejected — introduces non-determinism in the execution path.

---

## Freeze Level Impact

The separation principle is **Frozen**. The cognitive pipeline must never depend on execution outputs. The Skill Platform must consume DecisionSet as read-only input.

---

## References

- `docs/v1.2.0_architecture_freeze.md` — "DecisionSet is diagnostic only" (line 274)
- `docs/skill_runtime_architecture.md` — Skill Platform design specification (Epic C)
- `docs/roadmap.md` — Epic C (Skill Platform) definition
- `rationalevault/cognitive_head/decision.py` — DecisionSet implementation
