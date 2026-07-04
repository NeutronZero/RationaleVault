"""
RationaleVault Skill Platform — ExecutionContext.

An immutable bundle of all inputs required for skill execution.
The runtime accepts a single ExecutionContext rather than expanding
its signature with every new C2/C3/C4 requirement.

Design rules:
  - ExecutionContext is frozen — immutable after creation.
  - Carries the full lineage: decision → candidate → manifest → provenance.
  - Runtime config is a dict that can grow without changing the interface.
  - snapshot_hash is computed once at construction time.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rationalevault.skill_platform.bridge import SkillCandidate
from rationalevault.skill_platform.manifest import SkillManifest
from rationalevault.skill_platform.permissions import CapabilityModel
from rationalevault.skill_platform.provenance import Provenance, compute_snapshot_hash


@dataclass(frozen=True)
class ExecutionContext:
    """
    Immutable bundle of all inputs required for skill execution.

    The runtime accepts a single ExecutionContext rather than individual
    parameters. Future fields (estimated_cost, scheduling_hints,
    retry_strategy, etc.) are added here without changing the runtime
    interface.

    This is expected to be one of the longest-lived contracts in the
    platform — it sits at the boundary between cognition and execution.
    """
    # ── Lineage ────────────────────────────────────────────────────────────
    decision_id: str                       # DEC-[hash]
    synthesis_id: str                      # SYN-[hash]
    belief_id: str                         # BEL-[hash]
    source_event_ids: list[str]            # original event IDs from the Event Ledger

    # ── Skill selection ────────────────────────────────────────────────────
    manifest: SkillManifest                # selected skill manifest
    candidate: SkillCandidate              # bridge result (match metadata)

    # ── Execution inputs ───────────────────────────────────────────────────
    input_snapshot: dict[str, Any]         # frozen inputs to the skill
    provenance: Provenance                 # full lineage trace

    # ── Permissions ────────────────────────────────────────────────────────
    capabilities: CapabilityModel          # capabilities available for this execution

    # ── Configuration ──────────────────────────────────────────────────────
    gate_policy_version: str               # DecisionGatePolicy version
    runtime_config: dict[str, Any] = field(default_factory=dict)

    # ── Computed ───────────────────────────────────────────────────────────
    snapshot_hash: str = ""                # SHA-256 of input_snapshot

    def __post_init__(self) -> None:
        # Compute snapshot_hash if not provided
        if not self.snapshot_hash:
            object.__setattr__(
                self, "snapshot_hash", compute_snapshot_hash(self.input_snapshot)
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "synthesis_id": self.synthesis_id,
            "belief_id": self.belief_id,
            "source_event_ids": self.source_event_ids,
            "skill_id": self.manifest.skill_id,
            "skill_name": self.manifest.name,
            "skill_version": self.manifest.version,
            "input_snapshot": self.input_snapshot,
            "snapshot_hash": self.snapshot_hash,
            "gate_policy_version": self.gate_policy_version,
            "runtime_config": self.runtime_config,
            "provenance": self.provenance.to_dict(),
            "capabilities": self.capabilities.to_dict(),
        }

    @classmethod
    def build(
        cls,
        *,
        decision_id: str,
        synthesis_id: str,
        belief_id: str,
        source_event_ids: list[str],
        manifest: SkillManifest,
        candidate: SkillCandidate,
        input_snapshot: dict[str, Any],
        gate_policy_version: str,
        capabilities: CapabilityModel,
        runtime_config: dict[str, Any] | None = None,
    ) -> "ExecutionContext":
        """
        Factory method that constructs an ExecutionContext with auto-generated
        provenance and snapshot_hash.

        This is the recommended construction path — it ensures provenance
        is always populated and snapshot_hash is always computed.
        """
        from datetime import datetime, timezone

        provenance = Provenance(
            execution_id="",  # filled by runtime after execution_id is generated
            decision_id=decision_id,
            synthesis_id=synthesis_id,
            belief_id=belief_id,
            source_event_ids=source_event_ids,
            skill_version=manifest.version,
            gate_policy_version=gate_policy_version,
            input_snapshot_hash=compute_snapshot_hash(input_snapshot),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        return cls(
            decision_id=decision_id,
            synthesis_id=synthesis_id,
            belief_id=belief_id,
            source_event_ids=source_event_ids,
            manifest=manifest,
            candidate=candidate,
            input_snapshot=input_snapshot,
            provenance=provenance,
            capabilities=capabilities,
            gate_policy_version=gate_policy_version,
            runtime_config=runtime_config or {},
        )
