# SnapshotStore V2 — Revised Implementation Plan

## Architectural Invariant (Non-Negotiable)

**There is only one reducer execution model.**

Reducers accept `list[EventRecord]` and return state. Snapshot replay uses the same reducers with the same logic — only the starting state differs.

```
Full replay:    reduce([], initial_state=None)   → empty state
Snapshot replay: reduce(delta_events, initial_state=snapshot_state) → updated state
```

If implementing SnapshotStore requires introducing a second execution model (e.g., `apply_event_to_head()`), **stop and propose a design revision instead**.

---

## Revised PR Sequence

### PR 1: Schema, Dataclasses, Interface

**Files:**
- `migrations/0003_snapshots.sql` ✅ (done)
- `rationalevault/cognitive_head/snapshot_payload.py` — base + cognitive head payload
- `rationalevault/cognitive_head/snapshot.py` — updated interface
- `rationalevault/db/sqlite_store.py` — placeholder snapshot methods
- `rationalevault/db/postgres_store.py` — placeholder snapshot methods

### PR 2: Load & Validation

**Files:**
- `rationalevault/db/sqlite_store.py` — `load_latest_snapshot()`
- `rationalevault/db/postgres_store.py` — `load_latest_snapshot()`
- `rationalevault/cognitive_head/snapshot.py` — validation logic

### PR 3: Save & Policy

**Files:**
- `rationalevault/cognitive_head/snapshot_policy.py` — `SnapshotPolicy`
- `rationalevault/db/sqlite_store.py` — `save_snapshot()`
- `rationalevault/db/postgres_store.py` — `save_snapshot()`
- `rationalevault/cognitive_head/compiler.py` — save trigger

### PR 4: Delta Replay & Telemetry

**Files:**
- `rationalevault/cognitive_head/reducers.py` — add `initial_state` parameter
- `rationalevault/cognitive_head/compiler.py` — snapshot-assisted replay
- `rationalevault/telemetry/metrics.py` — 10 snapshot metrics

---

## PR 4 Detail: Single Reducer Execution Model

### Refactor reducers to accept optional initial state

```python
class TaskReducer:
    @staticmethod
    def reduce(
        events: list[EventRecord],
        initial_state: Optional[dict[str, TaskState]] = None,
    ) -> dict[str, TaskState]:
        tasks: dict[str, TaskState] = initial_state if initial_state is not None else {}
        for event in events:
            # ... existing fold logic (unchanged)
        return tasks
```

Same pattern for `DecisionReducer`, `QuestionReducer`, `ProjectReducer`.

### compiler.py: snapshot-assisted replay

```python
def compile_cognitive_head(project_id, store=None, snapshot_store=None):
    # 1. Try load snapshot
    snapshot = snapshot_store.load_latest(project_id, "cognitive_head") if snapshot_store else None

    # 2. Get events
    if snapshot:
        events = store.get_project_stream(project_id, since_sequence=snapshot.sequence)
    else:
        events = store.get_project_stream(project_id)

    # 3. Run reducers (same execution model, same logic)
    if snapshot:
        project_state = ProjectReducer.reduce(events, initial_state=snapshot.project_state)
        tasks = TaskReducer.reduce(events, initial_state=snapshot.tasks)
        decisions = DecisionReducer.reduce(events, initial_state=snapshot.decisions)
        questions = QuestionReducer.reduce(events, initial_state=snapshot.questions)
    else:
        project_state = ProjectReducer.reduce(events)
        tasks = TaskReducer.reduce(events)
        decisions = DecisionReducer.reduce(events)
        questions = QuestionReducer.reduce(events)

    # 4. Derive active state (same as before)
    # 5. Save snapshot if policy says so
    # 6. Return CognitiveHead
```

**No `apply_event_to_head()`. No second execution model. Same reducers, same logic.**

---

## Telemetry Metrics (10 total)

| Metric | Type | Description |
|--------|------|-------------|
| `snapshot_used` | bool | Whether snapshot was loaded |
| `snapshot_valid` | bool | Whether snapshot passed validation |
| `snapshot_load_ms` | float | Time to load and deserialize snapshot |
| `snapshot_save_ms` | float | Time to serialize and persist snapshot |
| `snapshot_validation_ms` | float | Time to validate snapshot hash/versions |
| `delta_events` | int | Number of events in delta (0 if snapshot is current) |
| `total_events_replayed` | int | Total events processed (delta or full) |
| `full_replay` | bool | Whether full replay was used |
| `compile_duration_ms` | float | Total compilation time |
| `snapshot_schema_mismatch` | bool | Whether schema version mismatch caused fallback |

---

## Benchmarks (Mandatory Before Merge)

| Events | Full Replay | Snapshot Replay | Speedup |
|--------|-------------|-----------------|---------|
| 100 | ? ms | ? ms | ?× |
| 1,000 | ? ms | ? ms | ?× |
| 5,000 | ? ms | ? ms | ?× |
| 10,000 | ? ms | ? ms | ?× |

---

## Acceptance Criteria (Revised)

1. `compile_cognitive_head()` returns **observationally equivalent** `CognitiveHead` with snapshots as without.
2. Snapshot-assisted replay is **observationally equivalent** to full replay for every existing regression test.
3. After N new events (default 100), a snapshot is saved.
4. A subsequent compile replays only delta events and uses the snapshot.
5. If snapshot is corrupt, fallback to full replay with a warning.
6. Telemetry metrics appear in the `retrieval-dashboard`.
7. All 1,771 tests pass.
8. **Benchmark table published** showing speedup at 100/1000/5000/10000 events.
