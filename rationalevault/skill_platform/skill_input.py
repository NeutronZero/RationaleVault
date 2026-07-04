"""
RationaleVault Skill Platform — SkillInput.

Immutable input bundle for skill execution. Replaces raw dict input
with a versioned, hashable value object.

Design rules:
  - SkillInput is frozen — immutable after creation.
  - version enables serialisation evolution.
  - input_hash is intrinsic — computed at construction time.
  - ProjectionSnapshot carries typed projection data.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ProjectionSnapshot:
    """
    Typed projection data for skill input.

    Keeps projection evolution independent of skill interface.
    """
    memory: dict[str, Any] = field(default_factory=dict)
    knowledge: dict[str, Any] = field(default_factory=dict)
    execution_state: dict[str, Any] = field(default_factory=dict)
    graph: dict[str, Any] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "memory": self.memory,
            "knowledge": self.knowledge,
            "execution_state": self.execution_state,
            "graph": self.graph,
            "context": self.context,
        }


@dataclass(frozen=True)
class SkillInput:
    """
    Immutable input bundle for skill execution.

    Every stage of the pipeline has a single immutable value object.
    SkillInput is the execution layer's equivalent of EvidenceBundle
    or ReasoningReport.
    """
    version: str = "1.0"
    decision_id: str = ""
    belief_id: str = ""
    belief_title: str = ""
    belief_content: str = ""
    confidence: float = 0.0
    category: str = ""
    projections: ProjectionSnapshot = field(default_factory=ProjectionSnapshot)
    metadata: dict[str, Any] = field(default_factory=dict)
    input_hash: str = ""

    def __post_init__(self) -> None:
        if not self.input_hash:
            canonical = json.dumps(
                {
                    "decision_id": self.decision_id,
                    "belief_id": self.belief_id,
                    "belief_title": self.belief_title,
                    "confidence": self.confidence,
                    "category": self.category,
                    "projections": self.projections.to_dict(),
                    "metadata": self.metadata,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            h = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16].upper()
            object.__setattr__(self, "input_hash", h)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "decision_id": self.decision_id,
            "belief_id": self.belief_id,
            "belief_title": self.belief_title,
            "belief_content": self.belief_content,
            "confidence": round(self.confidence, 4),
            "category": self.category,
            "projections": self.projections.to_dict(),
            "metadata": self.metadata,
            "input_hash": self.input_hash,
        }
