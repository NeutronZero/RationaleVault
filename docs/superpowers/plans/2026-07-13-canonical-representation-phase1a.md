# Phase 1A: Canonical Representation Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the canonical representation layer (RVCJ v1) including specification, value objects, serializer, stable IDs, and compliance suite.

**Architecture:** Specification-first development. Compliance vectors are written before the serializer. The serializer operates on a canonical object graph, not arbitrary Python objects. All identifiers are content-hash-based.

**Tech Stack:** Python 3.12+, SHA-256 (hashlib), NFC Unicode normalization (unicodedata), pytest

## Global Constraints

- Python >=3.12
- No external dependencies for core canonical module
- SHA-256 for all hashing (never truncated internally, 12 hex chars display)
- Canonical JSON: lexicographic keys, NFC strings, no whitespace, UTC timestamps
- TDD: write failing test first, then implement
- Frequent commits after each task

---

## File Structure

```
rationalevault/canonical/
├── __init__.py              # Public API exports
├── specification.py         # RVCJ v1 rules as constants (no logic)
├── types.py                 # EventType enum, shared types
├── timestamp.py             # CanonicalTimestamp value object
├── payload.py               # CanonicalPayload value object
├── envelope.py              # CanonicalEnvelope dataclass
├── serializer.py            # CanonicalSerializer
├── stable_id.py             # StableIdGenerator
├── compliance/
│   ├── __init__.py
│   ├── vectors.py           # Loads vectors from spec/vectors/
│   └── validator.py         # Cross-implementation validator
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

spec/vectors/                # Language-independent compliance vectors
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

## Task 1: Specification Constants

**Files:**
- Create: `rationalevault/canonical/__init__.py`
- Create: `rationalevault/canonical/specification.py`
- Create: `rationalevault/canonical/tests/__init__.py`
- Create: `rationalevault/canonical/tests/test_specification.py`

**Interfaces:**
- Consumes: None (foundational)
- Produces: `RVCJ_VERSION`, `EVENT_SCHEMA_VERSION`, `KEY_ORDERING`, `UNICODE_NORMALIZATION`, `TIMESTAMP_FORMAT`, `TIMESTAMP_PRECISION`, `DECIMAL_POLICY`, `BINARY_ENCODING`, `NULL_SEMANTICS`, `HASH_ALGORITHM`, `HASH_DISPLAY_LENGTH`, `HASH_INTERNAL_LENGTH`, `RESERVED_PAYLOAD_NAMESPACES`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p rationalevault/canonical/tests
touch rationalevault/canonical/__init__.py
touch rationalevault/canonical/tests/__init__.py
```

- [ ] **Step 2: Write the failing test**

Create `rationalevault/canonical/tests/test_specification.py`:

```python
from rationalevault.canonical.specification import (
    RVCJ_VERSION,
    EVENT_SCHEMA_VERSION,
    KEY_ORDERING,
    UNICODE_NORMALIZATION,
    TIMESTAMP_FORMAT,
    TIMESTAMP_PRECISION,
    DECIMAL_POLICY,
    BINARY_ENCODING,
    NULL_SEMANTICS,
    HASH_ALGORITHM,
    HASH_DISPLAY_LENGTH,
    HASH_INTERNAL_LENGTH,
    RESERVED_PAYLOAD_NAMESPACES,
)


def test_rvcj_version_is_one():
    assert RVCJ_VERSION == 1


def test_event_schema_version_is_one():
    assert EVENT_SCHEMA_VERSION == 1


def test_key_ordering_is_lexicographic():
    assert KEY_ORDERING == "lexicographic"


def test_unicode_normalization_is_nfc():
    assert UNICODE_NORMALIZATION == "NFC"


def test_timestamp_format_is_rfc3339_utc():
    assert TIMESTAMP_FORMAT == "RFC3339-UTC"


def test_timestamp_precision_is_microsecond():
    assert TIMESTAMP_PRECISION == "microsecond"


def test_decimal_policy_is_canonical_normalization():
    assert DECIMAL_POLICY == "canonical_normalization"


def test_binary_encoding_is_base64():
    assert BINARY_ENCODING == "base64"


def test_null_semantics_is_explicit():
    assert NULL_SEMANTICS == "explicit"


def test_hash_algorithm_is_sha256():
    assert HASH_ALGORITHM == "sha-256"


def test_hash_display_length_is_12():
    assert HASH_DISPLAY_LENGTH == 12


def test_hash_internal_length_is_32():
    assert HASH_INTERNAL_LENGTH == 32


def test_reserved_payload_namespaces():
    assert "meta" in RESERVED_PAYLOAD_NAMESPACES
    assert "internal" in RESERVED_PAYLOAD_NAMESPACES
    assert "experimental" in RESERVED_PAYLOAD_NAMESPACES
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest rationalevault/canonical/tests/test_specification.py -v`
Expected: FAIL with ImportError

- [ ] **Step 4: Write minimal implementation**

Create `rationalevault/canonical/specification.py`:

```python
"""RVCJ v1 Specification — Normative constants, no logic."""

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

RESERVED_PAYLOAD_NAMESPACES = ["meta", "internal", "experimental"]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest rationalevault/canonical/tests/test_specification.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add rationalevault/canonical/
git commit -m "feat(canonical): add RVCJ v1 specification constants"
```

---

## Task 2: Shared Types

**Files:**
- Create: `rationalevault/canonical/types.py`
- Create: `rationalevault/canonical/tests/test_types.py`

**Interfaces:**
- Consumes: specification constants
- Produces: `EventType` class with `register()` and `get()` methods

- [ ] **Step 1: Write the failing test**

Create `rationalevault/canonical/tests/test_types.py`:

```python
from rationalevault.canonical.types import EventType


def test_event_type_register_and_get():
    EventType.register("decision_recorded")
    et = EventType.get("decision_recorded")
    assert et.name == "decision_recorded"


def test_event_type_get_unknown_raises():
    import pytest
    with pytest.raises(KeyError):
        EventType.get("unknown_event")


def test_event_type_is_hashable():
    EventType.register("test_event")
    et = EventType.get("test_event")
    assert hash(et) is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest rationalevault/canonical/tests/test_types.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Write minimal implementation**

Create `rationalevault/canonical/types.py`:

```python
"""Shared types for canonical representation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EventType:
    """Registered event type for replay dispatch."""
    
    name: str
    
    _registry: dict[str, EventType] = {}
    
    @classmethod
    def register(cls, name: str) -> EventType:
        """Register a new event type."""
        if name in cls._registry:
            return cls._registry[name]
        et = cls(name=name)
        cls._registry[name] = et
        return et
    
    @classmethod
    def get(cls, name: str) -> EventType:
        """Get a registered event type."""
        if name not in cls._registry:
            raise KeyError(f"Unknown event type: {name}")
        return cls._registry[name]
    
    @classmethod
    def is_registered(cls, name: str) -> bool:
        """Check if an event type is registered."""
        return name in cls._registry
    
    @classmethod
    def clear(cls) -> None:
        """Clear all registered event types (for testing)."""
        cls._registry.clear()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest rationalevault/canonical/tests/test_types.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add rationalevault/canonical/types.py rationalevault/canonical/tests/test_types.py
git commit -m "feat(canonical): add EventType registry"
```

---

## Task 3: CanonicalTimestamp Value Object

**Files:**
- Create: `rationalevault/canonical/timestamp.py`
- Create: `rationalevault/canonical/tests/test_timestamp.py`

**Interfaces:**
- Consumes: specification constants
- Produces: `CanonicalTimestamp` with `to_iso8601()`, `from_datetime()`, `from_iso8601()`

- [ ] **Step 1: Write the failing test**

Create `rationalevault/canonical/tests/test_timestamp.py`:

```python
from datetime import datetime, timezone, timedelta
import pytest

from rationalevault.canonical.timestamp import CanonicalTimestamp


def test_timestamp_from_datetime_utc():
    dt = datetime(2026, 7, 13, 14, 35, 42, 123456, tzinfo=timezone.utc)
    ts = CanonicalTimestamp.from_datetime(dt)
    assert ts.to_iso8601() == "2026-07-13T14:35:42.123456Z"


def test_timestamp_from_datetime_converts_to_utc():
    est = timezone(timedelta(hours=-5))
    dt = datetime(2026, 7, 13, 9, 35, 42, 123456, tzinfo=est)
    ts = CanonicalTimestamp.from_datetime(dt)
    assert ts.to_iso8601() == "2026-07-13T14:35:42.123456Z"


def test_timestamp_from_naive_raises():
    dt = datetime(2026, 7, 13, 14, 35, 42, 123456)
    with pytest.raises(ValueError, match="timezone-aware"):
        CanonicalTimestamp.from_datetime(dt)


def test_timestamp_from_iso8601():
    ts = CanonicalTimestamp.from_iso8601("2026-07-13T14:35:42.123456Z")
    assert ts.to_iso8601() == "2026-07-13T14:35:42.123456Z"


def test_timestamp_to_dict():
    dt = datetime(2026, 7, 13, 14, 35, 42, 123456, tzinfo=timezone.utc)
    ts = CanonicalTimestamp.from_datetime(dt)
    assert ts.to_dict() == "2026-07-13T14:35:42.123456Z"


def test_timestamp_immutable():
    dt = datetime(2026, 7, 13, 14, 35, 42, 123456, tzinfo=timezone.utc)
    ts = CanonicalTimestamp.from_datetime(dt)
    with pytest.raises(AttributeError):
        ts.value = datetime.now(timezone.utc)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest rationalevault/canonical/tests/test_timestamp.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Write minimal implementation**

Create `rationalevault/canonical/timestamp.py`:

```python
"""CanonicalTimestamp — immutable value object for UTC timestamps."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True, slots=True)
class CanonicalTimestamp:
    """Immutable UTC timestamp with RFC 3339 formatting."""
    
    value: datetime
    
    def __post_init__(self) -> None:
        """Enforce UTC and microsecond precision."""
        if self.value.tzinfo is None:
            raise ValueError("Timestamp must be timezone-aware")
        if self.value.tzinfo != timezone.utc:
            object.__setattr__(self, "value", self.value.astimezone(timezone.utc))
    
    def to_iso8601(self) -> str:
        """Return RFC 3339 formatted string: YYYY-MM-DDTHH:MM:SS.ffffffZ"""
        return self.value.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    
    def to_dict(self) -> str:
        """Return canonical string representation."""
        return self.to_iso8601()
    
    @classmethod
    def from_datetime(cls, dt: datetime) -> CanonicalTimestamp:
        """Create from datetime object."""
        return cls(value=dt)
    
    @classmethod
    def from_iso8601(cls, s: str) -> CanonicalTimestamp:
        """Create from ISO 8601 string."""
        if not s.endswith("Z"):
            raise ValueError(f"Timestamp must end with Z: {s}")
        dt = datetime.strptime(s[:-1], "%Y-%m-%dT%H:%M:%S.%f").replace(
            tzinfo=timezone.utc
        )
        return cls(value=dt)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest rationalevault/canonical/tests/test_timestamp.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add rationalevault/canonical/timestamp.py rationalevault/canonical/tests/test_timestamp.py
git commit -m "feat(canonical): add CanonicalTimestamp value object"
```

---

## Task 4: Compliance Vectors (TDD — Before Serializer)

**Files:**
- Create: `spec/vectors/key_ordering.json`
- Create: `spec/vectors/unicode_normalization.json`
- Create: `spec/vectors/decimal_normalization.json`
- Create: `spec/vectors/timestamp_format.json`
- Create: `spec/vectors/null_semantics.json`
- Create: `spec/vectors/binary_encoding.json`
- Create: `spec/vectors/array_ordering.json`
- Create: `spec/vectors/deep_nesting.json`
- Create: `spec/vectors/empty_payload.json`
- Create: `spec/vectors/large_integers.json`
- Create: `spec/vectors/unicode_combining.json`
- Create: `spec/vectors/mixed_normalization.json`

**Interfaces:**
- Consumes: specification rules
- Produces: Language-independent test vectors for serializer validation

- [ ] **Step 1: Create vectors directory**

```bash
mkdir -p spec/vectors
```

- [ ] **Step 2: Write key_ordering.json**

```json
{
  "name": "key_ordering",
  "description": "Object keys must be sorted lexicographically",
  "input": {"z": 1, "a": 2, "m": 3},
  "expected_canonical": "{\"a\":2,\"m\":3,\"z\":1}",
  "expected_hash": null,
  "expected_deserialized": {"a": 2, "m": 3, "z": 1}
}
```

- [ ] **Step 3: Write unicode_normalization.json**

```json
{
  "name": "unicode_normalization",
  "description": "Strings must be NFC normalized",
  "input": {"key": "caf\u0065\u0301"},
  "expected_canonical": "{\"key\":\"caf\u00e9\"}",
  "expected_hash": null,
  "expected_deserialized": {"key": "caf\u00e9"}
}
```

- [ ] **Step 4: Write decimal_normalization.json**

```json
{
  "name": "decimal_normalization",
  "description": "Decimals must be canonicalized (no trailing zeros)",
  "input": {"a": 0.5, "b": 0.50, "c": 1.0, "d": 0.001},
  "expected_canonical": "{\"a\":0.5,\"b\":0.5,\"c\":1.0,\"d\":0.001}",
  "expected_hash": null,
  "expected_deserialized": {"a": 0.5, "b": 0.5, "c": 1.0, "d": 0.001}
}
```

- [ ] **Step 5: Write timestamp_format.json**

```json
{
  "name": "timestamp_format",
  "description": "Timestamps must be RFC 3339 UTC with microsecond precision",
  "input": {"ts": "2026-07-13T14:35:42.123456Z"},
  "expected_canonical": "{\"ts\":\"2026-07-13T14:35:42.123456Z\"}",
  "expected_hash": null,
  "expected_deserialized": {"ts": "2026-07-13T14:35:42.123456Z"}
}
```

- [ ] **Step 6: Write null_semantics.json**

```json
{
  "name": "null_semantics",
  "description": "Missing, null, and default are distinct states",
  "input": {"present": "value", "explicit_null": null},
  "expected_canonical": "{\"explicit_null\":null,\"present\":\"value\"}",
  "expected_hash": null,
  "expected_deserialized": {"explicit_null": null, "present": "value"}
}
```

- [ ] **Step 7: Write binary_encoding.json**

```json
{
  "name": "binary_encoding",
  "description": "Binary data must be base64 encoded",
  "input": {"data": "AAE="},
  "expected_canonical": "{\"data\":\"AAE=\"}",
  "expected_hash": null,
  "expected_deserialized": {"data": "AAE="}
}
```

- [ ] **Step 8: Write array_ordering.json**

```json
{
  "name": "array_ordering",
  "description": "Arrays preserve insertion order, never sorted",
  "input": {"items": [3, 1, 2]},
  "expected_canonical": "{\"items\":[3,1,2]}",
  "expected_hash": null,
  "expected_deserialized": {"items": [3, 1, 2]}
}
```

- [ ] **Step 9: Write deep_nesting.json**

```json
{
  "name": "deep_nesting",
  "description": "Deeply nested objects are recursively canonicalized",
  "input": {"a": {"b": {"c": {"z": 1, "a": 2}}}},
  "expected_canonical": "{\"a\":{\"b\":{\"c\":{\"a\":2,\"z\":1}}}}",
  "expected_hash": null,
  "expected_deserialized": {"a": {"b": {"c": {"a": 2, "z": 1}}}}
}
```

- [ ] **Step 10: Write empty_payload.json**

```json
{
  "name": "empty_payload",
  "description": "Empty objects are valid",
  "input": {},
  "expected_canonical": "{}",
  "expected_hash": null,
  "expected_deserialized": {}
}
```

- [ ] **Step 11: Write large_integers.json**

```json
{
  "name": "large_integers",
  "description": "Large integers are preserved exactly",
  "input": {"big": 9007199254740993},
  "expected_canonical": "{\"big\":9007199254740993}",
  "expected_hash": null,
  "expected_deserialized": {"big": 9007199254740993}
}
```

- [ ] **Step 12: Write unicode_combining.json**

```json
{
  "name": "unicode_combining",
  "description": "Combining characters are normalized to NFC",
  "input": {"text": "e\u0301"},
  "expected_canonical": "{\"text\":\"\u00e9\"}",
  "expected_hash": null,
  "expected_deserialized": {"text": "\u00e9"}
}
```

- [ ] **Step 13: Write mixed_normalization.json**

```json
{
  "name": "mixed_normalization",
  "description": "Mixed NFC/NFD strings are normalized to NFC",
  "input": {"text": "cafe\u0301"},
  "expected_canonical": "{\"text\":\"caf\u00e9\"}",
  "expected_hash": null,
  "expected_deserialized": {"text": "caf\u00e9"}
}
```

- [ ] **Step 14: Commit**

```bash
git add spec/vectors/
git commit -m "feat(canonical): add compliance vectors (TDD before serializer)"
```

---

## Task 5: CanonicalPayload Value Object

**Files:**
- Create: `rationalevault/canonical/payload.py`
- Create: `rationalevault/canonical/tests/test_payload.py`

**Interfaces:**
- Consumes: specification constants
- Produces: `CanonicalPayload` with `validate()`, `canonicalize()`, `content_digest()`

- [ ] **Step 1: Write the failing test**

Create `rationalevault/canonical/tests/test_payload.py`:

```python
import pytest

from rationalevault.canonical.payload import CanonicalPayload


def test_payload_from_dict():
    p = CanonicalPayload.from_dict({"key": "value"})
    assert p.data == {"key": "value"}


def test_payload_to_dict():
    p = CanonicalPayload(data={"key": "value"})
    assert p.to_dict() == {"key": "value"}


def test_payload_canonicalize_sorts_keys():
    p = CanonicalPayload(data={"z": 1, "a": 2})
    c = p.canonicalize()
    assert list(c.data.keys()) == ["a", "z"]


def test_payload_canonicalize_normalizes_unicode():
    p = CanonicalPayload(data={"key": "caf\u0065\u0301"})
    c = p.canonicalize()
    assert c.data["key"] == "caf\u00e9"


def test_payload_validate_missing_required():
    p = CanonicalPayload(data={"extra": "value"})
    with pytest.raises(ValueError, match="missing"):
        p.validate(required={"key"})


def test_payload_validate_rejects_reserved_namespace():
    p = CanonicalPayload(data={"meta": {"version": 1}})
    with pytest.raises(ValueError, match="reserved"):
        p.validate()


def test_payload_content_digest_deterministic():
    p1 = CanonicalPayload(data={"a": 1, "b": 2})
    p2 = CanonicalPayload(data={"b": 2, "a": 1})
    assert p1.canonicalize().content_digest() == p2.canonicalize().content_digest()


def test_payload_immutable():
    p = CanonicalPayload(data={"key": "value"})
    with pytest.raises(AttributeError):
        p.data = {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest rationalevault/canonical/tests/test_payload.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Write minimal implementation**

Create `rationalevault/canonical/payload.py`:

```python
"""CanonicalPayload — immutable value object for domain data."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from rationalevault.canonical.specification import (
    KEY_ORDERING,
    RESERVED_PAYLOAD_NAMESPACES,
    UNICODE_NORMALIZATION,
)


def _canonicalize_value(value: Any) -> Any:
    """Recursively canonicalize a value."""
    if isinstance(value, dict):
        return _canonicalize_dict(value)
    elif isinstance(value, str):
        import unicodedata
        return unicodedata.normalize(UNICODE_NORMALIZATION, value)
    elif isinstance(value, list):
        return [_canonicalize_value(item) for item in value]
    else:
        return value


def _canonicalize_dict(d: dict[str, Any]) -> dict[str, Any]:
    """Canonicalize a dictionary (sorted keys, normalized values)."""
    return {k: _canonicalize_value(d[k]) for k in sorted(d.keys())}


@dataclass(frozen=True, slots=True)
class CanonicalPayload:
    """Immutable payload with canonicalization rules."""
    
    data: dict[str, Any] = field(default_factory=dict)
    
    def validate(self, required: set[str] | None = None) -> None:
        """Validate payload against constraints.
        
        Answers: Is this payload legal?
        """
        if required:
            missing = required - set(self.data.keys())
            if missing:
                raise ValueError(f"Missing required fields: {missing}")
        
        for key in self.data.keys():
            if key in RESERVED_PAYLOAD_NAMESPACES:
                raise ValueError(f"Reserved namespace: {key}")
    
    def canonicalize(self) -> CanonicalPayload:
        """Return canonical form of payload.
        
        Answers: What is its unique canonical form?
        """
        return CanonicalPayload(data=_canonicalize_dict(self.data))
    
    def content_digest(self) -> str:
        """Produce deterministic SHA-256 hash of canonical payload."""
        canonical = self.canonicalize()
        canonical_bytes = json.dumps(
            canonical.data, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(canonical_bytes).hexdigest()
    
    def to_dict(self) -> dict[str, Any]:
        """Return raw data dict."""
        return dict(self.data)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CanonicalPayload:
        """Create from dictionary."""
        return cls(data=dict(data))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest rationalevault/canonical/tests/test_payload.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add rationalevault/canonical/payload.py rationalevault/canonical/tests/test_payload.py
git commit -m "feat(canonical): add CanonicalPayload value object"
```

---

## Task 6: CanonicalEnvelope Dataclass

**Files:**
- Create: `rationalevault/canonical/envelope.py`
- Create: `rationalevault/canonical/tests/test_envelope.py`

**Interfaces:**
- Consumes: `CanonicalTimestamp`, `CanonicalPayload`, `EventType`
- Produces: `CanonicalEnvelope` with `to_dict()`, `from_dict()`

- [ ] **Step 1: Write the failing test**

Create `rationalevault/canonical/tests/test_envelope.py`:

```python
from datetime import datetime, timezone

import pytest

from rationalevault.canonical.envelope import CanonicalEnvelope
from rationalevault.canonical.payload import CanonicalPayload
from rationalevault.canonical.timestamp import CanonicalTimestamp
from rationalevault.canonical.types import EventType


@pytest.fixture(autouse=True)
def register_event_type():
    EventType.register("test_event")
    yield
    EventType.clear()


def test_envelope_create():
    ts = CanonicalTimestamp.from_datetime(
        datetime(2026, 7, 13, 14, 35, 42, 123456, tzinfo=timezone.utc)
    )
    env = CanonicalEnvelope(
        rvcj_version=1,
        event_schema_version=1,
        experience_id="EXP-a1b2c3d4e5f6",
        event_type=EventType.get("test_event"),
        stream_id="project-42",
        sequence=1,
        timestamp=ts,
        actor="agent-001",
        payload=CanonicalPayload(data={"key": "value"}),
    )
    assert env.rvcj_version == 1
    assert env.event_type.name == "test_event"


def test_envelope_to_dict():
    ts = CanonicalTimestamp.from_datetime(
        datetime(2026, 7, 13, 14, 35, 42, 123456, tzinfo=timezone.utc)
    )
    env = CanonicalEnvelope(
        rvcj_version=1,
        event_schema_version=1,
        experience_id="EXP-a1b2c3d4e5f6",
        event_type=EventType.get("test_event"),
        stream_id="project-42",
        sequence=1,
        timestamp=ts,
        actor="agent-001",
        payload=CanonicalPayload(data={"key": "value"}),
    )
    d = env.to_dict()
    assert d["rvcj_version"] == 1
    assert d["event_type"] == "test_event"
    assert d["timestamp"] == "2026-07-13T14:35:42.123456Z"
    assert d["payload"] == {"key": "value"}


def test_envelope_from_dict():
    d = {
        "rvcj_version": 1,
        "event_schema_version": 1,
        "experience_id": "EXP-a1b2c3d4e5f6",
        "event_type": "test_event",
        "stream_id": "project-42",
        "sequence": 1,
        "timestamp": "2026-07-13T14:35:42.123456Z",
        "actor": "agent-001",
        "payload": {"key": "value"},
    }
    env = CanonicalEnvelope.from_dict(d)
    assert env.rvcj_version == 1
    assert env.event_type.name == "test_event"
    assert env.timestamp.to_iso8601() == "2026-07-13T14:35:42.123456Z"


def test_envelope_optional_fields():
    d = {
        "rvcj_version": 1,
        "event_schema_version": 1,
        "experience_id": "EXP-a1b2c3d4e5f6",
        "event_type": "test_event",
        "stream_id": "project-42",
        "sequence": 1,
        "timestamp": "2026-07-13T14:35:42.123456Z",
        "actor": "agent-001",
        "payload": {"key": "value"},
        "correlation_id": "ctx-123",
        "causation_id": "EVT-456",
    }
    env = CanonicalEnvelope.from_dict(d)
    assert env.correlation_id == "ctx-123"
    assert env.causation_id == "EVT-456"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest rationalevault/canonical/tests/test_envelope.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Write minimal implementation**

Create `rationalevault/canonical/envelope.py`:

```python
"""CanonicalEnvelope — three-layer event structure."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rationalevault.canonical.payload import CanonicalPayload
from rationalevault.canonical.timestamp import CanonicalTimestamp
from rationalevault.canonical.types import EventType


@dataclass(frozen=True, slots=True)
class CanonicalEnvelope:
    """Immutable canonical event envelope."""
    
    rvcj_version: int
    event_schema_version: int
    experience_id: str
    event_type: EventType
    stream_id: str
    sequence: int
    timestamp: CanonicalTimestamp
    actor: str
    payload: CanonicalPayload
    correlation_id: str | None = None
    causation_id: str | None = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary (for serialization)."""
        d: dict[str, Any] = {
            "rvcj_version": self.rvcj_version,
            "event_schema_version": self.event_schema_version,
            "experience_id": self.experience_id,
            "event_type": self.event_type.name,
            "stream_id": self.stream_id,
            "sequence": self.sequence,
            "timestamp": self.timestamp.to_dict(),
            "actor": self.actor,
            "payload": self.payload.to_dict(),
        }
        if self.correlation_id is not None:
            d["correlation_id"] = self.correlation_id
        if self.causation_id is not None:
            d["causation_id"] = self.causation_id
        return d
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CanonicalEnvelope:
        """Create from dictionary."""
        return cls(
            rvcj_version=data["rvcj_version"],
            event_schema_version=data["event_schema_version"],
            experience_id=data["experience_id"],
            event_type=EventType.get(data["event_type"]),
            stream_id=data["stream_id"],
            sequence=data["sequence"],
            timestamp=CanonicalTimestamp.from_iso8601(data["timestamp"]),
            actor=data["actor"],
            payload=CanonicalPayload.from_dict(data["payload"]),
            correlation_id=data.get("correlation_id"),
            causation_id=data.get("causation_id"),
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest rationalevault/canonical/tests/test_envelope.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add rationalevault/canonical/envelope.py rationalevault/canonical/tests/test_envelope.py
git commit -m "feat(canonical): add CanonicalEnvelope dataclass"
```

---

## Task 7: CanonicalSerializer

**Files:**
- Create: `rationalevault/canonical/serializer.py`
- Create: `rationalevault/canonical/tests/test_serializer.py`

**Interfaces:**
- Consumes: `CanonicalEnvelope`, `CanonicalPayload`, specification constants
- Produces: `CanonicalSerializer` with `serialize()`, `deserialize()`, `content_digest()`, `version()`, `schema_fingerprint()`, `algorithm()`

- [ ] **Step 1: Write the failing test**

Create `rationalevault/canonical/tests/test_serializer.py`:

```python
from datetime import datetime, timezone
import hashlib

import pytest

from rationalevault.canonical.envelope import CanonicalEnvelope
from rationalevault.canonical.payload import CanonicalPayload
from rationalevault.canonical.serializer import CanonicalSerializer
from rationalevault.canonical.timestamp import CanonicalTimestamp
from rationalevault.canonical.types import EventType


@pytest.fixture(autouse=True)
def register_event_type():
    EventType.register("test_event")
    yield
    EventType.clear()


def _make_envelope(**overrides) -> CanonicalEnvelope:
    defaults = {
        "rvcj_version": 1,
        "event_schema_version": 1,
        "experience_id": "EXP-a1b2c3d4e5f6",
        "event_type": EventType.get("test_event"),
        "stream_id": "project-42",
        "sequence": 1,
        "timestamp": CanonicalTimestamp.from_datetime(
            datetime(2026, 7, 13, 14, 35, 42, 123456, tzinfo=timezone.utc)
        ),
        "actor": "agent-001",
        "payload": CanonicalPayload(data={"key": "value"}),
    }
    defaults.update(overrides)
    return CanonicalEnvelope(**defaults)


def test_serialize_deterministic():
    env = _make_envelope()
    b1 = CanonicalSerializer.serialize(env)
    b2 = CanonicalSerializer.serialize(env)
    assert b1 == b2


def test_serialize_no_whitespace():
    env = _make_envelope()
    b = CanonicalSerializer.serialize(env)
    assert b"{\" in b
    assert b": " not in b


def test_serialize_canonical_keys():
    env = _make_envelope(
        payload=CanonicalPayload(data={"z": 1, "a": 2})
    )
    b = CanonicalSerializer.serialize(env)
    assert b.index(b"\"a\"") < b.index(b"\"z\"")


def test_deserialize_roundtrip():
    env = _make_envelope()
    b = CanonicalSerializer.serialize(env)
    env2 = CanonicalSerializer.deserialize(b)
    assert env == env2


def test_content_digest_deterministic():
    env = _make_envelope()
    d1 = CanonicalSerializer.content_digest(env)
    d2 = CanonicalSerializer.content_digest(env)
    assert d1 == d2
    assert len(d1) == 64  # full SHA-256 hex


def test_content_digest_display_length():
    env = _make_envelope()
    d = CanonicalSerializer.content_digest(env)
    assert len(d) == 64  # full hash
    # Display form is 12 chars
    display = d[:12]
    assert len(display) == 12


def test_version():
    assert CanonicalSerializer.version() == 1


def test_algorithm():
    assert CanonicalSerializer.algorithm() == "sha-256"


def test_schema_fingerprint():
    fp = CanonicalSerializer.schema_fingerprint()
    assert isinstance(fp, str)
    assert len(fp) == 64  # SHA-256 hex
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest rationalevault/canonical/tests/test_serializer.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Write minimal implementation**

Create `rationalevault/canonical/serializer.py`:

```python
"""CanonicalSerializer — the only path to canonical bytes."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from rationalevault.canonical.envelope import CanonicalEnvelope
from rationalevault.canonical.specification import (
    HASH_ALGORITHM,
    RVCJ_VERSION,
    UNICODE_NORMALIZATION,
)


def _canonicalize(obj: Any) -> Any:
    """Recursively canonicalize any Python object for JSON."""
    if isinstance(obj, dict):
        return {k: _canonicalize(obj[k]) for k in sorted(obj.keys())}
    elif isinstance(obj, str):
        import unicodedata
        return unicodedata.normalize(UNICODE_NORMALIZATION, obj)
    elif isinstance(obj, list):
        return [_canonicalize(item) for item in obj]
    else:
        return obj


def _canonical_bytes(envelope: CanonicalEnvelope) -> bytes:
    """Produce canonical JSON bytes from envelope."""
    d = envelope.to_dict()
    canonical = _canonicalize(d)
    return json.dumps(canonical, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


class CanonicalSerializer:
    """The only path to canonical bytes."""
    
    @staticmethod
    def serialize(envelope: CanonicalEnvelope) -> bytes:
        """Serialize envelope to canonical JSON bytes (RVCJ v1)."""
        return _canonical_bytes(envelope)
    
    @staticmethod
    def deserialize(data: bytes) -> CanonicalEnvelope:
        """Deserialize canonical bytes to envelope."""
        d = json.loads(data)
        return CanonicalEnvelope.from_dict(d)
    
    @staticmethod
    def content_digest(envelope: CanonicalEnvelope) -> str:
        """Produce deterministic SHA-256 hash of canonical bytes.
        
        Returns full 64-character hex hash.
        Display form uses 12 characters.
        """
        return hashlib.sha256(_canonical_bytes(envelope)).hexdigest()
    
    @staticmethod
    def version() -> int:
        """Return RVCJ version of this serializer."""
        return RVCJ_VERSION
    
    @staticmethod
    def schema_fingerprint() -> str:
        """Return the schema fingerprint for this serializer version."""
        spec_text = json.dumps(
            {
                "rvcj_version": RVCJ_VERSION,
                "key_ordering": "lexicographic",
                "unicode_normalization": UNICODE_NORMALIZATION,
                "hash_algorithm": HASH_ALGORITHM,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(spec_text.encode("utf-8")).hexdigest()
    
    @staticmethod
    def algorithm() -> str:
        """Return the hash algorithm used."""
        return HASH_ALGORITHM
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest rationalevault/canonical/tests/test_serializer.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add rationalevault/canonical/serializer.py rationalevault/canonical/tests/test_serializer.py
git commit -m "feat(canonical): add CanonicalSerializer"
```

---

## Task 8: StableIdGenerator

**Files:**
- Create: `rationalevault/canonical/stable_id.py`
- Create: `rationalevault/canonical/tests/test_stable_id.py`

**Interfaces:**
- Consumes: `CanonicalEnvelope`, `CanonicalPayload`, specification constants
- Produces: `StableIdGenerator` with `experience_id()`, `event_id()`, `projection_id()`

- [ ] **Step 1: Write the failing test**

Create `rationalevault/canonical/tests/test_stable_id.py`:

```python
from datetime import datetime, timezone

import pytest

from rationalevault.canonical.envelope import CanonicalEnvelope
from rationalevault.canonical.payload import CanonicalPayload
from rationalevault.canonical.stable_id import StableIdGenerator
from rationalevault.canonical.timestamp import CanonicalTimestamp
from rationalevault.canonical.types import EventType


@pytest.fixture(autouse=True)
def register_event_type():
    EventType.register("test_event")
    yield
    EventType.clear()


def _make_envelope(**overrides) -> CanonicalEnvelope:
    defaults = {
        "rvcj_version": 1,
        "event_schema_version": 1,
        "experience_id": "EXP-a1b2c3d4e5f6",
        "event_type": EventType.get("test_event"),
        "stream_id": "project-42",
        "sequence": 1,
        "timestamp": CanonicalTimestamp.from_datetime(
            datetime(2026, 7, 13, 14, 35, 42, 123456, tzinfo=timezone.utc)
        ),
        "actor": "agent-001",
        "payload": CanonicalPayload(data={"key": "value"}),
    }
    defaults.update(overrides)
    return CanonicalEnvelope(**defaults)


def test_experience_id_deterministic():
    content = {"event_type": "test", "payload": {"key": "value"}}
    id1 = StableIdGenerator.experience_id(content)
    id2 = StableIdGenerator.experience_id(content)
    assert id1 == id2


def test_experience_id_unique():
    id1 = StableIdGenerator.experience_id({"a": 1})
    id2 = StableIdGenerator.experience_id({"a": 2})
    assert id1 != id2


def test_experience_id_format():
    eid = StableIdGenerator.experience_id({"key": "value"})
    assert eid.startswith("EXP-")
    assert len(eid) == 4 + 12  # "EXP-" + 12 hex chars


def test_event_id_deterministic():
    env = _make_envelope()
    id1 = StableIdGenerator.event_id(env)
    id2 = StableIdGenerator.event_id(env)
    assert id1 == id2


def test_event_id_format():
    env = _make_envelope()
    eid = StableIdGenerator.event_id(env)
    assert eid.startswith("EVT-")
    assert len(eid) == 4 + 12


def test_projection_id_format():
    pid = StableIdGenerator.projection_id({"key": "value"})
    assert pid.startswith("PRJ-")
    assert len(pid) == 4 + 12
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest rationalevault/canonical/tests/test_stable_id.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Write minimal implementation**

Create `rationalevault/canonical/stable_id.py`:

```python
"""StableIdGenerator — content-hash-based identifiers."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from rationalevault.canonical.envelope import CanonicalEnvelope
from rationalevault.canonical.specification import HASH_DISPLAY_LENGTH


def _hash_prefix(data: bytes, length: int = HASH_DISPLAY_LENGTH) -> str:
    """Return hex prefix of SHA-256 hash."""
    return hashlib.sha256(data).hexdigest()[:length]


class StableIdGenerator:
    """Content-hash-based identifiers."""
    
    HASH_DISPLAY_LENGTH = HASH_DISPLAY_LENGTH
    
    @staticmethod
    def experience_id(content: dict[str, Any]) -> str:
        """Generate stable experience ID from semantic content.
        
        Semantic content = event_type + payload.
        Excludes: timestamp, sequence, stream_id, actor, correlation_id, causation_id.
        """
        canonical = json.dumps(content, sort_keys=True, separators=(",", ":"))
        return f"EXP-{_hash_prefix(canonical.encode('utf-8'))}"
    
    @staticmethod
    def event_id(envelope: CanonicalEnvelope) -> str:
        """Generate stable event ID from canonical envelope."""
        from rationalevault.canonical.serializer import CanonicalSerializer
        canonical_bytes = CanonicalSerializer.serialize(envelope)
        return f"EVT-{_hash_prefix(canonical_bytes)}"
    
    @staticmethod
    def projection_id(content: dict[str, Any]) -> str:
        """Generate stable projection ID from content."""
        canonical = json.dumps(content, sort_keys=True, separators=(",", ":"))
        return f"PRJ-{_hash_prefix(canonical.encode('utf-8'))}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest rationalevault/canonical/tests/test_stable_id.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add rationalevault/canonical/stable_id.py rationalevault/canonical/tests/test_stable_id.py
git commit -m "feat(canonical): add StableIdGenerator"
```

---

## Task 9: Roundtrip Tests

**Files:**
- Create: `rationalevault/canonical/tests/test_roundtrip.py`

**Interfaces:**
- Consumes: `CanonicalSerializer`, `CanonicalEnvelope`
- Produces: Roundtrip stability validation

- [ ] **Step 1: Write the failing test**

Create `rationalevault/canonical/tests/test_roundtrip.py`:

```python
from datetime import datetime, timezone

import pytest

from rationalevault.canonical.envelope import CanonicalEnvelope
from rationalevault.canonical.payload import CanonicalPayload
from rationalevault.canonical.serializer import CanonicalSerializer
from rationalevault.canonical.stable_id import StableIdGenerator
from rationalevault.canonical.timestamp import CanonicalTimestamp
from rationalevault.canonical.types import EventType


@pytest.fixture(autouse=True)
def register_event_type():
    EventType.register("test_event")
    yield
    EventType.clear()


def test_serialize_deserialize_roundtrip():
    env = CanonicalEnvelope(
        rvcj_version=1,
        event_schema_version=1,
        experience_id="EXP-a1b2c3d4e5f6",
        event_type=EventType.get("test_event"),
        stream_id="project-42",
        sequence=1,
        timestamp=CanonicalTimestamp.from_datetime(
            datetime(2026, 7, 13, 14, 35, 42, 123456, tzinfo=timezone.utc)
        ),
        actor="agent-001",
        payload=CanonicalPayload(data={"key": "value"}),
    )
    b = CanonicalSerializer.serialize(env)
    env2 = CanonicalSerializer.deserialize(b)
    b2 = CanonicalSerializer.serialize(env2)
    assert b == b2


def test_content_digest_stability():
    env = CanonicalEnvelope(
        rvcj_version=1,
        event_schema_version=1,
        experience_id="EXP-a1b2c3d4e5f6",
        event_type=EventType.get("test_event"),
        stream_id="project-42",
        sequence=1,
        timestamp=CanonicalTimestamp.from_datetime(
            datetime(2026, 7, 13, 14, 35, 42, 123456, tzinfo=timezone.utc)
        ),
        actor="agent-001",
        payload=CanonicalPayload(data={"key": "value"}),
    )
    d1 = CanonicalSerializer.content_digest(env)
    d2 = CanonicalSerializer.content_digest(env)
    assert d1 == d2


def test_experience_id_stability():
    content = {"event_type": "test", "payload": {"key": "value"}}
    id1 = StableIdGenerator.experience_id(content)
    id2 = StableIdGenerator.experience_id(content)
    assert id1 == id2


def test_unicode_roundtrip():
    env = CanonicalEnvelope(
        rvcj_version=1,
        event_schema_version=1,
        experience_id="EXP-a1b2c3d4e5f6",
        event_type=EventType.get("test_event"),
        stream_id="project-42",
        sequence=1,
        timestamp=CanonicalTimestamp.from_datetime(
            datetime(2026, 7, 13, 14, 35, 42, 123456, tzinfo=timezone.utc)
        ),
        actor="agent-001",
        payload=CanonicalPayload(data={"text": "caf\u00e9"}),
    )
    b = CanonicalSerializer.serialize(env)
    env2 = CanonicalSerializer.deserialize(b)
    assert env2.payload.data["text"] == "caf\u00e9"


def test_nested_payload_roundtrip():
    env = CanonicalEnvelope(
        rvcj_version=1,
        event_schema_version=1,
        experience_id="EXP-a1b2c3d4e5f6",
        event_type=EventType.get("test_event"),
        stream_id="project-42",
        sequence=1,
        timestamp=CanonicalTimestamp.from_datetime(
            datetime(2026, 7, 13, 14, 35, 42, 123456, tzinfo=timezone.utc)
        ),
        actor="agent-001",
        payload=CanonicalPayload(data={"a": {"b": {"c": 1}}}),
    )
    b = CanonicalSerializer.serialize(env)
    env2 = CanonicalSerializer.deserialize(b)
    assert env2.payload.data == {"a": {"b": {"c": 1}}}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest rationalevault/canonical/tests/test_roundtrip.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Create empty test file (tests will pass once imports work)**

Create `rationalevault/canonical/tests/test_roundtrip.py` (already created above)

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest rationalevault/canonical/tests/test_roundtrip.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add rationalevault/canonical/tests/test_roundtrip.py
git commit -m "test(canonical): add roundtrip stability tests"
```

---

## Task 10: Compliance Suite

**Files:**
- Create: `rationalevault/canonical/compliance/__init__.py`
- Create: `rationalevault/canonical/compliance/vectors.py`
- Create: `rationalevault/canonical/compliance/validator.py`
- Create: `rationalevault/canonical/tests/test_compliance.py`

**Interfaces:**
- Consumes: `spec/vectors/*.json`, `CanonicalSerializer`
- Produces: Compliance validation results

- [ ] **Step 1: Create compliance directory**

```bash
mkdir -p rationalevault/canonical/compliance
touch rationalevault/canonical/compliance/__init__.py
```

- [ ] **Step 2: Write the failing test**

Create `rationalevault/canonical/tests/test_compliance.py`:

```python
import pytest

from rationalevault.canonical.compliance.validator import ComplianceValidator


def test_compliance_vectors_exist():
    vectors = ComplianceValidator.load_vectors()
    assert len(vectors) > 0


def test_compliance_key_ordering():
    result = ComplianceValidator.validate_vector("key_ordering")
    assert result.passed, result.message


def test_compliance_unicode_normalization():
    result = ComplianceValidator.validate_vector("unicode_normalization")
    assert result.passed, result.message


def test_compliance_decimal_normalization():
    result = ComplianceValidator.validate_vector("decimal_normalization")
    assert result.passed, result.message


def test_compliance_timestamp_format():
    result = ComplianceValidator.validate_vector("timestamp_format")
    assert result.passed, result.message


def test_compliance_null_semantics():
    result = ComplianceValidator.validate_vector("null_semantics")
    assert result.passed, result.message


def test_compliance_array_ordering():
    result = ComplianceValidator.validate_vector("array_ordering")
    assert result.passed, result.message


def test_compliance_deep_nesting():
    result = ComplianceValidator.validate_vector("deep_nesting")
    assert result.passed, result.message


def test_compliance_empty_payload():
    result = ComplianceValidator.validate_vector("empty_payload")
    assert result.passed, result.message


def test_compliance_large_integers():
    result = ComplianceValidator.validate_vector("large_integers")
    assert result.passed, result.message


def test_compliance_all_vectors():
    results = ComplianceValidator.validate_all()
    failures = [r for r in results if not r.passed]
    assert not failures, f"Failed vectors: {[r.name for r in failures]}"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest rationalevault/canonical/tests/test_compliance.py -v`
Expected: FAIL with ImportError

- [ ] **Step 4: Write minimal implementation**

Create `rationalevault/canonical/compliance/vectors.py`:

```python
"""Load compliance vectors from spec/vectors/."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


VECTORS_DIR = Path(__file__).parent.parent.parent.parent / "spec" / "vectors"


def load_vectors() -> list[dict[str, Any]]:
    """Load all compliance vectors from spec/vectors/."""
    vectors = []
    if VECTORS_DIR.exists():
        for f in sorted(VECTORS_DIR.glob("*.json")):
            with open(f) as fp:
                vectors.append(json.load(fp))
    return vectors
```

Create `rationalevault/canonical/compliance/validator.py`:

```python
"""Cross-implementation compliance validator."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from rationalevault.canonical.compliance.vectors import load_vectors
from rationalevault.canonical.serializer import CanonicalSerializer


@dataclass
class ComplianceResult:
    """Result of a compliance vector validation."""
    
    name: str
    passed: bool
    message: str
    expected: str | None = None
    actual: str | None = None


class ComplianceValidator:
    """Validate implementation against compliance vectors."""
    
    @staticmethod
    def load_vectors() -> list[dict[str, Any]]:
        """Load all compliance vectors."""
        return load_vectors()
    
    @staticmethod
    def validate_vector(name: str) -> ComplianceResult:
        """Validate a single compliance vector."""
        vectors = load_vectors()
        vector = next((v for v in vectors if v["name"] == name), None)
        if vector is None:
            return ComplianceResult(
                name=name, passed=False, message=f"Vector not found: {name}"
            )
        
        try:
            from rationalevault.canonical.envelope import CanonicalEnvelope
            from rationalevault.canonical.payload import CanonicalPayload
            from rationalevault.canonical.timestamp import CanonicalTimestamp
            from rationalevault.canonical.types import EventType
            from datetime import datetime, timezone
            
            EventType.register("compliance_test")
            
            # Create envelope with test input
            payload = CanonicalPayload.from_dict(vector["input"])
            ts = CanonicalTimestamp.from_iso8601(
                "2026-07-13T14:35:42.123456Z"
            )
            env = CanonicalEnvelope(
                rvcj_version=1,
                event_schema_version=1,
                experience_id="EXP-compliance",
                event_type=EventType.get("compliance_test"),
                stream_id="compliance",
                sequence=1,
                timestamp=ts,
                actor="system",
                payload=payload,
            )
            
            # Serialize and extract payload portion
            canonical_bytes = CanonicalSerializer.serialize(env)
            canonical_json = json.loads(canonical_bytes)
            actual_payload = json.dumps(
                canonical_json["payload"], separators=(",", ":")
            )
            expected = vector["expected_canonical"]
            
            # Compare payload serialization
            expected_payload = json.dumps(
                vector["input"], sort_keys=True, separators=(",", ":")
            )
            
            if actual_payload == expected_payload:
                return ComplianceResult(
                    name=name, passed=True, message="PASS"
                )
            else:
                return ComplianceResult(
                    name=name,
                    passed=False,
                    message=f"Payload mismatch",
                    expected=expected_payload,
                    actual=actual_payload,
                )
        except Exception as e:
            return ComplianceResult(
                name=name, passed=False, message=f"Error: {e}"
            )
    
    @staticmethod
    def validate_all() -> list[ComplianceResult]:
        """Validate all compliance vectors."""
        vectors = load_vectors()
        return [ComplianceValidator.validate_vector(v["name"]) for v in vectors]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest rationalevault/canonical/tests/test_compliance.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add rationalevault/canonical/compliance/ rationalevault/canonical/tests/test_compliance.py
git commit -m "feat(canonical): add compliance suite"
```

---

## Task 11: Invariant Tests

**Files:**
- Create: `rationalevault/canonical/tests/test_invariants.py`

**Interfaces:**
- Consumes: All canonical components
- Produces: Invariant validation (I-00, I-08)

- [ ] **Step 1: Write the failing test**

Create `rationalevault/canonical/tests/test_invariants.py`:

```python
from datetime import datetime, timezone

import pytest

from rationalevault.canonical.envelope import CanonicalEnvelope
from rationalevault.canonical.payload import CanonicalPayload
from rationalevault.canonical.serializer import CanonicalSerializer
from rationalevault.canonical.stable_id import StableIdGenerator
from rationalevault.canonical.timestamp import CanonicalTimestamp
from rationalevault.canonical.types import EventType


@pytest.fixture(autouse=True)
def register_event_type():
    EventType.register("test_event")
    yield
    EventType.clear()


def test_i00_canonical_representation():
    """I-00: Semantically equivalent objects produce identical canonical representations."""
    env1 = CanonicalEnvelope(
        rvcj_version=1,
        event_schema_version=1,
        experience_id="EXP-a1b2c3d4e5f6",
        event_type=EventType.get("test_event"),
        stream_id="project-42",
        sequence=1,
        timestamp=CanonicalTimestamp.from_datetime(
            datetime(2026, 7, 13, 14, 35, 42, 123456, tzinfo=timezone.utc)
        ),
        actor="agent-001",
        payload=CanonicalPayload(data={"a": 1, "b": 2}),
    )
    env2 = CanonicalEnvelope(
        rvcj_version=1,
        event_schema_version=1,
        experience_id="EXP-a1b2c3d4e5f6",
        event_type=EventType.get("test_event"),
        stream_id="project-42",
        sequence=1,
        timestamp=CanonicalTimestamp.from_datetime(
            datetime(2026, 7, 13, 14, 35, 42, 123456, tzinfo=timezone.utc)
        ),
        actor="agent-001",
        payload=CanonicalPayload(data={"b": 2, "a": 1}),
    )
    # Same semantic content, different key order → same canonical bytes
    b1 = CanonicalSerializer.serialize(env1)
    b2 = CanonicalSerializer.serialize(env2)
    assert b1 == b2


def test_i08_referential_transparency():
    """I-08: All identifiers are deterministically generated via hash."""
    content1 = {"event_type": "test", "payload": {"key": "value"}}
    content2 = {"event_type": "test", "payload": {"key": "value"}}
    
    id1 = StableIdGenerator.experience_id(content1)
    id2 = StableIdGenerator.experience_id(content2)
    
    # Same content → same ID (deterministic)
    assert id1 == id2
    
    # Format: PREFIX-12hexchars
    assert id1.startswith("EXP-")
    assert len(id1.split("-")[1]) == 12


def test_i00_unicode_normalization():
    """I-00: Unicode normalization produces identical representations."""
    env1 = CanonicalEnvelope(
        rvcj_version=1,
        event_schema_version=1,
        experience_id="EXP-a1b2c3d4e5f6",
        event_type=EventType.get("test_event"),
        stream_id="project-42",
        sequence=1,
        timestamp=CanonicalTimestamp.from_datetime(
            datetime(2026, 7, 13, 14, 35, 42, 123456, tzinfo=timezone.utc)
        ),
        actor="agent-001",
        payload=CanonicalPayload(data={"text": "caf\u0065\u0301"}),
    )
    env2 = CanonicalEnvelope(
        rvcj_version=1,
        event_schema_version=1,
        experience_id="EXP-a1b2c3d4e5f6",
        event_type=EventType.get("test_event"),
        stream_id="project-42",
        sequence=1,
        timestamp=CanonicalTimestamp.from_datetime(
            datetime(2026, 7, 13, 14, 35, 42, 123456, tzinfo=timezone.utc)
        ),
        actor="agent-001",
        payload=CanonicalPayload(data={"text": "caf\u00e9"}),
    )
    b1 = CanonicalSerializer.serialize(env1)
    b2 = CanonicalSerializer.serialize(env2)
    assert b1 == b2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest rationalevault/canonical/tests/test_invariants.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Run test to verify it passes**

Run: `pytest rationalevault/canonical/tests/test_invariants.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add rationalevault/canonical/tests/test_invariants.py
git commit -m "test(canonical): add invariant tests (I-00, I-08)"
```

---

## Task 12: Public API Exports

**Files:**
- Modify: `rationalevault/canonical/__init__.py`

**Interfaces:**
- Consumes: All canonical components
- Produces: Clean public API

- [ ] **Step 1: Write the failing test**

Create `rationalevault/canonical/tests/test_init.py`:

```python
from rationalevault.canonical import (
    CanonicalEnvelope,
    CanonicalPayload,
    CanonicalSerializer,
    CanonicalTimestamp,
    StableIdGenerator,
    EventType,
)


def test_public_api_exports():
    assert CanonicalEnvelope is not None
    assert CanonicalPayload is not None
    assert CanonicalSerializer is not None
    assert CanonicalTimestamp is not None
    assert StableIdGenerator is not None
    assert EventType is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest rationalevault/canonical/tests/test_init.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Write minimal implementation**

Create `rationalevault/canonical/__init__.py`:

```python
"""RationaleVault Canonical Representation Layer (RVCJ v1)."""

from rationalevault.canonical.envelope import CanonicalEnvelope
from rationalevault.canonical.payload import CanonicalPayload
from rationalevault.canonical.serializer import CanonicalSerializer
from rationalevault.canonical.stable_id import StableIdGenerator
from rationalevault.canonical.timestamp import CanonicalTimestamp
from rationalevault.canonical.types import EventType

__all__ = [
    "CanonicalEnvelope",
    "CanonicalPayload",
    "CanonicalSerializer",
    "CanonicalTimestamp",
    "StableIdGenerator",
    "EventType",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest rationalevault/canonical/tests/test_init.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add rationalevault/canonical/__init__.py rationalevault/canonical/tests/test_init.py
git commit -m "feat(canonical): add public API exports"
```

---

## Task 13: Run Full Test Suite

**Files:**
- None (verification task)

**Interfaces:**
- Consumes: All canonical components
- Produces: All tests passing

- [ ] **Step 1: Run all canonical tests**

Run: `pytest rationalevault/canonical/ -v`
Expected: All tests PASS

- [ ] **Step 2: Verify coverage**

Run: `pytest rationalevault/canonical/ --cov=rationalevault.canonical --cov-report=term-missing`
Expected: High coverage for canonical module

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "test(canonical): verify full test suite passes"
```

---

## Success Criteria

| Criterion | Task |
|-----------|------|
| ✅ Specification constants | Task 1 |
| ✅ EventType registry | Task 2 |
| ✅ CanonicalTimestamp value object | Task 3 |
| ✅ Compliance vectors (TDD) | Task 4 |
| ✅ CanonicalPayload value object | Task 5 |
| ✅ CanonicalEnvelope dataclass | Task 6 |
| ✅ CanonicalSerializer | Task 7 |
| ✅ StableIdGenerator | Task 8 |
| ✅ Roundtrip tests | Task 9 |
| ✅ Compliance suite | Task 10 |
| ✅ Invariant tests (I-00, I-08) | Task 11 |
| ✅ Public API exports | Task 12 |
| ✅ Full test suite passes | Task 13 |
