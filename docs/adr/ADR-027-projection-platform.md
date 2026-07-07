# ADR-027: Projection Platform

> **Status:** Accepted
> **Date:** 2026-07-07
> **Implementation:** Phase A in v1.5
> **Deciders:** Chief Architect, Engineering Lead
> **Relates to:** ADR-026 (SnapshotStore V2)

---

## Context

v1.4 completed scalable replay for a single projection (`CognitiveHead`). The project now needs to support multiple projections (Knowledge, Embedding, Timeline, Recommendations, Governance, etc.) sharing the same deterministic replay, snapshot, and telemetry infrastructure.

The goal is to generalise the replay runtime into a **Projection Platform** that manages all projections uniformly, while preserving the architectural guarantees established in v1.4.

---

## Decision

### 1. Projection Laws (Non-negotiable)

Every projection MUST satisfy:

| # | Law | Description |
|---|-----|-------------|
| 1 | **Determinism** | Same event stream → same state. No external state (time, random, I/O). |
| 2 | **Replayability** | State reconstructible solely from events in the event ledger. Events are replayed in ledger order. |
| 3 | **Snapshotability** | Snapshots are caches, not authority. State → snapshot → state is lossless. |
| 4 | **Incrementality** | `replay(A+B) == replay(B, initial_state=replay(A))` for all reducers. |
| 5 | **Versioning** | Schema and logic versions evolve independently; stale snapshots invalidate automatically. |
| 6 | **Observability** | Emits `ReplayReport` with compile duration, event counts, snapshot metrics. |
| 7 | **Isolation** | Reads only declared event types. Does not inspect another projection's internal state. |
| 8 | **Idempotence** | Applying an already-applied event must not duplicate observable state. Duplicate event prevention is guaranteed by the event ledger's append-only nature; reducers are not responsible for deduplication. |

The Projection Laws are normative. Any implementation that violates them is non-conformant with the Projection Platform.

### 2. Projection Metadata

```python
class DependencyKind(Enum):
    STATE = "state"
    SEARCH = "search"
    EVENT_STREAM = "stream"
    QUERY = "query"
    EXPORT = "export"

@dataclass(frozen=True)
class ProjectionMetadata:
    id: str
    version: int                 # logic version (increment on reducer changes)
    schema_version: int          # snapshot payload schema version
    consumed_events: EventSelector
    capabilities: ProjectionCapabilities
    dependencies: list[ProjectionDependency]
    description: str = ""

@dataclass(frozen=True)
class ProjectionDependency:
    projection_id: str
    kind: DependencyKind
    optional: bool = False

@dataclass(frozen=True)
class EventSelector:
    types: frozenset[EventType] = frozenset()
    namespace: str = ""
    tags: frozenset[str] = frozenset()
```

### 3. Capabilities

```python
@dataclass(frozen=True)
class ProjectionCapabilities:
    searchable: bool = False
    snapshotable: bool = True
    observable: bool = True
    exportable: bool = False
    mutable: bool = False
```

### 4. ProjectionContext

```python
@dataclass
class ProjectionContext:
    projection_id: str
    event_store: EventStore
    snapshot_manager: SnapshotManager
    dependency_reader: DependencyReader   # read-only access to dependency states
    logger: Logger
    metrics: MetricsCollector
    config: dict[str, Any]
```

### 5. Projection Interface

```python
class Projection(Protocol):
    @property
    def metadata(self) -> ProjectionMetadata: ...

    def initialize(self, ctx: ProjectionContext) -> None: ...

    def reduce(self, events: list[EventRecord], initial_state: Optional[Any] = None) -> Any:
        """Pure event→state transformer. No dependency injection allowed."""
        ...

    def serialize(self, state: Any) -> dict: ...

    def deserialize(self, payload: dict) -> Any: ...

    def health(self) -> ProjectionHealth: ...

    def shutdown(self) -> None: ...

    # Optional (capability-gated)
    def search(self, ctx: ProjectionContext, query: str) -> list[SearchResult]: ...
    def export(self, ctx: ProjectionContext) -> dict: ...
    def metrics(self, ctx: ProjectionContext) -> dict: ...
```

### 6. Runtime Adapter (Separate from Projection)

```python
class RuntimeAdapter(Protocol):
    def build(self, state: Any) -> None: ...
    def destroy(self) -> None: ...
    def search(self, query: str) -> list[SearchResult]: ...
    def metrics(self) -> dict: ...
    def health(self) -> RuntimeHealth: ...
```

Projections use adapters to materialise views (FAISS, rustworkx, etc.) but do not own them. A RuntimeAdapter may be reconstructed or discarded at any time without affecting projection correctness. The platform is unaware of adapter internals.

### 7. Snapshot Invalidation Key

```python
@dataclass(frozen=True)
class SnapshotKey:
    projection_id: str
    projection_version: int          # manual increment on logic change
    schema_version: int
    dependencies_hash: str           # stable hash of all dependency SnapshotKeys
```

### 8. Registry (Explicit Registration)

```python
class ProjectionRegistry:
    def register(self, projection: Projection) -> None: ...
    def freeze(self) -> None: ...
    # Validation: existence of events, dependencies, no cycles, capability consistency
```

No auto-discovery. Explicit registration ensures deterministic startup.

### 9. Health Model

```python
class ProjectionHealth(Enum):
    UNKNOWN = "unknown"
    INITIALIZING = "initializing"
    BUILDING = "building"
    READY = "ready"
    STALE = "stale"
    FAILED = "failed"
    DEGRADED = "degraded"
    SHUTDOWN = "shutdown"
```

The platform owns health state; projections report their status via `health()`.

### 10. Platform Architecture

```
Event Ledger
       │
       ▼
Projection Platform
       │
   ┌───┼───┐
   ▼   ▼   ▼
Registry, ProjectionCompiler, SnapshotManager
       │
   ┌───┼───┐
   ▼   ▼   ▼
Projection instances
       │
       ▼
Projection API (internal)
       │
   ┌───┼───┐
   ▼   ▼   ▼
MCP, CLI, REST (adapters)
```

Transport adapters are separate from the platform, ensuring the platform remains reusable.

### 11. Migration Path

**Phase A:** Migrate `CognitiveHead` to the platform (zero-behavior change).
**Phase B:** Add `EmbeddingProjection` as the first new projection.

### 12. Projection Test Kit (Recommended Extension)

A separate suite of conformance tests should be built to validate that every projection satisfies the Projection Laws. This test kit will be created alongside the first projection migration, but it is not part of this ADR.

---

## Consequences

### Positive

- Unified abstraction for all projections.
- Reusable infrastructure (ProjectionCompiler, SnapshotManager, Telemetry).
- Determinism and correctness enforced by Projection Laws.
- Scalable (snapshots for every projection).
- Observable (per-projection `ReplayReport`).
- Extensible (new projections are plugins).
- Swappable backends via RuntimeAdapter.
- Explicit, deterministic registration.

### Negative

- Abstraction adds indirection.
- Migration requires refactoring CognitiveHead.

### Risks

Mitigated by two-phase migration and strong validation.

---

## Alternatives Considered

- **Hard-coded projections** → rejected (duplication).
- **External framework** → rejected (unfit for RationaleVault's requirements).
- **Embeddings as service** → rejected (breaks determinism).

---

## Validation

| Claim | Status | Evidence |
|-------|--------|----------|
| CognitiveHead migration | Verified | Phase A — zero-behavior change, 7 conformance laws pass |
| EmbeddingProjection | Verified | Phase B — second projection passes all 7 laws without platform changes |
| TimelineProjection | Verified | Phase C — third projection (narrative archetype) passes all 7 laws without platform changes |
| RecommendationProjection | Verified | Phase D — fourth projection (analytical archetype) passes all 7 laws without platform changes |
| GovernanceProjection | Verified | Phase E — fifth projection (policy evaluation archetype) passes all 7 laws without platform changes |
| Projection Laws enforceable | Verified | Protocol + Registry validation + five projections green |
| Snapshot invalidation practical | Verified | SnapshotKey with projection_version + schema_version + dependencies_hash |
| RuntimeAdapter isolation | Verified | Protocol separation from Projection; FAISSAdapter independent |
| Platform generality | Verified | Five fundamentally different projections (CognitiveHead, Embedding, Timeline, Recommendation, Governance) all pass unchanged Conformance Suite |

---

## References

- [cognitive_head/compiler.py](../rationalevault/cognitive_head/compiler.py) — Current `compile_cognitive_head()`
- [cognitive_head/replay_engine.py](../rationalevault/cognitive_head/replay_engine.py) — `ReplayEngine`
- [ADR-026: SnapshotStore V2](ADR-026-snapshot-store-v2.md) — Snapshot infrastructure
