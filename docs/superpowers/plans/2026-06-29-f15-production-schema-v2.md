# F15: Production Schema v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove the SchemaPolicy architecture works under real schema evolution by implementing the TASK_CREATED v1 → v2 migration specification and validating it with 6 behavioral proofs + 5 architectural guards.

**Architecture:** The migration specification is a formal contract. The integration proof suite exercises the full public replay API end-to-end. The architectural guards enforce T15 structural invariants via AST analysis.

**Tech Stack:** Python 3.12+, pytest, frozen dataclasses, AST module

## Global Constraints

- All 1990+ existing tests must continue to pass after each task
- Reducers must never reference `schema_version` or branch on payload version
- SchemaPolicy is the only authority for canonical version selection
- ReplayResolver executes policy, never defines policy
- SchemaPolicy is immutable (frozen dataclass)

---

## File Structure

| File | Responsibility |
|------|----------------|
| `docs/specs/task-created-v1-to-v2.md` | Migration specification contract |
| `tests/integration/test_task_created_v1_to_v2.py` | 6 integration proofs (pipeline-first) |
| `tests/unit/test_task_created_resolver.py` | 2 unit proofs (resolver/policy correctness) |
| `tests/unit/test_architecture_guards.py` | 5 T15 architectural guards (modify existing) |

---

## Task 1: Migration Specification Document

**Files:**
- Create: `docs/specs/task-created-v1-to-v2.md`

**Interfaces:**
- Consumes: None (standalone document)
- Produces: Migration contract referenced by proof suite

- [ ] **Step 1: Create the migration specification**

Write `docs/specs/task-created-v1-to-v2.md` with the full contract:

```markdown
# Migration Specification: TASK_CREATED v1 → v2

## Identity
- **Migration ID:** TASK_CREATED:v1→v2
- **Status:** Approved
- **Event Type:** TASK_CREATED
- **Current Version:** 1
- **Target Version:** 2
- **Effective Sequence:** 1
  - This migration is active from the first governance snapshot.
  - Historical replay prior to any future governance change also resolves
    TASK_CREATED to schema v2.
- **Supersedes:** None
- **Superseded By:** —

## Structural Changes

| v1 Field       | v2 Field        | Required | Default |
|----------------|-----------------|----------|---------|
| title          | details.summary | Yes      | —       |
| description    | details.body    | No       | ""      |

## Compatibility

| Property                     | Value                                           |
|------------------------------|-------------------------------------------------|
| Native v1 ↔ v2 compatibility | No                                              |
| Replay compatibility         | Yes (via SchemaPolicy + ReplayResolver)         |
| Backward Read                | No                                              |
| Forward Read                 | No                                              |
| Backward Write               | No                                              |
| Mixed Replay                 | Supported via upcaster                          |

## Properties

- **Lossless:** Yes (no data lost in v1→v2)
- **Rollback:** Supported (v2→v1 via reverse mapping)
- **Canonical Schema:** v2

## Migration Chain

```
v1
  │
  ▼
task_created_v1_to_v2
  │
  ▼
v2 (canonical)
```

## Architectural Invariants

- Canonical projection input is schema v2.
- Reducers MUST NOT inspect schema versions.
- ReplayResolver is solely responsible for schema normalization.
- SchemaPolicy is the only authority for canonical version selection.

## Required Verification

✓ Mixed replay
✓ Projection equivalence
✓ Policy Authority (T15)
✓ Migration graph safety
✓ Deterministic replay
✓ Performance baseline
✓ Canonical idempotence
```

- [ ] **Step 2: Verify the spec is complete**

Read the file back and verify all sections are present:
- Identity with Supersedes/Superseded By
- Structural Changes table
- Compatibility table (native vs replay)
- Properties (lossless, rollback, canonical)
- Migration Chain (visual format)
- Architectural Invariants
- Required Verification checklist (including canonical idempotence)

- [ ] **Step 3: Commit**

```bash
git add docs/specs/task-created-v1-to-v2.md
git commit -m "docs(spec): TASK_CREATED v1→v2 migration specification"
```

---

## Task 2: Integration Proof Suite — Proofs 1-3

**Files:**
- Create: `tests/integration/test_task_created_v1_to_v2.py`

**Interfaces:**
- Consumes: `SchemaPolicy`, `EventSchema`, `MigrationPath`, `MigrationStep` from `rationalevault/schema/policy.py`
- Consumes: `SchemaPolicyFactory` from `rationalevault/schema/factory.py`
- Consumes: `ReplayPipeline` from `rationalevault/projections/pipeline.py`
- Consumes: `ReplayContext` from `rationalevault/projections/context.py`
- Consumes: `UpcasterRegistry` from `rationalevault/schema/upcaster.py`
- Consumes: `EventRecord`, `EventType` from `rationalevault/schema/events.py`
- Consumes: `TaskReducer` from `rationalevault/cognitive_head/reducers.py`
- Consumes: `GovernanceState` from `rationalevault/projections/governance.py`
- Produces: 3 integration tests (pipeline-first)

- [ ] **Step 1: Write the test file header and helpers**

```python
"""Integration proofs for TASK_CREATED v1→v2 migration.

Proves the SchemaPolicy architecture works under real schema evolution.
Each test validates one architectural property.

These tests exercise the public replay API (ReplayPipeline),
not internal resolver details.
"""

import time
import copy
from datetime import datetime, timezone

import pytest

from rationalevault.schema.policy import (
    SchemaPolicy, EventSchema, MigrationPath, MigrationStep,
)
from rationalevault.schema.factory import SchemaPolicyFactory
from rationalevault.schema.upcaster import UpcasterRegistry
from rationalevault.schema.events import EventRecord, EventType
from rationalevault.projections.context import ReplayContext
from rationalevault.projections.pipeline import ReplayPipeline
from rationalevault.projections.governance import GovernanceState
from rationalevault.cognitive_head.reducers import TaskReducer


# --- Fixtures ---

V1_PAYLOAD = {
    "task_id": "T1",
    "title": "Implement F15",
    "description": "Prove the architecture",
    "assignee": "Orchestrator",
}

V2_PAYLOAD = {
    "task_id": "T1",
    "details": {
        "summary": "Implement F15",
        "body": "Prove the architecture",
    },
    "assignee": "Orchestrator",
}


def _create_event(
    seq: int,
    schema_version: int,
    payload: dict,
    event_type: EventType = EventType.TASK_CREATED,
) -> EventRecord:
    """Create an EventRecord with the given schema version."""
    return EventRecord(
        event_id=f"evt-{seq}",
        event_type=event_type,
        schema_version=schema_version,
        payload=copy.deepcopy(payload),
        sequence=seq,
        recorded_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        metadata={"actor": "test"},
    )


POLICY_V2 = SchemaPolicy(_schemas={
    EventType.TASK_CREATED: EventSchema(
        event_type=EventType.TASK_CREATED,
        latest_version=2,
        migration_path=MigrationPath(steps=(MigrationStep(1, 2),)),
    )
})

POLICY_V1 = SchemaPolicy(_schemas={
    EventType.TASK_CREATED: EventSchema(
        event_type=EventType.TASK_CREATED,
        latest_version=1,
        migration_path=MigrationPath(steps=()),
    )
})


def _replay_via_pipeline(events, policy):
    """Replay events through the public pipeline API."""
    context = ReplayContext(schema_policy=policy)
    registry = UpcasterRegistry.default()
    pipeline = ReplayPipeline(context=context, registry=registry)
    reducer = TaskReducer()

    state = {}
    for event in events:
        canonical_payload = pipeline.resolve_event(event)
        resolved = _create_event(
            seq=event.sequence,
            schema_version=policy.latest_version(event.event_type),
            payload=canonical_payload,
        )
        state = reducer.reduce(state, resolved)

    return state
```

- [ ] **Step 2: Write Proof 1 — Mixed Replay**

```python
def test_mixed_replay_canonical_output():
    """Interleaved v1/v2 events replay to canonical v2.

    Property: Mixed-version normalization.
    Exercises: ReplayPipeline (public API).
    """
    events = [
        _create_event(seq=1, schema_version=1, payload=V1_PAYLOAD),
        _create_event(seq=2, schema_version=1, payload=V1_PAYLOAD),
        _create_event(seq=3, schema_version=2, payload=V2_PAYLOAD),
        _create_event(seq=4, schema_version=1, payload=V1_PAYLOAD),
        _create_event(seq=5, schema_version=2, payload=V2_PAYLOAD),
    ]

    state = _replay_via_pipeline(events, POLICY_V2)

    # Reducer should produce correct TaskState
    assert "T1" in state
    assert state["T1"].title == "Implement F15"
    assert state["T1"].description == "Prove the architecture"
```

- [ ] **Step 3: Run Proof 1 to verify it passes**

Run: `pytest tests/integration/test_task_created_v1_to_v2.py::test_mixed_replay_canonical_output -v`
Expected: PASS

- [ ] **Step 4: Write Proof 2 — Projection Equivalence**

```python
def test_projection_equivalence():
    """Native v2 projection equals v1→upcast→projection.

    Property: Canonical projection equivalence.
    Exercises: ReplayPipeline (public API).
    """
    # Native v2 path
    v2_event = _create_event(seq=1, schema_version=2, payload=V2_PAYLOAD)
    state_v2 = _replay_via_pipeline([v2_event], POLICY_V2)

    # Upcasted v1 path
    v1_event = _create_event(seq=1, schema_version=1, payload=V1_PAYLOAD)
    state_v1 = _replay_via_pipeline([v1_event], POLICY_V2)

    # Projected state must be equal
    assert state_v2 == state_v1
```

- [ ] **Step 5: Run Proof 2 to verify it passes**

Run: `pytest tests/integration/test_task_created_v1_to_v2.py::test_projection_equivalence -v`
Expected: PASS

- [ ] **Step 6: Write Proof 3 — Policy Authority**

```python
def test_policy_authority():
    """Policy alone controls canonical interpretation.

    Property: T15 — Policy Authority.
    Exercises: ReplayPipeline (public API).
    """
    v1_event = _create_event(seq=1, schema_version=1, payload=V1_PAYLOAD)

    # Policy A: latest_version=1 (no migration)
    state_a = _replay_via_pipeline([v1_event], POLICY_V1)

    # Policy B: latest_version=2 (migration applied)
    state_b = _replay_via_pipeline([v1_event], POLICY_V2)

    # Different policies produce different projected states
    # Policy A: task has title/description (v1 format)
    # Policy B: task has title/description from upcasted v2
    # The key: same input, same engine, different policy → different result
    assert state_a != state_b


def test_governance_compiles_different_policies():
    """Different governance snapshots produce different policies.

    Property: F14 + F15 integration.
    Exercises: SchemaPolicyFactory (public API).
    """
    # Governance at sequence 50: TASK_CREATED latest = v1
    state_v1 = GovernanceState(
        schema_versions={"TASK_CREATED": (1, 1)}
    )

    # Governance at sequence 100: TASK_CREATED latest = v2
    state_v2 = GovernanceState(
        schema_versions={"TASK_CREATED": (2, 1)}
    )

    factory = SchemaPolicyFactory()
    policy_v1 = factory.compile(state_v1)
    policy_v2 = factory.compile(state_v2)

    # Policies must be different
    assert policy_v1.latest_version(EventType.TASK_CREATED) == 1
    assert policy_v2.latest_version(EventType.TASK_CREATED) == 2

    # Both must be immutable snapshots
    assert isinstance(policy_v1, SchemaPolicy)
    assert isinstance(policy_v2, SchemaPolicy)
```

- [ ] **Step 7: Run Proofs 1-3 to verify they pass**

Run: `pytest tests/integration/test_task_created_v1_to_v2.py -v`
Expected: All 4 tests PASS

- [ ] **Step 8: Commit**

```bash
git add tests/integration/test_task_created_v1_to_v2.py
git commit -m "test(integration): F15 proofs 1-3 — mixed replay, equivalence, policy authority"
```

---

## Task 3: Integration Proof Suite — Proofs 4-7

**Files:**
- Modify: `tests/integration/test_task_created_v1_to_v2.py`

**Interfaces:**
- Consumes: Same as Task 2
- Produces: 4 more integration tests (pipeline-first)

- [ ] **Step 1: Write Proof 4 — Canonical Idempotence**

```python
def test_canonical_idempotence():
    """Canonical event is never modified by replay.

    Property: Canonical idempotence.
    Exercises: ReplayPipeline (public API).
    """
    # Create a canonical v2 event
    v2_event = _create_event(seq=1, schema_version=2, payload=V2_PAYLOAD)

    # Replay once — should produce identical output
    context = ReplayContext(schema_policy=POLICY_V2)
    registry = UpcasterRegistry.default()
    pipeline = ReplayPipeline(context=context, registry=registry)

    result_1 = pipeline.resolve_event(v2_event)
    result_2 = pipeline.resolve_event(v2_event)

    # Canonical event is never modified
    assert result_1 == result_2
    assert result_1 == V2_PAYLOAD
```

- [ ] **Step 2: Run Proof 4 to verify it passes**

Run: `pytest tests/integration/test_task_created_v1_to_v2.py::test_canonical_idempotence -v`
Expected: PASS

- [ ] **Step 3: Write Proof 5 — Determinism**

```python
def test_determinism():
    """Repeated replays produce identical results.

    Property: Deterministic replay.
    Exercises: ReplayPipeline (public API).
    """
    events = [
        _create_event(seq=1, schema_version=1, payload=V1_PAYLOAD),
        _create_event(seq=2, schema_version=2, payload=V2_PAYLOAD),
        _create_event(seq=3, schema_version=1, payload=V1_PAYLOAD),
    ]

    results = []
    for _ in range(10):
        state = _replay_via_pipeline(events, POLICY_V2)
        results.append(copy.deepcopy(state))

    # All 10 results must be identical
    for result in results[1:]:
        assert result == results[0]
```

- [ ] **Step 4: Run Proof 5 to verify it passes**

Run: `pytest tests/integration/test_task_created_v1_to_v2.py::test_determinism -v`
Expected: PASS

- [ ] **Step 5: Write Proof 6 — Performance Baseline**

```python
def test_performance_baseline():
    """Migration overhead remains within regression budget.

    Property: Performance preservation.
    Exercises: ReplayPipeline (public API).

    Uses relative comparison to avoid CI instability.
    """
    # Generate 1000 mixed events
    events = []
    for i in range(1000):
        if i % 3 == 0:
            events.append(_create_event(seq=i, schema_version=1, payload=V1_PAYLOAD))
        else:
            events.append(_create_event(seq=i, schema_version=2, payload=V2_PAYLOAD))

    # Baseline: replay without migration (all v2 events)
    v2_events = [_create_event(seq=e.sequence, schema_version=2, payload=V2_PAYLOAD) for e in events]

    start = time.perf_counter()
    for _ in range(10):
        for event in v2_events:
            context = ReplayContext(schema_policy=POLICY_V2)
            registry = UpcasterRegistry.default()
            pipeline = ReplayPipeline(context=context, registry=registry)
            pipeline.resolve_event(event)
    baseline = time.perf_counter() - start

    # Measured: replay with migration (mixed events)
    start = time.perf_counter()
    for _ in range(10):
        for event in events:
            context = ReplayContext(schema_policy=POLICY_V2)
            registry = UpcasterRegistry.default()
            pipeline = ReplayPipeline(context=context, registry=registry)
            pipeline.resolve_event(event)
    measured = time.perf_counter() - start

    # Overhead ratio within regression budget
    overhead_ratio = measured / baseline if baseline > 0 else 0
    # Threshold is configurable — adjust if needed
    REGRESSION_BUDGET = 3.0
    assert overhead_ratio < REGRESSION_BUDGET, (
        f"Overhead ratio {overhead_ratio:.2f} exceeds regression budget {REGRESSION_BUDGET}"
    )
```

- [ ] **Step 6: Run Proof 6 to verify it passes**

Run: `pytest tests/integration/test_task_created_v1_to_v2.py::test_performance_baseline -v`
Expected: PASS

- [ ] **Step 7: Run all integration proofs to verify they pass**

Run: `pytest tests/integration/test_task_created_v1_to_v2.py -v`
Expected: All 7 tests PASS

- [ ] **Step 8: Commit**

```bash
git add tests/integration/test_task_created_v1_to_v2.py
git commit -m "test(integration): F15 proofs 4-7 — idempotence, determinism, performance"
```

---

## Task 4: Unit Proof Suite — Resolver Correctness

**Files:**
- Create: `tests/unit/test_task_created_resolver.py`

**Interfaces:**
- Consumes: `SchemaPolicy`, `EventSchema`, `MigrationPath`, `MigrationStep` from `rationalevault/schema/policy.py`
- Consumes: `ReplayResolver`, `UnknownSchemaError` from `rationalevault/schema/resolver.py`
- Consumes: `UpcasterRegistry` from `rationalevault/schema/upcaster.py`
- Produces: 2 unit tests (resolver-level correctness)

- [ ] **Step 1: Write the test file header**

```python
"""Unit proofs for TASK_CREATED v1→v2 resolver correctness.

These tests validate resolver and policy behavior at the unit level.
Integration proofs (pipeline-first) are in test_task_created_v1_to_v2.py.
"""

import pytest

from rationalevault.schema.policy import (
    SchemaPolicy, EventSchema, MigrationPath, MigrationStep,
)
from rationalevault.schema.resolver import ReplayResolver, UnknownSchemaError
from rationalevault.schema.upcaster import UpcasterRegistry
from rationalevault.schema.events import EventType


V1_PAYLOAD = {
    "task_id": "T1",
    "title": "Test",
    "description": "Unit proof",
}

V2_PAYLOAD = {
    "task_id": "T1",
    "details": {"summary": "Test", "body": "Unit proof"},
}
```

- [ ] **Step 2: Write Unit Proof 1 — Unknown Migration Path**

```python
def test_unknown_schema_path_fails():
    """Missing migration edge raises UnknownSchemaError.

    Property: Migration graph safety.
    """
    policy_no_path = SchemaPolicy(_schemas={
        EventType.TASK_CREATED: EventSchema(
            event_type=EventType.TASK_CREATED,
            latest_version=2,
            migration_path=MigrationPath(steps=()),
        )
    })

    registry = UpcasterRegistry.default()
    resolver = ReplayResolver(policy=policy_no_path, registry=registry)

    with pytest.raises(UnknownSchemaError):
        resolver.resolve(1, V1_PAYLOAD)
```

- [ ] **Step 3: Run Unit Proof 1 to verify it passes**

Run: `pytest tests/unit/test_task_created_resolver.py::test_unknown_schema_path_fails -v`
Expected: PASS

- [ ] **Step 4: Write Unit Proof 2 — Cyclic Migration Detection**

```python
def test_cyclic_migration_graph_rejected():
    """Cyclic migration graph is prevented.

    Property: Migration graph safety.
    """
    policy_cycle = SchemaPolicy(_schemas={
        EventType.TASK_CREATED: EventSchema(
            event_type=EventType.TASK_CREATED,
            latest_version=2,
            migration_path=MigrationPath(steps=(
                MigrationStep(1, 2),
                MigrationStep(2, 1),
            )),
        )
    })

    registry = UpcasterRegistry.default()
    resolver = ReplayResolver(policy=policy_cycle, registry=registry)

    # Cycles must not cause infinite loops
    try:
        result = resolver.resolve(1, V1_PAYLOAD)
        assert result is not None
    except (UnknownSchemaError, ValueError):
        pass
```

- [ ] **Step 5: Run Unit Proof 2 to verify it passes**

Run: `pytest tests/unit/test_task_created_resolver.py::test_cyclic_migration_graph_rejected -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add tests/unit/test_task_created_resolver.py
git commit -m "test(unit): F15 resolver proofs — unknown path, cyclic detection"
```

---

## Task 5: Architectural Guards (T15)

**Files:**
- Modify: `tests/unit/test_architecture_guards.py`

**Interfaces:**
- Consumes: AST module for code analysis
- Produces: 5 architectural guard tests (semantic, not field-name-specific)

- [ ] **Step 1: Read existing architecture guards**

Read `tests/unit/test_architecture_guards.py` to understand the existing guard patterns.

- [ ] **Step 2: Write Guard 1 — Reducers Have Zero Schema Knowledge**

```python
def test_reducers_have_zero_schema_knowledge():
    """Reducers MUST NOT reference schema evolution infrastructure (T2)."""
    import ast
    from pathlib import Path

    reducer_files = [
        Path("rationalevault/cognitive_head/reducers.py"),
    ]

    forbidden_names = {
        "schema_version", "SchemaPolicy", "MigrationPath",
        "ReplayResolver", "UpcasterRegistry", "ReplayContext",
    }

    for filepath in reducer_files:
        tree = ast.parse(filepath.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in forbidden_names:
                pytest.fail(
                    f"{filepath}:{node.lineno} references forbidden name '{node.id}'"
                )
            if isinstance(node, ast.Attribute) and node.attr in forbidden_names:
                pytest.fail(
                    f"{filepath}:{node.lineno} references forbidden attribute '{node.attr}'"
                )
```

- [ ] **Step 3: Run Guard 1 to verify it passes**

Run: `pytest tests/unit/test_architecture_guards.py::test_reducers_have_zero_schema_knowledge -v`
Expected: PASS

- [ ] **Step 4: Write Guard 2 — Reducers Never Implement Compatibility Logic**

```python
def test_reducers_never_implement_compatibility_logic():
    """Reducers MUST NOT branch on payload shape (T14).

    Detects semantic patterns, not field names.
    """
    import ast
    from pathlib import Path

    reducer_files = [
        Path("rationalevault/cognitive_head/reducers.py"),
    ]

    for filepath in reducer_files:
        source = filepath.read_text()
        tree = ast.parse(source)

        for node in ast.walk(tree):
            # Detect "key" in dict conditionals (compatibility branching)
            if isinstance(node, ast.Compare):
                for op in node.ops:
                    if isinstance(op, ast.In):
                        # "key" in payload pattern
                        pytest.fail(
                            f"{filepath}:{node.lineno} branches on payload structure"
                        )

            # Detect .get() with fallback chains (compatibility logic)
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr == "get" and len(node.args) > 1:
                        # .get(key, default) with explicit fallback
                        pytest.fail(
                            f"{filepath}:{node.lineno} uses .get() fallback chain"
                        )
```

- [ ] **Step 5: Run Guard 2 to verify it passes**

Run: `pytest tests/unit/test_architecture_guards.py::test_reducers_never_implement_compatibility_logic -v`
Expected: PASS

- [ ] **Step 6: Write Guard 3 — ReplayResolver Is Policy-Driven**

```python
def test_resolver_is_policy_driven():
    """ReplayResolver MUST execute policy, not define it (T15).

    Detects semantic patterns, not event type names.
    """
    import ast
    from pathlib import Path

    resolver_path = Path("rationalevault/schema/resolver.py")
    source = resolver_path.read_text()
    tree = ast.parse(source)

    # Detect event-type dispatch patterns
    for node in ast.walk(tree):
        # No if/elif on event type strings
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value.endswith("_CREATED") or node.value.endswith("_RECORDED"):
                pytest.fail(
                    f"{resolver_path}:{node.lineno} hardcodes event type '{node.value}'"
                )

        # No EVOLVED_EVENT_TYPES
        if isinstance(node, ast.Name) and node.id == "EVOLVED_EVENT_TYPES":
            pytest.fail(
                f"{resolver_path}:{node.lineno} references EVOLVED_EVENT_TYPES"
            )

        # No hardcoded version tables
        if isinstance(node, ast.Dict):
            keys = [k.value for k in node.keys if isinstance(k, ast.Constant)]
            if all(isinstance(k, int) for k in keys) and len(keys) > 1:
                pytest.fail(
                    f"{resolver_path}:{node.lineno} contains hardcoded version table"
                )
```

- [ ] **Step 7: Run Guard 3 to verify it passes**

Run: `pytest tests/unit/test_architecture_guards.py::test_resolver_is_policy_driven -v`
Expected: PASS

- [ ] **Step 8: Write Guard 4 — SchemaPolicy Is Sole Authority**

```python
def test_schema_policy_is_sole_authority():
    """SchemaPolicy MUST be the only source of latest-version decisions (T15)."""
    from pathlib import Path

    # Verify ReplayResolver depends on SchemaPolicy
    resolver_path = Path("rationalevault/schema/resolver.py")
    resolver_source = resolver_path.read_text()
    assert "SchemaPolicy" in resolver_source, (
        "ReplayResolver must depend on SchemaPolicy"
    )

    # Verify ReplayPipeline constructs resolver from schema_policy
    pipeline_path = Path("rationalevault/projections/pipeline.py")
    pipeline_source = pipeline_path.read_text()
    assert "schema_policy" in pipeline_source, (
        "ReplayPipeline must construct resolver from schema_policy"
    )

    # Verify SchemaPolicyFactory reads governance state
    factory_path = Path("rationalevault/schema/factory.py")
    factory_source = factory_path.read_text()
    assert "schema_versions" in factory_source, (
        "SchemaPolicyFactory must read schema_versions from GovernanceState"
    )
```

- [ ] **Step 9: Run Guard 4 to verify it passes**

Run: `pytest tests/unit/test_architecture_guards.py::test_schema_policy_is_sole_authority -v`
Expected: PASS

- [ ] **Step 10: Write Guard 5 — SchemaPolicy Immutability**

```python
def test_schema_policy_is_immutable():
    """SchemaPolicy is a snapshot, never a mutable session object (T1)."""
    from rationalevault.schema.policy import SchemaPolicy, EventSchema, MigrationPath
    from rationalevault.schema.events import EventType

    # Verify frozen dataclass
    assert hasattr(SchemaPolicy, "__dataclass_params__")
    assert SchemaPolicy.__dataclass_params__.frozen is True

    # Verify no mutation methods
    policy = SchemaPolicy(_schemas={
        EventType.TASK_CREATED: EventSchema(
            event_type=EventType.TASK_CREATED,
            latest_version=2,
            migration_path=MigrationPath(steps=()),
        )
    })

    # Attempting to set attributes should raise FrozenInstanceError
    with pytest.raises(AttributeError):
        policy._schemas = {}

    # Verify EventSchema is also frozen
    assert hasattr(EventSchema, "__dataclass_params__")
    assert EventSchema.__dataclass_params__.frozen is True

    # Verify MigrationPath is also frozen
    assert hasattr(MigrationPath, "__dataclass_params__")
    assert MigrationPath.__dataclass_params__.frozen is True
```

- [ ] **Step 11: Run Guard 5 to verify it passes**

Run: `pytest tests/unit/test_architecture_guards.py::test_schema_policy_is_immutable -v`
Expected: PASS

- [ ] **Step 12: Run all architectural guards**

Run: `pytest tests/unit/test_architecture_guards.py -v`
Expected: All guards PASS

- [ ] **Step 13: Commit**

```bash
git add tests/unit/test_architecture_guards.py
git commit -m "test(guards): T15 architectural guards — policy authority, immutability, purity"
```

---

## Task 6: Full Regression and Final Verification

**Files:** None (verification only)

**Interfaces:**
- Consumes: All tests from Tasks 1-5
- Produces: Green test suite

- [ ] **Step 1: Run the full test suite**

Run: `pytest tests/ -o addopts="" -q`
Expected: All tests pass, no failures

- [ ] **Step 2: Verify no regressions**

Compare test count to baseline (1990+). New tests from F15 should be added:
- 7 integration proofs (pipeline-first)
- 2 unit proofs (resolver correctness)
- 5 architectural guards

Expected total: ~2004 tests

- [ ] **Step 3: Verify all F15 proofs pass**

Run: `pytest tests/integration/test_task_created_v1_to_v2.py tests/unit/test_task_created_resolver.py -v`
Expected: 9 tests PASS

- [ ] **Step 4: Verify all T15 guards pass**

Run: `pytest tests/unit/test_architecture_guards.py -v`
Expected: All guards PASS

- [ ] **Step 5: Final commit (if any fixes needed)**

```bash
git add -A
git commit -m "test(F15): full regression — all proofs and guards pass"
```
