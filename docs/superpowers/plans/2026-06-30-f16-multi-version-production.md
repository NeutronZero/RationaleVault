# F16: Multi-Version Production Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Validate that the SchemaPolicy architecture scales to multiple independently evolving event types by implementing the DECISION_PROPOSED v1→v2 migration and proving independent per-event-type evolution with 8 integration proofs + 6 unit proofs + 1 architectural guard.

**Architecture:** The upcaster is a pure transformation function registered in UpcasterRegistry. The integration proof suite exercises the full public replay API with mixed event-type ledgers. The architectural guard enforces event-type local migration via AST analysis.

**Tech Stack:** Python 3.12+, pytest, frozen dataclasses, AST module

## Global Constraints

- All 2004+ existing tests must continue to pass after each task
- Reducers must never reference `schema_version` or branch on payload version
- SchemaPolicy is the only authority for canonical version selection
- ReplayResolver executes policy, never defines policy
- No changes to ReplayPipeline, ReplayResolver, ReplayContext, or SchemaPolicy infrastructure
- Migration graphs are local to each event type — no cross-event-type references
- Future schema evolution should not require reducer changes (after F16, canonical payload is consumed as-is)
- Shared migration helpers are intentionally deferred until three or more production migrations demonstrate genuine commonality

---

## File Structure

| File | Responsibility |
|------|----------------|
| `docs/specs/decision-proposed-v1-to-v2.md` | Migration specification contract |
| `rationalevault/schema/upcaster.py` | Add `decision_proposed_v1_to_v2()` + register |
| `rationalevault/cognitive_head/reducers.py` | Update DecisionReducer to consume canonical schema |
| `tests/unit/test_decision_proposed_resolver.py` | 6 unit proofs (upcoder correctness) |
| `tests/integration/test_decision_proposed_v1_to_v2.py` | 8 integration proofs (pipeline-first) |
| `tests/unit/test_architecture_guards.py` | Add event-type local migration guard |

---

## Task 1: Migration Specification Document

**Files:**
- Create: `docs/specs/decision-proposed-v1-to-v2.md`

**Interfaces:**
- Consumes: None (standalone document)
- Produces: Migration contract referenced by proof suite

- [ ] **Step 1: Create the migration specification**

Write `docs/specs/decision-proposed-v1-to-v2.md` with the full contract:

```markdown
# Migration Specification: DECISION_PROPOSED v1 → v2

## Identity
- **Migration ID:** DECISION_PROPOSED:v1→v2
- **Status:** Approved
- **Event Type:** DECISION_PROPOSED
- **Current Version:** 1
- **Target Version:** 2
- **Effective Sequence:** 1
- **Supersedes:** None
- **Superseded By:** —

## Structural Changes

| v1 Field     | v2 Field  | Required | Default     |
|--------------|-----------|----------|-------------|
| decision_id  | decision_id | Yes    | —           |
| title        | title     | Yes      | —           |
| description  | description | No    | ""          |
| rationale    | rationale | No       | ""          |
| —            | context   | No       | ""          |
| —            | category  | No       | "general"   |

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
decision_proposed_v1_to_v2
  │
  ▼
v2 (canonical)
```

## Upcaster Contract

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

## Independence Invariant

Migration paths are owned per event type.

```
TASK_CREATED:
    1 → 2

DECISION_PROPOSED:
    1 → 2
```

No migration edge may reference another event type.

## Architectural Invariants

- Canonical projection input is schema v2.
- Reducers MUST NOT inspect schema versions.
- SchemaPolicy is the sole authority for canonical version selection.
```

- [ ] **Step 2: Commit**

```bash
git add docs/specs/decision-proposed-v1-to-v2.md
git commit -m "docs(spec): DECISION_PROPOSED v1→v2 migration specification"
```

---

## Task 2: Upcaster Implementation

**Files:**
- Modify: `rationalevault/schema/upcaster.py`

**Interfaces:**
- Consumes: None (standalone function)
- Produces: `decision_proposed_v1_to_v2()` function, registered in `UpcasterRegistry.default()`

- [ ] **Step 1: Write the upcaster function**

Add to `rationalevault/schema/upcaster.py` after the `task_created_v1_to_v2` function:

```python
def decision_proposed_v1_to_v2(payload: dict[str, Any]) -> dict[str, Any]:
    """Upcasts DECISION_PROPOSED payload from v1 to v2 by adding context and category."""
    payload_copy = dict(payload)
    payload_copy.setdefault("context", "")
    payload_copy.setdefault("category", "general")
    return payload_copy
```

- [ ] **Step 2: Register in UpcasterRegistry.default()**

Update the `default()` classmethod:

```python
@classmethod
def default(cls) -> UpcasterRegistry:
    """Create a registry pre-populated with all production upcasters."""
    return cls({
        "TASK_CREATED": {1: task_created_v1_to_v2},
        "DECISION_PROPOSED": {1: decision_proposed_v1_to_v2},
    })
```

- [ ] **Step 3: Run existing tests to verify no regressions**

Run: `pytest tests/ -o addopts="" -q`
Expected: All 2004+ tests pass

- [ ] **Step 4: Commit**

```bash
git add rationalevault/schema/upcaster.py
git commit -m "feat(upcaster): add decision_proposed_v1_to_v2 + register"
```

---

## Task 3: Unit Proofs — Upcaster Correctness

**Files:**
- Create: `tests/unit/test_decision_proposed_resolver.py`

**Interfaces:**
- Consumes: `decision_proposed_v1_to_v2` from Task 2
- Produces: 6 unit tests validating upcoder correctness

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_decision_proposed_resolver.py`:

```python
"""Unit proofs for decision_proposed_v1_to_v2 upcoder correctness."""
from rationalevault.schema.upcaster import decision_proposed_v1_to_v2


class TestDecisionProposedV1ToV2:
    """Verify the upcoder transforms v1 payloads to canonical v2."""

    def test_adds_default_context(self) -> None:
        """v1 payload without context gets context=""."""
        v1 = {"decision_id": "d1", "title": "Use FastAPI"}
        result = decision_proposed_v1_to_v2(v1)
        assert result["context"] == ""
        assert result["decision_id"] == "d1"
        assert result["title"] == "Use FastAPI"

    def test_adds_default_category(self) -> None:
        """v1 payload without category gets category="general"."""
        v1 = {"decision_id": "d1", "title": "Use FastAPI"}
        result = decision_proposed_v1_to_v2(v1)
        assert result["category"] == "general"

    def test_preserves_existing_fields(self) -> None:
        """All existing v1 fields are preserved."""
        v1 = {
            "decision_id": "d1",
            "title": "Use FastAPI",
            "description": "For the API layer",
            "rationale": "Simpler than Flask",
        }
        result = decision_proposed_v1_to_v2(v1)
        assert result["decision_id"] == "d1"
        assert result["title"] == "Use FastAPI"
        assert result["description"] == "For the API layer"
        assert result["rationale"] == "Simpler than Flask"
        assert result["context"] == ""
        assert result["category"] == "general"

    def test_does_not_overwrite_existing_context(self) -> None:
        """If context already exists, it is preserved."""
        v1 = {"decision_id": "d1", "title": "T", "context": "prod context"}
        result = decision_proposed_v1_to_v2(v1)
        assert result["context"] == "prod context"

    def test_does_not_overwrite_existing_category(self) -> None:
        """If category already exists, it is preserved."""
        v1 = {"decision_id": "d1", "title": "T", "category": "architectural"}
        result = decision_proposed_v1_to_v2(v1)
        assert result["category"] == "architectural"

    def test_idempotent(self) -> None:
        """Applying the upcoder twice produces the same result."""
        v1 = {"decision_id": "d1", "title": "T"}
        once = decision_proposed_v1_to_v2(v1)
        twice = decision_proposed_v1_to_v2(once)
        assert once == twice
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `pytest tests/unit/test_decision_proposed_resolver.py -v`
Expected: All 6 tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_decision_proposed_resolver.py
git commit -m "test(unit): decision_proposed_v1_to_v2 upcaster correctness proofs"
```

---

## Task 4: DecisionReducer Canonical Consumption

**Files:**
- Modify: `rationalevault/cognitive_head/reducers.py`

**Interfaces:**
- Consumes: Canonical DECISION_PROPOSED v2 payload (with `context` and `category`)
- Produces: DecisionState with `context` and `category` fields

- [ ] **Step 1: Add context and category to DecisionState**

In `rationalevault/cognitive_head/reducers.py`, update the `DecisionState` dataclass:

```python
@dataclass
class DecisionState:
    decision_id: str
    title: str
    description: str
    status: str
    rationale: str
    context: str
    category: str
    superseded_by: str | None
    created_at: str | None
    accepted_at: str | None
    created_by: str | None
```

- [ ] **Step 2: Update DecisionReducer to consume canonical fields**

In the `DecisionReducer.reduce()` method, update the DECISION_PROPOSED branch:

```python
if et == EventType.DECISION_PROPOSED:
    if not decision_id:
        continue
    decisions[decision_id] = DecisionState(
        decision_id=decision_id,
        title=p.get("title", ""),
        description=p.get("description", ""),
        status="proposed",
        rationale=p.get("rationale", ""),
        context=p.get("context", ""),
        category=p.get("category", "general"),
        superseded_by=None,
        created_at=(
            event.recorded_at.isoformat()
            if event.recorded_at else None
        ),
        created_by=event.metadata.actor,
    )
```

- [ ] **Step 3: Update DecisionState docstring**

Update the class docstring to document the new fields:

```python
class DecisionState:
    """
    State of a single decision, folded from DECISION_* events.

    Fields:
        decision_id:  Unique identifier
        title:        Human-readable title
        description:  Longer explanation
        status:       "proposed" | "accepted" | "superseded"
        rationale:    Reasoning behind the decision
        context:      Additional context (canonical v2)
        category:     Decision category (canonical v2, default "general")
        superseded_by: decision_id that superseded this one, if any
        created_at:   ISO timestamp of DECISION_PROPOSED
        accepted_at:  ISO timestamp of DECISION_ACCEPTED
        created_by:   Actor who proposed the decision
    """
```

- [ ] **Step 4: Run existing tests to verify no regressions**

Run: `pytest tests/ -o addopts="" -q`
Expected: All 2004+ tests pass

- [ ] **Step 5: Commit**

```bash
git add rationalevault/cognitive_head/reducers.py
git commit -m "feat(reducer): DecisionReducer consumes canonical DecisionProposed schema"
```

---

## Task 5: Integration Proof Suite

**Files:**
- Create: `tests/integration/test_decision_proposed_v1_to_v2.py`

**Interfaces:**
- Consumes: `decision_proposed_v1_to_v2` (Task 2), `UpcasterRegistry.default()` (Task 2), `SchemaPolicy`, `ReplayPipeline`
- Produces: 8 integration proofs

- [ ] **Step 1: Write the integration proofs**

Create `tests/integration/test_decision_proposed_v1_to_v2.py`:

```python
"""Integration proofs for DECISION_PROPOSED v1→v2 — independent per-event-type evolution."""
from __future__ import annotations

import time
from rationalevault.schema.events import EventRecord, EventType, EventMetadata
from rationalevault.schema.policy import SchemaPolicy, EventSchema, MigrationPath, MigrationStep
from rationalevault.schema.upcaster import UpcasterRegistry
from rationalevault.projections.context import ReplayContext
from rationalevault.projections.pipeline import ReplayPipeline
from rationalevault.cognitive_head.reducers import DecisionReducer, TaskReducer
from datetime import datetime, timezone


def _make_event(
    event_type: EventType,
    payload: dict,
    sequence: int,
    schema_version: int = 1,
    recorded_at: datetime | None = None,
) -> EventRecord:
    return EventRecord(
        event_type=event_type,
        payload=payload,
        schema_version=schema_version,
        sequence=sequence,
        recorded_at=recorded_at or datetime(2025, 1, 1, tzinfo=timezone.utc),
        metadata=EventMetadata(actor="test"),
    )


def _make_policy(
    task_latest: int = 2,
    decision_latest: int = 2,
) -> SchemaPolicy:
    schemas = {}
    schemas[EventType.TASK_CREATED] = EventSchema(
        event_type=EventType.TASK_CREATED,
        latest_version=task_latest,
        migration_path=MigrationPath(steps=(
            MigrationStep(from_version=1, to_version=2),
        ) if task_latest >= 2 else ()),
    )
    schemas[EventType.DECISION_PROPOSED] = EventSchema(
        event_type=EventType.DECISION_PROPOSED,
        latest_version=decision_latest,
        migration_path=MigrationPath(steps=(
            MigrationStep(from_version=1, to_version=2),
        ) if decision_latest >= 2 else ()),
    )
    return SchemaPolicy(_schemas=schemas)


def _make_mixed_ledger() -> list[EventRecord]:
    return [
        _make_event(EventType.TASK_CREATED, {"title": "Task A", "description": "desc"}, 1, schema_version=1),
        _make_event(EventType.DECISION_PROPOSED, {"decision_id": "d1", "title": "Decision 1"}, 2, schema_version=1),
        _make_event(EventType.TASK_CREATED, {"title": "Task B", "description": ""}, 3, schema_version=2),
        _make_event(EventType.DECISION_PROPOSED, {"decision_id": "d2", "title": "Decision 2"}, 4, schema_version=1),
        _make_event(EventType.DECISION_PROPOSED, {
            "decision_id": "d3", "title": "Decision 3",
            "context": "has context", "category": "architectural",
        }, 5, schema_version=2),
    ]


class TestIndependentMigrationPaths:
    """Proof 1: Each event type migrates independently."""

    def test_task_migration_unaffected_by_decision(self) -> None:
        """TASK_CREATED migration works regardless of DECISION_PROPOSED presence."""
        policy = _make_policy(task_latest=2, decision_latest=1)
        registry = UpcasterRegistry.default()
        ctx = ReplayContext(schema_policy=policy)
        pipeline = ReplayPipeline(registry=registry, context=ctx)

        events = [
            _make_event(EventType.TASK_CREATED, {"title": "T1", "description": "d"}, 1, schema_version=1),
            _make_event(EventType.DECISION_PROPOSED, {"decision_id": "d1", "title": "D1"}, 2, schema_version=1),
        ]
        result = pipeline.process(events)

        task_events = [e for e in result if e.event_type == EventType.TASK_CREATED]
        assert task_events[0].payload["details"]["summary"] == "T1"

    def test_decision_migration_unaffected_by_task(self) -> None:
        """DECISION_PROPOSED migration works regardless of TASK_CREATED presence."""
        policy = _make_policy(task_latest=1, decision_latest=2)
        registry = UpcasterRegistry.default()
        ctx = ReplayContext(schema_policy=policy)
        pipeline = ReplayPipeline(registry=registry, context=ctx)

        events = [
            _make_event(EventType.TASK_CREATED, {"title": "T1", "description": "d"}, 1, schema_version=1),
            _make_event(EventType.DECISION_PROPOSED, {"decision_id": "d1", "title": "D1"}, 2, schema_version=1),
        ]
        result = pipeline.process(events)

        decision_events = [e for e in result if e.event_type == EventType.DECISION_PROPOSED]
        assert decision_events[0].payload["context"] == ""
        assert decision_events[0].payload["category"] == "general"


class TestMixedLedgerReplay:
    """Proof 2: Mixed-version ledger replays deterministically."""

    def test_repeated_replay_identical_output(self) -> None:
        """Replaying the same ordered mixed ledger produces identical results."""
        policy = _make_policy()
        registry = UpcasterRegistry.default()

        results = []
        for _ in range(5):
            ctx = ReplayContext(schema_policy=policy)
            pipeline = ReplayPipeline(registry=registry, context=ctx)
            result = pipeline.process(_make_mixed_ledger())
            results.append([(e.event_type, e.sequence, e.payload) for e in result])

        for r in results[1:]:
            assert r == results[0]


class TestPolicyIndependence:
    """Proof 3: Different policies produce different canonical outputs."""

    def test_policy_a_vs_policy_b(self) -> None:
        """Policy A (decisions v1) vs Policy B (decisions v2) produce different results."""
        policy_a = _make_policy(task_latest=2, decision_latest=1)
        policy_b = _make_policy(task_latest=2, decision_latest=2)
        registry = UpcasterRegistry.default()

        ledger = [
            _make_event(EventType.DECISION_PROPOSED, {"decision_id": "d1", "title": "D1"}, 1, schema_version=1),
        ]

        ctx_a = ReplayContext(schema_policy=policy_a)
        pipeline_a = ReplayPipeline(registry=registry, context=ctx_a)
        result_a = pipeline_a.process(ledger)

        ctx_b = ReplayContext(schema_policy=policy_b)
        pipeline_b = ReplayPipeline(registry=registry, context=ctx_b)
        result_b = pipeline_b.process(ledger)

        # Policy A: decision stays v1 (no context/category in payload)
        assert "context" not in result_a[0].payload
        assert "category" not in result_a[0].payload

        # Policy B: decision migrates to v2 (context/category added)
        assert result_b[0].payload["context"] == ""
        assert result_b[0].payload["category"] == "general"


class TestCanonicalIdempotence:
    """Proof 4: canonical(canonical(event)) == canonical(event)."""

    def test_idempotent_v1(self) -> None:
        """Upcasting a v1 event twice produces the same result."""
        v1 = {"decision_id": "d1", "title": "D1"}
        once = decision_proposed_v1_to_v2(v1)
        twice = decision_proposed_v1_to_v2(once)
        assert once == twice

    def test_idempotent_v2(self) -> None:
        """Upcasting an already-v2 event is a no-op."""
        v2 = {"decision_id": "d1", "title": "D1", "context": "c", "category": "cat"}
        result = decision_proposed_v1_to_v2(v2)
        assert result == v2


class TestDeterminism:
    """Proof 5: Replay is fully deterministic."""

    def test_deterministic_replay(self) -> None:
        """10 replays of the same ledger produce identical results."""
        policy = _make_policy()
        registry = UpcasterRegistry.default()
        ledger = _make_mixed_ledger()

        results = []
        for _ in range(10):
            ctx = ReplayContext(schema_policy=policy)
            pipeline = ReplayPipeline(registry=registry, context=ctx)
            result = pipeline.process(ledger)
            results.append([(e.event_type, e.sequence, e.payload) for e in result])

        for r in results[1:]:
            assert r == results[0]


class TestPerformanceBaseline:
    """Proof 6: Migration overhead within regression budget."""

    def test_migration_overhead(self) -> None:
        """Multi-event-type migration overhead is within 3.0x of baseline."""
        MAX_MIGRATION_OVERHEAD_RATIO = 3.0
        ledger_size = 1000

        # Build mixed ledger
        ledger = []
        for i in range(ledger_size):
            if i % 2 == 0:
                ledger.append(_make_event(
                    EventType.TASK_CREATED,
                    {"title": f"Task {i}", "description": ""},
                    i + 1, schema_version=1,
                ))
            else:
                ledger.append(_make_event(
                    EventType.DECISION_PROPOSED,
                    {"decision_id": f"d{i}", "title": f"Decision {i}"},
                    i + 1, schema_version=1,
                ))

        # Baseline: all events already canonical (v2)
        baseline_ledger = []
        for i in range(ledger_size):
            if i % 2 == 0:
                baseline_ledger.append(_make_event(
                    EventType.TASK_CREATED,
                    {"title": f"Task {i}", "details": {"summary": f"Task {i}", "body": ""}},
                    i + 1, schema_version=2,
                ))
            else:
                baseline_ledger.append(_make_event(
                    EventType.DECISION_PROPOSED,
                    {"decision_id": f"d{i}", "title": f"Decision {i}", "context": "", "category": "general"},
                    i + 1, schema_version=2,
                ))

        policy = _make_policy()
        registry = UpcasterRegistry.default()

        # Baseline timing
        ctx = ReplayContext(schema_policy=policy)
        pipeline = ReplayPipeline(registry=registry, context=ctx)
        start = time.perf_counter()
        pipeline.process(baseline_ledger)
        baseline_time = time.perf_counter() - start

        # Measured timing
        ctx = ReplayContext(schema_policy=policy)
        pipeline = ReplayPipeline(registry=registry, context=ctx)
        start = time.perf_counter()
        result = pipeline.process(ledger)
        measured_time = time.perf_counter() - start

        # Metrics
        migrated = sum(1 for e in result if e.schema_version == 2 and e.event_type in (
            EventType.TASK_CREATED, EventType.DECISION_PROPOSED))
        overhead = measured_time / baseline_time if baseline_time > 0 else 1.0

        assert overhead <= MAX_MIGRATION_OVERHEAD_RATIO, (
            f"Migration overhead {overhead:.2f}x exceeds budget {MAX_MIGRATION_OVERHEAD_RATIO}x"
        )


class TestEventTypeIsolation:
    """Proof 7: Missing upcaster fails locally."""

    def test_missing_decision_upcaster_fails_localized(self) -> None:
        """Registry without DECISION_PROPOSED migration fails only for DECISION events."""
        from rationalevault.schema.resolver import UnknownSchemaError

        # Registry with only TASK_CREATED migration
        registry = UpcasterRegistry({"TASK_CREATED": {1: __import__(
            "rationalevault.schema.upcaster", fromlist=["task_created_v1_to_v2"]
        ).task_created_v1_to_v2}})

        policy = _make_policy(task_latest=2, decision_latest=2)
        ctx = ReplayContext(schema_policy=policy)
        pipeline = ReplayPipeline(registry=registry, context=ctx)

        ledger = [
            _make_event(EventType.TASK_CREATED, {"title": "T1", "description": ""}, 1, schema_version=1),
            _make_event(EventType.DECISION_PROPOSED, {"decision_id": "d1", "title": "D1"}, 2, schema_version=1),
        ]

        # Should raise because DECISION_PROPOSED migration is missing
        try:
            pipeline.process(ledger)
            assert False, "Expected UnknownSchemaError"
        except UnknownSchemaError:
            pass


class TestRegistryCompleteness:
    """Proof 8: All policy migrations form complete executable chains."""

    def test_all_migrations_registered(self) -> None:
        """Every migration declared by SchemaPolicy exists in UpcasterRegistry."""
        policy = _make_policy()
        registry = UpcasterRegistry.default()

        for event_type in [EventType.TASK_CREATED, EventType.DECISION_PROPOSED]:
            schema = policy._schemas.get(event_type)
            if schema and schema.migration_path:
                for step in schema.migration_path.steps:
                    assert registry.is_registered(event_type, step.from_version), (
                        f"Migration {event_type.value} v{step.from_version}→v{step.to_version} "
                        f"not registered in UpcasterRegistry"
                    )

    def test_all_migrations_callable(self) -> None:
        """Every registered migration is a callable, not None or wrong function."""
        policy = _make_policy()
        registry = UpcasterRegistry.default()

        for event_type in [EventType.TASK_CREATED, EventType.DECISION_PROPOSED]:
            schema = policy._schemas.get(event_type)
            if schema and schema.migration_path:
                for step in schema.migration_path.steps:
                    fn = registry.get_upcaster(event_type, step.from_version)
                    assert fn is not None, (
                        f"Migration {event_type.value} v{step.from_version}→v{step.to_version} "
                        f"returned None from registry"
                    )
                    assert callable(fn), (
                        f"Migration {event_type.value} v{step.from_version}→v{step.to_version} "
                        f"is not callable: {fn}"
                    )
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `pytest tests/integration/test_decision_proposed_v1_to_v2.py -v`
Expected: All 8 tests PASS

- [ ] **Step 3: Run full test suite**

Run: `pytest tests/ -o addopts="" -q`
Expected: All 2004+ tests pass

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_decision_proposed_v1_to_v2.py
git commit -m "test(integration): F16 proofs — independent multi-type evolution"
```

---

## Task 6: Architectural Guard — Event-Type Local Migration

**Files:**
- Modify: `tests/unit/test_architecture_guards.py`

**Interfaces:**
- Consumes: AST analysis of upcaster functions
- Produces: 1 architectural guard test

- [ ] **Step 1: Add the guard test**

Append to `tests/unit/test_architecture_guards.py`:

```python
def test_event_type_local_migration() -> None:
    """Migration graphs are local to each event type (T3 + T15).

    Each event type owns an independent migration graph.
    No migration graph may depend upon another event type's graph.
    """
    import ast
    from pathlib import Path

    project_root = Path(__file__).resolve().parent.parent.parent
    upcaster_path = project_root / "rationalevault" / "schema" / "upcaster.py"
    if not upcaster_path.exists():
        return

    source = upcaster_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    # Find all upcaster functions (name contains "v1_to_v2" or similar pattern)
    upcaster_funcs = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and "_to_" in node.name:
            upcaster_funcs.append(node)

    # Get all event type names
    event_type_names = [et.value for et in EventType]

    for func in upcaster_funcs:
        func_source = ast.get_source_segment(source, func) or ""
        func_name = func.name

        # Determine which event type this upcaster belongs to
        owning_type = None
        for et_name in event_type_names:
            if et_name.lower() in func_name:
                owning_type = et_name
                break

        if owning_type is None:
            continue  # Can't determine ownership, skip

        # Check that no other event type is referenced
        for et_name in event_type_names:
            if et_name == owning_type:
                continue
            assert et_name not in func_source, (
                f"Upcaster {func_name} (owns {owning_type}) references "
                f"another event type: {et_name}"
            )

    # Verify each migration function has exactly one owning event type
    for func in upcaster_funcs:
        if "_to_" not in func.name:
            continue
        owning_types = [
            et_name for et_name in event_type_names
            if et_name.lower() in func.name
        ]
        assert len(owning_types) == 1, (
            f"Migration function {func.name} has {len(owning_types)} owning types: "
            f"{owning_types}. Expected exactly 1."
        )

    # Verify upcasters never import reducers or projections
    # (migration code must remain below the projection layer)
    reducer_imports = ["reducers", "Reducer", "cognitive_head"]
    projection_imports = ["projections", "pipeline", "ReplayPipeline"]
    for func in upcaster_funcs:
        func_source = ast.get_source_segment(source, func) or ""
        for import_name in reducer_imports + projection_imports:
            assert import_name not in func_source, (
                f"Upcaster {func.name} references layer above migration: {import_name}"
            )
```

- [ ] **Step 2: Run the guard test**

Run: `pytest tests/unit/test_architecture_guards.py::test_event_type_local_migration -v`
Expected: PASS

- [ ] **Step 3: Run all architecture guards**

Run: `pytest tests/unit/test_architecture_guards.py -v`
Expected: All guards PASS (including new one)

- [ ] **Step 4: Run full test suite**

Run: `pytest tests/ -o addopts="" -q`
Expected: All 2004+ tests pass

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_architecture_guards.py
git commit -m "test(guards): F16 event-type local migration guard (T3 + T15)"
```

---

## Task 7: Final Verification

**Files:**
- None (verification only)

**Interfaces:**
- Consumes: All previous tasks
- Produces: Final test count, regression report

- [ ] **Step 1: Run the full test suite**

Run: `pytest tests/ -o addopts="" -q`
Expected: ~2016 passing, 25 skipped

- [ ] **Step 2: Verify F16 proofs pass**

Run: `pytest tests/integration/test_decision_proposed_v1_to_v2.py -v`
Expected: 8/8 PASS

- [ ] **Step 3: Verify unit proofs pass**

Run: `pytest tests/unit/test_decision_proposed_resolver.py -v`
Expected: 6/6 PASS

- [ ] **Step 4: Verify architectural guards pass**

Run: `pytest tests/unit/test_architecture_guards.py -v`
Expected: All guards PASS

- [ ] **Step 5: Verify no frozen API changes**

Confirm no modifications to:
- `rationalevault/schema/policy.py`
- `rationalevault/schema/factory.py`
- `rationalevault/schema/resolver.py`
- `rationalevault/projections/pipeline.py`
- `rationalevault/projections/context.py`

- [ ] **Step 6: Document results**

No commit needed — verification only.
