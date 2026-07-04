# SchemaPolicy Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the global `target_schema_version` model with a per-event-type `SchemaPolicy` derived from `GovernanceState`, making the replay resolver a pure policy executor and restoring reducer purity.

**Architecture:** `SchemaPolicy` is an immutable value object compiled from `GovernanceState` by `SchemaPolicyFactory`. `ReplayResolver` consumes only `SchemaPolicy` + `UpcasterRegistry`, with no knowledge of versions or governance. `ReplayPipeline` owns resolver construction. Reducers receive only canonical events.

**Tech Stack:** Python 3.12+, dataclasses (frozen), pytest

## Reviewer Assignments

| Task | Lead | Mandatory Reviewers |
|------|------|---------------------|
| 1. SchemaPolicy types | Implementation Engineer | Architecture Reviewer, Validation Engineer |
| 2. SchemaPolicyFactory | Implementation Engineer | Architecture Reviewer, Schema Evolution Steward, Validation Engineer |
| 3A. ReplayResolver new API | Implementation Engineer | Architecture Reviewer, Theorem Guardian, Validation Engineer |
| 3B. Remove legacy resolver | Implementation Engineer | Architecture Reviewer, Theorem Guardian |
| 4. UpcasterRegistry cleanup | Implementation Engineer | Schema Evolution Steward, Validation Engineer |
| 5. ReplayContext simplification | Implementation Engineer | Architecture Reviewer, Theorem Guardian |
| 6. ReplayPipeline ownership | Implementation Engineer | Architecture Reviewer, Performance Engineer |
| 7. Canonical reducer | Implementation Engineer | Theorem Guardian, Validation Engineer |
| 8. T14 architecture guards | Validation Engineer | Theorem Guardian |
| 9. Integration update | Validation Engineer | Performance Engineer |
| 10. Final verification | Validation Engineer | Theorem Guardian (final sign-off), Documentation Engineer |

## Governance Workflow

```
Architecture Reviewer
        │
        ▼
Migration Designer → Migration Specification
        │
        ▼
Schema Evolution Steward
        │
        ▼
Theorem Guardian (Pre-Implementation Gate)
        │
        ▼
Implementation Engineer
        │
        ▼
Validation Engineer
        │
        ▼
Performance Engineer
        │
        ▼
Documentation Engineer
        │
        ▼
Replay Auditor (when production migrations exist)
        │
        ▼
Theorem Guardian (Final Constitutional Freeze)
```

## Global Constraints

- All existing events without explicit `schema_version` default to v1
- `SchemaPolicy` defaults unknown event types to `latest_version=1` with empty migration path
- No database migration required — `schema_version` field already exists on `EventRecord`
- Existing `GovernanceState.schema_versions` data feeds directly into `SchemaPolicyFactory.compile()`
- All 1,939 existing tests must continue to pass after each task
- Reducers must never reference `schema_version` or branch on payload version

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `rationalevault/schema/policy.py` | **CREATE** | `MigrationStep`, `MigrationPath`, `EventSchema`, `SchemaPolicy` — immutable metadata types |
| `rationalevault/schema/factory.py` | **CREATE** | `SchemaPolicyFactory` — compiles `SchemaPolicy` from `GovernanceState` |
| `rationalevault/schema/resolver.py` | **MODIFY** | Remove `target_schema_version`, `EVOLVED_EVENT_TYPES`; take `SchemaPolicy` + `UpcasterRegistry` |
| `rationalevault/schema/upcaster.py` | **MODIFY** | Remove auto-registration from `__init__`; registry becomes pure data structure |
| `rationalevault/projections/context.py` | **MODIFY** | Replace `target_schema_version` with `schema_policy`; remove `__post_init__` resolver rebuild |
| `rationalevault/projections/pipeline.py` | **MODIFY** | Own resolver construction; take `UpcasterRegistry` as dependency |
| `rationalevault/projections/service.py` | **MODIFY** | Pass registry through pipeline |
| `rationalevault/cognitive_head/reducers.py` | **MODIFY** | Remove v1/v2 branching in `TaskReducer`; use canonical v2 only |
| `tests/unit/schema/test_policy.py` | **CREATE** | Unit tests for `SchemaPolicy`, `MigrationStep`, `MigrationPath`, `EventSchema` |
| `tests/unit/schema/test_factory.py` | **CREATE** | Unit tests for `SchemaPolicyFactory` |
| `tests/unit/schema/test_resolver.py` | **MODIFY** | Update tests for new resolver interface |
| `tests/unit/test_architecture_guards.py` | **MODIFY** | Add T14 guard: flag reducers with schema version branching |
| `tests/integration/test_proven_schema_evolution.py` | **MODIFY** | Update integration test for new context/pipeline interface |

---

### Task 1: SchemaPolicy Types

**Files:**
- Create: `rationalevault/schema/policy.py`
- Create: `tests/unit/schema/test_policy.py`

**Interfaces:**
- Consumes: `EventType` from `rationalevault/schema/events.py`, `EventRecord` from `rationalevault/schema/events.py`
- Produces: `MigrationStep`, `MigrationPath`, `EventSchema`, `SchemaPolicy`

- [ ] **Step 1: Write failing tests for MigrationStep**

```python
# tests/unit/schema/test_policy.py
from rationalevault.schema.policy import MigrationStep, MigrationPath, EventSchema, SchemaPolicy
from rationalevault.schema.events import EventType

def test_migration_step_creation():
    step = MigrationStep(from_version=1, to_version=2)
    assert step.from_version == 1
    assert step.to_version == 2

def test_migration_step_is_frozen():
    step = MigrationStep(from_version=1, to_version=2)
    try:
        step.from_version = 3
        assert False, "Should be frozen"
    except AttributeError:
        pass
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/schema/test_policy.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'rationalevault.schema.policy'`

- [ ] **Step 3: Write minimal MigrationStep implementation**

```python
# rationalevault/schema/policy.py
from dataclasses import dataclass

@dataclass(frozen=True)
class MigrationStep:
    """Describes one version transition. No executable code."""
    from_version: int
    to_version: int
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/schema/test_policy.py::test_migration_step_creation tests/unit/schema/test_policy.py::test_migration_step_is_frozen -v`
Expected: PASS

- [ ] **Step 5: Write failing tests for MigrationPath**

```python
def test_migration_path_empty():
    path = MigrationPath(steps=())
    assert path.exists() is False

def test_migration_path_with_steps():
    path = MigrationPath(steps=(MigrationStep(1, 2),))
    assert path.exists() is True
    assert len(path.steps) == 1

def test_migration_path_is_frozen():
    path = MigrationPath(steps=())
    try:
        path.steps = (MigrationStep(1, 2),)
        assert False, "Should be frozen"
    except AttributeError:
        pass
```

- [ ] **Step 6: Run test to verify it fails**

Run: `pytest tests/unit/schema/test_policy.py -v -k "migration_path"`
Expected: FAIL with `NameError: name 'MigrationPath' is not defined`

- [ ] **Step 7: Write minimal MigrationPath implementation**

```python
# rationalevault/schema/policy.py (append)
from typing import Tuple

@dataclass(frozen=True)
class MigrationPath:
    """Ordered sequence of migration steps for an event type."""
    steps: Tuple[MigrationStep, ...] = ()

    def exists(self) -> bool:
        """True if any migration steps exist."""
        return len(self.steps) > 0
```

- [ ] **Step 8: Run test to verify it passes**

Run: `pytest tests/unit/schema/test_policy.py -v -k "migration_path"`
Expected: PASS

- [ ] **Step 9: Write failing tests for EventSchema**

```python
def test_event_schema_creation():
    schema = EventSchema(
        event_type=EventType.TASK_CREATED,
        latest_version=2,
        migration_path=MigrationPath(steps=(MigrationStep(1, 2),)),
    )
    assert schema.event_type == EventType.TASK_CREATED
    assert schema.latest_version == 2
    assert schema.migration_path.exists() is True

def test_event_schema_no_migration():
    schema = EventSchema(
        event_type=EventType.PROJECT_CREATED,
        latest_version=1,
        migration_path=MigrationPath(),
    )
    assert schema.latest_version == 1
    assert schema.migration_path.exists() is False
```

- [ ] **Step 10: Run test to verify it fails**

Run: `pytest tests/unit/schema/test_policy.py -v -k "event_schema"`
Expected: FAIL with `NameError: name 'EventSchema' is not defined`

- [ ] **Step 11: Write minimal EventSchema implementation**

```python
# rationalevault/schema/policy.py (append)
from rationalevault.schema.events import EventType

@dataclass(frozen=True)
class EventSchema:
    """Schema metadata for a single event type."""
    event_type: EventType
    latest_version: int
    migration_path: MigrationPath
```

- [ ] **Step 12: Run test to verify it passes**

Run: `pytest tests/unit/schema/test_policy.py -v -k "event_schema"`
Expected: PASS

- [ ] **Step 13: Write failing tests for SchemaPolicy**

```python
def test_schema_policy_default_event_type():
    policy = SchemaPolicy(_schemas={})
    assert policy.latest_version(EventType.PROJECT_CREATED) == 1
    assert policy.migration_path(EventType.PROJECT_CREATED).exists() is False

def test_schema_policy_explicit_event_type():
    policy = SchemaPolicy(_schemas={
        EventType.TASK_CREATED: EventSchema(
            event_type=EventType.TASK_CREATED,
            latest_version=2,
            migration_path=MigrationPath(steps=(MigrationStep(1, 2),)),
        )
    })
    assert policy.latest_version(EventType.TASK_CREATED) == 2
    assert policy.migration_path(EventType.TASK_CREATED).exists() is True

def test_schema_policy_is_current():
    from rationalevault.schema.events import EventRecord, EventMetadata
    from datetime import datetime
    from uuid import uuid4
    policy = SchemaPolicy(_schemas={
        EventType.TASK_CREATED: EventSchema(
            event_type=EventType.TASK_CREATED,
            latest_version=2,
            migration_path=MigrationPath(steps=(MigrationStep(1, 2),)),
        )
    })
    event = EventRecord(
        id=uuid4(), project_id=uuid4(), stream_id="test",
        version=1, event_type=EventType.TASK_CREATED,
        schema_version=2, payload={},
        metadata=EventMetadata(actor="test", source="test"),
        recorded_at=datetime.now(),
    )
    assert policy.is_current(event) is True

def test_schema_policy_is_not_current():
    from rationalevault.schema.events import EventRecord, EventMetadata
    from datetime import datetime
    from uuid import uuid4
    policy = SchemaPolicy(_schemas={
        EventType.TASK_CREATED: EventSchema(
            event_type=EventType.TASK_CREATED,
            latest_version=2,
            migration_path=MigrationPath(steps=(MigrationStep(1, 2),)),
        )
    })
    event = EventRecord(
        id=uuid4(), project_id=uuid4(), stream_id="test",
        version=1, event_type=EventType.TASK_CREATED,
        schema_version=1, payload={},
        metadata=EventMetadata(actor="test", source="test"),
        recorded_at=datetime.now(),
    )
    assert policy.is_current(event) is False

def test_schema_policy_event_types():
    policy = SchemaPolicy(_schemas={
        EventType.TASK_CREATED: EventSchema(
            event_type=EventType.TASK_CREATED,
            latest_version=2,
            migration_path=MigrationPath(),
        )
    })
    assert EventType.TASK_CREATED in list(policy.event_types())
```

- [ ] **Step 14: Run test to verify it fails**

Run: `pytest tests/unit/schema/test_policy.py -v -k "schema_policy"`
Expected: FAIL with `NameError: name 'SchemaPolicy' is not defined`

- [ ] **Step 15: Write SchemaPolicy implementation**

```python
# rationalevault/schema/policy.py (append)
from typing import Mapping, Iterable

@dataclass(frozen=True)
class SchemaPolicy:
    """Immutable snapshot of schema rules derived from GovernanceState.

    NOT a projection. A compiled execution contract built by SchemaPolicyFactory.
    Contains only facts — no executable code, no callables.
    """
    _schemas: Mapping[EventType, EventSchema]

    def latest_version(self, event_type: EventType) -> int:
        """Canonical latest version for this event type. Defaults to 1."""
        if event_type in self._schemas:
            return self._schemas[event_type].latest_version
        return 1

    def schema(self, event_type: EventType) -> EventSchema:
        """Full schema metadata for an event type."""
        if event_type in self._schemas:
            return self._schemas[event_type]
        return EventSchema(
            event_type=event_type,
            latest_version=1,
            migration_path=MigrationPath(),
        )

    def migration_path(self, event_type: EventType) -> MigrationPath:
        """Ordered migration steps for this event type."""
        return self.schema(event_type).migration_path

    def is_current(self, event: 'EventRecord') -> bool:
        """True if event is exactly at its canonical version. Strict equality."""
        return event.schema_version == self.latest_version(event.event_type)

    def can_resolve(self, event: 'EventRecord') -> bool:
        """True if the policy has a valid migration path for this event.

        An event can be resolved if:
        - It is already at canonical version (no migration needed), OR
        - A complete migration path exists from its version to canonical
        """
        if self.is_current(event):
            return True
        path = self.migration_path(event.event_type)
        if not path.exists():
            return False
        # Check path covers the event's version
        current = event.schema_version
        target = self.latest_version(event.event_type)
        for step in path.steps:
            if step.from_version == current:
                current = step.to_version
        return current == target

    def event_types(self) -> Iterable[EventType]:
        """All event types with explicit schema metadata."""
        return self._schemas.keys()
```

- [ ] **Step 16: Run all policy tests**

Run: `pytest tests/unit/schema/test_policy.py -v`
Expected: ALL PASS

- [ ] **Step 17: Run full test suite to verify no regressions**

Run: `pytest tests/ -o addopts="" -q`
Expected: 1939 passed, 25 skipped

- [ ] **Step 18: Commit**

```bash
git add rationalevault/schema/policy.py tests/unit/schema/test_policy.py
git commit -m "feat(schema): add SchemaPolicy types (MigrationStep, MigrationPath, EventSchema, SchemaPolicy)"
```

---

### Task 2: SchemaPolicyFactory

**Files:**
- Create: `rationalevault/schema/factory.py`
- Create: `tests/unit/schema/test_factory.py`

**Interfaces:**
- Consumes: `GovernanceState` from `rationalevault/projections/governance.py`, `EventType` from `rationalevault/schema/events.py`
- Produces: `SchemaPolicy` from `rationalevault/schema/policy.py`

- [ ] **Step 1: Write failing tests for SchemaPolicyFactory**

```python
# tests/unit/schema/test_factory.py
from rationalevault.schema.factory import SchemaPolicyFactory
from rationalevault.schema.policy import SchemaPolicy
from rationalevault.projections.governance import GovernanceState

def test_factory_compiles_empty_governance():
    state = GovernanceState(policies={}, schema_versions={})
    factory = SchemaPolicyFactory()
    policy = factory.compile(state)
    assert isinstance(policy, SchemaPolicy)

def test_factory_default_event_type():
    from rationalevault.schema.events import EventType
    state = GovernanceState(policies={}, schema_versions={})
    factory = SchemaPolicyFactory()
    policy = factory.compile(state)
    assert policy.latest_version(EventType.PROJECT_CREATED) == 1

def test_factory_compile_at_sequence():
    from rationalevault.schema.events import EventType
    state = GovernanceState(policies={}, schema_versions={})
    factory = SchemaPolicyFactory()
    policy = factory.compile_at_sequence(state, sequence=100)
    assert isinstance(policy, SchemaPolicy)
    assert policy.latest_version(EventType.PROJECT_CREATED) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/schema/test_factory.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'rationalevault.schema.factory'`

- [ ] **Step 3: Write minimal SchemaPolicyFactory implementation**

```python
# rationalevault/schema/factory.py
from rationalevault.schema.policy import SchemaPolicy, EventSchema, MigrationPath
from rationalevault.projections.governance import GovernanceState

class SchemaPolicyFactory:
    """Compiles SchemaPolicy from GovernanceState.

    Does NOT own UpcasterRegistry. Only compiles metadata.
    Does NOT modify GovernanceState — reads it, compiles, returns new object.
    """

    def compile(self, governance_state: GovernanceState) -> SchemaPolicy:
        """Build SchemaPolicy from current governance state."""
        schemas = {}
        for event_type_str, (version, _eff_seq) in governance_state.schema_versions.items():
            from rationalevault.schema.events import EventType
            try:
                event_type = EventType(event_type_str)
            except ValueError:
                continue
            schemas[event_type] = EventSchema(
                event_type=event_type,
                latest_version=version,
                migration_path=MigrationPath(),
            )
        return SchemaPolicy(_schemas=schemas)

    def compile_at_sequence(self, governance_state: GovernanceState, sequence: int) -> SchemaPolicy:
        """Build SchemaPolicy as of a specific ledger sequence."""
        schemas = {}
        for event_type_str, (version, eff_seq) in governance_state.schema_versions.items():
            if eff_seq <= sequence:
                from rationalevault.schema.events import EventType
                try:
                    event_type = EventType(event_type_str)
                except ValueError:
                    continue
                schemas[event_type] = EventSchema(
                    event_type=event_type,
                    latest_version=version,
                    migration_path=MigrationPath(),
                )
        return SchemaPolicy(_schemas=schemas)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/schema/test_factory.py -v`
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `pytest tests/ -o addopts="" -q`
Expected: 1939 passed, 25 skipped

- [ ] **Step 6: Commit**

```bash
git add rationalevault/schema/factory.py tests/unit/schema/test_factory.py
git commit -m "feat(schema): add SchemaPolicyFactory for compiling policy from GovernanceState"
```

---

### Task 3A: ReplayResolver — New API with Compatibility

**Files:**
- Modify: `rationalevault/schema/resolver.py`
- Modify: `tests/unit/schema/test_resolver.py`

**Interfaces:**
- Consumes: `SchemaPolicy` from `rationalevault/schema/policy.py`, `UpcasterRegistry` from `rationalevault/schema/upcaster.py`
- Produces: `ReplayResolver` with `resolve()` and `resolve_all()` methods, supporting both new (policy) and legacy (target_schema_version) interfaces during transition

- [ ] **Step 1: Write failing tests for new resolver interface**

```python
# Add to tests/unit/schema/test_resolver.py
from rationalevault.schema.policy import SchemaPolicy, EventSchema, MigrationPath, MigrationStep
from rationalevault.schema.upcaster import UpcasterRegistry
from rationalevault.schema.resolver import ReplayResolver

def test_resolver_with_schema_policy():
    policy = SchemaPolicy(_schemas={})
    registry = UpcasterRegistry()
    resolver = ReplayResolver(policy=policy, registry=registry)
    assert resolver is not None

def test_resolver_current_event_unchanged():
    from rationalevault.schema.events import EventType, EventRecord, EventMetadata
    from datetime import datetime
    from uuid import uuid4
    policy = SchemaPolicy(_schemas={
        EventType.TASK_CREATED: EventSchema(
            event_type=EventType.TASK_CREATED,
            latest_version=2,
            migration_path=MigrationPath(steps=(MigrationStep(1, 2),)),
        )
    })
    registry = UpcasterRegistry()
    resolver = ReplayResolver(policy=policy, registry=registry)
    event = EventRecord(
        id=uuid4(), project_id=uuid4(), stream_id="test",
        version=1, event_type=EventType.TASK_CREATED,
        schema_version=2, payload={"details": {"summary": "test", "body": ""}},
        metadata=EventMetadata(actor="test", source="test"),
        recorded_at=datetime.now(),
    )
    result = resolver.resolve(event)
    assert result.schema_version == 2
    assert result.payload == event.payload

def test_resolver_upcasts_event():
    from rationalevault.schema.events import EventType, EventRecord, EventMetadata
    from datetime import datetime
    from uuid import uuid4
    policy = SchemaPolicy(_schemas={
        EventType.TASK_CREATED: EventSchema(
            event_type=EventType.TASK_CREATED,
            latest_version=2,
            migration_path=MigrationPath(steps=(MigrationStep(1, 2),)),
        )
    })
    registry = UpcasterRegistry()
    resolver = ReplayResolver(policy=policy, registry=registry)
    event = EventRecord(
        id=uuid4(), project_id=uuid4(), stream_id="test",
        version=1, event_type=EventType.TASK_CREATED,
        schema_version=1, payload={"title": "test", "description": "desc"},
        metadata=EventMetadata(actor="test", source="test"),
        recorded_at=datetime.now(),
    )
    result = resolver.resolve(event)
    assert result.schema_version == 2
    assert "details" in result.payload
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/schema/test_resolver.py -v -k "schema_policy or upcasts_event"`
Expected: FAIL (current resolver takes `target_schema_version`, not `policy`)

- [ ] **Step 3: Add new API alongside legacy support**

Add `policy` and `registry` parameters to `ReplayResolver.__init__`. Keep legacy `target_schema_version` and `EVOLVED_EVENT_TYPES` temporarily. New API takes precedence when `policy` is provided.

```python
class ReplayResolver:
    def __init__(self, policy: SchemaPolicy | None = None, registry: UpcasterRegistry | None = None,
                 target_schema_version: int = 2):  # legacy param, deprecated
        self._policy = policy
        self._registry = registry or UpcasterRegistry()
        self._target_schema_version = target_schema_version  # legacy

    def resolve(self, event: EventRecord) -> EventRecord:
        if self._policy is not None:
            return self._resolve_with_policy(event)
        return self._resolve_legacy(event)

    def _resolve_with_policy(self, event: EventRecord) -> EventRecord:
        """New policy-based resolution."""
        if self._policy.is_current(event):
            return event
        if not self._policy.can_resolve(event):
            raise UnknownSchemaError(...)
        path = self._policy.migration_path(event.event_type)
        current_payload = dict(event.payload)
        current_version = event.schema_version
        for step in path.steps:
            if step.from_version == current_version:
                upcaster = self._registry.get_upcaster(event.event_type, step.from_version)
                if upcaster is None:
                    raise UnknownSchemaError(...)
                current_payload = upcaster(current_payload)
                current_version = step.to_version
        return EventRecord(... schema_version=current_version, payload=current_payload, ...)

    def _resolve_legacy(self, event: EventRecord) -> EventRecord:
        """Legacy resolution — will be removed in Task 3B."""
        # Keep existing implementation temporarily
        ...
```

- [ ] **Step 4: Run tests to verify both APIs work**

Run: `pytest tests/unit/schema/test_resolver.py -v`
Expected: All tests pass (new tests pass via policy, legacy tests pass via legacy path)

- [ ] **Step 5: Run full test suite**

Run: `pytest tests/ -o addopts="" -q`
Expected: 1939 passed, 25 skipped

- [ ] **Step 6: Commit**

```bash
git add rationalevault/schema/resolver.py tests/unit/schema/test_resolver.py
git commit -m "refactor(schema): ReplayResolver adds policy API alongside legacy support"
```

---

### Task 3B: Remove Legacy Resolver Interface

**Files:**
- Modify: `rationalevault/schema/resolver.py`
- Modify: `tests/unit/schema/test_resolver.py`

**Prerequisites:** Tasks 5 and 6 must be complete (all callers migrated to new interface)

**Interfaces:**
- Consumes: `SchemaPolicy`, `UpcasterRegistry`
- Produces: `ReplayResolver` with policy-only interface (no legacy)

- [ ] **Step 1: Remove legacy parameters and methods**

Remove `target_schema_version` parameter, `EVOLVED_EVENT_TYPES`, and `_resolve_legacy()` method. Keep only `_resolve_with_policy()`.

```python
class ReplayResolver:
    def __init__(self, policy: SchemaPolicy, registry: UpcasterRegistry):
        self._policy = policy
        self._registry = registry

    def resolve(self, event: EventRecord) -> EventRecord:
        if self._policy.is_current(event):
            return event
        if not self._policy.can_resolve(event):
            raise UnknownSchemaError(...)
        # ... walk path ...
```

- [ ] **Step 2: Remove all legacy test cases**

Delete tests that use `target_schema_version` or `EVOLVED_EVENT_TYPES`.

- [ ] **Step 3: Run full test suite**

Run: `pytest tests/ -o addopts="" -q`
Expected: 1939 passed, 25 skipped

- [ ] **Step 4: Verify no references to legacy interface**

Run: `grep -r "target_schema_version" rationalevault/`
Expected: No results

Run: `grep -r "EVOLVED_EVENT_TYPES" rationalevault/`
Expected: No results

- [ ] **Step 5: Commit**

```bash
git add rationalevault/schema/resolver.py tests/unit/schema/test_resolver.py
git commit -m "refactor(schema): remove legacy ReplayResolver interface, policy-only"
```

---

### Task 4: UpcasterRegistry Cleanup

**Files:**
- Modify: `rationalevault/schema/upcaster.py`

**Interfaces:**
- Consumes: `EventType` from `rationalevault/schema/events.py`
- Produces: `UpcasterRegistry` with `register()` and `get_upcaster()` methods

- [ ] **Step 1: Remove auto-registration from UpcasterRegistry.__init__**

Current `__init__` auto-registers `task_created_v1_to_v2`. Move this registration to the test setup or a dedicated registration function. The registry becomes a pure data structure.

```python
class UpcasterRegistry:
    def __init__(self):
        self._upcasters: dict[tuple[str, int], UpcasterCallable] = {}

    def register(self, event_type: EventType, source_version: int, upcaster: UpcasterCallable):
        self._upcasters[(event_type.value, source_version)] = upcaster

    def get_upcaster(self, event_type: EventType, source_version: int) -> UpcasterCallable | None:
        return self._upcasters.get((event_type.value, source_version))
```

- [ ] **Step 2: Update tests to explicitly register upcasters**

In test setup, call `registry.register(EventType.TASK_CREATED, 1, task_created_v1_to_v2)` instead of relying on auto-registration.

- [ ] **Step 3: Run full test suite**

Run: `pytest tests/ -o addopts="" -q`
Expected: 1939 passed, 25 skipped

- [ ] **Step 4: Commit**

```bash
git add rationalevault/schema/upcaster.py
git commit -m "refactor(schema): UpcasterRegistry becomes pure data structure, no auto-registration"
```

---

### Task 5: ReplayContext Simplification

**Files:**
- Modify: `rationalevault/projections/context.py`

**Interfaces:**
- Consumes: `SchemaPolicy` from `rationalevault/schema/policy.py`
- Produces: `ReplayContext` with `schema_policy` field (no `target_schema_version`, no `resolver`)

- [ ] **Step 1: Rewrite ReplayContext**

```python
@dataclass(frozen=True)
class ReplayContext:
    """Session parameters for replay execution.

    Contains NO schema version logic.
    Contains NO resolver — that belongs in ReplayPipeline.
    SchemaPolicy is the single source of truth for schema decisions.
    """
    max_sequence: Optional[int] = None
    schema_policy: SchemaPolicy = field(default_factory=lambda: SchemaPolicyFactory().compile(GovernanceState()))
```

- [ ] **Step 2: Remove __post_init__ resolver rebuilding**

Delete the `__post_init__` method that compares `target_schema_version` and rebuilds the resolver.

- [ ] **Step 3: Update InterpretiveContextBuilder**

```python
class InterpretiveContextBuilder:
    def build(self, governance_state: GovernanceState, request: ReplayRequest) -> InterpretiveContext:
        factory = SchemaPolicyFactory()
        policy = factory.compile(governance_state)
        replay_ctx = ReplayContext(max_sequence=request.sequence, schema_policy=policy)
        return InterpretiveContext(
            governance=governance_state,
            replay_mode=request.mode,
            sequence=request.sequence,
            replay_context=replay_ctx,
        )
```

- [ ] **Step 4: Update all callers of ReplayContext**

Search for `ReplayContext(target_schema_version=` and replace with `ReplayContext(schema_policy=...)`.

- [ ] **Step 5: Run full test suite**

Run: `pytest tests/ -o addopts="" -q`
Expected: 1939 passed, 25 skipped

- [ ] **Step 6: Commit**

```bash
git add rationalevault/projections/context.py
git commit -m "refactor(projections): ReplayContext takes SchemaPolicy, removes target_schema_version"
```

---

### Task 6: ReplayPipeline Owns Execution

**Files:**
- Modify: `rationalevault/projections/pipeline.py`
- Modify: `rationalevault/projections/service.py`

**Interfaces:**
- Consumes: `ReplayContext`, `UpcasterRegistry`
- Produces: `ReplayPipeline` with `process()` method that owns resolver construction

- [ ] **Step 1: Rewrite ReplayPipeline**

```python
class ReplayPipeline:
    def __init__(self, context: ReplayContext, registry: UpcasterRegistry | None = None):
        self._context = context
        self._registry = registry or UpcasterRegistry()
        self._resolver = ReplayResolver(context.schema_policy, self._registry)

    def process(self, events: Iterable[EventRecord]) -> list[EventRecord]:
        """Filter by max_sequence, resolve each event to canonical form."""
        filtered = events
        if self._context.max_sequence is not None:
            filtered = [e for e in filtered if e.event_sequence <= self._context.max_sequence]
        return self._resolver.resolve_all(filtered)
```

- [ ] **Step 2: Update ReplayService to pass registry through**

```python
class ReplayService:
    def __init__(self, store=None, registry: UpcasterRegistry | None = None):
        self._store = store or EventStore()
        self._registry = registry or UpcasterRegistry()

    def load_project_events(self, project_id, context):
        replay_ctx = context if isinstance(context, ReplayContext) else context.replay_context
        pipeline = ReplayPipeline(replay_ctx, self._registry)
        raw_events = self._store.get_events(project_id)
        return pipeline.process(raw_events)
```

- [ ] **Step 3: Run full test suite**

Run: `pytest tests/ -o addopts="" -q`
Expected: 1939 passed, 25 skipped

- [ ] **Step 4: Commit**

```bash
git add rationalevault/projections/pipeline.py rationalevault/projections/service.py
git commit -m "refactor(projections): ReplayPipeline owns resolver construction, takes UpcasterRegistry"
```

---

### Task 7: TaskReducer Canonical-Only

**Files:**
- Modify: `rationalevault/cognitive_head/reducers.py`

**Interfaces:**
- Consumes: Canonical events from replay layer
- Produces: Task state dict

- [ ] **Step 1: Remove v1/v2 branching in TaskReducer**

Replace:
```python
details = p.get("details", {})
title = details.get("summary") if isinstance(details, dict) else None
if title is None:
    title = p.get("title", "")
```

With:
```python
details = payload["details"]
title = details["summary"]
description = details["body"]
```

- [ ] **Step 2: Run full test suite**

Run: `pytest tests/ -o addopts="" -q`
Expected: 1939 passed, 25 skipped

- [ ] **Step 3: Commit**

```bash
git add rationalevault/cognitive_head/reducers.py
git commit -m "refactor(reducers): TaskReducer uses canonical v2 payload only"
```

---

### Task 8: Architecture Guards (T14)

**Files:**
- Modify: `tests/unit/test_architecture_guards.py`

**Interfaces:**
- Consumes: AST analysis of reducer source files
- Produces: Test pass/fail for canonical boundary enforcement

- [ ] **Step 1: Add T14 guard test**

```python
def test_reducer_canonical_boundary_guard():
    """Reducers must not reference schema_version or branch on payload version."""
    import ast
    import pathlib

    reducers_path = pathlib.Path("rationalevault/cognitive_head/reducers.py")
    source = reducers_path.read_text()
    tree = ast.parse(source)

    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name) and node.value.id == "event":
                if node.attr == "schema_version":
                    violations.append(f"Line {node.lineno}: event.schema_version reference")
        if isinstance(node, ast.Compare):
            for comparator in node.comparators:
                if isinstance(comparator, ast.Constant) and isinstance(comparator.value, int):
                    if comparator.value in (1, 2, 3):
                        violations.append(f"Line {node.lineno}: possible schema version branch")

    assert len(violations) == 0, f"T14 violations: {violations}"
```

- [ ] **Step 2: Run guard test**

Run: `pytest tests/unit/test_architecture_guards.py::test_reducer_canonical_boundary_guard -v`
Expected: PASS

- [ ] **Step 3: Run full test suite**

Run: `pytest tests/ -o addopts="" -q`
Expected: 1939 passed, 25 skipped

- [ ] **Step 4: Commit**

```bash
git add tests/unit/test_architecture_guards.py
git commit -m "test(guards): add T14 canonical boundary guard for reducers"
```

---

### Task 9: Update Integration Test

**Files:**
- Modify: `tests/integration/test_proven_schema_evolution.py`

**Interfaces:**
- Consumes: Updated `ReplayContext`, `ReplayPipeline`, `SchemaPolicyFactory`
- Produces: Verified mixed-version replay equivalence

- [ ] **Step 1: Update integration test for new interface**

Replace `ReplayContext(target_schema_version=2)` with:
```python
from rationalevault.schema.factory import SchemaPolicyFactory
from rationalevault.schema.policy import SchemaPolicy, EventSchema, MigrationPath, MigrationStep
from rationalevault.schema.upcaster import UpcasterRegistry

registry = UpcasterRegistry()
registry.register(EventType.TASK_CREATED, 1, task_created_v1_to_v2)
policy = SchemaPolicy(_schemas={
    EventType.TASK_CREATED: EventSchema(
        event_type=EventType.TASK_CREATED,
        latest_version=2,
        migration_path=MigrationPath(steps=(MigrationStep(1, 2),)),
    )
})
context = ReplayContext(schema_policy=policy)
pipeline = ReplayPipeline(context, registry)
```

- [ ] **Step 2: Run integration test**

Run: `pytest tests/integration/test_proven_schema_evolution.py -v`
Expected: PASS

- [ ] **Step 3: Run full test suite**

Run: `pytest tests/ -o addopts="" -q`
Expected: 1939 passed, 25 skipped

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_proven_schema_evolution.py
git commit -m "test(integration): update schema evolution test for SchemaPolicy interface"
```

---

### Task 10: Final Verification

**Files:**
- None (verification only)

- [ ] **Step 1: Run full test suite**

Run: `pytest tests/ -o addopts="" -q`
Expected: 1939 passed, 25 skipped

- [ ] **Step 2: Run architecture guards**

Run: `pytest tests/unit/test_architecture_guards.py -v`
Expected: ALL PASS

- [ ] **Step 3: Verify no references to old interface**

Run: `grep -r "target_schema_version" rationalevault/`
Expected: No results

Run: `grep -r "EVOLVED_EVENT_TYPES" rationalevault/`
Expected: No results

- [ ] **Step 4: Verify all tests pass with canonical-only reducer**

Run: `pytest tests/unit/schema/ tests/integration/test_proven_schema_evolution.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit final state**

```bash
git add -A
git commit -m "feat(schema): SchemaPolicy architecture complete — per-event-type schema versioning"
```

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-06-29-schema-policy-implementation.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
