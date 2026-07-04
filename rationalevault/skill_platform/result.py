"""
RationaleVault Skill Platform — SkillResult.

Every skill execution produces a SkillResult, even on failure.
This is the formal output contract that flows from skill execution
into the Event Ledger and the Execution State Projection.

Design rules:
  - SkillResult is frozen — immutable after creation.
  - SRT-[hash] is derived from (execution_id, output_hash).
  - On failure, outputs={}, artifacts=[], error carries the reason.
  - Provenance is always present — even on failure.
  - Factory methods enforce the invariant that every path produces
    a valid SkillResult.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from rationalevault.skill_platform.provenance import Provenance, compute_snapshot_hash
from rationalevault.skill_platform.artifact import ArtifactLineage
from rationalevault.skill_platform.gate import ArtifactPromotionReport


class SkillResultStatus(str, Enum):
    """Final status of a skill execution."""
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"
    DENIED = "DENIED"


@dataclass(frozen=True)
class SkillResult:
    """
    Immutable output contract for skill execution.

    result_id is deterministic: SRT-[hash] from (execution_id, output_hash).
    Every execution — success or failure — produces a SkillResult.
    """
    result_id: str                        # SRT-[hash] from (execution_id, output_hash)
    execution_id: str                     # SKE-[hash]
    decision_id: str                      # DEC-[hash]
    skill_id: str                         # SKL-[hash]
    status: SkillResultStatus             # COMPLETED | FAILED | TIMEOUT | DENIED
    outputs: dict[str, Any]               # skill-produced output (empty dict on failure)
    artifacts: list[str]                  # paths or IDs of produced artifacts (empty on failure)
    metrics: dict[str, Any]               # deterministic measurements (duration_ms, etc.)
    warnings: list[str]                   # non-fatal issues (empty if clean)
    error: str | None                     # error message (None on success)
    duration_ms: int                      # wall-clock time
    provenance: Provenance                # full lineage trace
    artifact_lineages: list[ArtifactLineage] = field(default_factory=list)
    promotion_report: ArtifactPromotionReport | None = None


    @staticmethod
    def _generate_result_id(execution_id: str, output_hash: str) -> str:
        data = f"result:{execution_id}:{output_hash}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"SRT-{h}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_id": self.result_id,
            "execution_id": self.execution_id,
            "decision_id": self.decision_id,
            "skill_id": self.skill_id,
            "status": self.status.value,
            "outputs": self.outputs,
            "artifacts": self.artifacts,
            "metrics": self.metrics,
            "warnings": self.warnings,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "provenance": self.provenance.to_dict(),
            "artifact_lineages": [al.to_dict() for al in self.artifact_lineages],
            "promotion_report": self.promotion_report.to_dict() if self.promotion_report else None,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "SkillResult":
        return cls(
            result_id=d["result_id"],
            execution_id=d["execution_id"],
            decision_id=d["decision_id"],
            skill_id=d["skill_id"],
            status=SkillResultStatus(d["status"]),
            outputs=d.get("outputs", {}),
            artifacts=d.get("artifacts", []),
            metrics=d.get("metrics", {}),
            warnings=d.get("warnings", []),
            error=d.get("error"),
            duration_ms=d.get("duration_ms", 0),
            provenance=Provenance.from_dict(d["provenance"]),
            artifact_lineages=[ArtifactLineage.from_dict(al) for al in d.get("artifact_lineages", [])],
            promotion_report=ArtifactPromotionReport.from_dict(d["promotion_report"]) if d.get("promotion_report") else None,
        )

    @classmethod
    def success(
        cls,
        execution_id: str,
        decision_id: str,
        skill_id: str,
        outputs: dict[str, Any],
        artifacts: list[str],
        metrics: dict[str, Any],
        warnings: list[str],
        duration_ms: int,
        provenance: Provenance,
        artifact_lineages: list[ArtifactLineage] = None,
        promotion_report: ArtifactPromotionReport = None,
    ) -> "SkillResult":
        output_hash = compute_snapshot_hash(outputs)
        result_id = cls._generate_result_id(execution_id, output_hash)
        return cls(
            result_id=result_id,
            execution_id=execution_id,
            decision_id=decision_id,
            skill_id=skill_id,
            status=SkillResultStatus.COMPLETED,
            outputs=outputs,
            artifacts=artifacts,
            metrics=metrics,
            warnings=warnings,
            error=None,
            duration_ms=duration_ms,
            provenance=provenance,
            artifact_lineages=artifact_lineages if artifact_lineages is not None else [],
            promotion_report=promotion_report,
        )

    @classmethod
    def failure(
        cls,
        execution_id: str,
        decision_id: str,
        skill_id: str,
        error: str,
        duration_ms: int,
        provenance: Provenance,
        status: SkillResultStatus = SkillResultStatus.FAILED,
    ) -> "SkillResult":
        output_hash = compute_snapshot_hash({"error": error})
        result_id = cls._generate_result_id(execution_id, output_hash)
        return cls(
            result_id=result_id,
            execution_id=execution_id,
            decision_id=decision_id,
            skill_id=skill_id,
            status=status,
            outputs={},
            artifacts=[],
            metrics={},
            warnings=[],
            error=error,
            duration_ms=duration_ms,
            provenance=provenance,
        )

    @classmethod
    def denied(
        cls,
        execution_id: str,
        decision_id: str,
        skill_id: str,
        denial_reason: str,
        provenance: Provenance,
    ) -> "SkillResult":
        output_hash = compute_snapshot_hash({"denied": denial_reason})
        result_id = cls._generate_result_id(execution_id, output_hash)
        return cls(
            result_id=result_id,
            execution_id=execution_id,
            decision_id=decision_id,
            skill_id=skill_id,
            status=SkillResultStatus.DENIED,
            outputs={},
            artifacts=[],
            metrics={},
            warnings=[],
            error=denial_reason,
            duration_ms=0,
            provenance=provenance,
        )
