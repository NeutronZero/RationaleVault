"""
RationaleVault Skill Platform — OutputValidator.

Validates SkillOutput against output_schema. Returns a structured
ValidationResult rather than a bare bool.

Design rules:
  - ValidationResult carries valid, errors, and warnings.
  - Validator is deterministic — same output → same result.
  - Warnings do not block execution; errors do.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ValidationResult:
    """
    Structured result of output validation.

    valid      — True if output passes all required checks
    errors     — list of blocking validation errors
    warnings   — list of non-blocking issues
    """
    valid: bool
    errors: list[str]
    warnings: list[str]
    evaluation_version: str = "1.0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "evaluation_version": self.evaluation_version,
        }


class OutputValidator:
    """
    Validates SkillOutput against output_schema.

    Returns a ValidationResult with valid, errors, and warnings.
    """

    EVALUATION_VERSION = "1.0"

    @staticmethod
    def validate(
        output: dict[str, Any],
        output_schema: dict[str, Any],
    ) -> ValidationResult:
        """
        Validate output against JSON Schema.

        Checks:
          1. Required fields present
          2. Types match schema
          3. No unexpected top-level keys (warning)
        """
        errors: list[str] = []
        warnings: list[str] = []

        if not output_schema:
            # Empty schema — no validation rules
            return ValidationResult(
                valid=True,
                errors=[],
                warnings=[],
                evaluation_version=OutputValidator.EVALUATION_VERSION,
            )

        # Check required fields
        required = output_schema.get("required", [])
        for field_name in required:
            if field_name not in output:
                errors.append(f"Missing required field: {field_name}")

        # Check types for properties defined in schema
        properties = output_schema.get("properties", {})
        for key, prop_schema in properties.items():
            if key in output:
                expected_type = prop_schema.get("type")
                if expected_type:
                    actual_value = output[key]
                    if not OutputValidator._type_matches(actual_value, expected_type):
                        errors.append(
                            f"Field '{key}' expected type '{expected_type}', "
                            f"got '{type(actual_value).__name__}'"
                        )

        # Warn about unexpected top-level keys
        if properties:
            defined_keys = set(properties.keys())
            actual_keys = set(output.keys())
            unexpected = actual_keys - defined_keys
            if unexpected:
                warnings.append(
                    f"Unexpected fields: {', '.join(sorted(unexpected))}"
                )

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            evaluation_version=OutputValidator.EVALUATION_VERSION,
        )

    @staticmethod
    def _type_matches(value: Any, expected_type: str) -> bool:
        """Check if a value matches a JSON Schema type."""
        type_map = {
            "string": str,
            "number": (int, float),
            "integer": int,
            "boolean": bool,
            "array": list,
            "object": dict,
        }
        expected = type_map.get(expected_type)
        if expected is None:
            return True  # unknown type, pass
        return isinstance(value, expected)
