# Reference Kernel — Section 3: Projection Runtime Specification

**Version:** 1.0-rc1
**Date:** July 15, 2026
**Status:** Draft — Not Yet Ratified
**Depends On:** AF-003 (Replay Engine)
**Provides:** Projection Lifecycle, Runtime Registry, Dependency Management, Versioning, Scheduling, Exposure Contract

---

## 1. Purpose

The Replay Engine reconstructs Understanding — the composite state of all active Projections at a given logical position. The Projection Runtime is what happens next. It answers the question:

> **How is reconstructed Understanding organized and managed over time?**

Replay produces Understanding. The Runtime governs it. These are two different responsibilities, owned by two different constitutional layers.

### 1.1 What the Projection Runtime owns

Exactly six concepts:

1. **Projection Lifecycle** — the states a Projection transitions through (registered, initialized, replaying, consistent, invalid, rebuilding)
2. **Projection Registry** — runtime discovery, registration, versioning, metadata
3. **Projection Dependencies** — the dependency graph between Projections, cycle prohibition, deterministic ordering
4. **Projection Versioning** — schema versioning, migration, invalidation, rebuild rules
5. **Projection Scheduling** — when rebuilds happen (immediate, lazy, background)
6. **Projection Exposure** — the contract for safely exposing Projection state to consumers

### 1.2 What the Projection Runtime does NOT own

- Context assembly, retrieval, ranking
- Prompt construction
- Embeddings
- LLM interaction
- Decision making
- Query execution

These belong to AF-005 (Context Runtime) and AF-006 (Reasoning Runtime).

### 1.3 Relationship to Replay

```
Replay Engine (AF-003)
    │
    │  Produces
    ▼
Understanding
    │
    │  Managed by
    ▼
Projection Runtime (AF-004)
    │
    │  Consumes
    ▼
Projection Registry ──── Replay Engine
    │                      │
    │  Provides            │  Reads
    ▼                      ▼
Reducers               Ledger (AF-002)
```

The Runtime consumes Replay's output (Understanding) and provides Replay's input (registered Reducers). This creates a circular dependency at the architectural level, but it is not cyclic: the Runtime registers Reducers *before* Replay runs, and consumes Understanding *after* Replay completes. The dependency is temporal, not structural.

---

## 2. Formal Definition

> **The Projection Runtime is the governance layer that manages the lifecycle, dependencies, versioning, scheduling, and exposure of Projections — the computational units that transform Events into structured Understanding.**

Let:

- `Projection` = a named unit of computation with a Reducer, a schema version, declared dependencies, and lifecycle state
- `D` = a directed acyclic graph of Projection dependencies
- `Registry` = the authoritative collection of all registered Projections with metadata
- `S` = a scheduling policy (immediate | lazy | background)
- `V` = a version identifier (Projection schema version)
- `Lifecycle` = the state machine governing Projection availability

The Runtime satisfies:

```
∀ p ∈ Registry : dependencies(p) ⊆ Registry             (I-13)
∀ p ∈ Registry : acyclic(dependencies(p))               (I-14)
∀ p ∈ Registry : state(p) ∈ Lifecycle                   (lifecycle compliance)
∀ p ∈ Registry : version(p) = V ⇒ state(p) = consistent (version compliance)
```

---

## 3. Architectural Invariants

### I-13: Projection Isolation

> A Projection SHALL observe only its declared dependencies and the replayed Event stream.

No hidden coupling, no shared mutable state, no runtime lookups outside the declared dependency graph. Isolation guarantees that the dependency graph is an accurate model of runtime behavior.

### I-14: Dependency Acyclicity

> Projection dependencies SHALL form a directed acyclic graph (DAG).

Cyclic dependencies make deterministic ordering impossible. The Registry MUST reject registration that would introduce a cycle.

---

## 4. Projection Model

### 4.1 Projection Definition

A Projection is defined by:

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Unique projection identifier |
| `reducer` | `ReducerFunc` | Pure function `(state, event) -> state` (AF-003 I-12) |
| `schema_version` | `int` | Monotonically increasing version number |
| `dependencies` | `list[str]` | Names of Projections this Projection depends on |
| `metadata` | `dict` | Extensible metadata (description, author, tags, etc.) |

### 4.2 Projection Identity

A Projection's identity is `(name, schema_version)`. Two registrations with the same `name` but different `schema_version` represent different versions of the same conceptual Projection. The Registry may hold only one active version per `name`.

---

## 5. Projection Lifecycle

Every registered Projection transitions through a defined lifecycle:

```
        ┌──────────────────────────────────┐
        │                                  │
        v                                  │
  ┌──────────┐     ┌────────────┐     ┌──────────┐
  │Registered│────→│Initializing│────→│Consistent│
  └──────────┘     └────────────┘     └──────────┘
       │                                  │
       │                                  │
       │                           ┌──────┴──────┐
       │                           │             │
       │                           v             v
       │                     ┌──────────┐  ┌──────────┐
       │                     │ Invalid  │  │ Rebuilding│
       │                     └──────────┘  └──────────┘
       │                           │             │
       │                           └──────┬──────┘
       │                                  │
       v                                  v
  ┌──────────┐                       ┌──────────┐
  │Deregistered│                     │Consistent│ (after rebuild)
  └──────────┘                       └──────────┘
```

### 5.1 State Descriptions

| State | Meaning |
|-------|---------|
| `Registered` | Known to the Registry, not yet initialized |
| `Initializing` | First replay in progress (transitional) |
| `Consistent` | Fully replayed, state reflects current Ledger head |
| `Invalid` | State is stale — dependency changed or schema version mismatch |
| `Rebuilding` | Replay in progress after invalidation (transitional) |
| `Deregistered` | Removed from the Registry |

### 5.2 Lifecycle Rules

1. A Projection MUST be `Registered` before it can transition to `Initializing`.
2. A Projection MUST complete `Initializing` (first replay) before it can become `Consistent`.
3. A Projection MUST become `Invalid` when any of its dependencies change `schema_version`.
4. A Projection MUST become `Invalid` when its own `schema_version` is incremented.
5. A Projection MUST rebuild (transition through `Rebuilding` to `Consistent`) after invalidation.
6. A Projection MUST NOT be exposed to consumers while in `Initializing` or `Rebuilding` states.

---

## 6. Projection Registry

### 6.1 Runtime Registry

The Runtime Registry is distinct from Replay's `ProjectionRegistry` (AF-003). Replay's registry is a simple ordered collection of Reducers. The Runtime Registry adds:

- Lifecycle state tracking
- Dependency graph management
- Schema version history
- Scheduling metadata
- Exposure controls

### 6.2 Registry Operations

| Operation | Description |
|-----------|-------------|
| `register(projection)` | Add a Projection to the Registry. Validates dependencies and acyclicity. |
| `deregister(name)` | Remove a Projection. Invalidates dependents. |
| `get(name)` | Retrieve a Projection's state and metadata. |
| `list()` | List all registered Projections. |
| `resolve_dependency_order()` | Topological sort of registered Projections. |

### 6.3 Registration Validation

The Registry MUST reject registration if:

1. A Projection with the same `name` and `schema_version` already exists (idempotent).
2. Any declared dependency does not exist in the Registry.
3. Adding the Projection would introduce a dependency cycle (I-14).

---

## 7. Dependency Model

### 7.1 Declared Dependencies

Each Projection declares its dependencies by `name`. The dependency declaration is a list of zero or more Projection names. A Projection with zero dependencies depends only on the replayed Event stream (I-13).

### 7.2 Dependency Graph

The Registry maintains a directed graph where:

- Nodes = registered Projections
- Edges = `A depends on B`

### 7.3 Topological Ordering

Replay processes Projections in topological order according to the dependency DAG. All dependencies of a Projection MUST reach `Consistent` state before the dependent Projection begins replaying. This guarantees that when a Projection reads its dependency's state, that state is current.

### 7.4 Cycle Prohibition

The Registry SHALL reject any registration that would introduce a cycle (I-14). Cycle detection is performed at registration time using DFS-based topological sort.

---

## 8. Projection Versioning

### 8.1 Schema Version

Each Projection has a `schema_version` field. This is an integer that MUST be incremented whenever the Projection's schema (the shape of its state) changes in a backward-incompatible way.

### 8.2 Version Rules

1. Incrementing `schema_version` invalidates the Projection.
2. Incrementing `schema_version` invalidates all dependent Projections.
3. After invalidation, the Projection MUST rebuild before it can become `Consistent`.
4. The Registry tracks only one active version per Projection `name`.
5. Version history (previous schema versions) MAY be retained for migration support.

### 8.3 Migration

When a Projection's schema version changes, its state is discarded and rebuilt from scratch via full replay. Incremental migration (transforming old state to new schema) is a future optimization and is NOT part of this specification.

---

## 9. Projection Scheduling

### 9.1 Scheduling Policies

The Runtime supports three rebuild scheduling policies:

| Policy | Behavior | Use Case |
|--------|----------|----------|
| `immediate` | Rebuild starts as soon as invalidation is detected | Critical projections |
| `lazy` | Rebuild deferred until first consumer access | Projections with expensive rebuilds |
| `background` | Rebuild runs asynchronously when resources permit | Non-critical projections |

### 9.2 Schedule Definition

Scheduling is defined at registration time:

```python
@dataclass(frozen=True)
class ProjectionSchedule:
    policy: str  # "immediate" | "lazy" | "background"
    priority: int | None = None  # lower = higher priority (background only)
```

The default policy is `immediate`.

### 9.3 Default Policy

If no schedule is specified, the default scheduling policy is `immediate` — rebuild starts immediately upon invalidation. This guarantees the strongest consistency semantics and is appropriate for most projections.

---

## 10. Projection Exposure

### 10.1 Exposure Contract

The Runtime exposes Projection state through a single operation:

```python
def read(name: str) -> ProjectionState | None:
```

This operation:

1. Returns `None` if the Projection is not registered.
2. Returns `None` if the Projection is in `Initializing` or `Rebuilding` state.
3. Triggers a lazy rebuild if the schedule is `lazy` and the Projection is `Invalid`.
4. Returns the current state if the Projection is `Consistent`.

### 10.2 Exposure Guarantees

- Reads are safe: a consumer never receives stale or mid-rebuild state.
- Reads are race-free: rebuild and read are synchronized (rebuild completes before read returns).
- Reads are immutable: the returned state is a snapshot, not a live reference.

---

## 11. Compliance Scenarios (PP)

The following scenarios define the Projection Protocol compliance suite. Each scenario is a language-independent specification artifact.

| ID | Scenario | Invariants |
|----|----------|------------|
| PP-01 | Register a single Projection with no dependencies | I-13 |
| PP-02 | Register multiple Projections with dependency ordering | I-13, I-14 |
| PP-03 | Increment schema_version and verify invalidation | — |
| PP-04 | Transition through full lifecycle: Registered → Consistent | — |
| PP-05 | Register, invalidate, rebuild, verify Consistent state | — |
| PP-06 | Register a Projection that would create a dependency cycle → rejection | I-14 |
| PP-07 | Register dependency, invalidate dependency, verify dependent invalidated | I-13 |
| PP-08 | Lazy rebuild: access invalid Projection, verify rebuild before return | — |
| PP-09 | Concurrent read during rebuild returns None (graceful) | — |
| PP-10 | Topological ordering: dependencies replay before dependents | I-14 |

---

## 12. Constitutional Traceability

| Requirement | Source | Verification |
|-------------|--------|-------------|
| Projection Isolation | I-13 | PP-01, PP-05, PP-07 |
| Dependency Acyclicity | I-14 | PP-02, PP-06, PP-10 |
| Lifecycle compliance | Section 5 | PP-04, PP-05 |
| Version compliance | Section 8 | PP-03 |
| Schedule compliance | Section 9 | PP-08, PP-09 |
| An invalid Projection is not exposed | Section 10 | PP-09 |

---

## 13. Non-Guarantees

The Projection Runtime explicitly does NOT guarantee:

1. **Real-time consistency** — eventual consistency is the default. Projections may lag behind the Ledger head.
2. **Historical version access** — only the current version is exposed. Historical states are not retained.
3. **Migration support** — schema changes discard state. Incremental migration is a future optimization.
4. **Cross-Projection atomicity** — each Projection rebuilds independently. There is no transactional rebuild across projections.
5. **External side-effect management** — Projections that violate I-12 (Reducer Purity) are detected but not prevented at the Runtime layer.

---

## 14. Decisions Log

| Decision | Rationale |
|----------|-----------|
| Runtime Registry is separate from Replay's Registry | Different responsibilities: Replay consumes a simple ordered list; Runtime manages lifecycle, versions, dependencies, scheduling |
| Default scheduling is `immediate` | Strongest consistency; `lazy` and `background` are explicit opt-ins |
| Schema version increments cause full rebuild | Simplicity first; incremental migration can be added later |
| Exposure returns `None` for non-Consistent projections | Fail-safe: never expose stale or mid-rebuild state |
| Lifecycle state machine is defined at the spec level | Required for I-13 and I-14 compliance; implementors must not deviate |

---

## 15. Freeze Criteria

AF-004 is ratifiable when:

1. [ ] All PP compliance scenarios (PP-01 through PP-10) have language-independent specification artifacts in `spec/vectors/projection/`
2. [ ] I-13 (Projection Isolation) test passes in the reference implementation
3. [ ] I-14 (Dependency Acyclicity) test passes in the reference implementation
4. [ ] Runtime Registry correctly validates dependencies at registration time
5. [ ] Lifecycle state transitions are correctly implemented
6. [ ] Lazy rebuild triggers before read-return
7. [ ] Dependency cycle is correctly detected and rejected
8. [ ] Full existing test suite (AF-001 + AF-002 + AF-003) has zero regressions
9. [ ] This specification document is frozen
10. [ ] Compliance suite (PP-01..PP-10) passes against the reference implementation
