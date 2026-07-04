"""RationaleVault Capability Resolver — Resolves effective agent capabilities.

CapabilityResolver computes the intersection of:
  - Agent profile capabilities (what the agent CAN do)
  - Workspace denied capabilities (what the workspace BLOCKS)

Result: effective capabilities for a specific agent in a specific workspace.

Design rules:
  - Pure functions, no I/O.
  - Deterministic: same inputs → identical capabilities.
  - Capabilities are composable (set operations).
"""
from __future__ import annotations

from datetime import datetime, timezone

from rationalevault.runtime.models import (
    AgentCapabilities,
    AgentProfile,
    Capability,
    CapabilityProfile,
    CAPABILITY_PROFILES,
)


class CapabilityResolver:
    """Resolves effective capabilities for an agent in a workspace."""

    @staticmethod
    def resolve(
        profile: AgentProfile,
        denied: frozenset[Capability] | None = None,
        reference_time: datetime | None = None,
    ) -> AgentCapabilities:
        """Resolve effective capabilities from profile and denials.

        Args:
            profile: Agent profile with granted capabilities.
            denied: Capabilities denied by workspace policy.
            reference_time: Deterministic timestamp.

        Returns:
            AgentCapabilities with granted, denied, and effective sets.
        """
        now = (reference_time or datetime.now(timezone.utc)).isoformat()
        denied = denied or frozenset()

        return AgentCapabilities(
            profile_id=profile.profile_id,
            granted=profile.capabilities,
            denied=denied,
            resolved_at=now,
        )

    @staticmethod
    def resolve_from_profile_name(
        profile_name: str,
        vendor: str = "CUSTOM",
        denied: frozenset[Capability] | None = None,
        reference_time: datetime | None = None,
    ) -> AgentCapabilities:
        """Resolve capabilities from a predefined profile name.

        Maps CapabilityProfile enum to a capability set, then resolves.
        """
        try:
            cap_profile = CapabilityProfile(profile_name.upper())
        except ValueError:
            # Unknown profile — no capabilities
            return AgentCapabilities(
                profile_id=f"profile:{profile_name}",
                granted=frozenset(),
                denied=denied or frozenset(),
                resolved_at=(reference_time or datetime.now(timezone.utc)).isoformat(),
            )

        granted = CAPABILITY_PROFILES.get(cap_profile, frozenset())

        return AgentCapabilities(
            profile_id=f"profile:{profile_name}",
            granted=granted,
            denied=denied or frozenset(),
            resolved_at=(reference_time or datetime.now(timezone.utc)).isoformat(),
        )

    @staticmethod
    def can_perform(
        capabilities: AgentCapabilities,
        action: Capability,
    ) -> bool:
        """Check if an agent can perform a specific action."""
        return capabilities.has(action)

    @staticmethod
    def merge_capabilities(
        caps_a: AgentCapabilities,
        caps_b: AgentCapabilities,
    ) -> AgentCapabilities:
        """Merge two capability sets (union of granted, intersection of denied)."""
        return AgentCapabilities(
            profile_id=caps_a.profile_id,
            granted=caps_a.granted | caps_b.granted,
            denied=caps_a.denied & caps_b.denied,
            resolved_at=caps_a.resolved_at,
        )
