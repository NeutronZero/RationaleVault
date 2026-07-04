# ADR-008: Reflection Event Hierarchy

> **Status:** Proposed
> **Date:** 2026-06-26
> **Deciders:** Core architecture team
> **Relates to:** ADR-001 (Event Sourcing), ADR-003 (Cognitive Pipeline), v1.6.0 Reflection Freeze, v1.7.0 Reflection Engine Freeze

---

## Context

The reflection system (F0/F1) produces `Reflection` domain objects and `ReflectionReport` but never persists them to the Event Ledger as first-class events. The `EventType.REFLECTION_GENERATED` enum exists but nothing emits it. This means:

1. Reflection state cannot be rebuilt from events alone.
2. There is no audit trail for why reflections were approved or rejected.
3. The reflection pipeline bypasses the event-sourcing invariant established in ADR-001.

Additionally, the reflection event hierarchy should mirror the execution event hierarchy for consistency:

```text
Execution:
  SKILL_EXECUTED → ExecutionStateProjection → ExecutionState

Reflection:
  REFLECTION_*_CREATED → ReflectionStateProjection → ReflectionState
```

---

## Decision

Introduce a four-event hierarchy for the reflection pipeline, where each event has an immutable payload (separate from domain objects) and includes `schema_version` for forward compatibility.

### Event Hierarchy

```text
REFLECTION_CANDIDATE_CREATED
        ↓
REFLECTION_ASSESSED
        ↓
REFLECTION_GENERATED
        ↓
REFLECTION_TRACED
```

### Design Rules

1. **Domain objects ≠ Event payloads.** `Reflection`, `ReflectionCandidate`, and `ReflectionAssessment` are ephemeral implementation details. `ReflectionCandidateCreatedPayload`, `ReflectionAssessedPayload`, `ReflectionGeneratedPayload`, and `ReflectionTracedPayload` are the persisted contracts.

2. **Every payload includes `schema_version: str = "1.0"`.** This enables forward-compatible schema evolution without breaking replay.

3. **`ReflectionAssessment` stays ephemeral.** The assessment is an implementation detail of the rule engine. The persisted contract is `ReflectionAssessedPayload`.

4. **`ReflectionTracedPayload` is an event, not a side artifact.** Traces are emitted as `REFLECTION_TRACED` events and reconstructed via `ReflectionTraceProjection`. This enables queries like "Why was this reflection rejected six months ago?"

5. **`ReflectionEventBundle` collects all payloads.** `ReflectionStateProjection.project()` returns both a `ReflectionReport` (domain) and a `ReflectionEventBundle` (event payloads for ledger emission).

### Identifier Families

| Prefix | Purpose | Ephemeral |
|--------|---------|-----------|
| `RCAND-` | Reflection candidates | Yes |
| `REFL-` | Reflections | No |
| `RREP-` | Reflection reports | No |
| `RTRC-` | Reflection traces | No |

All registered in the `IdentifierRegistry` (ADR-008 companion).

---

## Consequences

### Positive

- **Event-sourcing invariant preserved.** Reflection state can be fully rebuilt from `REFLECTION_GENERATED` and `REFLECTION_TRACED` events.
- **Audit trail.** `REFLECTION_TRACED` events record which rules fired, why, and which learning records contributed.
- **Consistency with execution pipeline.** Both execution and reflection follow `Event → Projection → State`.
- **Schema evolution.** `schema_version` on every payload enables future changes without breaking replay.
- **Separation of concerns.** Domain models remain implementation details; event payloads are the contracts.

### Negative

- **Four events per reflection cycle.** More events to manage, but each is small and immutable.
- **Payload serialization overhead.** Minimal — payloads are frozen dataclasses with `to_dict()`/`from_dict()`.

### Risks

- If the reflection pipeline is extended (e.g., multi-step reflection), the event hierarchy may need additional intermediate events. Mitigated by the `schema_version` mechanism.

---

## Alternatives Considered

1. **Emit `Reflection` objects directly.** Rejected — domain objects should not be the event contract. Event schemas may evolve independently from in-memory models.

2. **Persist `ReflectionAssessment` as-is.** Rejected — assessments are implementation details of the rule engine. The persisted contract should be the assessed payload, not the full assessment object.

3. **Two-event hierarchy (GENERATED + TRACED only).** Rejected — loses the CANDIDATE_CREATED and ASSESSED events, making it impossible to compute statistics like approval ratio without reconstructing them indirectly.

---

## Freeze Level Impact

This ADR establishes the reflection event hierarchy as **L2 (Stable)**. Individual payloads are **L2 (Stable)** and may be extended via `schema_version` evolution.

The existing v1.6.0 and v1.7.0 reflection freezes remain valid. This ADR adds event emission alongside the existing domain object creation.

---

## References

- `rationalevault/skill_platform/reflection_events.py` — Event payload definitions
- `rationalevault/schema/events.py` — EventType enum (updated with new reflection events)
- `rationalevault/schema/identifier_registry.py` — Identifier prefix registry
- `rationalevault/skill_platform/reflection_engine.py` — Updated to produce payloads
- `rationalevault/projections/reflection.py` — Updated to return `(ReflectionReport, ReflectionEventBundle)`
- `docs/v1.6.0_reflection_freeze.md` — F0 contracts
- `docs/v1.7.0_reflection_engine_freeze.md` — F1 engine
