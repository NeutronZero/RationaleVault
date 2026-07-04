"""
RationaleVault Skill Platform — SkillOutput.

Immutable output bundle from skill execution. Replaces raw dict output
with a versioned, hashable value object.

Design rules:
  - SkillOutput is frozen — immutable after creation.
  - version enables serialisation evolution.
  - output_hash is intrinsic — computed at construction time.
  - Structured fields replace markdown/text reports.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SkillOutput:
    """
    Immutable output bundle from skill execution.

    Every stage of the pipeline has a single immutable value object.
    SkillOutput is the execution layer's equivalent of Belief or
    DecisionSet.
    """
    version: str = "1.0"
    status: str = "completed"              # "completed" | "failed" | "partial"
    confirmed_items: list[str] = field(default_factory=list)
    challenged_items: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    summary: str = ""
    metrics: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    output_hash: str = ""

    def __post_init__(self) -> None:
        if not self.output_hash:
            canonical = json.dumps(
                {
                    "status": self.status,
                    "confirmed_items": self.confirmed_items,
                    "challenged_items": self.challenged_items,
                    "recommendations": self.recommendations,
                    "summary": self.summary,
                    "metrics": self.metrics,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            h = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16].upper()
            object.__setattr__(self, "output_hash", h)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "status": self.status,
            "confirmed_items": self.confirmed_items,
            "challenged_items": self.challenged_items,
            "recommendations": self.recommendations,
            "summary": self.summary,
            "metrics": self.metrics,
            "warnings": self.warnings,
            "output_hash": self.output_hash,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "SkillOutput":
        return cls(
            version=d.get("version", "1.0"),
            status=d.get("status", "completed"),
            confirmed_items=d.get("confirmed_items", []),
            challenged_items=d.get("challenged_items", []),
            recommendations=d.get("recommendations", []),
            summary=d.get("summary", ""),
            metrics=d.get("metrics", {}),
            warnings=d.get("warnings", []),
            output_hash=d.get("output_hash", ""),
        )
