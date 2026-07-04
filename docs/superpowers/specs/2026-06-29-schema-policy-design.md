# SchemaPolicy Architecture Design Spec

> **Date:** 2026-06-29
> **Status:** Approved
> **Supersedes:** The global `target_schema_version` model in `ReplayResolver`, `ReplayContext`, and `InterpretiveContextBuilder`

---

## Problem Statement

The current schema versioning model uses a single global `target_schema_version = 2` hardcoded in three places (`ReplayResolver`, `ReplayContext`, `InterpretiveContextBuilder`). This creates:

1. **`EVOLVED_EVENT_TYPES` hardcoded set** — compensates for the global version by listing which event types actually have migrations
2. **`ReplayContext.__post_init__` resolver rebuilding** — silently reconstructs resolver when versions drift, creating two sources of truth
3. **Reducers knowing multiple schemas** — `TaskReducer` branches on `payload.get("details")` vs `payload.get("title")`, mixing schema translation with business logic
4. **`UnknownSchemaError` edge cases** — exception logic oscillates between "always throw" and "never throw" depending on whether an event type is in the evolved set

A single integer `target_schema_version = 3` means nothing when `PROJECT_CREATED` is v1, `TASK_CREATED` is v3, and `DECISION_CREATED` is v2.

---

## Architectural Direction

Replace the global version model with a per-event-type `SchemaPolicy` derived from `GovernanceState`. The policy is an immutable value object (not a projection) compiled by a factory. The factory contains no executable upcaster logic — it only compiles metadata. The resolver becomes a pure policy executor with no knowledge of versions, evolved types, or governance. The replay pipeline owns the executable machinery (resolver + registry).

### Target Architecture

```
GovernanceEvents → GovernanceProjection → GovernanceState
                                              ↓
                                     SchemaPolicyFactory
                                              ↓
                                        SchemaPolicy (immutable)
                                              ↓
                                  InterpretiveContextBuilder
                                              ↓
                                        ReplayContext (pure data)
                                              ↓
                                        ReplayPipeline
                                              ↓
                                        ReplayResolver
                                              ↓
                                      UpcasterRegistry
                                              ↓
                                       Canonical Event
                                              ↓
                                          Projection
```

---

## Design Sections

### 1. SchemaPolicy — The Core Abstraction

An immutable value object that answers schema questions for any event type. It contains only metadata — no executable code, no governance knowledge, no replay mechanics.

```python
@dataclass(frozen=True)
class MigrationStep:
    """Describes one version transition. No executable code."""
    from_version: int
    to_version: int

@dataclass(frozen=True)
class MigrationPath:
    """Ordered sequence of migration steps for an event type."""
    steps: tuple[MigrationStep, ...]

    def exists(self) -> bool:
        """True if any migration steps exist."""
        return len(self.steps) > 0

@dataclass(frozen=True)
class EventSchema:
    """Schema metadata for a single event type."""
    event_type: EventType
    latest_version: int
    migration_path: MigrationPath

@dataclass(frozen=True)
class SchemaPolicy:
    """Immutable snapshot of schema rules derived from GovernanceState.

    NOT a projection. A compiled execution contract built by SchemaPolicyFactory.
    Contains only facts — no executable code, no callables.
    """
    _schemas: Mapping[EventType, EventSchema]  # private, accessed via methods

    def latest_version(self, event_type: EventType) -> int:
        """Canonical latest version for this event type. Defaults to 1."""
        ...

    def schema(self, event_type: EventType) -> EventSchema:
        """Full schema metadata for an event type."""
        ...

    def migration_path(self, event_type: EventType) -> MigrationPath:
        """Ordered migration steps for this event type."""
        ...

    def is_current(self, event: EventRecord) -> bool:
        """True if event is exactly at its canonical version. Strict equality."""
        return event.schema_version == self.latest_version(event.event_type)

    def can_resolve(self, event: EventRecord) -> bool:
        """True if the policy has a valid migration path for this event.

        An event can be resolved if:
        - It is already at canonical version (no migration needed), OR
        - A complete migration path exists from its version to canonical
        """
        ...

    def event_types(self) -> Iterable[EventType]:
        """All event types with explicit schema metadata."""
        ...
```

**Default behavior:** Event types not in the policy default to `latest_version=1` with empty migration path. Every existing event immediately works — backward compatible by construction.

**Strict equality on `is_current()`:** Uses `==` not `>=`. An event with `schema_version=3` when `latest_version=2` is NOT current — it's an unknown future version and should error.

---

### 2. SchemaPolicyFactory — The Compiler

Compiles an immutable `SchemaPolicy` from `GovernanceState`. This is NOT a projection — it packages projected governance knowledge into an execution contract. It contains NO executable upcaster logic — that belongs in the replay engine.

```python
class SchemaPolicyFactory:
    """Compiles SchemaPolicy from GovernanceState.

    Does NOT own UpcasterRegistry. Only compiles metadata.
    Does NOT modify GovernanceState — reads it, compiles, returns new object.
    """

    def compile(self, governance_state: GovernanceState) -> SchemaPolicy:
        """Build SchemaPolicy from current governance state.

        For each event type in GovernanceState.schema_versions:
          - Reads latest_version from governance
          - Builds EventSchema with MigrationPath (metadata only, no callables)

        Event types NOT in governance default to:
          - latest_version = 1
          - migration_path = empty
        """
        ...

    def compile_at_sequence(
        self,
        governance_state: GovernanceState,
        sequence: int,
    ) -> SchemaPolicy:
        """Build SchemaPolicy as of a specific ledger sequence.

        Used for historical replay — reconstructs the schema policy
        that was active at time T.
        """
        ...
```

---

### 3. ReplayResolver — Pure Policy Executor

The resolver has NO knowledge of versions, evolved types, or governance. It only knows how to walk a `MigrationPath` and apply upcasters from `UpcasterRegistry`.

```python
class ReplayResolver:
    """Executes schema migration policy on events.

    Has NO knowledge of:
    - What the latest version is for any event type
    - Which event types have been evolved
    - Where schema policy comes from

    Only knows:
    - How to walk a MigrationPath
    - How to apply upcasters from UpcasterRegistry
    """

    def __init__(self, policy: SchemaPolicy, registry: UpcasterRegistry):
        self._policy = policy
        self._registry = registry

    def resolve(self, event: EventRecord) -> EventRecord:
        """Resolve event to canonical schema version.

        1. Check policy.is_current(event) → return unchanged
        2. Check policy.can_resolve(event) → if False, raise UnknownSchemaError
        3. Get policy.migration_path(event.event_type)
        4. Walk path, applying upcasters from registry
        5. Return resolved EventRecord
        """
        ...

    def resolve_all(self, events: Iterable[EventRecord]) -> list[EventRecord]:
        """Resolve a stream of events."""
        return [self.resolve(e) for e in events]
```

**Error model:** Policy determines resolution capability. `policy.can_resolve(event)` returns False if no valid migration path exists — resolver raises `UnknownSchemaError`. All reasoning about what's resolvable lives in policy; resolver simply executes.

---

### 4. ReplayContext — Pure Data

`ReplayContext` is purely declarative. It carries configuration only — no execution machinery.

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

**What's removed:**
- `target_schema_version: int` field
- `resolver: ReplayResolver` field
- `__post_init__` version comparison and resolver rebuilding

**What's added:**
- `schema_policy: SchemaPolicy` — the only schema configuration

**`ReplayPipeline` takes ownership of execution:**

```python
class ReplayPipeline:
    def __init__(self, context: ReplayContext, registry: UpcasterRegistry | None = None):
        self._context = context
        self._registry = registry or UpcasterRegistry()
        self._resolver = ReplayResolver(context.schema_policy, self._registry)

    def process(self, events: Iterable[EventRecord]) -> list[EventRecord]:
        """Filter by max_sequence, resolve each event to canonical form."""
        ...
```

**`InterpretiveContextBuilder` changes:**

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

---

### 5. Reducer Purity — Canonical Boundary Invariant

**Invariant: Reducers operate exclusively on canonical domain events.**

The replay layer is the only layer permitted to transform historical representations into canonical representations. Everything downstream operates exclusively on canonical events.

**Before (current):**
```python
# TaskReducer — knows BOTH v1 and v2
details = p.get("details", {})
title = details.get("summary") if isinstance(details, dict) else None
if title is None:
    title = p.get("title", "")  # fallback to v1
```

**After:**
```python
# TaskReducer — knows ONLY canonical v2
details = payload["details"]
title = details["summary"]
```

**Failure semantics:** If a reducer receives a non-canonical event, that is a bug in the replay layer. The reducer should fail loudly — not handle gracefully. Defensive fallback hides replay bugs.

**Architectural invariant (T14 — Canonical Projection Input):**

> For every event stream **E**, replay produces a canonical stream **C(E)** such that every projection operates only on **C(E)**.
>
> Formally: `Projection(E)` is forbidden. Only `Projection(C(E))` is permitted.

**Violation signature:**
- Reducer references `event.schema_version`
- Reducer branches on payload version
- Reducer contains `payload.get(...)` fallbacks introduced for historical schema support
- Any code path where `Projection` receives non-canonical events

**Enforcement:** Extend existing AST-based architectural guards (`test_architecture_guards.py`) to flag reducers containing schema version branching or compatibility fallback patterns.

---

### 6. Migration Specification Format

The Migration Designer produces a first-class governance artifact. Every specialist interacts with it from a different perspective.

```markdown
# Migration Specification

## Identity

- **Migration ID:** TASK_CREATED:v1→v2
- **Status:** Draft | Approved | Implemented | Frozen
- **Event Type:** TASK_CREATED
- **Current Version:** 1
- **Target Version:** 2

## Compatibility

- **Backward Read:** Yes
- **Forward Read:** No
- **Backward Write:** No
- **Mixed Replay:** Supported

## Structural Changes

| v1 Field | v2 Field | Required | Default |
|----------|----------|----------|---------|
| title | details.summary | Yes | — |
| description | details.body | No | "" |

## Semantic Changes

None

## Properties

- **Lossless:** Yes — Every v1 field has a deterministic destination
- **Rollback:** Supported — Downcaster v2→v1, no limitations
- **Canonical Schema:** v2

## Migration Path

```
v1 → v2 (task_created_v1_to_v2 upcaster)
```

## Required Verification

- [ ] Historical replay produces correct state
- [ ] Mixed-version replay produces identical state as native v2
- [ ] Roundtrip (upcast then downcast) preserves data
- [ ] Canonical projection equivalence: v1→upcast→projection == native v2→projection
- [ ] Replay benchmark unchanged

## Constitutional Traceability

- **Implements:** T14 Canonical Projection Input
- **Preserves:** T2 Projection Purity, T11 Monotonic Understanding
- **Verified By:** Schema Evolution Steward, Theorem Guardian
```

---

### 7. Schema Evolution Steward Role

A governance role that bridges design and implementation without blurring either responsibility.

**Responsibilities:**
- Owns `SchemaPolicy` correctness (reviews compiled policy, does not build it)
- Reviews migration specifications before implementation
- Verifies migration graphs remain acyclic
- Verifies canonical uniqueness (exactly one canonical version per event type)
- Verifies canonical stability (once a version is canonical, its schema identity is immutable)
- Verifies version monotonicity (migration edges always point toward newer versions)
- Verifies migration completeness (every version from 1 to latest has a path)
- Verifies rollback policy
- Verifies policy completeness (event coverage, migration coverage, canonical version, rollback metadata)
- Verifies deterministic replay (v1→v2→v3 produces same result as v1→v3)

**Does NOT:**
- Write code
- Modify migrations
- Override architecture decisions
- Validate implementation correctness, code quality, or runtime performance

**Is consulted by:**
- Migration Designer (before spec is finalized)
- Theorem Guardian (during constitutional review)
- Implementation Engineer (if migration questions arise)

---

## Updated Governance Workflow

```
Architecture Reviewer
        │
        ▼
Migration Designer → Migration Specification
        │
        ▼
Schema Evolution Steward
        ├── Policy completeness
        ├── Canonical uniqueness
        ├── Canonical stability
        ├── Graph acyclicity
        ├── Migration coverage
        ├── Rollback verification
        ├── Deterministic replay
        └── Version monotonicity
        │
        ▼
Theorem Guardian
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
Theorem Guardian (final sign-off)
```

---

## Files Affected

| File | Change |
|------|--------|
| `rationalevault/schema/policy.py` | **NEW** — `MigrationStep`, `MigrationPath`, `EventSchema`, `SchemaPolicy` |
| `rationalevault/schema/factory.py` | **NEW** — `SchemaPolicyFactory` |
| `rationalevault/schema/resolver.py` | **MODIFY** — Remove `target_schema_version`, `EVOLVED_EVENT_TYPES`; take `SchemaPolicy` + `UpcasterRegistry` |
| `rationalevault/schema/upcaster.py` | **MODIFY** — Remove auto-registration from `__init__`; registry becomes pure data structure |
| `rationalevault/projections/context.py` | **MODIFY** — Replace `target_schema_version` with `schema_policy`; remove `__post_init__` resolver rebuild |
| `rationalevault/projections/pipeline.py` | **MODIFY** — Own resolver construction; take `UpcasterRegistry` as dependency |
| `rationalevault/projections/service.py` | **MODIFY** — Pass registry through pipeline |
| `rationalevault/cognitive_head/reducers.py` | **MODIFY** — Remove v1/v2 branching in `TaskReducer`; use canonical v2 only |
| `tests/unit/test_architecture_guards.py` | **MODIFY** — Add T14 guard: flag reducers with schema version branching |
| `tests/unit/schema/test_resolver.py` | **MODIFY** — Update tests for new resolver interface |
| `tests/integration/test_proven_schema_evolution.py` | **MODIFY** — Update integration test for new context/pipeline interface |

---

## Architectural Invariants Preserved

| Invariant | How Preserved |
|-----------|---------------|
| T1 — Replay Equivalence | SchemaPolicy is deterministic; same governance state produces same policy |
| T2 — Projection Purity | Reducers contain no schema logic; canonical boundary enforced |
| T3 — Schema Evolution Safety | MigrationPath ensures complete upcaster chain; Steward verifies |
| T11 — Monotonic Understanding | GovernanceState remains source of truth; SchemaPolicy is derived snapshot |
| T14 — Canonical Projection Input | Projection(C(E)) is permitted; Projection(E) is forbidden |
| **Canonical Stability** | Once a version becomes canonical, its schema identity is immutable. A version cannot change meaning after being designated canonical. |

---

## Backward Compatibility

- All existing events without explicit `schema_version` default to v1
- `SchemaPolicy` defaults unknown event types to `latest_version=1` with empty migration path
- No database migration required — `schema_version` field already exists on `EventRecord`
- Existing `GovernanceState.schema_versions` data feeds directly into `SchemaPolicyFactory.compile()`

---

## What This Design Is Not

- **Not a new projection layer** — SchemaPolicy is a compiled value object, not a projection
- **Not a migration framework** — It defines metadata and paths; upcasters remain pure functions
- **Not a breaking change** — Default behavior preserves all existing semantics
- **Not a replacement for GovernanceState** — GovernanceState remains authoritative; SchemaPolicy is derived

---

*SchemaPolicy Architecture Design Spec — v1.0*
*Approved: 2026-06-29*
*Implements: F15 (Schema Evolution) governance refinement*
