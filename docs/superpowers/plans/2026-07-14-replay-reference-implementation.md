# Phase 1B.2: Replay Engine Reference Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the Replay Engine: Understanding reconstruction, Reducer contract, Snapshot management, and ReplayMode equivalence, following the ratified AF-003 specification.

**Architecture:** Specification-first development. RP compliance vectors are written before the implementation. Full/delta/fast-path equivalence demonstrated against both Ledger backends.

**Tech Stack:** Python 3.12+, Canonical Layer (AF-001), Ledger (AF-002), pytest

## Global Constraints

- Python >=3.12
- No external dependencies for core replay module (stdlib only)
- TDD: write failing test first, then implement
- Milestone-based commits (not per-task)
- Correctness over throughput — no caching, batching, or optimization
- No LLM calls, network I/O, or filesystem access in reducers (per I-12)
- Replay Engine consumes Ledger only — no direct database access

## File Structure

```
rationalevault/replay/
├── __init__.py                  # Public API exports
├── types.py                     # ReplayScope, ReplayMode, ReplayResult, Understanding
├── projection.py                # Projection identity, ProjectionSet
├── interface.py                 # ReplayEngine ABC
├── reducer.py                   # Reducer base class / protocol
├── snapshot.py                  # Snapshot, SnapshotManager
├── engine/
│   ├── __init__.py
│   ├── full.py                   # Full replay strategy
│   ├── delta.py                  # Delta replay strategy
│   ├── fast_path.py              # Fast path replay strategy
│   └── planner.py                # ReplayPlanner (internal)
├── compliance/
│   ├── __init__.py
│   ├── vectors.py                # Loads vectors from spec/vectors/replay/
│   └── validator.py              # Compliance validation
└── tests/
    ├── __init__.py
    ├── test_types.py             # ReplayScope, ReplayMode, ReplayResult, Understanding
    ├── test_reducer.py           # Reducer contract, I-12
    ├── test_full_replay.py       # Full replay strategy
    ├── test_delta_replay.py      # Delta replay strategy
    ├── test_snapshot.py          # SnapshotManager, equivalence
    ├── test_compliance.py        # RP-01 through RP-09
    └── test_invariants.py        # I-01..I-12 replay-specific invariants

spec/vectors/replay/              # Compliance vectors (RP-01..RP-09)
├── rp-01-empty-ledger.json
├── rp-02-single-event.json
├── rp-03-snapshot-equivalence.json
├── rp-04-multi-event-commit.json
├── rp-05-multiple-streams.json
├── rp-06-fast-path.json
├── rp-07-idempotent-replay.json
├── rp-08-schema-evolution.json
└── rp-09-interrupted-replay.json
```

## Commit Strategy

Milestone-based commits:

| Milestone | Tasks | Commit Message |
|-----------|-------|----------------|
| Types | 1 | `feat(replay): add ReplayScope, ReplayMode, ReplayResult, Understanding` |
| Projection | 2 | `feat(replay): add Projection identity and ProjectionSet` |
| Reducer | 3 | `feat(replay): add Reducer protocol and laws` |
| Engine Interface | 4 | `feat(replay): add ReplayEngine ABC` |
| Full Replay | 5 | `feat(replay): implement full replay strategy` |
| Delta Replay | 6 | `feat(replay): implement delta replay strategy` |
| Snapshot Manager | 7 | `feat(replay): implement SnapshotManager with equivalence validation` |
| Fast Path & Planner | 8 | `feat(replay): implement fast path and replay planner` |
| Compliance | 9 | `test(replay): add compliance vectors RP-01 through RP-09` |
| Invariants | 10 | `test(replay): add invariant tests I-01..I-12` |
| Validation | 11 | `test(replay): verify full test suite passes` |

---

## Task 1: Value Objects (ReplayScope, ReplayMode, ReplayResult, Understanding)

**Files:**
- Create: `rationalevault/replay/__init__.py`
- Create: `rationalevault/replay/types.py`
- Create: `rationalevault/replay/tests/__init__.py`
- Create: `rationalevault/replay/tests/test_types.py`

**Interfaces:**
- `ReplayScope` — "global" or "stream" with optional `stream_id`
- `ReplayMode` — "auto", "full", "delta", "fast_path"
- `ReplayResult` — `(understanding, report, version, replay_position)`
- `Understanding` — `(projections: dict, boundary: int)`
- `ReplayReport` — `(mode, events_processed, snapshot_used, replay_position, version)`
- All dataclasses MUST be `frozen=True`

**Test coverage:**
- ReplayScope defaults to "global"
- ReplayMode defaults to "auto"
- Understanding stores projections dict and boundary
- ReplayResult packages Understanding with report
- All types are immutable
- Understanding equality is structural

- [ ] **Step 1: Read the existing Ledger commit.py for value object patterns**
- [ ] **Step 2: Write the failing test** (ImportError for types module)
- [ ] **Step 3: Run test to verify it fails**
- [ ] **Step 4: Implement value objects in types.py**
- [ ] **Step 5: Run test to verify it passes**
- [ ] **Step 6: Commit**

---

## Task 2: Projection Identity and ProjectionSet

**Files:**
- Create: `rationalevault/replay/projection.py`

**Interfaces:**
- `Projection` — `(projection_id, version, reducer: Callable)`
- `ProjectionSet` — ordered collection of Projections
- Registration preserves insertion order

**Test coverage:**
- Projection stores id, version, reducer
- ProjectionSet maintains deterministic iteration order
- Registration by projection_id
- Duplicate registration raises error
- Empty ProjectionSet is valid

- [ ] **Step 1: Read AF-003 Section 4.0 (Projection Identity)**
- [ ] **Step 2: Write the failing test**
- [ ] **Step 3: Run test to verify it fails**
- [ ] **Step 4: Implement Projection and ProjectionSet**
- [ ] **Step 5: Run test to verify it passes**
- [ ] **Step 6: Commit**

---

## Task 3: Reducer Protocol

**Files:**
- Create: `rationalevault/replay/reducer.py`
- Create: `rationalevault/replay/errors.py`
- Create: `rationalevault/replay/tests/test_reducer.py`

**Interfaces:**
- `Reducer` protocol/ABC — `reduce(event: CanonicalEnvelope, state: Any) -> Any`
- `ReducerError` for violations
- Helpers for testing Reducer purity (I-12)

**Test coverage:**
- Reducer is callable with event and state
- Determinism: same (event, state) → same result
- Purity: reducer has no observable side effects (check via mock)
- Unknown events are silently ignored
- Forward compatibility: unknown event types do not crash

- [ ] **Step 1: Write the failing test** (ImportError for reducer)
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Implement Reducer protocol**
- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Commit**

---

## Task 4: ReplayEngine ABC

**Files:**
- Create: `rationalevault/replay/interface.py`

**Interfaces:**
- `ReplayEngine(ABC)` — `replay(ledger, scope, mode, snapshot) -> ReplayResult`
- `load_snapshot(projection_id) -> Snapshot | None`
- `save_snapshot(projection_id, snapshot) -> None`

**Test coverage:**
- ReplayEngine is abstract (cannot instantiate)
- replay() is abstract
- load_snapshot() is abstract
- save_snapshot() is abstract

- [ ] **Step 1: Write the failing test**
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Implement abstract base class**
- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Commit**

---

## Task 5: Full Replay Strategy

**Files:**
- Create: `rationalevault/replay/engine/__init__.py`
- Create: `rationalevault/replay/engine/full.py`
- Create: `rationalevault/replay/engine/test_full_replay.py`

**Interfaces:**
- `FullReplayEngine(ReplayEngine)` — replays all events from Ledger
- Uses `read_from(0)` for global scope
- Applies each event to all Projections in registered order
- Produces Understanding at the end of the Ledger

**Test coverage:**
- Empty Ledger → empty Understanding
- Single Event → Understanding with one event processed
- Multiple Events → processed in global_order
- Multiple Projections → each receives all events
- Stream scope → only events from that stream
- Deterministic: same result on repeated calls

- [ ] **Step 1: Write the failing test**
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Implement FullReplayEngine**
- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Commit**

---

## Task 6: Delta Replay Strategy

**Files:**
- Create: `rationalevault/replay/engine/delta.py`
- Create: `rationalevault/replay/engine/test_delta_replay.py`

**Interfaces:**
- `DeltaReplayEngine(ReplayEngine)` — replays from a Snapshot
- Loads Snapshot state as initial Projection state
- Applies events after the Snapshot's `replay_position`
- Returns Understanding at target position

**Test coverage:**
- Delta replay from valid Snapshot → same Understanding as Full
- Delta replay with position 0 → Full replay (empty snapshot)
- Delta replay rejects invalid Snapshot (schema version mismatch)
- Delta replay rejects Snapshot ahead of Ledger
- Understanding equality across modes

- [ ] **Step 1: Write the failing test**
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Implement DeltaReplayEngine**
- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Commit**

---

## Task 7: SnapshotManager

**Files:**
- Create: `rationalevault/replay/snapshot.py`
- Create: `rationalevault/replay/tests/test_snapshot.py`

**Interfaces:**
- `Snapshot` — `(projection_id, version, state, replay_position, schema_version, dependencies_hash?)`
- `SnapshotManager` — manages creation, loading, validation
- `validate(snapshot, ledger, projections) -> bool` — checks I-07 equivalence
- `invalidate(projection_id)` — marks snapshots stale

**Test coverage:**
- Snapshot stores all fields
- SnapshotManager.save() stores snapshot
- SnapshotManager.load() retrieves by projection_id
- SnapshotManager.load() returns None for unknown projection
- validate() returns True for valid snapshot
- validate() returns False for schema version mismatch
- validate() returns False for position ≠ snapshot content
- EventCountPolicy: snapshot created after N events
- Invalidation triggers fallback to empty load

- [ ] **Step 1: Write the failing test**
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Implement Snapshot and SnapshotManager**
- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Commit**

---

## Task 8: Fast Path and Replay Planner

**Files:**
- Create: `rationalevault/replay/engine/fast_path.py`
- Create: `rationalevault/replay/engine/planner.py`
- Create: `rationalevault/replay/engine/test_planner.py`

**Interfaces:**
- `FastPathReplayEngine(ReplayEngine)` — optimized delta for 99% coverage
- `ReplayPlanner` — internal: selects optimal strategy
  - Snapshot available + valid → Delta
  - Snapshot available + fast path available → Fast Path
  - No snapshot → Full
  - Explicit mode overrides Planner

**Test coverage:**
- Planner selects Full when no snapshot exists
- Planner selects Delta when valid snapshot exists
- Planner selects Fast Path when infrastructure available
- Explicit mode override works
- Planner decisions do NOT affect Understanding (I-07)
- Fast Path produces identical Understanding to Full

- [ ] **Step 1: Write the failing test**
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Implement FastPathReplayEngine and ReplayPlanner**
- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Commit**

---

## Task 9: Compliance Vectors (RP-01 through RP-09)

**Files:**
- Already exist: `spec/vectors/replay/rp-*.json`
- Create: `rationalevault/replay/compliance/__init__.py`
- Create: `rationalevault/replay/compliance/vectors.py`
- Create: `rationalevault/replay/compliance/validator.py`
- Create: `rationalevault/replay/tests/test_compliance.py`

**Interfaces:**
- `load_vectors()` — loads RP JSON from spec/
- `ReplayComplianceValidator` — validates vectors against ReplayEngine

**Test coverage:**
- All 9 vectors load successfully
- Each vector validates against FullReplayEngine
- Understanding matches expected output
- Invariants listed in each vector are satisfied

- [ ] **Step 1: Write the failing test** (ImportError for compliance module)
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Write compliance module (vectors loader)**
- [ ] **Step 4: Write compliance validator**
- [ ] **Step 5: Write parametrized test_rp_01 through test_rp_09**
- [ ] **Step 6: Run test to verify it passes**
- [ ] **Step 7: Commit**

---

## Task 10: Invariant Tests (I-01 through I-12)

**Files:**
- Create: `rationalevault/replay/tests/test_invariants.py`

**Test coverage:**

| Invariant | Test |
|-----------|------|
| I-01 | Replay Determinism — same Ledger + Projections → same Understanding |
| I-01a | Replay Completeness — every event in scope presented to every Reducer |
| I-07 | Replay Equivalence — Full ≡ Delta ≡ Fast Path |
| I-08 | Referential Transparency — deterministic identifiers |
| I-09 | Projection Monotonicity — composable, isolated |
| I-11 | Ledger completeness via Ledger backend |
| I-12 | Reducer Purity — no side effects observable |

- [ ] **Step 1: Write the failing test**
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Implement all invariant tests**
- [ ] **Step 4: Run test to verify it passes (depends on previous tasks)**
- [ ] **Step 5: Commit**

---

## Task 11: Full Test Suite Validation

- [ ] **Step 1: Run all replay value object tests**
- [ ] **Step 2: Run all projection tests**
- [ ] **Step 3: Run all reducer tests**
- [ ] **Step 4: Run all full replay tests**
- [ ] **Step 5: Run all delta replay tests**
- [ ] **Step 6: Run all snapshot tests**
- [ ] **Step 7: Run all fast path / planner tests**
- [ ] **Step 8: Run all compliance tests**
- [ ] **Step 9: Run all invariant tests**
- [ ] **Step 10: Run Full Ledger suite + Replay suite together (no regressions)**
- [ ] **Step 11: Commit final validation**

---

## Success Criteria

| Criterion | Description |
|-----------|-------------|
| ✅ | ReplayScope and ReplayMode are defined as value objects |
| ✅ | Understanding is the primary output of Replay |
| ✅ | ReplayResult packages Understanding with metadata |
| ✅ | Projection identity is defined and registered in order |
| ✅ | Reducer protocol enforces determinism and purity (I-12) |
| ✅ | Full replay produces correct Understanding from any Ledger |
| ✅ | Delta replay from Snapshot ≡ Full replay (I-07) |
| ✅ | SnapshotManager validates equivalence before returning snapshot |
| ✅ | Fast Path replay produces identical Understanding |
| ✅ | Replay Planner selects optimal strategy without affecting output |
| ✅ | All compliance scenarios (RP-01..RP-09) pass |
| ✅ | All constitutional invariants (I-01..I-12) pass |
| ✅ | No regressions in Ledger test suite |
| ✅ | Full test suite passes |
