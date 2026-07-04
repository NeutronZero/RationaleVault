"""
RationaleVault Skill Platform — SkillEventEmitter.

Converts execution records into immutable SkillExecutionEvent objects.
Decouples execution artifacts (SkillResult) from persistence (Event Ledger).

Design rules:
  - Emitter receives ExecutionSummary, not SkillResult.
  - ExecutionSummary is the decoupling layer between execution and persistence.
  - Emitter produces SkillExecutionEvent — an immutable value object.
  - The caller appends the event to the Ledger (ledger-ignorant design).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rationalevault.skill_platform.provenance import Provenance
from rationalevault.skill_platform.skill_event import SkillExecutionEvent


@dataclass(frozen=True)
class ExecutionSummary:
    """
    Decoupling layer between execution artifacts and persistence.

    Contains the minimum information needed to produce a
    SkillExecutionEvent without coupling to SkillResult internals.
    """
    execution_id: str
    decision_id: str
    skill_id: str
    skill_name: str
    skill_version: str
    state: str
    input_hash: str
    output_hash: str
    error: str | None
    started_at: str | None
    completed_at: str | None
    duration_ms: int
    provenance: Provenance
    timeout_seconds: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "decision_id": self.decision_id,
            "skill_id": self.skill_id,
            "skill_name": self.skill_name,
            "skill_version": self.skill_version,
            "state": self.state,
            "input_hash": self.input_hash,
            "output_hash": self.output_hash,
            "error": self.error,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_ms": self.duration_ms,
            "provenance": self.provenance.to_dict(),
            "timeout_seconds": self.timeout_seconds,
        }


class SkillEventEmitter:
    """
    Converts ExecutionSummary into SkillExecutionEvent.

    The emitter never sees SkillResult — it receives ExecutionSummary,
    keeping execution artifacts decoupled from persistence.
    """

    @staticmethod
    def emit(summary: ExecutionSummary) -> SkillExecutionEvent:
        """
        Emit a SkillExecutionEvent from an ExecutionSummary.
        """
        return SkillExecutionEvent(
            execution_id=summary.execution_id,
            decision_id=summary.decision_id,
            skill_id=summary.skill_id,
            skill_name=summary.skill_name,
            skill_version=summary.skill_version,
            state=summary.state,
            input_hash=summary.input_hash,
            output_hash=summary.output_hash,
            error=summary.error,
            started_at=summary.started_at,
            completed_at=summary.completed_at,
            duration_ms=summary.duration_ms,
            provenance=summary.provenance,
            timeout_seconds=summary.timeout_seconds,
        )

    @staticmethod
    def from_record(record: Any) -> ExecutionSummary:
        """
        Build an ExecutionSummary from a SkillExecutionRecord.

        This is the bridge between C1's record and C2's event system.
        """
        return ExecutionSummary(
            execution_id=record.execution_id,
            decision_id=record.context.decision_id,
            skill_id=record.context.manifest.skill_id,
            skill_name=record.context.manifest.name,
            skill_version=record.context.manifest.version,
            state=record.state.value,
            input_hash=record.context.snapshot_hash,
            output_hash="",  # computed by SkillOutput
            error=record.error,
            started_at=record.started_at,
            completed_at=record.completed_at,
            duration_ms=0,  # computed from started_at/completed_at
            provenance=record.context.provenance,
            timeout_seconds=record.timeout_seconds,
        )
