# ADR-026: SnapshotStore V2

> **Status:** Accepted
> **Date:** 2026-07-06
> **Implementation:** Complete in v1.4.0
> **Deciders:** Chief Architect, User
> **Relates to:** ADR-024 (Replay Infrastructure), SnapshotStore V1 placeholder

---

## Context

`compile_cognitive_head()` replays the **entire** event ledger on every invocation. At V1 scale (hundreds of events, local SQLite), this is fast enough. But the project is designed to grow: projects accumulate decisions, tasks, questions, knowledge, and memory events over weeks or months. At thousands of events, full replay becomes a measurable bottleneck.

The V1 `SnapshotStore` placeholder (`cognitive_head/snapshot.py`) defines the interface but returns `None` unconditionally, forcing full replay. The V2 implementation fills this interface with a real storage backend.

**Key constraint:** Snapshots must preserve determinism. The same event sequence must always produce identical snapshot state. Snapshots are an optimization, not a new source of truth.

---

## Decision

### 1. Snapshot Schema

Add a `relay_snapshots` table to both SQLite and PostgreSQL backends:

```sql
CREATE TABLE relay_snapshots (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID NOT NULL,
    sequence        BIGINT NOT NULL,       -- event_sequence of last event in snapshot
    head_json       JSONB NOT NULL,        -- serialized CognitiveHead
    schema_version  INTEGER NOT NULL DEFAULT 1,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (project_id)                    -- one latest snapshot per project
);
```

**SQLite variant:** `head_json TEXT NOT NULL` (JSON stored as text), `created_at TEXT NOT NULL DEFAULT (datetime('now'))`.

One snapshot per project. The `UNIQUE (project_id)` constraint enforces this. New snapshots replace old ones via `INSERT OR REPLACE` (SQLite) or `ON CONFLICT (project_id) DO UPDATE` (PostgreSQL).

### 2. Snapshot Data Model

Extend the existing `Snapshot` dataclass in `cognitive_head/snapshot.py`:

```python
@dataclass
class Snapshot:
    project_id: UUID
    sequence: int
    head: CognitiveHead
    schema_version: int = 1
```

Serialization uses `CognitiveHead.to_dict()` for `head_json`. Deserialization uses `CognitiveHead.from_dict()`.

### 3. Replay Algorithm

```
compile_cognitive_head(project_id):
    1. snapshot = snapshot_store.load_latest_snapshot(project_id)
    2. if snapshot is None:
           # Full replay (current behavior)
           events = store.get_project_stream(project_id)
           head = replay_all(events)
    3. else:
           # Delta replay
           events = store.get_project_stream(project_id, since_sequence=snapshot.sequence)
           if events:
               head = apply_events_after_snapshot(snapshot.head, events)
           else:
               head = snapshot.head   # no new events, snapshot is current
    4. return head
```

`apply_events_after_snapshot()` runs the same four reducers on the delta events only, starting from the snapshot's `CognitiveHead` state. This is **not** a new reducer — it reuses the existing reducer logic on the delta event stream.

**Critical invariant:** The snapshot is valid if and only if replaying events after `snapshot.sequence` produces the same result as replaying all events from the beginning. This holds because reducers are pure functions of `list[EventRecord]`.

### 4. Snapshot Validity

A snapshot is **invalid** (and treated as absent) when:

- `snapshot.schema_version != current_schema_version` — schema mismatch, full replay required.
- The project stream has been migrated or rewritten — sequence numbers may not align.
- `CognitiveHead.from_dict()` raises an exception — corrupted data.

Invalid snapshots are silently discarded. The system falls back to full replay. No error is raised.

### 5. Trigger Policy

Snapshots are saved:

- **After N events:** Configurable threshold (default: 100 new events since last snapshot). Checked at the end of `compile_cognitive_head()`.
- **On explicit call:** `snapshot_store.save_snapshot()` is public API.
- **Not on every event:** Snapshot I/O would dominate event append latency.

The trigger is implemented inside `compile_cognitive_head()`, after compilation succeeds:

```python
if snapshot is None or (current_sequence - snapshot.sequence) >= SNAPSHOT_THRESHOLD:
    snapshot_store.save_snapshot(Snapshot(
        project_id=project_id,
        sequence=current_sequence,
        head=head,
    ))
```

### 6. Determinism Guarantees

Snapshots preserve determinism because:

1. **Reducers are pure:** `TaskReducer.reduce(events)` depends only on the event list, not external state.
2. **Snapshots capture reducer output:** `CognitiveHead` is the output of four pure reducers applied to events.
3. **Delta replay is equivalent:** Applying reducers to `events[sequence > N]` produces identical state to applying reducers to all events, because reducers are idempotent and commutative with respect to event ordering.

The `compiled_at` timestamp is the only non-deterministic field. It is excluded from snapshot comparison and from determinism checks.

### 7. Version Compatibility

| Scenario | Behavior |
|----------|----------|
| `snapshot.schema_version == current` | Use snapshot, delta replay |
| `snapshot.schema_version != current` | Discard snapshot, full replay |
| `snapshot.head` fails deserialization | Discard snapshot, full replay |
| No snapshot exists | Full replay |
| Snapshot sequence > latest event_sequence | Discard snapshot, full replay |

Version mismatch is the primary mechanism for handling schema evolution. When `CognitiveHead` gains new fields, the schema version increments, and all existing snapshots are automatically invalidated.

### 8. Failure Modes

| Failure | Recovery |
|---------|----------|
| Snapshot load fails (DB error) | Log warning, full replay |
| Snapshot save fails (DB error) | Log warning, continue (next compile will retry) |
| Snapshot corrupt (deserialization fails) | Discard, full replay |
| Snapshot sequence stale | Delta replay covers the gap |
| Concurrent snapshot writes | `UNIQUE` constraint prevents duplicates; last writer wins |

All failures degrade gracefully to full replay. No data loss is possible because the event ledger is immutable.

### 9. Migration Strategy

**No migration required for existing data.** The `relay_snapshots` table is new and additive. Existing projects continue to work via full replay until snapshots are created.

For new deployments:
1. Add `relay_snapshots` table DDL to `migrations/0003_snapshots.sql`.
2. Update `SnapshotStore` implementations (SQLite, PostgreSQL) to use the new table.
3. Update `compile_cognitive_head()` to use snapshot-assisted replay.

---

## Consequences

### Positive

- **O(delta) replay:** After the first snapshot, `compile_cognitive_head()` only replays new events, not the entire ledger.
- **Graceful degradation:** Any snapshot failure falls back to full replay. No correctness risk.
- **Determinism preserved:** Snapshots are pure projections of reducer output. Same events always produce same state.
- **Schema evolution safe:** Version mismatch automatically invalidates stale snapshots.
- **No API changes:** `compile_cognitive_head()` signature unchanged. Callers are unaffected.

### Negative

- **Storage overhead:** One JSON blob per project. At typical CognitiveHead sizes (~2KB JSON), this is negligible.
- **Snapshot I/O:** Save operation adds a write after compilation. Mitigated by threshold-based triggering (not every compile).
- **Complexity:** New table, new save/load logic, new delta replay path. This is the minimum complexity required to solve the O(N) problem.

### Risks

- **Snapshot staleness:** If the snapshot threshold is too high, snapshots may be rare and delta replay still large. The default (100 events) is conservative; tune based on telemetry.
- **Schema version drift:** If `CognitiveHead` changes without incrementing `schema_version`, stale snapshots could produce incorrect state. This is mitigated by including `schema_version` in the `CognitiveHead` dataclass.

---

## Alternatives Considered

### Alternative 1: In-Memory Cache

Cache the compiled `CognitiveHead` in memory after first compilation.

**Rejected because:** In-memory cache doesn't survive process restarts. Snapshots must be durable to survive CLI restarts, MCP server restarts, and agent session switches. In-memory cache is an optimization for a single process; snapshots solve the problem across processes.

### Alternative 2: Incremental Reducer State

Store partial reducer state (e.g., current task map) and apply only new events to it.

**Rejected because:** This requires each reducer to expose its internal state for serialization and to implement an `apply_delta()` method. It couples reducers to the snapshot system and violates the principle that reducers are pure functions of `list[EventRecord]`. Snapshots capture the *output* of reducers, not their internals.

### Alternative 3: Event Counting Only

Track event count and skip replay if count hasn't changed.

**Rejected because:** This doesn't work for delta replay — we still need to apply new events. It only avoids replay when nothing has changed, which is already fast.

---

## Freeze Level Impact

- **L2 (Projection Layer):** `compile_cognitive_head()` gains snapshot-assisted replay. The function signature is unchanged. Callers are unaffected.
- **L1 (Event Store):** No changes. Snapshots are a read-side optimization.
- **L3 (Schema):** New table `relay_snapshots` is additive. No existing tables are modified.

---

## Architectural Freeze (v1.4.0)

The following replay subsystem contracts are **frozen** unless superseded by a new ADR:

| Contract | Scope |
|----------|-------|
| Event replay semantics | Reducers are pure functions of `list[EventRecord]` |
| `ReplayEngine` contract | Owns all replay strategy; exclusive supplier of `initial_state` |
| `SnapshotManager` API | load, save, refresh, delete, validate |
| Snapshot payload versioning | `schema_version` field with automatic invalidation |
| Reducer incremental invariant | `reduce(A+B) == reduce(B, initial_state=reduce(A))` |
| `ReplayReport` schema | mode, events_replayed, events_reused, snapshot status |

Future changes to these contracts require a new ADR with explicit justification.

---

## Validation

| Claim | Status | Evidence |
|-------|--------|----------|
| Replay equivalence | Verified | 44 tests in `tests/equivalence/test_replay_equivalence.py` — reducer invariants, random streams, cumulative drift |
| Backend parity | Verified | Snapshot tests run on both SQLite and PostgreSQL via `backend_parity` CI job |
| Determinism | Verified | `TestSnapshotDeterminism` — same events produce identical snapshot bytes and hash |
| Benchmarks | Verified | `benchmarks/snapshot_benchmark.py` — 43–95% improvement across 100–10,000 events |
| CI coverage | Verified | `replay_equivalence` and `snapshot` markers; PostgreSQL full-suite CI |

---

## References

- [cognitive_head/snapshot.py](../rationalevault/cognitive_head/snapshot.py) — V1 placeholder interface
- [cognitive_head/compiler.py](../rationalevault/cognitive_head/compiler.py) — `compile_cognitive_head()`
- [ADR-024: Replay Infrastructure](ADR-024-replay-infrastructure.md) — Schema-versioned replay
- [migrations/0001_initial.sql](../migrations/0001_initial.sql) — Existing `relay_events` table
