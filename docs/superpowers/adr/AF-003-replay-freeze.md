# AF-003: Replay Engine Specification

**Status:** Frozen

**Date:** July 14, 2026

**Version:** 1.0

**Depends On:** AF-001 (Canonical Representation), AF-002 (Ledger)

**Provides:** Deterministic Replay Contract, Understanding Reconstruction, Snapshot Equivalence

---

## Specification Document

The normative specification is located at:
`docs/superpowers/specs/2026-07-14-reference-kernel-section2-replay.md`

---

## Constitutional Scope

This freeze establishes:

- The Replay Engine as the deterministic reconstructor of Understanding from the Ledger
- The formal Replay model: `replay(L, P) = U`
- The Replay Boundary as a first-class concept
- Reducer Purity (I-12) as the foundational invariant
- Replay Equivalence (I-07) as the correctness criterion
- The constitutional boundary between Replay and Runtime

---

## Invariants Enforced

| ID | Invariant |
|----|-----------|
| I-01 | Replay Determinism |
| I-01a | Replay Completeness |
| I-07 | Replay Equivalence |
| I-08 | Referential Transparency |
| I-09 | Projection Monotonicity |
| I-11 | Ledger Completeness |
| I-12 | Reducer Purity |

---

## Compliance Vectors

| ID | Name | File |
|----|------|------|
| RP-01 | Empty Ledger | `spec/vectors/replay/rp-01-empty-ledger.json` |
| RP-02 | Single Event | `spec/vectors/replay/rp-02-single-event.json` |
| RP-03 | Snapshot Equivalence | `spec/vectors/replay/rp-03-snapshot-equivalence.json` |
| RP-04 | Multi-Event Commit | `spec/vectors/replay/rp-04-multi-event-commit.json` |
| RP-05 | Multiple Streams | `spec/vectors/replay/rp-05-multiple-streams.json` |
| RP-06 | Fast Path | `spec/vectors/replay/rp-06-fast-path.json` |
| RP-07 | Idempotent Replay | `spec/vectors/replay/rp-07-idempotent-replay.json` |
| RP-08 | Schema Evolution | `spec/vectors/replay/rp-08-schema-evolution.json` |
| RP-09 | Interrupted Replay | `spec/vectors/replay/rp-09-interrupted-replay.json` |

---

## Freeze Criteria Validation

- [x] Replay model formally defined
- [x] Replay Boundary as formal concept
- [x] Replay Scope (Global/Stream) defined
- [x] Replay Modes defined
- [x] ReplayResult includes Understanding + Report + Replay Position
- [x] Reducer contract (I-12) defined
- [x] Snapshot contract defined
- [x] Equivalence (I-07) formalized
- [x] Replay compliance scenarios (RP-01..RP-09) specified
- [x] Constitutional traceability matrix complete
- [x] Explicit non-guarantees recorded
- [x] Decisions log captures design rationale
- [x] Existing ADRs mapped
- [x] Freeze criteria documented

---

## Ratification

**AF-003 is ratified effective July 14, 2026.**

**Next Phase:** Implementation Plan for Phase 1B.2 (Replay Engine Reference)
