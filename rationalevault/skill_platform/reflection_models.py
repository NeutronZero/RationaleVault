from __future__ import annotations
import hashlib
from dataclasses import dataclass
from enum import Enum
from typing import Any


class ReflectionReason(str, Enum):
    """Triggers/reasons for initiating a reflection event."""
    OUTCOME_MISMATCH = "OUTCOME_MISMATCH"
    CONTRADICTION_DETECTED = "CONTRADICTION_DETECTED"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    GATE_BLOCK = "GATE_BLOCK"
    MANUAL_TRIGGER = "MANUAL_TRIGGER"
    PERFORMANCE_DEGRADATION = "PERFORMANCE_DEGRADATION"


class ReflectionStatus(str, Enum):
    """The lifecycle states of a reflection process."""
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    ABORTED = "ABORTED"


@dataclass(frozen=True)
class ReflectionConfig:
    """Configuration policies for controlling the Reflection Engine behavior."""
    version: str
    enabled: bool
    confidence_threshold: float
    enabled_reasons: list[ReflectionReason]

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "enabled": self.enabled,
            "confidence_threshold": round(self.confidence_threshold, 4),
            "enabled_reasons": [reason.value for reason in self.enabled_reasons],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ReflectionConfig:
        return cls(
            version=d["version"],
            enabled=d["enabled"],
            confidence_threshold=d["confidence_threshold"],
            enabled_reasons=[ReflectionReason(r) for r in d["enabled_reasons"]],
        )


@dataclass(frozen=True)
class ReflectionCandidate:
    """An ephemeral model indicating a candidate scenario eligible for reflection."""
    candidate_id: str  # RCAND-[hash]
    source_artifact_id: str
    reason: ReflectionReason
    context: dict[str, Any]
    created_at: str
    config_version: str

    @staticmethod
    def generate_candidate_id(source_artifact_id: str, reason: ReflectionReason, config_version: str) -> str:
        data = f"candidate_reflection:{source_artifact_id}:{reason.value}:{config_version}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"RCAND-{h}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "source_artifact_id": self.source_artifact_id,
            "reason": self.reason.value,
            "context": self.context,
            "created_at": self.created_at,
            "config_version": self.config_version,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ReflectionCandidate:
        return cls(
            candidate_id=d["candidate_id"],
            source_artifact_id=d["source_artifact_id"],
            reason=ReflectionReason(d["reason"]),
            context=d["context"],
            created_at=d["created_at"],
            config_version=d["config_version"],
        )


@dataclass(frozen=True)
class Reflection:
    """An immutable event-sourced reflection object containing insights and guidelines."""
    reflection_id: str  # REFL-[hash]
    candidate_id: str
    status: ReflectionStatus
    insights: list[str]
    reconstructed_rationale: str
    actionable_guidelines: list[str]
    created_at: str
    completed_at: str | None = None

    @staticmethod
    def generate_reflection_id(candidate_id: str, created_at: str) -> str:
        data = f"reflection:{candidate_id}:{created_at}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"REFL-{h}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "reflection_id": self.reflection_id,
            "candidate_id": self.candidate_id,
            "status": self.status.value,
            "insights": self.insights,
            "reconstructed_rationale": self.reconstructed_rationale,
            "actionable_guidelines": self.actionable_guidelines,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Reflection:
        return cls(
            reflection_id=d["reflection_id"],
            candidate_id=d["candidate_id"],
            status=ReflectionStatus(d["status"]),
            insights=d["insights"],
            reconstructed_rationale=d["reconstructed_rationale"],
            actionable_guidelines=d["actionable_guidelines"],
            created_at=d["created_at"],
            completed_at=d.get("completed_at"),
        )


@dataclass(frozen=True)
class ReflectionReport:
    """A compilation snapshot representing executed reflections and aggregated analytical findings."""
    report_id: str  # RREP-[hash]
    reflections: list[Reflection]
    summary: dict[str, Any]
    created_at: str

    @staticmethod
    def generate_report_id(reflections: list[Reflection], created_at: str) -> str:
        ids_str = ",".join(sorted(r.reflection_id for r in reflections))
        data = f"report:{ids_str}:{created_at}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"RREP-{h}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "reflections": [r.to_dict() for r in self.reflections],
            "summary": self.summary,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ReflectionReport:
        return cls(
            report_id=d["report_id"],
            reflections=[Reflection.from_dict(r) for r in d["reflections"]],
            summary=d["summary"],
            created_at=d["created_at"],
        )
