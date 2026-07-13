# Phase 1B.1: Ledger Reference Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the Ledger logical model, in-memory backend, append/read semantics, idempotency, and compliance suite following the ratified AF-002 specification.

**Architecture:** Specification-first development. Compliance vectors are written before the serializer. Single commit model — no duplicate logic. In-memory backend validated before SQLite.

**Tech Stack:** Python 3.12+, Canonical Layer (AF-001), sqlite3 (stdlib), pytest

## Global Constraints

- Python >=3.12
- No external dependencies for core ledger module (stdlib only)
- SQLite backend uses stdlib `sqlite3` only
- TDD: write failing test first, then implement
- Milestone-based commits (not per-task)
- Correctness over throughput — no caching, batching, or optimization

## File Structure

```
rationalevault/ledger/
├── __init__.py                  # Public API exports
├── commit.py                    # Commit, CommitReceipt value objects
├── entry.py                     # LedgerEntry value object
├── interface.py                 # Ledger ABC (abstract storage contract)
├── storage/
│   ├── __init__.py
│   ├── memory.py                # In-memory backend (reference)
│   └── sqlite.py                # SQLite backend (production)
├── compliance/
│   ├── __init__.py
│   ├── vectors.py               # Loads vectors from spec/vectors/ledger/
│   └── validator.py             # Compliance validation
└── tests/
    ├── __init__.py
    ├── test_commit.py            # Commit, CommitReceipt, LedgerEntry
    ├── test_memory_ledger.py     # In-memory ledger tests
    ├── test_sqlite_ledger.py     # SQLite ledger tests
    ├── test_compliance.py        # RC-01 through RC-08
    └── test_invariants.py        # I-02..I-06, I-11

spec/vectors/ledger/              # Compliance vectors
├── rc-01-empty-stream.json
├── rc-02-single-event.json
├── rc-03-multiple-ordered.json
├── rc-04-single-commit.json
├── rc-05-multi-event-commit.json
├── rc-06-snapshot-tail.json
├── rc-07-multiple-streams.json
└── rc-08-idempotent-append.json
```

## Commit Strategy

Milestone-based commits:

| Milestone | Tasks | Commit Message |
|-----------|-------|----------------|
| Value Objects | 1 | `feat(ledger): add Commit, CommitReceipt, LedgerEntry value objects` |
| In-Memory Backend | 2, 3 | `feat(ledger): add Ledger ABC and in-memory storage backend` |
| SQLite Backend | 4 | `feat(ledger): add SQLite storage backend` |
| Append Semantics | 5 | `feat(ledger): implement atomic append with idempotency` |
| Read Semantics | 6 | `feat(ledger): implement read_stream, read_from, exists, stream_exists` |
| Idempotency | 7 | `feat(ledger): implement idempotent append with DuplicateCommitError` |
| Compliance | 8 | `test(ledger): add compliance vectors RC-01 through RC-08` |
| Invariants | 9 | `test(ledger): add invariant tests I-02..I-06, I-11` |
| Validation | 10 | `test(ledger): verify full test suite passes for both backends` |

---

## Task 1: Commit, CommitReceipt, LedgerEntry Value Objects

**Files:**
- Create: `rationalevault/ledger/__init__.py`
- Create: `rationalevault/ledger/commit.py`
- Create: `rationalevault/ledger/entry.py`
- Create: `rationalevault/ledger/tests/__init__.py`
- Create: `rationalevault/ledger/tests/test_commit.py`

**Interfaces:**
- Consumes: `CanonicalEnvelope`, `CanonicalSerializer`, `CanonicalTimestamp`
- Produces: Immutable value objects for Commit, CommitReceipt, LedgerEntry

**Value Objects:**

```python
@dataclass(frozen=True)
class Commit:
    commit_id: str          # SHA-256(canonical serialization of events array)
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
    timestamp: str
    payload: dict
    global_order: int
```

- [ ] **Step 1: Create directory structure**
- [ ] **Step 2: Write the failing test** (`test_commit.py` — tests for creation, immutability, field access)
- [ ] **Step 3: Run test to verify it fails** (ImportError)
- [ ] **Step 4: Write minimal implementation** (`commit.py`, `entry.py`, `__init__.py`)
- [ ] **Step 5: Run test to verify it passes**
- [ ] **Step 6: Commit**

---

## Task 2: Ledger ABC (Abstract Storage Contract)

**Files:**
- Create: `rationalevault/ledger/interface.py`

**Interfaces:**
- Consumes: `Commit`, `LedgerEntry`
- Produces: Abstract storage contract

**Interface:**

```python
from __future__ import annotations

from abc import ABC, abstractmethod


class Ledger(ABC):
    @abstractmethod
    def append(self, commit: Commit) -> CommitReceipt:
        ...

    @abstractmethod
    def read_stream(self, stream_id: str) -> list[LedgerEntry]:
        ...

    @abstractmethod
    def read_from(self, global_order: int) -> list[LedgerEntry]:
        ...

    @abstractmethod
    def exists(self, commit_id: str) -> bool:
        ...

    @abstractmethod
    def stream_exists(self, stream_id: str) -> bool:
        ...
```

- [ ] **Step 1: Write the failing test** (ImportError — ABC module doesn't exist yet)
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Write minimal implementation**
- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Commit**

---

## Task 3: In-Memory Ledger Backend

**Files:**
- Create: `rationalevault/ledger/storage/__init__.py`
- Create: `rationalevault/ledger/storage/memory.py`
- Create: `rationalevault/ledger/tests/test_memory_ledger.py`

**Interfaces:**
- Consumes: `Ledger` ABC, `Commit`, `CommitReceipt`, `LedgerEntry`
- Produces: In-memory implementation for testing

- [ ] **Step 1: Write the failing test** (basic append, read, stream listing)
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Write minimal implementation** (dict-based storage with global_order counter)
- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Commit**

---

## Task 4: SQLite Ledger Backend

**Files:**
- Create: `rationalevault/ledger/storage/sqlite.py`
- Create: `rationalevault/ledger/tests/test_sqlite_ledger.py`

**Interfaces:**
- Consumes: `Ledger` ABC, same test suite as in-memory
- Produces: Production SQLite implementation

- [ ] **Step 1: Write the failing test** (same structure as in-memory tests)
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Write minimal implementation** (sqlite3-based with schema, transactions)
- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Commit**

---

## Task 5: Append Semantics (Atomic, Gap-Free)

**Files:**
- Modify: `rationalevault/ledger/storage/memory.py`, `rationalevault/ledger/storage/sqlite.py`

**Interfaces:**
- Consumes: Existing backends
- Produces: Append with sequence contiguity, gap detection, atomicity

- [ ] **Step 1: Write the failing test** (test sequence contiguity, test gap rejection, test multi-event commit atomicity)
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Implement append in both backends with sequence allocation**
- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Commit**

---

## Task 6: Read Semantics (read_stream, read_from, exists)

**Files:**
- Modify: Both backends

**Interfaces:**
- Consumes: Existing backends
- Produces: `read_stream()`, `read_from()`, `exists()`, `stream_exists()` fully implemented

- [ ] **Step 1: Write the failing test** (read_stream ordering, read_from global order, empty stream, unknown stream)
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Implement read methods in both backends**
- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Commit**

---

## Task 7: Idempotent Append (DuplicateCommitError)

**Files:**
- Modify: Both backends
- Create: exception definitions in `rationalevault/ledger/errors.py`

**Interfaces:**
- Consumes: Existing backends
- Produces: `DuplicateCommitError` for re-append of same commit_id; `StreamConflictError` for sequence gaps

- [ ] **Step 1: Write the failing test** (append same commit twice returns same receipt, no duplication)
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Implement idempotency in both backends**
- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Commit**

---

## Task 8: Compliance Vectors (RC-01 through RC-08)

**Files:**
- Create: `spec/vectors/ledger/rc-*.json` (8 vector files)
- Create: `rationalevault/ledger/compliance/__init__.py`
- Create: `rationalevault/ledger/compliance/vectors.py`
- Create: `rationalevault/ledger/compliance/validator.py`
- Create: `rationalevault/ledger/tests/test_compliance.py`

**Interfaces:**
- Consumes: `Ledger` implementations
- Produces: Compliance validation against spec artifacts

- [ ] **Step 1: Write the failing test** (ImportError for compliance module)
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Write 8 compliance vector JSON files**
- [ ] **Step 4: Write compliance module (vectors loader, validator)**
- [ ] **Step 5: Write compliance tests for RC-01 through RC-08**
- [ ] **Step 6: Run test to verify it passes**
- [ ] **Step 7: Commit**

---

## Task 9: Invariant Tests (I-02 through I-06, I-11)

**Files:**
- Create: `rationalevault/ledger/tests/test_invariants.py`

**Interfaces:**
- Consumes: `Ledger` implementations
- Produces: Constitutional invariant validation

**Test coverage:**

| Invariant | Test |
|-----------|------|
| I-02 | Never Mutates History — append event, verify read back is identical |
| I-02a | Append-Only — verify no delete/update operations exist |
| I-03 | Stream Ordering — append events in known order, verify read order matches |
| I-04 | Commit Atomicity — verify partial commits are never visible |
| I-05 | Idempotent Append — same commit_id returns same receipt |
| I-06 | Commit Order Preservation — multi-event commit preserves event order |
| I-11 | Replay Completeness — all events in a stream are returned |

- [ ] **Step 1: Write the failing test**
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Run test to verify it passes** (depends on previous tasks)
- [ ] **Step 4: Commit**

---

## Task 10: Full Test Suite Validation

**Files:**
- None (verification task)

- [ ] **Step 1: Run all in-memory ledger tests**
- [ ] **Step 2: Run all SQLite ledger tests**
- [ ] **Step 3: Run all compliance tests (both backends)**
- [ ] **Step 4: Run all invariant tests (both backends)**
- [ ] **Step 5: Verify identical behavior between backends**
- [ ] **Step 6: Commit final verification**

---

## Success Criteria

| Criterion | Description |
|-----------|-------------|
| ✅ | Ledger supports append-only writes (I-02a) |
| ✅ | Streams provide deterministic ordering (I-03) |
| ✅ | `append()` is atomic and idempotent (I-04, I-05) |
| ✅ | Multi-event Commits preserve event order (I-06) |
| ✅ | Reads return fully committed Commits only |
| ✅ | All compliance scenarios (RC-01..RC-08) pass |
| ✅ | All constitutional invariants (I-02..I-06, I-11) pass |
| ✅ | In-Memory and SQLite backends produce identical behavior |
| ✅ | No data duplication on idempotent append |
| ✅ | Full test suite passes for both backends |
