"""CanonicalPayload — immutable value object for domain data."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rationalevault.canonical.canonicalizer import canonicalize
from rationalevault.canonical.specification import RESERVED_PAYLOAD_NAMESPACES


@dataclass(frozen=True, slots=True)
class CanonicalPayload:
    """Immutable payload with canonicalization rules.

    Hashing is NOT here — it belongs in CanonicalSerializer.
    """

    data: dict[str, Any] = field(default_factory=dict)

    def validate(self, required: set[str] | None = None) -> None:
        """Validate payload against constraints.

        Answers: Is this payload legal?
        - Required fields present
        - No reserved namespaces
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

        Delegates to canonicalizer.canonicalize() — single path.
        """
        return CanonicalPayload(data=canonicalize(self.data))

    def to_dict(self) -> dict[str, Any]:
        """Return raw data dict."""
        return dict(self.data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CanonicalPayload:
        """Create from dictionary."""
        return cls(data=dict(data))
