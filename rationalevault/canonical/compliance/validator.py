"""Compliance validator for cross-implementation verification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rationalevault.canonical.canonicalizer import canonicalize
from rationalevault.canonical.compliance.vectors import load_vector, load_vectors
from rationalevault.canonical.serializer import CanonicalSerializer
from rationalevault.canonical.envelope import CanonicalEnvelope
from rationalevault.canonical.payload import CanonicalPayload
from rationalevault.canonical.timestamp import CanonicalTimestamp
from rationalevault.canonical.types import EventType


@dataclass(frozen=True)
class ValidationResult:
    """Result of a compliance validation."""

    passed: bool
    message: str
    expected: str | None = None
    actual: str | None = None


class ComplianceValidator:
    """Validate serializer output against compliance vectors."""

    @staticmethod
    def load_vectors() -> dict[str, Any]:
        """Load all compliance vectors."""
        return load_vectors()

    @staticmethod
    def validate_vector(name: str) -> ValidationResult:
        """Validate a single compliance vector."""
        try:
            vector = load_vector(name)
        except FileNotFoundError as e:
            return ValidationResult(False, str(e))

        # The vector contains input JSON and expected canonical output
        input_data = vector.get("input")
        expected_canonical = vector.get("expected_canonical")

        if input_data is None or expected_canonical is None:
            return ValidationResult(
                False, f"Vector {name} missing input or expected_canonical"
            )

        # Canonicalize the input
        try:
            canonical = canonicalize(input_data)
        except Exception as e:
            return ValidationResult(False, f"Canonicalization failed: {e}")

        # Convert canonical to JSON string (no whitespace)
        import json
        actual = json.dumps(canonical, separators=(",", ":"), ensure_ascii=False)

        # expected_canonical is already a string, compare directly
        if actual == expected_canonical:
            return ValidationResult(True, f"Vector {name} passed")
        return ValidationResult(
            False, f"Vector {name} failed", expected=expected_canonical, actual=actual
        )

    @staticmethod
    def validate_all() -> list[ValidationResult]:
        """Validate all compliance vectors."""
        vectors = load_vectors()
        results = []
        for name in vectors:
            results.append(ComplianceValidator.validate_vector(name))
        return results