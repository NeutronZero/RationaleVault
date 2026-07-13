# Phase 1A: Canonical Representation Layer

**Document Status:** Approved Design — Ready for Implementation

**Effective Date:** July 13, 2026

**Document Version:** 1.0

**Scope:** Canonical Representation Layer (Phase 1A of AC1 Validation)

**Architecture Candidate:** AC1

**Depends On:** Architecture Candidate 1 (AC1) Specification

---

# 1. Purpose

Phase 1A implements the foundational canonical representation that all subsequent RationaleVault v2.0 components build on. It produces the canonical serialization, stable identity, and event envelope infrastructure required for deterministic replay.

**This is the executable specification for I-00 (Canonical Representation) and I-08 (Referential Transparency).**

---

# 2. Deliverables

| # | Deliverable | Description |
|---|-------------|-------------|
| 1 | RVCJ v1 Specification | Formal canonical JSON rules as a normative document |
| 2 | Canonical Event Envelope | The three-layer event structure |
| 3 | Canonical Serializer | The only path to canonical bytes |
| 4 | Stable ID Generator | Content-hash-based identifiers |
| 5 | Canonical Compliance Suite | Cross-implementation validation vectors |

---

# 3. Architectural Invariants

Phase 1A validates the following invariants:

| Invariant | Statement | Validation |
|-----------|-----------|------------|
| **I-00** | Canonical Representation | Semantically equivalent objects produce identical canonical representations. |
| **I-08** | Referential Transparency | All identifiers are deterministically generated via hash of their content and context. |

**Depends on:** None (foundational layer).

**Enables:** I-01 (Replay Determinism), I-10 (Schema Evolution Compatibility).

---

# 4. Module Structure

```
rationalevault/
└── canonical/
    ├── __init__.py
    ├── specification.py      # RVCJ v1 rules as constants (no logic)
    ├── envelope.py           # CanonicalEnvelope dataclass
    ├── serializer.py         # CanonicalSerializer implementation
    ├── stable_id.py          # StableIdGenerator
    ├── types.py              # Shared types (EventTypes, etc.)
    ├── compliance/
    │   ├── __init__.py
    │   ├── vectors.py        # Compliance test vectors
    │   └── validator.py      # Cross-implementation validator
    └── tests/
        ├── __init__.py
        ├── test_specification.py
        ├── test_envelope.py
        ├── test_serializer.py
        ├── test_stable_id.py
        ├── test_roundtrip.py
        ├── test_compliance.py
        └── test_invariants.py
```

---

# 5. Component 1: RVCJ v1 Specification

## 5.1 Normative Document

The specification defines canonicalization rules as Python constants. It contains **no logic** — only the rules that the serializer implements.

```python
# rationalevault/canonical/specification.py

RVCJ_VERSION = 1

KEY_ORDERING = "lexicographic"
UNICODE_NORMALIZATION = "NFC"
TIMESTAMP_FORMAT = "RFC3339-UTC"
TIMESTAMP_PRECISION = "microsecond"
DECIMAL_POLICY = "canonical_normalization"
BINARY_ENCODING = "base64"
NULL_SEMANTICS = "explicit"
```

## 5.2 Canonicalization Rules

### 5.2.1 Object Ordering

Object keys are sorted **lexicographically** (byte ordering) after serialization to JSON.

```python
{"z": 1, "a": 2} → {"a": 2, "z": 1}
```

### 5.2.2 Strings

- Unicode NFC normalized
- UTF-8 encoded
- No escaped characters beyond JSON standard

```python
"café" → NFC normalized "café"
```

### 5.2.3 Integers

- Native JSON integer representation
- No leading zeros
- No plus sign

```python
42 → 42
+42 → 42
042 → 42
```

### 5.2.4 Decimals

**Canonical Decimal Normalization** — not fixed precision.

Rules:
1. No trailing zeros after decimal point (unless integer)
2. No scientific notation
3. No plus sign on exponent
4. Decimal point present only if fractional part exists
5. Leading zero required for values < 1

```python
0.5      → 0.5       (not 0.500000)
0.50     → 0.5       (trailing zero removed)
1.0      → 1.0       (decimal point preserved)
0.001    → 0.001     (no truncation)
1e3      → 1000      (scientific notation resolved)
+1.0     → 1.0       (plus sign removed)
```

### 5.2.5 Timestamps

- UTC only
- RFC 3339 / ISO-8601 format
- Microsecond precision (6 decimal places)
- Always include `Z` suffix

```python
datetime(2026, 7, 13, 14, 35, 42, 123456, tzinfo=UTC)
→ "2026-07-13T14:35:42.123456Z"
```

### 5.2.6 Null Semantics

Three distinct states:

| State | JSON Representation | Meaning |
|-------|---------------------|---------|
| **Missing** | Key absent from object | Field was not provided |
| **Null** | `"key": null` | Field was explicitly set to null |
| **Default** | `"key": <value>` | Field was set to a default value |

**Critical for schema evolution:** Missing ≠ Null ≠ Default.

### 5.2.7 Booleans

Standard JSON:
- `true`
- `false`

### 5.2.8 Binary

- Base64 encoded
- String representation in JSON

```python
b"\x00\x01" → "AAE="
```

### 5.2.9 Arrays

- Preserve insertion order
- Never sorted
- Elements are recursively canonicalized

### 5.2.10 Schema Fingerprint

Every canonical schema exposes:

```python
SCHEMA_FINGERPRINT = sha256(specification_text)
```

Used for producer/consumer agreement verification.

---

# 6. Component 2: Canonical Event Envelope

## 6.1 Three-Layer Structure

### Layer 1: Constitutional Metadata (Required)

Fields that define replay behavior.

### Layer 2: Provenance Metadata (Required + Optional)

Fields that define explainability and tracing.

### Layer 3: Domain Payload

Everything domain-specific.

## 6.2 Field Specification

| Field | Layer | Required | Type | Description |
|-------|-------|----------|------|-------------|
| `schema_version` | 1 | Yes | int | Envelope version (starts at 1) |
| `experience_id` | 1 | Yes | str | Groups events into one experience |
| `event_type` | 1 | Yes | str | Replay dispatch key |
| `stream_id` | 1 | Yes | str | Ordering boundary identifier |
| `sequence` | 1 | Yes | int | Deterministic order within stream |
| `timestamp` | 2 | Yes | str | UTC ISO-8601, microsecond precision |
| `actor` | 2 | Yes | str | Origin of the experience |
| `correlation_id` | 2 | No | str | Cross-event tracing |
| `causation_id` | 2 | No | str | Event lineage |
| `payload` | 3 | Yes | CanonicalPayload | Domain-specific data |

## 6.3 Field Definitions

### `schema_version`

- **Required:** Yes
- **Type:** int
- **Description:** Version of the envelope schema. Drives schema evolution.
- **Constraint:** Must be a positive integer.

### `experience_id`

- **Required:** Yes
- **Type:** str
- **Description:** Groups events belonging to a single Experience. One Experience may generate multiple events.
- **Format:** `EXP-{hash_prefix}` (12 hex characters)
- **Generation:** Hash of semantic content (excluding recording metadata).

### `event_type`

- **Required:** Yes
- **Type:** str
- **Description:** Determines replay dispatch. Must be a known event type.
- **Constraint:** Non-empty string.

### `stream_id`

- **Required:** Yes
- **Type:** str
- **Description:** Defines the smallest unit for which deterministic ordering is required. Ordering is guaranteed within a stream.
- **Semantic:** Stream identity represents ordering boundary, not entity identity.
- **Examples:** `project-42`, `conversation-17`, `agent-5`, `task-19`

### `sequence`

- **Required:** Yes
- **Type:** int
- **Description:** Deterministic order within a stream. Combined with `stream_id`, uniquely identifies event ordering.
- **Constraint:** Monotonically increasing within a stream.

### `timestamp`

- **Required:** Yes
- **Type:** str
- **Description:** UTC timestamp for auditing and provenance. Never used for replay ordering.
- **Format:** `YYYY-MM-DDTHH:MM:SS.ffffffZ`
- **Constraint:** Always UTC. Always microsecond precision.

### `actor`

- **Required:** Yes
- **Type:** str
- **Description:** Origin of the experience. Every experience has an actor.
- **Examples:** `agent-001`, `system`, `scheduler`, `user-123`

### `correlation_id`

- **Required:** No
- **Type:** str
- **Description:** Groups related events for tracing. Optional.

### `causation_id`

- **Required:** No
- **Type:** str
- **Description:** Represents "what caused this event." Replaces `parent_event_id` for clearer event lineage.

### `payload`

- **Required:** Yes
- **Type:** CanonicalPayload
- **Description:** Domain-specific data. The architecture does not constrain payload structure.

## 6.4 CanonicalPayload

A wrapper around domain data that enforces canonical rules.

```python
@dataclass(frozen=True)
class CanonicalPayload:
    data: dict[str, Any]
```

**Purpose:** Encapsulates payload-level canonicalization rules, validation, and schema evolution constraints.

**Interface:**
```python
@dataclass(frozen=True)
class CanonicalPayload:
    data: dict[str, Any]
    
    def to_dict(self) -> dict[str, Any]: ...
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'CanonicalPayload': ...
```

## 6.5 CanonicalEnvelope

```python
@dataclass(frozen=True)
class CanonicalEnvelope:
    schema_version: int
    experience_id: str
    event_type: str
    stream_id: str
    sequence: int
    timestamp: str
    actor: str
    payload: CanonicalPayload
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None
    
    def to_dict(self) -> dict[str, Any]: ...
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'CanonicalEnvelope': ...
```

---

# 7. Component 3: Canonical Serializer

The **single path** to canonical bytes. All other code uses this interface.

## 7.1 Interface

```python
class CanonicalSerializer:
    @staticmethod
    def serialize(envelope: CanonicalEnvelope) -> bytes:
        """Serialize envelope to canonical JSON bytes (RVCJ v1)."""
        ...
    
    @staticmethod
    def deserialize(data: bytes) -> CanonicalEnvelope:
        """Deserialize canonical bytes to envelope."""
        ...
    
    @staticmethod
    def hash(envelope: CanonicalEnvelope) -> str:
        """Produce deterministic SHA-256 hash of canonical bytes.
        
        Returns full 64-character hex hash.
        Display form uses 12 characters.
        """
        ...
    
    @staticmethod
    def schema_fingerprint() -> str:
        """Return the schema fingerprint for this serializer version."""
        ...
```

## 7.2 Serialization Pipeline

```
CanonicalEnvelope
    ↓
to_dict()
    ↓
RVCJ canonicalization
    ↓
JSON serialization (no whitespace)
    ↓
UTF-8 encoding
    ↓
canonical bytes
```

## 7.3 Constraints

- **No `json.dumps()` directly.** Only `CanonicalSerializer.serialize()` produces canonical bytes.
- **Deterministic:** Same envelope → same bytes, always.
- **Roundtrip stable:** `deserialize(serialize(env)) == env`.
- **Schema fingerprint verifiable:** `schema_fingerprint()` matches specification hash.

---

# 8. Component 4: Stable ID Generator

Content-hash-based identifiers.

## 8.1 ID Format

```
{PREFIX}-{HASH_DISPLAY}
```

| Entity | Prefix | Example |
|--------|--------|---------|
| Experience | `EXP` | `EXP-a1b2c3d4e5f6` |
| Event | `EVT` | `EVT-a1b2c3d4e5f6` |
| Projection | `PRJ` | `PRJ-a1b2c3d4e5f6` |

## 8.2 Hash Rules

- **Algorithm:** SHA-256
- **Internal:** Full 256-bit hash (never truncated)
- **Display:** 12 hexadecimal characters (48 bits visible)
- **Storage:** Full hash stored for future use

## 8.3 Two Identity Types

### Experience ID

Hash of **semantic content** (excluding recording metadata).

Two recordings of the same experience produce the same Experience ID.

```python
StableIdGenerator.experience_id(content: dict[str, Any]) -> str
```

### Event ID

Hash of **canonical envelope** (including recording metadata).

Each recording is unique.

```python
StableIdGenerator.event_id(envelope: CanonicalEnvelope) -> str
```

## 8.4 Interface

```python
class StableIdGenerator:
    HASH_DISPLAY_LENGTH = 12
    
    @staticmethod
    def experience_id(content: dict[str, Any]) -> str:
        """Generate stable experience ID from semantic content."""
        ...
    
    @staticmethod
    def event_id(envelope: CanonicalEnvelope) -> str:
        """Generate stable event ID from canonical envelope."""
        ...
    
    @staticmethod
    def projection_id(content: dict[str, Any]) -> str:
        """Generate stable projection ID from content."""
        ...
```

---

# 9. Component 5: Canonical Compliance Suite

Cross-implementation validation vectors.

## 9.1 Purpose

Validate independent implementations (Python, Rust, Go, Java) against the same specification.

## 9.2 Structure

```
canonical/
└── compliance/
    ├── __init__.py
    ├── vectors.py        # Test vectors (input → expected output)
    └── validator.py      # Validation runner
```

## 9.3 Test Vector Format

```python
COMPLIANCE_VECTORS = [
    {
        "name": "key_ordering",
        "input": {"z": 1, "a": 2},
        "expected_canonical": '{"a":2,"z":1}',
        "expected_hash": "sha256_of_canonical_bytes"
    },
    {
        "name": "unicode_nfc",
        "input": {"key": "café"},  # with combining accent
        "expected_canonical": '{"key":"café"}',  # NFC normalized
        "expected_hash": "..."
    },
    # ... more vectors
]
```

## 9.4 Compliance Requirements

An implementation is compliant if:
1. All test vectors produce identical canonical bytes
2. All test vectors produce identical hashes
3. Roundtrip serialize → deserialize → serialize is stable
4. Schema fingerprint matches specification hash

---

# 10. Test Suite

## 10.1 Serialization Stability Tests

| Test | Description |
|------|-------------|
| `test_deterministic_serialization` | Same object → same bytes |
| `test_key_ordering` | Different key orderings → same bytes |
| `test_unicode_normalization` | Different Unicode forms → same bytes |
| `test_decimal_normalization` | Different decimal representations → same bytes |
| `test_null_handling` | Explicit null vs missing vs default |
| `test_timestamp_format` | UTC, microsecond precision, Z suffix |

## 10.2 Stable ID Tests

| Test | Description |
|------|-------------|
| `test_experience_id_deterministic` | Same content → same ID |
| `test_experience_id_unique` | Different content → different ID |
| `test_event_id_deterministic` | Same envelope → same ID |
| `test_event_id_unique` | Different envelopes → different IDs |
| `test_id_format` | PREFIX-12hexchars format |

## 10.3 Roundtrip Tests

| Test | Description |
|------|-------------|
| `test_serialize_deserialize_roundtrip` | serialize → deserialize → serialize identical |
| `test_hash_stability` | Hash is identical across calls |

## 10.4 Invariant Tests

| Test | Invariant |
|------|-----------|
| `test_i00_canonical_representation` | Semantically equivalent objects produce identical canonical representations |
| `test_i08_referential_transparency` | All identifiers are deterministically generated via hash |

## 10.5 Compliance Tests

| Test | Description |
|------|-------------|
| `test_compliance_vectors` | All vectors pass |
| `test_cross_version_stability` | v1 serializer → deserialize → v2 serializer produces same semantic object |
| `test_envelope_validation` | Rejects missing required fields, duplicate fields, invalid timestamps, invalid IDs |
| `test_schema_fingerprint` | All serializers report same fingerprint |

---

# 11. Invariant I-00: Canonical Representation

## 11.1 Statement

> **Semantically equivalent objects must produce identical canonical representations.**

## 11.2 Formal Definition

For any two objects `A` and `B`:

```
semantic_equal(A, B) → canonical_bytes(A) == canonical_bytes(B)
```

## 11.3 Enforcement

- Canonicalization rules are deterministic
- No external state influences serialization
- Compliance suite validates across implementations

## 11.4 Relationship to Other Invariants

```
I-00 Canonical Representation
    ↓
I-08 Referential Transparency
    ↓
I-01 Replay Determinism
```

---

# 12. Implementation Order

## 12.1 Dependencies

```
specification.py (no dependencies)
    ↓
envelope.py (depends on specification)
    ↓
serializer.py (depends on envelope, specification)
    ↓
stable_id.py (depends on serializer)
    ↓
compliance/ (depends on all above)
```

## 12.2 Implementation Sequence

1. `specification.py` — Define rules as constants
2. `types.py` — Shared type definitions
3. `envelope.py` — CanonicalEnvelope and CanonicalPayload
4. `serializer.py` — CanonicalSerializer
5. `stable_id.py` — StableIdGenerator
6. `compliance/vectors.py` — Test vectors
7. `compliance/validator.py` — Validation runner
8. Tests — All test files

---

# 13. Success Criteria

Phase 1A is complete when:

| Criterion | Description |
|-----------|-------------|
| ✅ Specification | RVCJ v1 specification written and validated |
| ✅ Serializer | CanonicalSerializer produces deterministic bytes |
| ✅ Stable IDs | StableIdGenerator produces content-hash-based IDs |
| ✅ Invariant I-00 | Canonical representation stability passes |
| ✅ Invariant I-08 | Referential transparency passes |
| ✅ Compliance | All compliance vectors pass |
| ✅ Roundtrip | serialize → deserialize → serialize is stable |

---

# 14. What Phase 1A Does NOT Do

- Does not implement the Reference Ledger
- Does not implement Replay
- Does not implement Projections
- Does not integrate with existing v1.4.0 code
- Does not handle legacy event formats

**Phase 1B** adds the Reference Kernel. **Phase 2** adds Canonicalization Adapters for legacy integration.

---

# 15. Decisions Log

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Canonical format | JSON (RVCJ v1) | Human-readable, excellent tooling, stable over decades |
| Hash algorithm | SHA-256 | Universal, mature, boring — exactly what infrastructure should be |
| Hash display length | 12 hex characters | Readable, ~48 bits visible, low collision probability |
| Hash internal length | Full 256 bits | Never truncate internally, future-proof |
| Decimal precision | Canonical normalization | No trailing zeros, no fixed precision, deterministic |
| Identity separation | Experience ID ≠ Event ID | Semantic content vs recording metadata |
| Schema evolution | Never migrate history | Canonicalization adapters transform legacy events |
| Replay input | Canonical events only | Architectural principle: replay is unaware of legacy |

---

# Sign-off

This document constitutes the **Phase 1A Design Specification** for the RationaleVault v2.0 Canonical Representation Layer.

**Design Status:** Approved

**Next Phase:** Implementation

**Validation:** Will be validated through the Canonical Compliance Suite and invariant tests.
