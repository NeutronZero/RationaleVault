"""
RationaleVault Memory Lifecycle — Evidence-driven memory promotion.

Memory promotion is driven by evidence, not time:
  - Reference frequency: how often a memory is referenced
  - Reference velocity: rate of references over time
  - Promotion history: past promotions of this memory
  - Reflection references: how many reflections reference this memory

Design rules:
  - MTRANS-[hash] for memory transition events.
  - Transitions are append-only — never mutated.
  - Memory states: CANDIDATE → ACTIVE → PROMOTED → ARCHIVED.
  - Promotion thresholds are configurable via MemoryPromotionPolicy.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum
from typing import Any


# =====================================================================
# Enums
# =====================================================================

class MemoryState(str, Enum):
    """Lifecycle states for memory objects."""
    CANDIDATE = "CANDIDATE"
    ACTIVE = "ACTIVE"
    PROMOTED = "PROMOTED"
    ARCHIVED = "ARCHIVED"


class TransitionType(str, Enum):
    """Types of memory state transitions."""
    CREATED = "CREATED"
    ACTIVATED = "ACTIVATED"
    PROMOTED = "PROMOTED"
    ARCHIVED = "ARCHIVED"
    SUPerseded = "SUPerseded"


# =====================================================================
# Domain Models
# =====================================================================

@dataclass(frozen=True)
class MemoryEvidence:
    """
    Evidence metrics for a memory object.

    Used to determine promotion eligibility.
    """
    memory_id: str
    reference_count: int            # Total references
    reference_velocity: float       # References per day
    reflection_count: int           # How many reflections reference this
    promotion_count: int            # Past promotions
    last_referenced_at: str | None
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "reference_count": self.reference_count,
            "reference_velocity": round(self.reference_velocity, 4),
            "reflection_count": self.reflection_count,
            "promotion_count": self.promotion_count,
            "last_referenced_at": self.last_referenced_at,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> MemoryEvidence:
        return cls(
            memory_id=d["memory_id"],
            reference_count=d.get("reference_count", 0),
            reference_velocity=d.get("reference_velocity", 0.0),
            reflection_count=d.get("reflection_count", 0),
            promotion_count=d.get("promotion_count", 0),
            last_referenced_at=d.get("last_referenced_at"),
            created_at=d.get("created_at", ""),
        )


@dataclass(frozen=True)
class MemoryPromotionPolicy:
    """
    Configurable thresholds for memory promotion.

    Append-only — PPOL-[hash] for versioning.
    """
    version: str = "1.0"
    min_reference_count: int = 3
    min_reference_velocity: float = 0.1    # refs per day
    min_reflection_count: int = 1
    max_promotion_count: int = 5
    require_reflection: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "min_reference_count": self.min_reference_count,
            "min_reference_velocity": self.min_reference_velocity,
            "min_reflection_count": self.min_reflection_count,
            "max_promotion_count": self.max_promotion_count,
            "require_reflection": self.require_reflection,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> MemoryPromotionPolicy:
        return cls(
            version=d.get("version", "1.0"),
            min_reference_count=d.get("min_reference_count", 3),
            min_reference_velocity=d.get("min_reference_velocity", 0.1),
            min_reflection_count=d.get("min_reflection_count", 1),
            max_promotion_count=d.get("max_promotion_count", 5),
            require_reflection=d.get("require_reflection", True),
        )


@dataclass(frozen=True)
class MemoryTransition:
    """
    Record of a memory state transition.

    MTRANS-[hash] — immutable, append-only.
    """
    transition_id: str              # MTRANS-[hash]
    memory_id: str
    from_state: MemoryState
    to_state: MemoryState
    transition_type: TransitionType
    rationale: str
    evidence: MemoryEvidence
    created_at: str

    @staticmethod
    def generate_transition_id(
        memory_id: str,
        from_state: str,
        to_state: str,
        created_at: str,
    ) -> str:
        data = f"memory_transition:{memory_id}:{from_state}:{to_state}:{created_at}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"MTRANS-{h}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "transition_id": self.transition_id,
            "memory_id": self.memory_id,
            "from_state": self.from_state.value,
            "to_state": self.to_state.value,
            "transition_type": self.transition_type.value,
            "rationale": self.rationale,
            "evidence": self.evidence.to_dict(),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> MemoryTransition:
        return cls(
            transition_id=d["transition_id"],
            memory_id=d["memory_id"],
            from_state=MemoryState(d["from_state"]),
            to_state=MemoryState(d["to_state"]),
            transition_type=TransitionType(d["transition_type"]),
            rationale=d.get("rationale", ""),
            evidence=MemoryEvidence.from_dict(d["evidence"]),
            created_at=d["created_at"],
        )


@dataclass(frozen=True)
class MemoryPromotionReport:
    """
    Aggregated report of a memory promotion evaluation.

    Contains the evidence, policy evaluation, and resulting transition.
    """
    report_id: str
    memory_id: str
    current_state: MemoryState
    proposed_state: MemoryState
    eligible: bool
    evidence: MemoryEvidence
    transition: MemoryTransition | None
    findings: list[str]
    warnings: list[str]
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "memory_id": self.memory_id,
            "current_state": self.current_state.value,
            "proposed_state": self.proposed_state.value,
            "eligible": self.eligible,
            "evidence": self.evidence.to_dict(),
            "transition": self.transition.to_dict() if self.transition else None,
            "findings": self.findings,
            "warnings": self.warnings,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> MemoryPromotionReport:
        transition_data = d.get("transition")
        return cls(
            report_id=d["report_id"],
            memory_id=d["memory_id"],
            current_state=MemoryState(d["current_state"]),
            proposed_state=MemoryState(d["proposed_state"]),
            eligible=d.get("eligible", False),
            evidence=MemoryEvidence.from_dict(d["evidence"]),
            transition=MemoryTransition.from_dict(transition_data) if transition_data else None,
            findings=d.get("findings", []),
            warnings=d.get("warnings", []),
            created_at=d["created_at"],
        )
