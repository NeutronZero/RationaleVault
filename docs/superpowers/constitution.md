# RationaleVault Architecture Constitution

**Version:** 1.0
**Status:** Ratified
**Date:** July 15, 2026

---

## 1. Layer Architecture

```
Experience (raw)
    │
    ▼
AF-001  Canonical Representation
    │    Events are captured in a deterministic, portable, content-addressed format.
    │
    ▼
AF-002  Ledger
    │    Events are durably committed in append-only streams with total ordering.
    │
    ▼
AF-003  Replay Engine
    │    Events are replayed through projection reducers to reconstruct Understanding.
    │
    ▼
Understanding (composite state)
    │
    ▼
AF-004  Projection Runtime  [future]
    │    Understanding is organized, versioned, registered, and scheduled.
    │
    ▼
AF-005  Context Runtime  [future]
    │    Understanding is curated into actionable context.
    │
    ▼
AF-006  Reasoning Runtime  [future]
    │    Context drives autonomous reasoning and decision-making.
```

## 2. Dependency Graph

```
AF-001 (self-contained)
    ↑
AF-002 (depends on AF-001)
    ↑
AF-003 (depends on AF-002)
    ↑
AF-004 (depends on AF-003)
    ↑
AF-005 (depends on AF-004)
    ↑
AF-006 (depends on AF-005)
```

Each layer depends only on the layer immediately below it. There are no skip dependencies.

## 3. Constitutional Articles

| Article | Title | Status | Document |
|---------|-------|--------|----------|
| AF-001 | Canonical Representation | Frozen | `specs/2026-07-13-canonical-representation-layer.md` |
| AF-002 | Ledger | Frozen | `specs/2026-07-14-reference-kernel-section1-ledger.md` |
| AF-003 | Replay Engine | Frozen | `specs/2026-07-14-reference-kernel-section2-replay.md` |
| AF-004 | Projection Runtime | Planned | — |
| AF-005 | Context Runtime | Planned | — |
| AF-006 | Reasoning Runtime | Planned | — |

### 3.1 How Constitutional Articles Work

Each AF article is a **frozen specification** that defines:
- The constitutional contract (interface, behavior, invariants)
- The reference implementation (correctness, not performance)
- Compliance vectors (language-independent scenario descriptions)

An article is **ratified** when its specification, implementation, compliance suite, and invariant tests all pass and are frozen. Once frozen, an article's contract cannot be changed without a new AF version.

## 4. Invariant Index

| Invariant | Owner | Description |
|-----------|-------|-------------|
| I-00 | AF-001 | Canonical representation determinism — semantically equivalent objects produce identical canonical bytes |
| I-00a | AF-001 | Unicode NFC normalization — canonically equivalent strings produce identical representations |
| I-01 | AF-003 | Replay determinism — same Ledger + same Projections → same Understanding |
| I-01a | AF-003 | Replay completeness — every event in scope is presented to every registered Reducer |
| I-02 | AF-002 | Ledger never mutates history — committed data is immutable |
| I-02a | AF-002 | Ledger has no delete or update operations |
| I-03 | AF-002 | Stream ordering is deterministic — sequence numbers are monotonic and gap-free |
| I-04 | AF-002 | Commit atomicity — a Commit's events are all persisted or none are |
| I-05 | AF-002 | Idempotent append — same commit_id returns identical receipt without duplication |
| I-06 | AF-002 | Commit order preservation — events are readable in the order they were committed |
| I-07 | AF-003 | Replay equivalence — Full ≡ Delta ≡ Fast Path produce identical Understanding |
| I-08 | AF-001/AF-003 | Referential transparency — identifiers are content-hash deterministic |
| I-09 | AF-003 | Projection monotonicity — projections are composable and isolated |
| I-10 | AF-003 | Schema evolution — historical events with older schemas replay successfully |
| I-11 | AF-002/AF-003 | Ledger/replay completeness — all committed events are presented during replay |
| I-12 | AF-003 | Reducer purity — reducers MUST NOT mutate inputs or have side effects |

## 5. Compliance Suites

| Suite | Vectors | Coverage |
|-------|---------|----------|
| RVCJ (Canonical) | key_ordering, unicode_normalization, timestamps, payloads, deep_nesting | I-00, I-00a, I-08 |
| Ledger RC-01..RC-08 | empty stream, single event, multiple ordered, single/multi commit, snapshot replay, multiple streams, idempotent append | I-02 through I-06, I-11 |
| Replay RP-01..RP-09 | empty ledger, single event, snapshot equivalence, multi-event commit, multiple streams, fast path, idempotent replay, schema evolution, interrupted replay | I-01, I-01a, I-07, I-10, I-11, I-12 |

## 6. Architecture Decision Records

ADRs document the design decisions that produced this constitution.

```
Constitution  (this document — normative entry point)
    ↑
ADRs          (design decisions — explanatory)
    ↑
Specifications (detailed contracts — per AF article)
    ↑
Implementations (executable code)
```

### Key ADRs

| ADR | Title |
|-----|-------|
| AF-001-freeze | Canonical Representation — ratification record |
| AF-002-freeze | Ledger — ratification record |
| AF-003-freeze | Replay Engine — ratification record |

Full list: `docs/superpowers/adr/`

## 7. Reference Implementations

| Layer | Module | Backend |
|-------|--------|---------|
| AF-001 | `rationalevault/canonical/` | Pure functions |
| AF-002 | `rationalevault/ledger/` | `MemoryLedger`, `SQLiteLedger` |
| AF-003 | `rationalevault/replay/` | `DefaultReplayer` |

All reference implementations prioritize correctness and readability over performance.

## 8. Implementation Status

| Component | Tests | Status |
|-----------|-------|--------|
| AF-001 Canonical Representation | 79 passing | ✅ Frozen |
| AF-002 Ledger | 93 passing | ✅ Frozen |
| AF-003 Replay Engine | 129 passing, 2 skipped | ✅ Frozen |
| **Deterministic Cognitive Kernel** | **301 passing, 2 skipped** | **✅ Validated** |

## 9. Architecture Timeline

```
AC1 — Deterministic Cognitive Kernel
├── AF-001  Canonical Representation    [Jul 13, 2026]  ✓
├── AF-002  Ledger                      [Jul 14, 2026]  ✓
├── AF-003  Replay Engine               [Jul 14, 2026]  ✓
├── Kernel Validated                    [Jul 15, 2026]  ✓
│
├── (future)
│   ├── AF-004  Projection Runtime
│   ├── AF-005  Context Runtime
│   └── AF-006  Reasoning Runtime
```

## 10. Governance

- Constitutional articles (AF-NNN) are frozen by ratification.
- Once frozen, an article's contract may only be amended by publishing a new AF version with a supersedes clause.
- Compliance vectors are part of the specification and must pass before ratification.
- Invariants are cross-cutting — they may span multiple AF articles.
- The reference implementation is authoritative for behavioral questions.
