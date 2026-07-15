# Architecture Candidate 1 — Validation Report

**Date:** July 15, 2026
**Status:** Validated
**Milestone:** M1 — Deterministic Cognitive Kernel

---

## 1. Executive Summary

AC1 set out to prove that **events can be canonically represented, durably committed, and deterministically reconstructed into composite understanding** — a complete deterministic pipeline from raw experience to structured knowledge.

That objective has been achieved.

The pipeline `Canonical → Ledger → Replay → Understanding` now exists as an executable, specification-governed system backed by 301 passing tests, 3 compliance suites, 12 constitutional invariants, and 2 backend implementations. All foundational contracts (AF-001, AF-002, AF-003) are frozen, independently testable, and implementation-independent.

---

## 2. Constitutional Artifacts

| Artifact | Status | Tests | Evidence |
|----------|--------|-------|----------|
| AF-001 Canonical Representation | Frozen | 79 | `rationalevault/canonical/` |
| AF-002 Ledger (Memory + SQLite) | Frozen | 93 | `rationalevault/ledger/` |
| AF-003 Replay Engine | Frozen | 129 | `rationalevault/replay/` |
| **Total** | **Validated** | **301** | |

### 2.1 AF-001 — Canonical Representation

Specification: `docs/superpowers/specs/2026-07-13-canonical-representation-layer.md`

- EventType StrEnum (immutable)
- CanonicalTimestamp (RFC 3339, UTC, microsecond precision)
- CanonicalPayload (schema-versioned data wrapper)
- CanonicalEnvelope (three-layer event structure)
- CanonicalSerializer (single serialization path)
- StableIdGenerator (content-hash-based identifiers)
- Compliance vectors (RVCJ key ordering, normalization, timestamps, payloads, deep nesting)

### 2.2 AF-002 — Ledger

Specification: `docs/superpowers/specs/2026-07-14-reference-kernel-section1-ledger.md`

- Commit, CommitBuilder, CommitReceipt value objects
- Ledger ABC (append, read_stream, read_from, exists, stream_exists)
- MemoryLedger (reference implementation)
- SQLiteLedger (persistent backend)
- Compliance vectors RC-01 through RC-08
- Backend behavioral equivalence validation

### 2.3 AF-003 — Replay Engine

Specification: `docs/superpowers/specs/2026-07-14-reference-kernel-section2-replay.md`

- ReplayBoundary, ReplayScope, ReplayMode value objects
- Understanding (primary domain output)
- ReplayReport, ReplayResult (transport packaging)
- ReplayEngine ABC (replay, replay_to, replay_stream)
- DefaultReplayer (reference implementation)
- ProjectionIdentity, ProjectionRegistry (ordered registration)
- Reducer protocol, purity enforcement (I-12)
- Compliance vectors RP-01 through RP-09

---

## 3. Invariants

| Invariant | Layer | Specification | Test Evidence |
|-----------|-------|--------------|---------------|
| I-00 | AF-001 | Canonical representation determinism | `canonical/tests/test_invariants.py` |
| I-00a | AF-001 | Unicode NFC normalization | `canonical/tests/test_invariants.py` |
| I-01 | AF-003 | Replay determinism | `replay/tests/test_invariants.py::TestI01ReplayDeterminism` |
| I-01a | AF-003 | Replay completeness | `replay/tests/test_invariants.py::TestI01aReplayCompleteness` |
| I-02 | AF-002 | Ledger never mutates history | `ledger/tests/test_invariants.py::test_i02_never_mutates_history` |
| I-02a | AF-002 | Ledger has no delete/update | `ledger/tests/test_invariants.py::test_i02a_ledger_has_no_delete_method` |
| I-03 | AF-002 | Stream ordering deterministic | `ledger/tests/test_invariants.py::test_i03_stream_ordering_deterministic` |
| I-04 | AF-002 | Commit atomicity | `ledger/tests/test_invariants.py::test_i04_commit_atomicity_*` |
| I-05 | AF-002 | Idempotent append | `ledger/tests/test_invariants.py::test_i05_idempotent_append_*` |
| I-06 | AF-002 | Commit order preservation | `ledger/tests/test_invariants.py::test_i06_commit_order_preservation` |
| I-07 | AF-003 | Replay equivalence (Full≡Delta≡FastPath) | Infrastructure-dependent — deferred |
| I-08 | AF-001/AF-003 | Referential transparency (canonical IDs) | `canonical/tests/test_invariants.py::test_i08_referential_transparency` |
| I-09 | AF-003 | Projection monotonicity | `replay/tests/test_invariants.py::TestI09ProjectionMonotonicity` |
| I-10 | AF-003 | Schema evolution | RP-08 compliance vector |
| I-11 | AF-002/AF-003 | Ledger completeness / replay completeness | `ledger/tests/test_invariants.py::test_i11_*`, `replay/tests/test_invariants.py::TestI11LedgerCompleteness` |
| I-12 | AF-003 | Reducer purity | `replay/tests/test_invariants.py::TestI12ReducerPurity` |

---

## 4. Compliance Suites

### 4.1 RVCJ Compliance (Canonical)

- Location: `spec/vectors/canonical/`
- Vectors: key_ordering, unicode_normalization, timestamps, payloads, deep_nesting
- Validator: `rationalevault/canonical/compliance/validator.py`

### 4.2 Ledger Compliance RC-01..RC-08

- Location: `spec/vectors/ledger/rc-*.json`
- Scenarios: empty stream, single event, multiple ordered events, single/multi-event commits, snapshot replay, multiple streams, idempotent append
- Validator: `rationalevault/ledger/compliance/validator.py`
- Tested against: MemoryLedger, SQLiteLedger

### 4.3 Replay Compliance RP-01..RP-09

- Location: `spec/vectors/replay/rp-*.json`
- Scenarios: empty ledger, single event, snapshot equivalence, multi-event commit, multiple streams, fast path, idempotent replay, schema evolution, interrupted replay
- Validator: `rationalevault/replay/compliance/validator.py`
- RP-03 (delta) and RP-06 (fast path) skipped — require snapshot infrastructure

---

## 5. Reference Implementations

| Layer | Implementation | Lines | Backends |
|-------|---------------|-------|----------|
| Canonical | `rationalevault/canonical/` | ~500 | N/A (pure) |
| Ledger | `rationalevault/ledger/` | ~700 | Memory + SQLite |
| Replay | `rationalevault/replay/` | ~600 | DefaultReplayer |

---

## 6. Test Evidence

| Subsystem | Tests | Key Files |
|-----------|-------|-----------|
| Canonical value objects | 30 | `test_types.py`, `test_timestamp.py`, `test_payload.py` |
| Canonical envelope | 10 | `test_envelope.py` |
| Canonical serializer | 8 | `test_serializer.py` |
| Canonical stable IDs | 8 | `test_id_generator.py` |
| Canonical compliance | 6 | `test_compliance.py` |
| Canonical invariants | 3 | `test_invariants.py` |
| Canonical roundtrip | 6 | `test_roundtrip.py` |
| Canonical public API | 8 | `test_public_api.py` |
| **AF-001 total** | **79** | |
| Ledger commit value objects | 11 | `test_commit.py` |
| Ledger interface (ABC + backends) | 46 | `test_interface.py`, `test_memory_ledger.py`, `test_sqlite_ledger.py` |
| Ledger compliance | 16 | `test_compliance.py` |
| Ledger invariants | 13 | `test_invariants.py` |
| Ledger backend equivalence | 7 | `test_backend_equivalence.py` |
| **AF-002 total** | **93** | |
| Replay value objects | 30 | `test_types.py` |
| Replay interface (ABC) | 5 | `test_interface.py` |
| Projection registry | 10 | `test_registry.py` |
| DefaultReplayer contract | 34 | `test_default_replayer.py` |
| Reducer protocol & purity | 23 | `test_reducer.py` |
| Compliance vectors | 10 | `test_compliance.py` |
| Invariant tests | 27 | `test_invariants.py` |
| **AF-003 total** | **129** | |
| **Grand total** | **301** | |

---

## 7. Deferred Work

The following items are explicitly deferred to preserve architectural discipline — correctness before optimization.

| Deferred Item | Rationale | Depends On |
|---------------|-----------|------------|
| SnapshotManager | Replay correctness is proven without snapshots | Need snapshot policy |
| Delta replay strategy | Only meaningful with SnapshotManager | SnapshotManager |
| Fast-path replay engine | Optimization over delta — premature before snapshots | Delta replay |
| ReplayPlanner | Internal routing — no value until 2+ strategies exist | Delta + FastPath |

The architecture proves `Correctness → Optimization`. All four items can be added later without revisiting the constitutional model.

---

## 8. Validation Statement

> **Architecture Candidate 1 is validated.**

The deterministic cognitive kernel `Canonical → Ledger → Replay → Understanding` has been specified, implemented, compliance-tested, and invariant-verified across two backend implementations with 301 passing tests and zero regressions.

Future constitutional layers (AF-004 Projection Runtime onward) proceed from a validated kernel.
