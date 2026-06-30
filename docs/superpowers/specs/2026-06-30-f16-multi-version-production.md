# F16 — Multi-Version Production

## Status

**APPROVED**

## Summary

F16 validates that the SchemaPolicy architecture scales to **multiple independently evolving event types**. F15 proved schema evolution for a single event type (TASK_CREATED). F16 introduces a second production migration (DECISION_PROPOSED v1→v2) and proves that:

1. Migration graphs are local to each event type
2. SchemaPolicy remains the sole authority across multiple event types
3. Adding a new migrated event type requires no changes to the replay infrastructure
4. Canonicalization is deterministic and idempotent across event types

## Approach

**Single Migration** — Migrate DECISION_PROPOSED v1→v2 with enrichment (add `context` and `category` fields). Mirrors F15 pattern exactly, validates independent per-event-type evolution.

## Migration Specification

### DECISION_PROPOSED v1→v2

| Field       |    v1    |    v2    |            Canonical           |
| ----------- | :------: | :------: | :----------------------------: |
| decision_id |     ✓    |     ✓    |            Required            |
| title       |     ✓    |     ✓    |            Required            |
| description | Optional | Optional |            Optional            |
| rationale   | Optional | Optional |            Optional            |
| context     |     —    | Optional |     Optional (default `""`)    |
| category    |     —    | Optional | Optional (default `"general"`) |

### Compatibility

```
Native v1 ↔ v2:    No
Replay compatibility: Yes
Lossless:            Yes
Rollback:            Yes
Canonical schema:    v2
```

### Upcaster Contract

```
decision_proposed_v1_to_v2

Input:
    schema_version == 1

Output:
    schema_version == 2

Guarantees:
    - preserves all existing fields
    - adds context=""
    - adds category="general"
    - deterministic
    - idempotent
```

### Independence Invariant

Migration paths are owned per event type.

```
TASK_CREATED:
    1 → 2

DECISION_PROPOSED:
    1 → 2
```

No migration edge may reference another event type.

## Integration Proofs

### Proof 1: Independent Migration Paths

Replay a ledger with both TASK_CREATED (v1→v2) and DECISION_PROPOSED (v1→v2) events. Verify:

- TASK_CREATED migration is unaffected by DECISION_PROPOSED
- DECISION_PROPOSED migration is unaffected by TASK_CREATED
- Canonical output correct for both types
- Migration graphs are event-type local

### Proof 2: Mixed Ledger Replay

Replay the same ordered mixed-version ledger repeatedly. Verify:

- Identical canonical output on every replay
- Event sequence is authoritative (not reordered)
- Both resolved event stream and projected state match

### Proof 3: Policy Independence

Create two governance snapshots:

**Policy A:**
```
TASK_CREATED:      latest = 2
DECISION_PROPOSED: latest = 1
```
→ TASK events migrate, DECISION events remain v1

**Policy B:**
```
TASK_CREATED:      latest = 2
DECISION_PROPOSED: latest = 2
```
→ Both event types migrate

Replay the same ledger under both policies. Verify different canonical outputs. This demonstrates T15.

### Proof 4: Canonical Idempotence

Verify for both event types:

```
canonical(canonical(event)) == canonical(event)
```

For native v1 and native v2 inputs.

### Proof 5: Determinism

10 repeated replays of the same mixed ledger. Verify:

- Resolved event stream identical
- Projected state identical
- Entire replay pipeline deterministic

### Proof 6: Performance Baseline

Self-contained benchmark comparing:

**Baseline:** Mixed ledger, 0 migrations (all events already canonical)
**Measured:** Mixed ledger with both event types migrating

Metrics:
```
Total events:           N
Migrated events:        M
Already canonical:      K
Migration ratio:        M/N
TASK_CREATED migrated:  X
DECISION_PROPOSED migrated: Y
Replay throughput:      events/sec
Overhead ratio:         measured / baseline
```

Budget: `MAX_MIGRATION_OVERHEAD_RATIO = 3.0`

### Proof 7: Event-Type Isolation

Construct a registry missing only the DECISION_PROPOSED migration. Verify:

- TASK_CREATED still migrates successfully
- DECISION_PROPOSED fails with UnknownSchemaError
- Replay does not silently substitute another migration path
- Failures are localized per event type

### Proof 8: Registry Completeness

Verify that every migration declared by SchemaPolicy exists in UpcasterRegistry:

```python
for event_type in policy.event_types():
    path = policy.migration_path(event_type)
    for step in path.steps:
        assert registry.has(event_type, step.from_version, step.to_version)
```

This catches the failure mode where governance declares a migration, SchemaPolicy compiles successfully, but the upcoder was never registered. The problem would be silent until replay time.

## Architectural Guards

### Event-Type Local Migration (T3 + T15)

**Intent:** A migration implementation may only transform the schema of its declared event type.

**Must not:**
- Reference another `EventType`
- Inspect another event type's payload
- Dispatch to another event type's migration
- Depend on another event type's canonical schema

**Implementation:** AST scan of upcaster functions. Fail if:
- `EventType.TASK_CREATED` appears in DECISION_PROPOSED upcaster (or vice versa)
- String literal `"TASK_CREATED"` appears in DECISION_PROPOSED upcaster
- Import of another event type's migration function

**Additional validation:** Every migration function has exactly one owning event type.

**Theorem connection:** Protects T15 (Policy Authority) and T3 (Schema Evolution Safety).

**Statement:** Each event type owns an independent migration graph. No migration graph may depend upon another event type's graph.

## Testing Strategy

### Architecture Guards (1 new)

```
Architecture Guards
 └── Event-Type Local Migration (T3 + T15)
```

### Unit (3 new)

```
Unit
 ├── decision_proposed_v1_to_v2 correctness
 ├── DecisionReducer canonical consumption
 └── Resolver/Upcaster edge cases
```

### Integration (8 new)

```
Integration
 ├── Independent Migration Paths
 ├── Mixed Ledger Replay
 ├── Policy Independence
 ├── Canonical Idempotence
 ├── Determinism
 ├── Performance Baseline
 ├── Event-Type Isolation
 └── Registry Completeness
```

### Expected Totals

```
Baseline:    ~2004 passing
F16:         +12 new tests
Expected:    ~2016 passing
```

## Acceptance Criteria

- ✅ Existing tests remain green
- ✅ Existing benchmarks remain within budget
- ✅ No frozen API changes
- ✅ No new architectural guard failures
- ✅ No changes to ReplayPipeline, ReplayResolver, ReplayContext, or SchemaPolicy infrastructure are required to introduce a second migrated event type

F16's strongest architectural claim:

> **Adding a new migrated event type requires only registration — not replay-engine changes.**

## Files Affected

### New

- `docs/specs/decision-proposed-v1-to-v2.md` — Migration specification
- `tests/integration/test_decision_proposed_v1_to_v2.py` — Integration proofs (8 tests)
- `tests/unit/test_decision_proposed_resolver.py` — Unit proofs (3 tests)

### Modified

- `rationalevault/schema/upcaster.py` — Add `decision_proposed_v1_to_v2()` + register `DECISION_PROPOSED: v1 → v2`
- `rationalevault/cognitive_head/reducers.py` — Update DecisionReducer to consume canonical DecisionProposed schema, remain version-agnostic
- `tests/unit/test_architecture_guards.py` — Add event-type local migration guard

## Relation to F15

| Property | F15 | F16 |
|----------|-----|-----|
| Event types migrated | 1 (TASK_CREATED) | 2 (TASK_CREATED + DECISION_PROPOSED) |
| Migration paths | 1 | 2 (independent) |
| Replay engine changes | Yes (policy-driven) | None |
| New architectural concepts | SchemaPolicy, policy authority | None (validation only) |
| Proof focus | Single migration correctness | Independent multi-type evolution |

F16 does not introduce new architectural concepts. It validates that the existing architecture scales to multiple independently evolving event types.
