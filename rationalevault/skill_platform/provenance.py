"""
RationaleVault Skill Platform — Provenance.

Every execution result carries a Provenance record that traces its
origin through the full pipeline.

Design rules:
  - Provenance is frozen — immutable after creation.
  - Chains IDs: SKE → DEC → SYN → BEL → source events.
  - input_snapshot_hash enables replay verification.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Provenance:
    """
    Full lineage trace for a skill execution.

    Given the same source_event_ids, skill_version, and
    gate_policy_version, replaying the execution must produce
    identical output (for idempotent skills) or fail identically.
    """
    execution_id: str                    # SKE-[hash]
    decision_id: str                     # DEC-[hash]
    synthesis_id: str                    # SYN-[hash]
    belief_id: str                       # BEL-[hash]
    source_event_ids: list[str]          # original event IDs from the Event Ledger
    skill_version: str                   # skill manifest version
    gate_policy_version: str             # DecisionGatePolicy version
    input_snapshot_hash: str             # SHA-256 of inputs (replay verification)
    timestamp: str                       # ISO timestamp

    def to_dict(self) -> dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "decision_id": self.decision_id,
            "synthesis_id": self.synthesis_id,
            "belief_id": self.belief_id,
            "source_event_ids": self.source_event_ids,
            "skill_version": self.skill_version,
            "gate_policy_version": self.gate_policy_version,
            "input_snapshot_hash": self.input_snapshot_hash,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Provenance":
        return cls(
            execution_id=d["execution_id"],
            decision_id=d["decision_id"],
            synthesis_id=d["synthesis_id"],
            belief_id=d["belief_id"],
            source_event_ids=d.get("source_event_ids", []),
            skill_version=d.get("skill_version", ""),
            gate_policy_version=d.get("gate_policy_version", ""),
            input_snapshot_hash=d.get("input_snapshot_hash", ""),
            timestamp=d.get("timestamp", ""),
        )


def compute_snapshot_hash(inputs: dict[str, Any]) -> str:
    """Deterministic SHA-256 of a JSON-serialised input snapshot."""
    canonical = json.dumps(inputs, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16].upper()
