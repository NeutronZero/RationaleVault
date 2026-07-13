"""StableIdGenerator — deterministic event_id and experience_id generation."""

from __future__ import annotations

import hashlib

from rationalevault.canonical.specification import (
    HASH_ALGORITHM,
    HASH_DISPLAY_LENGTH,
)
from rationalevault.canonical.timestamp import CanonicalTimestamp


def _hash_to_hex(data: bytes) -> str:
    """Hash data and return full hex string."""
    h = hashlib.new(HASH_ALGORITHM)
    h.update(data)
    return h.hexdigest()


class StableIdGenerator:
    """Generate deterministic event_id and experience_id from canonical bytes."""

    @staticmethod
    def generate_event_id(
        experience_id: str,
        event_type: str,
        sequence: int,
        timestamp: CanonicalTimestamp,
    ) -> str:
        """Generate stable event_id from input parameters."""
        seed = f"{experience_id}:{event_type}:{sequence}:{timestamp.to_iso8601()}"
        full = _hash_to_hex(seed.encode("utf-8"))
        return f"EVT-{full[:HASH_DISPLAY_LENGTH]}"

    @staticmethod
    def generate_experience_id(
        actor: str,
        stream_id: str,
        timestamp: CanonicalTimestamp,
    ) -> str:
        """Generate stable experience_id from input parameters."""
        seed = f"{actor}:{stream_id}:{timestamp.to_iso8601()}"
        full = _hash_to_hex(seed.encode("utf-8"))
        return f"EXP-{full[:HASH_DISPLAY_LENGTH]}"
