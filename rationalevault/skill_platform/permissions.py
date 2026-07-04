"""
RationaleVault Skill Platform — Permission Model.

Skills access projections through a capability-based permission model.
Each skill declares the capabilities it needs; the runtime verifies them
before execution.

Design rules:
  - CAPABILITY_KEYS is the canonical set of all capability keys.
  - PermissionDecision is a structured record, not a bare tuple.
  - Only the Skill Runtime itself holds 'ledger:write'.
  - Individual skills never write to the ledger directly.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


CAPABILITY_KEYS: list[str] = [
    "projection:memory",
    "projection:knowledge",
    "projection:graph",
    "projection:context",
    "projection:organization",
    "ledger:read",
    "ledger:write",
    "skill:execute",
]


@dataclass(frozen=True)
class PermissionDecision:
    """
    Structured result of a permission check.

    Provides audit trail, denial reason, and evaluation version —
    useful for C2/C3 policy versions and explanation without API changes.
    """
    allowed: bool
    missing_capabilities: list[str]
    denial_reason: str
    evaluation_version: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "missing_capabilities": self.missing_capabilities,
            "denial_reason": self.denial_reason,
            "evaluation_version": self.evaluation_version,
        }


class CapabilityModel:
    """
    Holds the set of capabilities available in an execution context.

    The Skill Runtime creates a CapabilityModel with the capabilities
    it grants to a skill. PermissionChecker verifies required_permissions
    against this model.
    """

    def __init__(self, capabilities: list[str] | None = None) -> None:
        self._capabilities: set[str] = set(capabilities or [])

    def grant(self, capability: str) -> None:
        if capability not in CAPABILITY_KEYS:
            raise ValueError(f"Unknown capability: {capability}")
        self._capabilities.add(capability)

    def revoke(self, capability: str) -> None:
        self._capabilities.discard(capability)

    def has(self, capability: str) -> bool:
        return capability in self._capabilities

    def available(self) -> list[str]:
        return sorted(self._capabilities)

    def to_dict(self) -> dict[str, Any]:
        return {"capabilities": sorted(self._capabilities)}


class PermissionChecker:
    """
    Verifies that a skill's required_permissions are satisfied by the
    available capabilities.

    Returns a PermissionDecision — a structured record that carries
    the full audit trail of the check.
    """

    EVALUATION_VERSION = "1.0"

    @staticmethod
    def check(
        required_permissions: list[str],
        capability_model: CapabilityModel,
    ) -> PermissionDecision:
        missing = [
            p for p in required_permissions
            if not capability_model.has(p)
        ]

        if not missing:
            return PermissionDecision(
                allowed=True,
                missing_capabilities=[],
                denial_reason="",
                evaluation_version=PermissionChecker.EVALUATION_VERSION,
            )

        denial_reason = (
            f"Missing capabilities: {', '.join(missing)}"
        )
        return PermissionDecision(
            allowed=False,
            missing_capabilities=missing,
            denial_reason=denial_reason,
            evaluation_version=PermissionChecker.EVALUATION_VERSION,
        )
