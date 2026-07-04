"""
RationaleVault Skill Platform — SkillExecutionEvent.

Immutable event object produced by the event emitter.
Convertible to a SKILL_EXECUTED event payload for the Event Ledger.

Design rules:
  - SkillExecutionEvent is frozen — immutable after creation.
  - to_payload() produces the dict for Event Ledger append.
  - The emitter never sees SkillResult directly — it receives
    ExecutionSummary (decoupling execution artifacts from persistence).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rationalevault.skill_platform.provenance import Provenance


@dataclass(frozen=True)
class SkillExecutionEvent:
    """
    Immutable event object for SKILL_EXECUTED.

    Produced by SkillEventEmitter from ExecutionSummary.
    Consumed by caller for Event Ledger append.
    """
    version: str = "1.0"
    event_type: str = "SKILL_EXECUTED"
    execution_id: str = ""
    decision_id: str = ""
    skill_id: str = ""
    skill_name: str = ""
    skill_version: str = ""
    state: str = ""                         # COMPLETED | FAILED | TIMEOUT | DENIED
    input_hash: str = ""
    output_hash: str = ""
    error: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    duration_ms: int = 0
    provenance: Provenance | None = None
    timeout_seconds: int = 0

    def to_payload(self) -> dict[str, Any]:
        """Convert to a SKILL_EXECUTED event payload dict."""
        return {
            "version": self.version,
            "event_type": self.event_type,
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
            "provenance": self.provenance.to_dict() if self.provenance else {},
            "timeout_seconds": self.timeout_seconds,
        }

    def to_dict(self) -> dict[str, Any]:
        return self.to_payload()
