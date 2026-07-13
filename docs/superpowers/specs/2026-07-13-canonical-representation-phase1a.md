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

## 3.1 Constitutional Principle

The following principle has **constitutional status** and must not be violated:

> **Replay consumes canonical events only.**

This protects the replay engine from every future compatibility concern:
- Legacy formats → Canonicalization Adapters → Replay
- External connectors → Canonicalization Adapters → Replay
- Future RVCJ versions → Canonicalization Adapters → Replay

Replay remains permanently simple. This principle must be preserved in all future versions.

**Depends on:** None (foundational layer).

**Enables:** I-01 (Replay Determinism), I-10 (Schema Evolution Compatibility).

---

# 4. Module Structure

```
rationalevault/
└── canonical/
    ├── __init__.py
    ├── specification.py      # RVCJ v1 rules as constants (no logic)
    ├── types.py              # Shared types (EventType enum, etc.)
    ├── timestamp.py          # CanonicalTimestamp value object
    ├── payload.py            # CanonicalPayload value object
    ├── envelope.py           # CanonicalEnvelope dataclass
    ├── serializer.py         # CanonicalSerializer implementation
    ├── stable_id.py          # StableIdGenerator
    ├── compliance/
    │   ├── __init__.py
    │   ├── vectors.py        # Loads vectors from spec/vectors/
    │   └── validator.py      # Cross-implementation validator
    └── tests/
        ├── __init__.py
        ├── test_specification.py
        ├── test_timestamp.py
        ├── test_payload.py
        ├── test_envelope.py
        ├── test_serializer.py
        ├── test_stable_id.py
        ├── test_roundtrip.py
        ├── test_compliance.py
        └── test_invariants.py

spec/
└── vectors/                  # Language-independent compliance vectors
    ├── key_ordering.json
    ├── unicode_normalization.json
    ├── decimal_normalization.json
    ├── timestamp_format.json
    ├── null_semantics.json
    ├── binary_encoding.json
    ├── array_ordering.json
    ├── deep_nesting.json
    ├── empty_payload.json
    ├── large_integers.json
    ├── unicode_combining.json
    └── mixed_normalization.json
```

---

# 5. Component 1: RVCJ v1 Specification

## 5.1 Normative Document

The specification defines canonicalization rules as Python constants. It contains **no logic** — only the rules that the serializer implements.

```python
# rationalevault/canonical/specification.py

RVCJ_VERSION = 1
EVENT_SCHEMA_VERSION = 1

KEY_ORDERING = "lexicographic"
UNICODE_NORMALIZATION = "NFC"
TIMESTAMP_FORMAT = "RFC3339-UTC"
TIMESTAMP_PRECISION = "microsecond"
DECIMAL_POLICY = "canonical_normalization"
BINARY_ENCODING = "base64"
NULL_SEMANTICS = "explicit"

HASH_ALGORITHM = "sha-256"
HASH_DISPLAY_LENGTH = 12
HASH_INTERNAL_LENGTH = 32  # bytes

RESERVED_PAYLOAD_NAMESPACES = ["meta"]
```

## 5.2 Canonicalization Rules

### 5.2.0 Reserved Extension Points

The following namespaces are reserved for future extensions:

| Namespace | Purpose | Status |
|-----------|---------|--------|
| `meta/` | System-level metadata | Reserved, unused |
| `internal/` | Internal implementation details | Reserved, unused |
| `experimental/` | Experimental features | Reserved, unused |

Payloads must not use these as keys. Future versions may use these for system-level metadata without breaking existing payloads.

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
| `rvcj_version` | 1 | Yes | int | RVCJ envelope format version (starts at 1) |
| `event_schema_version` | 1 | Yes | int | Event payload schema version (starts at 1) |
| `experience_id` | 1 | Yes | str | Groups events into one experience |
| `event_type` | 1 | Yes | EventType | Replay dispatch key (enum/registry) |
| `stream_id` | 1 | Yes | str | Ordering boundary identifier |
| `sequence` | 1 | Yes | int | Deterministic order within stream |
| `timestamp` | 2 | Yes | str | UTC ISO-8601, microsecond precision |
| `actor` | 2 | Yes | str | Origin of the experience |
| `correlation_id` | 2 | No | str | Cross-event tracing |
| `causation_id` | 2 | No | str | Event lineage |
| `payload` | 3 | Yes | CanonicalPayload | Domain-specific data |

## 6.3 Field Definitions

### `rvcj_version`

- **Required:** Yes
- **Type:** int
- **Description:** Version of the RVCJ envelope format. Drives envelope-level schema evolution.
- **Constraint:** Must be a positive integer. Starts at 1.
- **Independence:** Evolves independently of event payload schema.

### `event_schema_version`

- **Required:** Yes
- **Type:** int
- **Description:** Version of the event payload schema. Drives payload-level schema evolution.
- **Constraint:** Must be a positive integer. Starts at 1.
- **Independence:** Evolves independently of envelope format.

### `experience_id`

- **Required:** Yes
- **Type:** str
- **Description:** Groups events belonging to a single Experience. One Experience may generate multiple events.
- **Format:** `EXP-{hash_prefix}` (12 hex characters)
- **Generation:** Hash of semantic content (see Section 6.6).

### `event_type`

- **Required:** Yes
- **Type:** EventType (enum/registry)
- **Description:** Determines replay dispatch. Must be a registered event type.
- **Constraint:** Must be a known EventType. Schema evolution safer with enum than arbitrary strings.

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
- **Type:** CanonicalTimestamp (value object)
- **Description:** UTC timestamp for auditing and provenance. Never used for replay ordering.
- **Format:** RFC 3339 / ISO-8601, microsecond precision, UTC only
- **Constraint:** Always UTC. Always microsecond precision. Enforced by value object.

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

An immutable value object that enforces canonical rules on domain data.

```python
@dataclass(frozen=True)
class CanonicalPayload:
    data: dict[str, Any]
    
    def validate(self) -> None:
        """Validate payload against schema constraints.
        
        Answers: Is this payload legal?
        - Required fields present
        - Types correct
        - No extra fields (strict mode)
        """
        ...
    
    def canonicalize(self) -> 'CanonicalPayload':
        """Return canonical form of payload.
        
        Answers: What is its unique canonical form?
        - Keys sorted lexicographic
        - Values normalized (NFC, decimal, timestamps)
        - Recursively applied to nested objects
        """
        ...
    
    def content_digest(self) -> str:
        """Produce deterministic hash of canonical payload."""
        ...
    
    def to_dict(self) -> dict[str, Any]: ...
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'CanonicalPayload': ...
```

**Processing Pipeline:**
```
Raw Payload
    ↓
validate()        ← Is this payload legal?
    ↓
canonicalize()    ← What is its unique canonical form?
    ↓
Canonical Payload
    ↓
content_digest()  ← What is its deterministic hash?
```

**Reserved Namespaces:** `meta/`, `internal/`, `experimental/` — reserved for future extensions. Payloads must not use these as keys.

## 6.5 CanonicalTimestamp

An immutable value object that enforces UTC timestamps with RFC 3339 formatting.

```python
@dataclass(frozen=True)
class CanonicalTimestamp:
    value: datetime
    
    def __post_init__(self) -> None:
        """Enforce UTC and microsecond precision."""
        if self.value.tzinfo is None:
            raise ValueError("Timestamp must be timezone-aware")
        if self.value.tzinfo != UTC:
            self.value = self.value.astimezone(UTC)
    
    def to_iso8601(self) -> str:
        """Return RFC 3339 formatted string: YYYY-MM-DDTHH:MM:SS.ffffffZ"""
        ...
    
    def to_dict(self) -> str:
        """Return canonical string representation."""
        return self.to_iso8601()
    
    @classmethod
    def from_datetime(cls, dt: datetime) -> 'CanonicalTimestamp': ...
    
    @classmethod
    def from_iso8601(cls, s: str) -> 'CanonicalTimestamp': ...
```

**Constraints:**
- Always UTC (enforced on construction)
- Always microsecond precision
- Always RFC 3339 format with `Z` suffix
- Immutable after creation

## 6.6 Semantic Content Definition

The `experience_id` is generated from **semantic content** — the meaning of the experience, not its recording.

### Included in Semantic Content

| Field | Rationale |
|-------|-----------|
| `event_type` | Defines what kind of experience occurred |
| `payload` | Contains the domain-specific meaning |

### Excluded from Semantic Content

| Field | Rationale |
|-------|-----------|
| `timestamp` | Recording metadata, not meaning |
| `sequence` | Recording metadata, not meaning |
| `stream_id` | Ordering boundary, not identity |
| `actor` | Origin, not semantic content (unless semantically significant) |
| `correlation_id` | Tracing metadata, not meaning |
| `causation_id` | Lineage metadata, not meaning |

### Formal Definition

```
SemanticContent = {
    event_type: EventType,
    payload: CanonicalPayload
}
```

**Invariant:** Two recordings of the same experience produce the same `experience_id`.

## 6.7 CanonicalEnvelope

```python
@dataclass(frozen=True)
class CanonicalEnvelope:
    rvcj_version: int
    event_schema_version: int
    experience_id: str
    event_type: EventType
    stream_id: str
    sequence: int
    timestamp: CanonicalTimestamp
    actor: str
    payload: CanonicalPayload
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None
    
    def to_dict(self) -> dict[str, Any]: ...
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'CanonicalEnvelope': ...
```

## 6.8 Canonical Object

The serializer operates on a **canonical object graph**, not arbitrary Python objects. This keeps serialization independent of the envelope implementation.

```
CanonicalEnvelope
    ↓
canonicalize()
    ↓
Canonical Object (normalized, validated)
    ↓
CanonicalSerializer.serialize()
    ↓
canonical bytes
```

The Canonical Object is an intermediate representation that:
1. Has all required fields populated
2. Has all values in canonical form
3. Is validated against schema constraints
4. Is ready for serialization

This layer ensures that serialization is a pure function of the canonical object, not dependent on how the envelope was constructed.

## 6.9 Canonical Processing Pipeline

The full processing pipeline distinguishes validation from canonicalization:

```
Raw Input
    ↓
Validation          ← Is this input legal?
    ↓
Canonicalization    ← What is its unique canonical form?
    ↓
Canonical Object
    ↓
Serialization       ← What are its canonical bytes?
    ↓
Canonical Bytes
```

**Validation** answers: "Is this input legal?"
- Required fields present
- Types correct
- Constraints satisfied

**Canonicalization** answers: "What is its unique canonical form?"
- Keys sorted
- Values normalized
- Recursively applied

Keeping these responsibilities distinct makes schema evolution cleaner.

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
    def content_digest(envelope: CanonicalEnvelope) -> str:
        """Produce deterministic SHA-256 hash of canonical bytes.
        
        Returns full 64-character hex hash.
        Display form uses 12 characters.
        """
        ...
    
    @staticmethod
    def version() -> int:
        """Return RVCJ version of this serializer."""
        ...
    
    @staticmethod
    def schema_fingerprint() -> str:
        """Return the schema fingerprint for this serializer version."""
        ...
    
    @staticmethod
    def algorithm() -> str:
        """Return the hash algorithm used (e.g., 'sha-256')."""
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
Canonical Object (normalized, validated)
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
- **Canonical Object layer:** Serializer operates on canonical object, not raw envelope.

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
        """Generate stable experience ID from semantic content.
        
        Semantic content = event_type + payload.
        Excludes: timestamp, sequence, stream_id, actor, correlation_id, causation_id.
        """
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

Cross-implementation validation vectors. **The vectors are the specification.** The validator merely executes them.

## 9.1 Purpose

Validate independent implementations (Python, Rust, Go, Java) against the same specification. The compliance vectors are **language-independent specification artifacts** — not Python fixtures.

## 9.2 Structure

```
spec/
└── vectors/
    ├── key_ordering.json
    ├── unicode_normalization.json
    ├── decimal_normalization.json
    ├── timestamp_format.json
    ├── null_semantics.json
    ├── binary_encoding.json
    ├── array_ordering.json
    ├── deep_nesting.json
    ├── empty_payload.json
    ├── large_integers.json
    ├── unicode_combining.json
    └── mixed_normalization.json

rationalevault/
└── canonical/
    └── compliance/
        ├── __init__.py
        ├── vectors.py        # Loads vectors from spec/
        └── validator.py      # Executes compliance tests
```

## 9.3 Test Vector Format

```json
{
  "name": "key_ordering",
  "description": "Object keys must be sorted lexicographically",
  "input": {"z": 1, "a": 2},
  "expected_canonical": "{\"a\":2,\"z\":1}",
  "expected_hash": "sha256_of_canonical_bytes",
  "expected_deserialized": {"a": 2, "z": 1}
}
```

## 9.4 Compliance Requirements

An implementation is compliant if:
1. All test vectors produce identical canonical bytes
2. All test vectors produce identical hashes
3. All test vectors produce identical deserialized objects
4. Roundtrip serialize → deserialize → serialize is stable
5. Schema fingerprint matches specification hash

## 9.5 Pathological Test Vectors

| Vector | Description |
|--------|-------------|
| `unicode_combining` | Combining characters vs precomposed |
| `mixed_normalization` | Mixed NFC/NFD in same string |
| `large_integers` | integers > 2^53 |
| `deep_nesting` | 100+ levels of nested objects |
| `empty_payload` | Empty payload object |
| `all_nulls` | All fields explicitly null |

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
| `test_content_digest_stability` | content_digest is identical across calls |

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
| `test_pathological_unicode` | Combining characters, mixed normalization |
| `test_pathological_integers` | Large integers > 2^53 |
| `test_pathological_nesting` | Deep nesting 100+ levels |
| `test_pathological_empty` | Empty payloads, all-null fields |

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
types.py (depends on specification)
    ↓
timestamp.py (depends on specification)
    ↓
payload.py (depends on specification, types)
    ↓
envelope.py (depends on timestamp, payload, types)
    ↓
serializer.py (depends on envelope, specification)
    ↓
stable_id.py (depends on serializer, envelope)
    ↓
compliance/ (depends on all above)
```

## 12.2 Implementation Sequence

1. `specification.py` — Define rules as constants
2. `types.py` — Shared type definitions (EventType enum)
3. `timestamp.py` — CanonicalTimestamp value object
4. `spec/vectors/` — Write compliance vectors BEFORE serializer (TDD at spec level)
5. `payload.py` — CanonicalPayload value object
6. `envelope.py` — CanonicalEnvelope dataclass
7. `serializer.py` — CanonicalSerializer
8. `stable_id.py` — StableIdGenerator
9. `compliance/validator.py` — Validation runner
10. Tests — All test files

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
| ✅ Compliance | All compliance vectors pass (including pathological) |
| ✅ Roundtrip | serialize → deserialize → serialize is stable |
| ✅ Two versions | rvcj_version and event_schema_version are independent |
| ✅ Semantic content | Experience ID generation follows formal definition |
| ✅ Canonical object | Serializer operates on canonical object graph |
| ✅ Compliance vectors | Language-independent spec artifacts in spec/vectors/ |
| ✅ CanonicalTimestamp | Value object enforces UTC, validation, canonical formatting |
| ✅ Processing pipeline | Validation and canonicalization are distinct |
| ✅ Reserved namespaces | meta/, internal/, experimental/ reserved |
| ✅ Constitutional principle | "Replay consumes canonical events only" documented |

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
| Replay input | Canonical events only | Constitutional principle: replay is unaware of legacy |
| Version axes | rvcj_version + event_schema_version | Independent evolution of envelope format and payload schema |
| Compliance vectors | Language-independent spec artifacts | Vectors define compliance; validator merely executes |
| Serializer method | content_digest() | Avoids Python builtin hash() conflict |
| Canonical object | Intermediate layer | Serializer operates on normalized, validated object graph |
| Payload namespaces | meta/, internal/, experimental/ | Reserved for future extensions |
| Timestamp | CanonicalTimestamp value object | UTC enforcement, validation, canonical formatting |
| Processing pipeline | Validation → Canonicalization | Distinct responsibilities for schema evolution |
| Replay isolation | Constitutional principle | Protects replay from all future compatibility concerns |

---

# 16. Implementation Notes for Integrators

## 16.1 Version Compatibility

v1.4.0 events are **not directly compatible** with v2.0 canonical events. They must be converted by Canonicalization Adapters before replay. The replay engine is intentionally unaware of legacy formats.

## 16.2 Serialization Contract

All implementations must use `CanonicalSerializer.serialize()` to produce canonical bytes. Direct use of `json.dumps()` is forbidden — it produces non-canonical output that breaks determinism.

## 16.3 ID Format

- **Display form:** 12 hexadecimal characters (e.g., `EXP-a1b2c3d4e5f6`)
- **Internal form:** Full SHA-256 hash (256 bits, never truncated)
- **Storage:** Full hash stored for future use; display form used for human interaction

## 16.4 Two Version Axes

- `rvcj_version`: Envelope format version. Changes when envelope structure changes.
- `event_schema_version`: Payload schema version. Changes when payload structure changes.

These evolve independently. A payload schema change does not require an envelope format change, and vice versa.

## 16.5 Reserved Namespaces

The following namespaces are reserved in all payloads:

| Namespace | Purpose | Status |
|-----------|---------|--------|
| `meta/` | System-level metadata | Reserved, unused |
| `internal/` | Internal implementation details | Reserved, unused |
| `experimental/` | Experimental features | Reserved, unused |

Implementations must not use these as payload keys. Future versions may use these for system-level metadata without breaking existing payloads.

---

# Sign-off

This document constitutes the **Phase 1A Design Specification** for the RationaleVault v2.0 Canonical Representation Layer.

**Design Status:** Approved

**Next Phase:** Implementation

**Validation:** Will be validated through the Canonical Compliance Suite and invariant tests.
