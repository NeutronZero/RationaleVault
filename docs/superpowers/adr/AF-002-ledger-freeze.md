# Architecture Freeze AF-002

## Component
Reference Kernel — Section 1: Ledger

## Status
**Frozen**

## Depends On
AF-001 (Canonical Representation Layer)

## Provides
- Append Contract
- Replay Input Contract
- Commit Model

## Verification
- Replay compliance scenarios RC-01 through RC-08 specified
- Commit model finalized
- Constitutional traceability matrix complete
- Ledger API stabilized
- Explicit non-guarantees recorded
- Decisions log captures all design rationale

## Constitutional Invariants
I-02, I-02a (Append-Only / Never Mutates), I-03 (Stream Ordering), I-04 (Commit Atomicity), I-05 (Idempotent Append), I-06 (Commit Order Preservation), I-11 (Replay Completeness)

## Change Policy
Changes to the Ledger logical model (Commit semantics, ordering guarantees, append contract, stream semantics, or constitutional invariants) require a Constitutional ADR. Implementation improvements — storage backends, indexing, performance, batching — do not require reopening AF-002.

## Specification
`docs/superpowers/specs/2026-07-14-reference-kernel-section1-ledger.md`
