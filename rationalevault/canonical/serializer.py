"""CanonicalSerializer — the only path to canonical bytes."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from rationalevault.canonical.canonicalizer import canonicalize
from rationalevault.canonical.envelope import CanonicalEnvelope
from rationalevault.canonical.specification import (
    HASH_ALGORITHM,
    RVCJ_VERSION,
)


def _canonical_bytes(envelope: CanonicalEnvelope) -> bytes:
    """Produce canonical JSON bytes from envelope."""
    d = envelope.to_dict()
    canonical = canonicalize(d)
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
                "unicode_normalization": "NFC",
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
