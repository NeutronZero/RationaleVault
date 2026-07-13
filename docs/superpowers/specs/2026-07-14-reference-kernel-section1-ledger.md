# Reference Kernel — Section 1: Ledger Specification

**Version:** 1.0-rc1
**Date:** July 14, 2026
**Status:** Draft — Not Yet Ratified
**Depends On:** AF-001 (Canonical Representation Layer), RVCJ v1, Canonical Event Envelope
**Provides:** Append Contract, Replay Input Contract, Commit Model

---

## 1. Purpose

The Ledger is the authoritative, append-only logical record of committed experience. It defines persistence semantics independent of any storage implementation. The Ledger is not a database; it is a **logical abstraction** that any conforming storage backend must satisfy.

This specification defines:

- The logical Ledger model
- Stream semantics and ordering guarantees
- The atomic Commit abstraction
- The append and read contract
- Replay compliance scenarios as specification artifacts
- Explicit constitutional traceability
- Freeze criteria for Section 1

---

## 2. Architectural Invariants (Ledger-Specific)

The Ledger is responsible for upholding the following invariants derived from the AC1 Constitution:

| ID | Invariant | Source |
|----|-----------|--------|
| I-02 | Replay Never Mutates History | Article 2 |
| I-02a | Append-Only — no record is ever modified, deleted, or overwritten | Article 2 |
| I-03 | Streams provide deterministic event ordering | Article 3 |
| I-04 | Commit Atomicity — a Commit is either fully visible or not visible at all | Article 2 |
| I-05 | Idempotent Append — identical commits produce exactly one visible record | Article 2 |
| I-06 | Commit Order Preservation — events within a Commit SHALL be replayed in the order defined by the Commit | Article 3 |
| I-11 | Replay Completeness — replay produces every committed event in order | Article 3 |

**These invariants are normative.** Any storage backend claiming Ledger conformance must satisfy all of them.

---

## 3. Domain Model

### 3.1 Stream

> **A stream is the smallest logical boundary within which deterministic event ordering is guaranteed.**

- Streams are identified by a `stream_id` (opaque string, supplied by the caller).
- There is no global ordering across streams.
- Events within a stream are totally ordered by sequence number.
- Streams are created implicitly on first append; no prior registration is required.
- Empty streams have no representation in the Ledger.

### 3.2 Sequence

Each event within a stream is assigned a monotonically increasing, non-negative integer sequence number.

- Sequences start at 1 within each stream.
- Sequence numbers are contiguous: no gaps. Events within a single Commit receive consecutive sequence numbers.
- Sequence numbers are immutable once assigned.
- Sequence ordering within a stream is deterministic and reproducible.

### 3.3 Commit

> **A Commit is the atomic persistence unit of the Ledger.**

- A Commit contains 1..N canonically serialized Events.
- A SHALL contain events belonging to exactly one Experience.
- One Experience SHALL be recorded as exactly one Commit. *(This is a constitutional constraint of AC1, derived from the Experience-Oriented model. It is not a universal property of event-sourced systems.)*
- A Commit is either fully visible or not visible at all (Commit Atomicity, I-04).
- Every Commit carries a `commit_id` — a stable, content-addressed digest derived exclusively from its events.
- The reference implementation may initially support only single-event commits; the model permits multi-event commits.
- Commits are immutable once persisted.

The hierarchy:

```
Experience  (domain concept, canonical envelope)
    │ same Experience → same Commit
    ▼
Commit      (atomic persistence unit, 1..N events)
    │
    ▼
Event       (immutable record within a commit)
```

### 3.4 LedgerEntry

A `LedgerEntry` is the persisted representation of a single event within a Commit. It consists of:

```
LedgerEntry {
    stream_id:       str
    sequence:        int
    commit_id:       str        // content-addressed digest of the containing Commit
    event_id:        str        // stable, content-addressed (from CanonicalEnvelope)
    rvcj_version:    int
    event_schema:    int
    event_type:      str
    timestamp:       str        // RFC 3339 UTC
    payload:         dict
    global_order:    int        // logical total ordering, assigned at persistence time
}
```

---

## 4. Component: The Ledger

The Ledger is defined as an abstract component. The implementation plan will introduce a `LedgerStorage` SPI that decouples the Ledger's logical invariants from any specific storage backend. This document defines only the logical contract.

### 4.1 Interface

```python
class Ledger(ABC):
    @abstractmethod
    def append(self, commit: Commit) -> CommitReceipt:
        """Append a Commit atomically.

        Returns a CommitReceipt containing commit_id and sequence assignments.

        Raises:
            DuplicateCommitError: if commit_id already exists (idempotent replay)
            StreamConflictError:  if sequence gap detected
        """
        ...

    @abstractmethod
    def read_stream(self, stream_id: str) -> list[LedgerEntry]:
        """Read all events in a stream, in sequence order.

        Returns empty list for unknown streams.
        """
        ...

    @abstractmethod
    def read_from(self, global_order: int) -> list[LedgerEntry]:
        """Read all events with global_order >= the given value, in order.

        Used by replay engines for delta/fast-path replay.
        """
        ...

    @abstractmethod
    def exists(self, commit_id: str) -> bool:
        """Return True if a Commit has already been persisted."""
        ...

    @abstractmethod
    def stream_exists(self, stream_id: str) -> bool:
        """Return True if the stream has any committed events."""
        ...
```

### 4.2 Append Semantics

- `append()` is **atomic**: either the entire Commit is persisted, or none of it is.
- `append()` is **idempotent**: calling `append()` with the same `commit_id` returns the same `CommitReceipt` without duplicating events (I-05).
- `append()` assigns sequence numbers contiguously within the target stream.
- `append()` rejects commits that would create sequence gaps.
- `append()` is **ordered**: concurrent appends to the same stream are serialized.

### 4.3 Read Semantics

- `read_stream()` returns events in ascending sequence order.
- `read_from()` returns events in ascending global order.
- Reads observe only fully committed logical commits.
- Reads observe a snapshot of the Ledger at the moment the read begins. Concurrent appends are not visible until after they complete.

---

## 5. The Commit Model

### 5.1 Atomic Write Contract

A Commit satisfies the following contract:

```python
@dataclass(frozen=True)
class Commit:
    commit_id: str          # content-addressed: SHA-256(canonical serialization of events array)
    stream_id: str
    events: list[CanonicalEnvelope]  # 1..N events
```

- `commit_id` is a content-addressable digest derived **exclusively** from the events. No additional metadata (timestamp, actor, stream_id) is included.
- The digest is computed by serializing the ordered event list as a canonical JSON array (via `Canonicalizer.canonicalize`), then applying SHA-256 to the resulting canonical bytes. This removes any ambiguity about encoding boundaries.
- The same events always produce the same `commit_id` (deterministic, I-08).
- Multi-event commits preserve event order within the commit as specified by the caller.
- Events within a commit receive consecutive sequence numbers.

### 5.2 Commit Receipt

```python
@dataclass(frozen=True)
class CommitReceipt:
    commit_id: str
    stream_id: str
    sequence_start: int      # first event's sequence number in this Commit
    sequence_end: int        # last event's sequence number (sequence_start + len(events) - 1)
    global_order: int        # assigned by the Ledger at persistence time
```

### 5.3 Failure Modes

- **If `append()` fails before persisting:** no partial Commit is visible. The caller may retry.
- **If `append()` fails after persisting:** replayed `append()` returns the existing `CommitReceipt` (idempotent).
- **The Ledger never exposes partially committed Commits.** (Commit Atomicity, I-04)

---

## 6. Stream Registry

### 6.1 Registration

- Streams are created implicitly on first `append()` to a new `stream_id`.
- No explicit stream creation, deletion, or listing is required by the Ledger interface.
- Stream metadata is managed by a separate StreamRegistry component (out of scope for this section).

### 6.2 Metadata (Reserved Namespace)

Reserved for future StreamRegistry use:

| Field | Status | Description |
|-------|--------|-------------|
| `stream_id` | normative | Opaque identifier |
| `created_at` | reserved | First commit timestamp |
| `event_count` | reserved | Total committed event count |
| `partition_key` | reserved | Sharding partition |
| `schema_version` | reserved | Event schema version bound to this stream |

---

## 7. Idempotency & Deduplication

- The Ledger deduplicates by `commit_id`.
- If a Commit with the same `commit_id` already exists, `append()` returns the original `CommitReceipt`.
- Idempotency is **exactly-once**, not at-least-once: the caller receives the same receipt for retries.
- Idempotency scope is the entire Ledger: identical `commit_id` values in different streams are distinct (content addressing makes this extremely unlikely).
- There is no time window on deduplication; deduplication is permanent.

---

## 8. Replay Compliance Scenarios

The following compliance scenarios are specification artifacts, not implementation tests. Any conforming Replay Engine must produce the expected output for each.

### Scenario RC-01: Empty Stream

```
Ledger: (empty)
Replay scope: stream "test-stream"
Expected output: empty projection
```

### Scenario RC-02: Single Event

```
Ledger: stream "test-stream" ← [E1 at seq 1]
Replay scope: stream "test-stream"
Expected output: [E1]
```

### Scenario RC-03: Multiple Ordered Events

```
Ledger: stream "test-stream" ← [E1 at seq 1, E2 at seq 2, E3 at seq 3]
Replay scope: stream "test-stream"
Expected output: [E1, E2, E3]
```

### Scenario RC-04: Single Commit

```
Ledger: stream "test-stream" ← Commit{C1: [E1]}
Replay scope: stream "test-stream"
Expected output: [E1]
```

### Scenario RC-05: Multi-Event Commit

```
Ledger: stream "test-stream" ← Commit{C1: [E1, E2, E3]}
Replay scope: stream "test-stream"
Expected output: [E1, E2, E3]
```

### Scenario RC-06: Snapshot + Replay Tail

```
Ledger: stream "test-stream" ← [E1 at seq 1, E2 at seq 2, E3 at seq 3, E4 at seq 4]
Snapshot: state_before_seq(3)    // represents state after processing E1, E2
Replay scope: seq 3..4
Expected output: [E3, E4]
Expected final state: apply(initial, [E3, E4])
```

### Scenario RC-07: Multiple Independent Streams

```
Ledger: stream "A" ← [A1, A2]
        stream "B" ← [B1, B2, B3]
Replay scope: all streams
Expected output (per stream): A=[A1, A2], B=[B1, B2, B3]
```

### Scenario RC-08: Idempotent Re-Run

```
Ledger: stream "test-stream" ← [E1 at seq 1]
append(Commit{C1: [E1]}) returns existing receipt
Ledger: stream "test-stream" still has [E1 at seq 1] (no duplication)
```

---

## 9. Constitutional Traceability

| Ledger Guarantee | Constitution | Invariant | Scenario |
|-----------------|--------------|-----------|----------|
| Append-only history | Article 2 | I-02, I-02a | RC-08 |
| Commit Atomicity | Article 2 | I-04 | RC-05 |
| Commit Order Preservation | Article 3 | I-06 | RC-05 |
| Idempotent append | Article 2 | I-05 | RC-08 |
| Stream ordering | Article 3 | I-03 | RC-03 |
| Deterministic replay | Article 3 | I-01 | RC-02, RC-06 |
| Replay completeness | Article 3 | I-11 | RC-07 |
| Event immutability | Article 2 | I-02 | RC-08 |
| Deterministic IDs (event_id) | Article 3 | I-08 | CanonicalEnvelope |
| Deterministic IDs (commit_id) | Article 3 | I-08 | Section 5.1 |

---

## 10. Explicit Non-Guarantees

The Ledger does **not** guarantee:

| Aspect | Not Guaranteed | Belongs To |
|--------|---------------|------------|
| Global ordering across streams | Cross-stream event order is not defined | Replay Engine |
| Temporal ordering | `global_order` is a logical sequence, not wall-clock time | Implementation |
| Query capabilities | No search, filter, or index | Projection Runtime |
| Storage technology | No requirement for SQL, NoSQL, or filesystem | Implementation |
| Retention policies | No TTL, compaction, or archival | Operations |
| Transactions across streams | No two-phase commit or distributed TX | Future ADR |
| Replication | No sync, async, or quorum replication | Operations |
| Consensus | No Paxos, Raft, or distributed agreement | Operations |
| Encryption | No at-rest or in-transit encryption | Operations |
| Compression | No storage compression | Implementation |
| Performance characteristics | No latency, throughput, or capacity SLAs | Benchmarking (Phase 3) |
| Indexing | No secondary indexes | Projection Runtime |
| Schema migration | No automatic event schema evolution | Future ADR |

---

## 11. Data Structures

```python
@dataclass(frozen=True)
class Commit:
    commit_id: str
    stream_id: str
    events: list[CanonicalEnvelope]  # 1..N

@dataclass(frozen=True)
class CommitReceipt:
    commit_id: str
    stream_id: str
    sequence_start: int
    sequence_end: int
    global_order: int

@dataclass(frozen=True)
class LedgerEntry:
    stream_id: str
    sequence: int
    commit_id: str
    event_id: str
    rvcj_version: int
    event_schema_version: int
    event_type: str
    timestamp: str       # RFC 3339 UTC
    payload: dict
    global_order: int
```

---

## 12. Decisions Log

| # | Decision | Rationale |
|---|----------|-----------|
| D-01 | Commit is the atomic persistence unit, not Event | Enables future multi-event transactional writes without changing the Ledger model |
| D-02 | commit_id is content-addressed (SHA-256) | Deterministic; replay idempotency without coordination |
| D-03 | Sequence numbers start at 1, contiguous, no gaps | Simplifies replay correctness; gaps indicate lost events |
| D-04 | Global order is a monotonically increasing integer | Enables delta replay and fast-path replay without full stream scan |
| D-05 | Read operations never block | Simplifies concurrency model; snapshot isolation via append-only semantics |
| D-06 | Streams are created implicitly | Avoids registration ceremony; simplifies first-append workflow |
| D-07 | Single-event commits are the reference implementation baseline | Multi-event commits are permitted by the model but not required |
| D-08 | No stream listing in Ledger interface | Stream discovery belongs to StreamRegistry, not the Ledger |
| D-09 | commit_id derived exclusively from canonical event serialization | Ensures determinism and cross-implementation reproducibility; no metadata influences the digest |
| D-10 | A Commit SHALL contain events from exactly one Experience | Preserves atomicity alignment; keeps replay reasoning simple and compositional |
| D-11 | global_order is a logical sequence assigned at persistence time, not append time | Correct for crash recovery: only persisted commits have a defined order |

---

## Freeze Criteria

Section 1 (Ledger) is considered complete when:

- [ ] All replay compliance scenarios (RC-01 through RC-08) are specified.
- [ ] Commit model (Section 5) is finalized.
- [ ] Constitutional traceability matrix (Section 9) is complete.
- [ ] Ledger API (Section 4.1) is stabilized.
- [ ] Explicit non-guarantees (Section 10) are recorded.
- [ ] No unresolved architectural questions remain.
- [ ] Decisions log (Section 12) captures all design rationale.
- [ ] Implementation plan (TDD) exists for the reference Ledger.
- [ ] Ledger interface validated against at least two storage backends (in-memory for testing, SQLite for production).
- [ ] This document has been ratified by architectural review.

---

## Appendix A: Replay Compliance Vectors (Ledger)

Each compliance vector is a JSON file in `spec/vectors/ledger/` following the same format as Phase 1A:

```json
{
  "name": "rc-01-empty-stream",
  "description": "Replay of empty stream produces empty projection",
  "ledger": {},
  "replay": {"stream_id": "test-stream"},
  "expected": [],
  "invariants": ["I-11"]
}
```

Vector directory structure:

```
spec/vectors/ledger/
├── rc-01-empty-stream.json
├── rc-02-single-event.json
├── rc-03-multiple-ordered.json
├── rc-04-single-commit.json
├── rc-05-multi-event-commit.json
├── rc-06-snapshot-tail.json
├── rc-07-multiple-streams.json
├── rc-08-idempotent-append.json
```

---

## Appendix B: Stream Registry Schema (Reserved)

Reserved for Phase 1B.2 — not yet defined.

```python
@dataclass
class StreamMetadata:
    stream_id: str
    created_at: CanonicalTimestamp  # reserved
    event_count: int                # reserved
    partition_key: str | None       # reserved
    schema_version: int             # reserved
    metadata: dict                  # reserved — extensible
```
