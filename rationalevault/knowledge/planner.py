"""
RationaleVault Planner Evolution — Event-sourced planner adjustment projection.

The planner is stateless, consumes a projection. Policies are append-only (PPOL-1 → PPOL-2 → PPOL-3).

Design rules:
  - PlannerAdjustmentProjection is the single source of planner state.
  - Policies are append-only — never mutated, only superseded.
  - PlannerAdjustment records what changed and why.
  - PADJ-[hash] for adjustment records, PPOL-[hash] for policies.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum
from typing import Any


# =====================================================================
# Enums
# =====================================================================

class AdjustmentType(str, Enum):
    """Types of planner adjustments."""
    THRESHOLD_UPDATE = "THRESHOLD_UPDATE"
    POLICY_SUPERSede = "POLICY_SUPERSede"
    STRATEGY_CHANGE = "STRATEGY_CHANGE"
    PRIORITY_REORDER = "PRIORITY_REORDER"
    EVIDENCE_WEIGHT = "EVIDENCE_WEIGHT"


class AdjustmentStatus(str, Enum):
    """Status of a planner adjustment."""
    PROPOSED = "PROPOSED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"


# =====================================================================
# Domain Models
# =====================================================================

@dataclass(frozen=True)
class PlannerPolicy:
    """
    Immutable planner policy configuration.

    Policies are append-only — PPOL-1 → PPOL-2 → PPOL-3.
    Never mutated, only superseded.
    """
    policy_id: str                  # PPOL-[hash]
    version: int
    config: dict[str, Any]
    description: str
    superseded_by: str | None       # PPOL-[hash] of next policy
    created_at: str

    @staticmethod
    def generate_policy_id(version: int, config: dict[str, Any], created_at: str) -> str:
        config_str = str(sorted(config.items()))
        data = f"planner_policy:v{version}:{config_str}:{created_at}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"PPOL-{h}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "version": self.version,
            "config": self.config,
            "description": self.description,
            "superseded_by": self.superseded_by,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PlannerPolicy:
        return cls(
            policy_id=d["policy_id"],
            version=d["version"],
            config=d.get("config", {}),
            description=d.get("description", ""),
            superseded_by=d.get("superseded_by"),
            created_at=d["created_at"],
        )


@dataclass(frozen=True)
class PlannerAdjustment:
    """
    Record of a planner adjustment.

    PADJ-[hash] — immutable, append-only.
    """
    adjustment_id: str              # PADJ-[hash]
    adjustment_type: AdjustmentType
    source_policy_id: str | None    # PPOL-[hash] being adjusted
    target_policy_id: str | None    # PPOL-[hash] being created (if any)
    rationale: str
    status: AdjustmentStatus
    created_at: str

    @staticmethod
    def generate_adjustment_id(
        adjustment_type: str,
        source_policy_id: str | None,
        created_at: str,
    ) -> str:
        data = f"planner_adjustment:{adjustment_type}:{source_policy_id}:{created_at}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"PADJ-{h}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "adjustment_id": self.adjustment_id,
            "adjustment_type": self.adjustment_type.value,
            "source_policy_id": self.source_policy_id,
            "target_policy_id": self.target_policy_id,
            "rationale": self.rationale,
            "status": self.status.value,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PlannerAdjustment:
        return cls(
            adjustment_id=d["adjustment_id"],
            adjustment_type=AdjustmentType(d["adjustment_type"]),
            source_policy_id=d.get("source_policy_id"),
            target_policy_id=d.get("target_policy_id"),
            rationale=d.get("rationale", ""),
            status=AdjustmentStatus(d["status"]),
            created_at=d["created_at"],
        )


@dataclass(frozen=True)
class PlannerAdjustmentProjection:
    """
    Projection of all planner adjustments and policies.

    This is the planner's view of the world.
    The planner is stateless and consumes this projection.
    """
    policies: list[PlannerPolicy]
    adjustments: list[PlannerAdjustment]
    active_policy_id: str | None
    version: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "policies": [p.to_dict() for p in self.policies],
            "adjustments": [a.to_dict() for a in self.adjustments],
            "active_policy_id": self.active_policy_id,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PlannerAdjustmentProjection:
        return cls(
            policies=[PlannerPolicy.from_dict(p) for p in d.get("policies", [])],
            adjustments=[PlannerAdjustment.from_dict(a) for a in d.get("adjustments", [])],
            active_policy_id=d.get("active_policy_id"),
            version=d.get("version", 1),
        )
