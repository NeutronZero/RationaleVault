# F15: Production Schema v2 — TASK_CREATED v1 → v2

**Date:** 2026-06-29
**Status:** Approved
**Epoch:** F15

---

## Overview

F15 validates the SchemaPolicy architecture under real schema evolution. The first production migration (`TASK_CREATED v1 → v2`) proves every architectural decision made since F11.

This is not an implementation milestone. It is a **proof milestone** — the architecture is validated by executable tests that its core guarantees hold.

---

## Dependency Chain

```
F11  Event ledger purity
        ↓
F12  Schema versioning
        ↓
F13  Replay infrastructure
        ↓
F14  Governance & interpretation
        ↓
F15  First production schema evolution
```

Until a real schema changes, F14 is still proving an architecture against hypothetical inputs. The first production migration turns those abstractions into working engineering.

---

## Migration Specification

### Identity

- **Migration ID:** TASK_CREATED:v1→v2
- **Status:** Approved
- **Event Type:** TASK_CREATED
- **Current Version:** 1
- **Target Version:** 2
- **Effective Sequence:** 1
  - This migration is active from the first governance snapshot.
  - Historical replay prior to any future governance change also resolves TASK_CREATED to schema v2.
- **Supersedes:** None
- **Superseded By:** —

### Structural Changes

| v1 Field       | v2 Field        | Required | Default |
|----------------|-----------------|----------|---------|
| title          | details.summary | Yes      | —       |
| description    | details.body    | No       | ""      |

### Compatibility

| Property                     | Value                                           |
|------------------------------|-------------------------------------------------|
| Native v1 ↔ v2 compatibility | No                                              |
| Replay compatibility         | Yes (via SchemaPolicy + ReplayResolver)         |
| Backward Read                | No                                              |
| Forward Read                 | No                                              |
| Backward Write               | No                                              |
| Mixed Replay                 | Supported via upcaster                          |

### Properties

- **Lossless:** Yes (no data lost in v1→v2)
- **Rollback:** Supported (v2→v1 via reverse mapping)
- **Canonical Schema:** v2

### Migration Chain

```
v1
  │
  ▼
task_created_v1_to_v2
  │
  ▼
v2 (canonical)
```

### Architectural Invariants

- Canonical projection input is schema v2.
- Reducers MUST NOT inspect schema versions.
- ReplayResolver is solely responsible for schema normalization.
- SchemaPolicy is the only authority for canonical version selection.

### Required Verification

✓ Mixed replay
✓ Projection equivalence
✓ Policy Authority (T15)
✓ Migration graph safety
✓ Deterministic replay
✓ Performance baseline

---

## Proof Suite

### File: `tests/integration/test_task_created_v1_to_v2.py`

Six behavioral proofs, each testing one architectural property.

### Proof 1: Mixed Replay

**Property:** Interleaved v1/v2 events replay to a single canonical v2 stream.

```python
def test_mixed_replay_canonical_output():
    """Interleaved v1/v2 events replay to canonical v2."""
    # Create 5 events: v1, v1, v2, v1, v2
    # Replay through pipeline with SchemaPolicy(latest_version=2)
    # Assert all 5 events resolve to canonical v2 format
    # Assert TaskReducer produces correct TaskState for each
```

### Proof 2: Projection Equivalence

**Property:** Native v2 projection equals v1→upcast→projection.

```python
def test_projection_equivalence():
    """Native v2 projection equals v1→upcast→projection."""
    # Replay native v2 event → resolved_events, projected_state
    # Replay v1 event (pipeline upcasts) → resolved_events_upcasted, projected_state_upcasted
    # Assert resolved_events == resolved_events_upcasted
    # Assert projected_state == projected_state_upcasted
```

### Proof 3: Policy Authority (T15)

**Property:** SchemaPolicy alone controls interpretation. Same input, same engine, different policy → different canonical output.

```python
def test_policy_authority():
    """Policy alone controls canonical interpretation."""
    # Policy A: TASK_CREATED latest_version=1 (no migration)
    # Policy B: TASK_CREATED latest_version=2 (migration applied)
    # Same v1 input event, same replay engine
    # Policy A → canonical v1 output
    # Policy B → canonical v2 output
    # Only SchemaPolicy changes

def test_governance_compiles_different_policies():
    """Different governance snapshots produce different policies."""
    # GovernanceState at seq 50: TASK_CREATED latest=v1
    # GovernanceState at seq 100: TASK_CREATED latest=v2
    # SchemaPolicyFactory.compile_at_sequence(state, 50) → policy_v1
    # SchemaPolicyFactory.compile_at_sequence(state, 100) → policy_v2
    # Assert policy_v1 != policy_v2
    # Assert both are immutable snapshots
```

### Proof 4: Migration Graph Safety

**Property:** Incomplete or invalid migration graphs fail with UnknownSchemaError.

```python
def test_unknown_schema_path_fails():
    """Missing migration edge raises UnknownSchemaError."""
    # TASK_CREATED schema_version=3
    # Policy: latest=4, migration chain 3→4 missing
    # Assert UnknownSchemaError raised

def test_cyclic_migration_graph_rejected():
    """Cyclic migration graph is prevented at policy construction."""
    # Policy: TASK_CREATED migration 1→2, 2→1 (cycle)
    # Assert SchemaPolicyFactory rejects or SchemaPolicy.can_resolve returns False
    # Note: cycles are prevented during SchemaPolicy construction,
    # not at resolver execution time
```

### Proof 5: Determinism

**Property:** Repeated replays produce identical results.

```python
def test_determinism():
    """Repeated replays produce identical results."""
    # Replay mixed events 10 times
    # Assert all results are identical
```

### Proof 6: Performance Baseline

**Property:** Migration overhead is measurable and bounded.

```python
def test_performance_baseline():
    """Migration overhead is within acceptable bounds."""
    # Replay 1000 events without migration → baseline
    # Replay 1000 events with migration → measured
    # Assert overhead_ratio < threshold
    # Use relative comparison, not absolute timing
```

---

## Architectural Guards (T15)

### File: `tests/unit/test_architecture_guards.py`

Five theorem-oriented guards that enforce structural rules.

### Guard 1: Reducers Have Zero Schema Knowledge (T2)

```python
def test_reducers_have_zero_schema_knowledge():
    """Reducers MUST NOT reference schema evolution infrastructure."""
    # AST-scan all reducer files
    # Assert no references to: schema_version, SchemaPolicy, MigrationPath,
    #   ReplayResolver, UpcasterRegistry
```

### Guard 2: Reducers Never Implement Compatibility Logic (T14)

```python
def test_reducers_never_implement_compatibility_logic():
    """Reducers MUST NOT branch on payload shape."""
    # AST-scan reducer functions
    # Assert no conditional on payload structure (e.g., "details" in payload)
    # Assert no compatibility fallback chains
```

### Guard 3: ReplayResolver Is Policy-Driven (T15)

```python
def test_resolver_is_policy_driven():
    """ReplayResolver MUST execute policy, not define it."""
    # AST-scan resolver.py
    # Assert no EventType.X comparisons
    # Assert no string comparisons against event types
    # Assert no EVOLVED_EVENT_TYPES
    # Assert no hardcoded version tables
```

### Guard 4: SchemaPolicy Is Sole Authority (T15)

```python
def test_schema_policy_is_sole_authority():
    """SchemaPolicy MUST be the only source of latest-version decisions."""
    # Verify ReplayResolver depends on SchemaPolicy
    # Verify ReplayPipeline constructs resolver from ReplayContext.schema_policy
    # Verify no module except SchemaPolicyFactory decides latest schema version
```

### Guard 5: SchemaPolicy Immutability (T1)

```python
def test_schema_policy_is_immutable():
    """SchemaPolicy is a snapshot, never a mutable session object."""
    # Verify frozen dataclass
    # Assert no mutation methods
    # Assert no mutable public fields
```

---

## Guard-to-Theorem Mapping

| Guard | Protects                           |
|-------|------------------------------------|
| G1    | T2 — Projection Purity             |
| G2    | T14 — Canonical Projection Input   |
| G3    | T15 — Policy Authority             |
| G4    | T3 — Schema Evolution Safety       |
| G5    | T1 — Replay Determinism            |

---

## Implementation Tasks

### Task 1: Migration Specification Document

Write `docs/specs/task-created-v1-to-v2.md` with the full contract above.

### Task 2: Integration Proof Suite

Write `tests/integration/test_task_created_v1_to_v2.py` with 6 proofs.

### Task 3: Architectural Guards

Add 5 T15 guards to `tests/unit/test_architecture_guards.py`.

### Task 4: Final Verification

Run full test suite. All tests must pass. No regressions.

---

## Acceptance Gates

| Stage                    | Gate                                                     |
|--------------------------|----------------------------------------------------------|
| Migration Designer       | Migration specification approved                         |
| Schema Evolution Steward | Policy completeness verified                             |
| Validation Engineer      | Six proofs pass                                          |
| Performance Engineer     | Overhead within threshold                                |
| Theorem Guardian         | T15 + architectural guards pass                          |
| Release                  | Full regression suite green (1990+ tests, 0 failures)    |
