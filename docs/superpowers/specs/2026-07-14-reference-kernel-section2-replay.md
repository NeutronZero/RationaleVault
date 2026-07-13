# Reference Kernel — Section 2: Replay Engine Specification

**Version:** 1.0-rc1
**Date:** July 14, 2026
**Status:** Draft — Not Yet Ratified
**Depends On:** AF-001 (Canonical Representation Layer), AF-002 (Ledger), ADR-024, ADR-026, ADR-027
**Provides:** Deterministic Replay Contract, Understanding Reconstruction, Snapshot Equivalence

---

## 1. Purpose

The Replay Engine is the deterministic heart of RationaleVault. It consumes committed Events from the Ledger and produces **Understanding** — the composite state of all active Projections at a given logical position. Understanding is the foundation on which every higher-level capability (context retrieval, reasoning, decision-making) is built.

The Replay Engine is responsible for three things, and three things only:

1. **Reconstruct Understanding** from the Ledger
2. **Validate equivalence** — every replay mode produces identical Understanding
3. **Manage Snapshots** — optimize replay without compromising correctness

This specification defines:

- The formal Replay model
- The relationship between Ledger, Events, Projections, and Understanding
- The Reducer contract (I-12)
- The Snapshot contract
- Replay compliance scenarios as specification artifacts
- Explicit constitutional traceability
- Freeze criteria for Section 2

> **A note on scope.**
>
> The Replay Engine reconstructs Understanding. It does **not** interpret, query, retrieve, reason over, or present Understanding. Interpretation belongs to the Projection Runtime. This boundary is constitutional: Replay remains permanently ignorant of how Understanding is consumed.
>
> The Replay Engine also does **not** define individual Projections (Memory, Knowledge, World Model, Policy, Analytics, etc.). Those are Projection implementations. Replay only understands the Reducer contract.

---

## 2. Formal Definition of Replay

> **Replay is the deterministic reconstruction of Understanding by applying committed Events from the Ledger, in global logical order, through pure Reducer functions.**

Let:

- `L` = a Ledger state (an immutable, append-only sequence of Commits)
- `P` = a ProjectionSet (a collection of pure Reducers, each maintaining isolated state)
- `R` = a Reducer `(event, state) -> new_state`
- `U` = Understanding (the aggregate of all Projection states)

Then:

```
replay(L, P) = U
replay(L, P, target=global_order(N)) = U_N  -- Understanding at position N
replay(L, P, snapshot=S) = replay(L, P)      -- equivalence (I-07)
```

Where:

- `U` is identical for identical `L` and `P` (Determinism — I-01)
- Every event in scope is processed exactly once (Completeness — I-01a)
- No Reducer has side effects (Purity — I-12)

---

## 3. Architectural Invariants (Replay-Specific)

The Replay Engine upholds the following invariants:

| ID | Invariant | Source |
|----|-----------|--------|
| I-01 | **Replay Determinism** — Given the same Ledger state and the same ProjectionSet, replay produces identical Understanding every time | Constitution Article 3 |
| I-01a | **Replay Completeness** — Every committed event within the replay scope is presented to every Reducer exactly once. Reducers MAY ignore events they do not recognize. This is a forward compatibility mechanism | Constitution Article 3 |
| I-07 | **Replay Equivalence** — Snapshot replay produces the same Understanding as full replay | ADR-026 |
| I-08 | **Referential Transparency** — All identifiers are deterministically generated | Constitution Article 3 |
| I-09 | **Projection Monotonicity** — Projections are composable; state flows downward | Constitution Article 4 |
| I-11 | **Replay Completeness (Ledger-level)** — The Ledger provides every committed event | AF-002 |
| I-12 | **Reducer Purity** — A Reducer SHALL have no observable side effects. It SHALL NOT perform I/O, call LLMs, or access external state. It SHALL be a deterministic function of `(event, state) -> new_state` | New |

> **I-12 is the cornerstone.** Because every Reducer is pure, the Replay Engine is necessarily pure. Idempotency, equivalence, and restartability are consequences, not goals.

**These invariants are normative.** Any Replay Engine implementation must satisfy all of them.

---

## 4. Replay Model

### 4.0 Projection Identity

> **A Projection is an independently reducible view of the Ledger, identified by a stable identity and version.**

```python
@dataclass(frozen=True)
class Projection:
    projection_id: str     # Stable identifier, e.g. "memory", "knowledge"
    version: int           # Incremented when reducer logic changes
    reducer: Callable      # Pure function (event, state) -> new_state
```

- `projection_id` is used in Snapshot keys and Replay Boundary tracking
- `version` drives Snapshot invalidation: a version change invalidates all existing Snapshots for that Projection
- The `reducer` is the pure function defined by Section 8

Projections are registered with the Replay Engine. Registration order determines Reducer execution order.

> **Reducers SHALL be invoked in a deterministic order defined by Projection registration. This order SHALL be consistent across Replay Engine implementations.**

Without this rule, two implementations could iterate over Projections in different orders. If Projections ever depend on shared events (even indirectly through observation order), this would violate Replay Determinism (I-01).

### 4.1 Replay → Understanding → ProjectionSet

```
       Ledger
         │
         ▼
┌────────────────────┐
│   Replay Engine    │
│  ┌──────────────┐  │
│  │   Reducer 1  │  │
│  │   Reducer 2  │  │
│  │   Reducer N  │  │
│  └──────────────┘  │
└────────┬───────────┘
         │
         ▼
┌────────────────────┐
│    Understanding   │
│  ┌──────────────┐  │
│  │  Projection  │  │  ← Memory
│  │  Projection  │  │  ← Knowledge
│  │  Projection  │  │  ← World Model
│  │  ...         │  │
│  └──────────────┘  │
└────────────────────┘
         │
         ▼
   ┌────────────┐
   │ Projection │
   │  Runtime   │  ← interprets Understanding
   └────────────┘
```

The Replay Engine ends at Understanding. The Projection Runtime begins there. This boundary is constitutional.

### 4.2 Replay Scope

> **The scope defines which Events are included in a replay.**

| Scope | Ordering | Use Case |
|-------|----------|----------|
| **Global** (default) | All streams, ordered by `global_order` | Cross-stream projections, Understanding reconstruction |
| **Stream** | Single stream, ordered by `sequence` | Projections with explicit stream affinity |

> **Unless explicitly declared otherwise by a Projection, Replay SHALL operate over the complete Ledger in global logical order.**

This prevents accidental architectural fragmentation. Stream-level replay is a specialization for projections that can declare stream affinity; it is not the default.

### 4.3 Replay Modes

| Mode | Description |
|------|-------------|
| **Auto** (default) | The Engine chooses the optimal mode based on Snapshot availability and Event count |
| **Full** | Replay from the beginning of the Ledger. No snapshot required |
| **Delta** | Replay from a Snapshot, applying only Events after the Snapshot's position. Fails if no Snapshot |
| **Fast Path** | Optimized Delta replay achieving 99%+ coverage. Fails if Snapshot infrastructure unavailable |

The caller specifies `mode` as an optional parameter. If `mode` is `Auto` (the default), the Engine's internal Replay Planner selects the optimal strategy. Explicit mode selection is primarily used for testing and equivalence verification.

> **Replay SHALL produce identical Understanding regardless of the selected replay strategy.** (I-07)
>
> **Planner decisions SHALL NOT affect observable Replay behavior.**

These guarantees mean the Planner is purely an optimization concern. No caller should ever need to know whether a Snapshot was used.

### 4.4 Replay Boundary

> **A Replay Boundary is the greatest committed `global_order` value included in a reconstructed Understanding.**

A Replay Boundary of `N` means Understanding was produced by processing all Events with `global_order <= N`.

Examples:

- `global_order = 105` (Understanding includes all Events up to and including `global_order` 105)
- A Snapshot position
- The end of the Ledger

Replay Boundaries enable:

- **Delta replay** — "replay everything after Boundary 105"
- **Snapshot validation** — "does the Snapshot at Boundary 105 match full replay to 105?"
- **Incremental replay** — "advance Understanding from Boundary 105 to 110"
- **Distributed replay** — "partition replay across Boundaries 0-100, 101-200"

A Replay Boundary is always a `global_order` value. It is never wall-clock time.

---

## 5. Replay Inputs

The Replay Engine consumes **only**:

```
Ledger
  │
  ├── Commits
  │     │
  │     └── Events (CanonicalEnvelope)
  │
  └── read_stream(stream_id)    — per-stream ordering
  └── read_from(global_order)   — global ordering
```

Nothing else.

- No databases
- No files
- No network
- No adapters

Adapters belong **before** the Ledger. Schema resolution happens **before** replay reaches the Engine (ADR-024: `ReplayResolver` sits between the raw event stream and the Engine).

---

## 6. Replay Outputs

> **Replay computes Understanding. ReplayResult packages Understanding together with replay metadata.**

### 6.1 Understanding (Primary)

> **Understanding is the composite state of all active Projections at a specific Replay Boundary.**

```python
@dataclass(frozen=True)
class Understanding:
    projections: dict[str, Any]   # Projection ID → Projection state
    boundary: int                 # Replay Boundary (greatest global_order included)
```

Understanding is:

- **The primary domain output of Replay** — Replay exists to produce Understanding
- **Not stored directly** — it is always materialized through the Replay Engine
- **Immutable for a given Ledger state** — same Ledger, same ProjectionSet, same Understanding
- **Composable** — individual Projection states can be reduced independently

### 6.2 ReplayResult (Transport)

> **ReplayResult packages Understanding together with replay metadata.**

```python
@dataclass(frozen=True)
class ReplayResult:
    understanding: Understanding   # The composite state of all Projections
    report: ReplayReport           # How replay was performed
    version: int                   # rvcj_version (canonical representation version)
    replay_position: int           # Replay Boundary (greatest global_order included)
```

- `understanding` — the primary output. Everything else is metadata
- `report` — replay telemetry (mode, events processed, snapshot hit/miss)
- `version` — the `rvcj_version` governing canonical Event interpretation
- `replay_position` — the Replay Boundary at which Understanding was materialized

### 6.3 ReplayReport

```python
@dataclass(frozen=True)
class ReplayReport:
    mode: str                     # "full", "delta", "fast_path", "auto"
    events_processed: int
    snapshot_used: bool
    replay_position: int          # global_order
    version: int
```

The Report is observability infrastructure. It is not a source of truth.

---

## 7. Replay Guarantees

| Guarantee | Formal Statement |
|-----------|-----------------|
| **Determinism** | `replay(L, P) == replay(L, P)` for identical `L` and `P` (I-01) |
| **Completeness** | Every Event in scope is presented to every Reducer exactly once (I-01a) |
| **Equivalence** | `replay(L, mode=Delta, snapshot=S) == replay(L, mode=Full)` (I-07) |
| **Prefix Determinism** | `replay(L, target=N)` produces Understanding identical to `truncate(replay(L), N)` |
| **Idempotency** | `replay(L); replay(L) == replay(L)` — replay is safe to repeat |
| **Restartability** | Replay can be interrupted and resumed. The result is identical to uninterrupted replay |
| **Purity** | No Reducer has side effects. Replay does not write, call, or modify anything outside the Engine (I-12) |

---

## 8. Reducer Contract

### 8.1 Definition

> **A Reducer is a pure function that transforms a Projection's state by applying a single Event.**

```python
def reduce(event: CanonicalEnvelope, state: Any) -> Any:
    ...
```

- The function MUST be deterministic
- The function MUST NOT perform I/O
- The function MUST NOT call LLMs or external services
- The function MUST NOT access shared mutable state
- Unknown Event types SHALL be ignored by Reducers that do not recognize them (forward compatibility). Implementations MAY log unknown Event types for observability

### 8.2 Reducer Laws (from ADR-027)

| Law | Statement |
|-----|-----------|
| **Determinism** | `reduce(e, s)` always produces the same output for the same `(e, s)` |
| **Replayability** | `fold(reduce, events, initial_state)` is reproducible |
| **Snapshotability** | Serialized state can be deserialized and reduction continued |
| **Incrementality** | `replay(A+B) == replay(B, initial_state=replay(A))` |
| **Idempotence** | `reduce(e, reduce(e, s)) == reduce(e, s)` |
| **Isolation** | No Reducer reads another Projection's state |
| **Composability** | Projection states combine into Understanding without conflict |

---

## 9. Snapshot Contract

### 9.1 Definition

> **A Snapshot is the serialized state of a Projection at a specific Replay Boundary, stored for optimization.**

```python
@dataclass(frozen=True)
class Snapshot:
    projection_id: str
    version: int                 # Projection logic version
    state: bytes                 # Serialized Projection state
    replay_position: int         # global_order at capture
    schema_version: int          # Snapshot payload schema version
    dependencies_hash: str | None = None  # Optional: content hash of Projection
                                       # dependencies (e.g. other Projection states
                                       # consumed during reduction). Used to detect
                                       # dependency changes that invalidate the Snapshot.
                                       # If None, dependency detection is not performed.
```

### 9.2 Creation Policy

- **EventCountPolicy** — Capture a Snapshot every N Events (default: 100)
- One Snapshot per Projection
- Snapshots are **never** a source of truth. They are optimizations with strict equivalence guarantees

### 9.3 Equivalence (I-07)

For any Ledger state `L`, Snapshot `S` captured at Replay Boundary `P`, and target Boundary `T >= P`:

```
replay(L, Full) ≡ replay(L, Delta, snapshot=S, target=T)
```

A Snapshot is valid iff this equivalence holds.

### 9.4 Validation

- The `SnapshotManager.validate()` method checks equivalence by comparing Delta replay to Full replay
- **Validation is defined in terms of Understanding equality, not byte equality.** Comparing serialized Snapshot state byte-for-byte is NOT a valid equivalence check
- If equivalence fails, the Snapshot is discarded and Full replay is used
- Schema version mismatch automatically invalidates the Snapshot
- All Snapshot fallbacks are silent — the caller always receives the correct Understanding

### 9.5 Versioning

- Snapshots carry the Projection's `version` and payload `schema_version`
- If a Projection's reducer logic changes (version increment), existing Snapshots are invalid
- If the Snapshot payload format changes (schema_version increment), existing Snapshots are invalid
- Invalid Snapshots degrade to Full replay

---

## 10. Replay Compliance Scenarios

Each scenario specifies a Ledger state and a Replay expectation. These are normative specification artifacts.

| ID | Name | Description |
|----|------|-------------|
| RP-01 | **Empty Ledger** | Replay produces empty Understanding (no Projections have events) |
| RP-02 | **Single Event** | Replay produces Understanding with one Event processed |
| RP-03 | **Snapshot Equivalence** | Delta replay from a Snapshot produces Understanding identical to Full replay |
| RP-04 | **Multi-Event Commit** | Multi-Event Commit preserves Event order through Replay |
| RP-05 | **Multiple Streams** | Global replay orders Events by `global_order` across streams |
| RP-06 | **Fast Path** | Fast Path replay produces Understanding identical to Full replay |
| RP-07 | **Idempotent Replay** | Replaying the same scope twice produces identical Understanding |
| RP-08 | **Schema Evolution** | Replay of historical Events with an older schema version succeeds |
| RP-09 | **Interrupted Replay** | Replay interrupted at Boundary 100, then resumed to Boundary 200, produces Understanding identical to uninterrupted replay through Boundary 200 |

**Vector directory:** `spec/vectors/replay/`

---

## 11. Constitutional Traceability

| Replay Guarantee | Constitution | Invariant | Scenario |
|-----------------|--------------|-----------|----------|
| Deterministic replay | Article 3 | I-01 | RP-01..RP-08 |
| Replay completeness | Article 3 | I-01a | RP-02, RP-05 |
| Snapshot equivalence | ADR-026 | I-07 | RP-03 |
| Referential transparency | Article 3 | I-08 | All identifiers |
| Projection monotonicity | Article 4 | I-09 | All |
| Schema compatibility | ADR E-001 | I-10 | RP-08 |
| Ledger completeness | AF-002 | I-11 | All |
| Reducer purity | New | I-12 | All |
| Restartability | Article 3 | I-01 | RP-09 |

---

## 12. Explicit Non-Guarantees

The Replay Engine does **not** guarantee:

| Aspect | Not Guaranteed | Belongs To |
|--------|---------------|------------|
| Real-time ordering | Ordering is logical, not temporal | Ledger (AF-002) |
| Query capabilities | No search, filter, or index | Projection Runtime |
| Context retrieval | No retrieval, ranking, or blending | Context Runtime |
| Reasoning or decisions | No LLM calls, tool use, or policy evaluation | Evaluation Runtime |
| Storage technology | No requirement for SQL, NoSQL, or filesystem | Implementation |
| Caching | No result caching | Future ADR |
| Parallelization | No distributed or multi-threaded replay | Future ADR |
| Performance SLAs | No latency or throughput targets | Phase 3 Benchmarking |
| Streaming | No continuous real-time replay | Future ADR |
| Deterministic execution time | Only deterministic output is guaranteed. Execution time is implementation-dependent | Implementation |

---

## 13. Decisions Log

| # | Decision | Rationale |
|---|----------|-----------|
| D-12 | Default replay scope is Global, ordered by `global_order` | Cross-stream consistency is the safe default. Stream-level replay requires explicit Projection affinity. Prevents accidental architectural fragmentation. |
| D-13 | Understanding is the primary domain output. ProjectionSet is its internal composition | Aligns with Phase 1A domain language. Replay produces Understanding. Understanding contains Projections. Cleaner semantics. |
| D-14 | EventCountPolicy (100) is the default Snapshot policy | Balanced between replay cost and storage overhead. Overridable but rarely needs to be. |
| D-15 | Replay Planner is an internal implementation detail. Callers specify `mode` optionally | Callers should not need to know whether a Snapshot was used. The guarantee is equivalence. |
| D-16 | ReplayResult includes `replay_position` (Replay Boundary) | Enables delta replay, incremental replay, Snapshot validation, and distributed replay without exposing internal state. |
| D-17 | I-12 is Reducer Purity, not Replay Purity | Stronger guarantee. If every Reducer is pure, the Engine is necessarily pure. Directly testable. |
| D-18 | Replay ends at ReplayResult. Understanding is consumed by the Projection Runtime | Constitutional boundary. Keeps Replay permanently ignorant of how Understanding is interpreted. |
| D-19 | Unknown Event types SHALL be ignored by Reducers that do not recognize them | Forward compatibility. New Event types in future versions do not break historical replay. |
| D-20 | Reducers SHALL be invoked in deterministic order defined by Projection registration | Prevents ordering-dependent non-determinism across implementations. Essential for I-01. |
| D-21 | Understanding is the primary domain output. ReplayResult packages Understanding with metadata | Replay computes Understanding. ReplayResult is merely the transport object. Keeps domain concept primary. |
| D-22 | Planner decisions SHALL NOT affect observable Replay behavior | Guarantees the Planner is purely an optimization concern. No caller should need to know whether a Snapshot was used. |

---

## Freeze Criteria

Section 2 (Replay Engine) is considered complete when:

- [ ] All replay compliance scenarios (RP-01 through RP-09) are specified, with normative vector files.
- [ ] Understanding is established as the primary domain output of Replay.
- [ ] Replay Boundary is defined as a formal concept.
- [ ] Reducer purity (I-12) is defined and testable.
- [ ] Snapshot equivalence (I-07) is formalized with validation rules.
- [ ] Constitutional traceability matrix (Section 11) is complete.
- [ ] Replay Engine API is stabilized.
- [ ] Explicit non-guarantees (Section 12) are recorded.
- [ ] Decisions log (Section 13) captures all design rationale.
- [ ] Implementation plan (TDD) exists for the Replay Engine.
- [ ] Replay Engine validated against at least one implementation.
- [ ] Snapshot equivalence validated in both Delta and Fast Path modes.
- [ ] This document has been ratified by architectural review.

---

## Appendix A: Replay Compliance Vectors (Replay)

Each compliance vector is a JSON file in `spec/vectors/replay/` following the same format as AF-001 and AF-002:

```json
{
  "name": "rp-01-empty-ledger",
  "description": "Replay of empty Ledger produces empty Understanding",
  "ledger": {},
  "replay": {"scope": "global"},
  "expected": {"projections": {}},
  "invariants": ["I-01", "I-01a"]
}
```

Vector directory structure:

```
spec/vectors/replay/
├── rp-01-empty-ledger.json
├── rp-02-single-event.json
├── rp-03-snapshot-equivalence.json
├── rp-04-multi-event-commit.json
├── rp-05-multiple-streams.json
├── rp-06-fast-path.json
├── rp-07-idempotent-replay.json
├── rp-08-schema-evolution.json
├── rp-09-interrupted-replay.json
```

---

## Appendix B: Existing ADR Coverage (Informative)

This specification constitutionalizes principles first established in the following ADRs:

| ADR | Content | Status |
|-----|---------|--------|
| ADR-024 | Replay infrastructure, ReplayResolver, ReplayContext | Incorporated into I-12 and Section 5 |
| ADR-026 | Snapshot store, delta replay, equivalence, invalidation | Incorporated into I-07 and Section 9 |
| ADR-027 | Projection laws, reducer interface, platform architecture | Incorporated into Section 8 |
| tests/equivalence/ | ~44 equivalence tests | Incorporated into I-07 validation |

These ADRs remain valid as implementation guidance. AF-003 is the normative constitutional specification.

---

*End of Section 2: Replay Engine Specification*
