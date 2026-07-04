"""
RationaleVault Skill Platform — Execution State Projection.

A BASE projection that tracks skill execution state from SKILL_EXECUTED
events in the Event Ledger. This is not operational telemetry — it is a
first-class evidence source for the cognitive pipeline.

Design rules:
  - BASE projection: folds ledger events directly.
  - Ephemeral: compiled on demand, never persisted.
  - Read-only: skills cannot mutate it.
  - No reliability computation inside the projection — that is a derived
    metric computed by evaluator/doctor.
  - Deterministic: same events → same execution state.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from rationalevault.projections.base import BaseProjection, ProjectionKind, SemVer
from rationalevault.schema.events import EventRecord, EventType


@dataclass(frozen=True)
class ExecutionEntry:
    """A single execution record derived from a SKILL_EXECUTED event."""
    execution_id: str
    decision_id: str
    skill_id: str
    state: str                             # COMPLETED | FAILED | TIMEOUT | DENIED
    input_hash: str
    output_hash: str
    error: str | None
    started_at: str | None
    completed_at: str | None
    duration_ms: int | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "decision_id": self.decision_id,
            "skill_id": self.skill_id,
            "state": self.state,
            "input_hash": self.input_hash,
            "output_hash": self.output_hash,
            "error": self.error,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_ms": self.duration_ms,
        }


@dataclass(frozen=True)
class ExecutionState:
    """
    Deterministic projection of skill execution state.

    Contains raw counts and lists — no derived analysis.
    Reliability metrics are computed externally by evaluator/doctor.
    """
    pending_decisions: list[str]           # DEC- IDs with no SKILL_EXECUTED event
    completed_executions: list[ExecutionEntry]
    failed_executions: list[ExecutionEntry]
    timeout_executions: list[ExecutionEntry]
    denied_executions: list[ExecutionEntry]
    execution_counts: dict[str, int]      # skill_id → total executions
    success_counts: dict[str, int]        # skill_id → successful executions
    durations: dict[str, list[int]]       # skill_id → list of durations_ms
    total_executions: int
    total_completed: int
    total_failed: int
    total_timeout: int
    total_denied: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "pending_decisions": self.pending_decisions,
            "completed_executions": [e.to_dict() for e in self.completed_executions],
            "failed_executions": [e.to_dict() for e in self.failed_executions],
            "timeout_executions": [e.to_dict() for e in self.timeout_executions],
            "denied_executions": [e.to_dict() for e in self.denied_executions],
            "execution_counts": self.execution_counts,
            "success_counts": self.success_counts,
            "durations": self.durations,
            "total_executions": self.total_executions,
            "total_completed": self.total_completed,
            "total_failed": self.total_failed,
            "total_timeout": self.total_timeout,
            "total_denied": self.total_denied,
        }


class ExecutionStateProjection(BaseProjection):
    """
    BASE projection tracking skill execution state.

    Folds SKILL_EXECUTED events from the Event Ledger.
    """
    projection_name: ClassVar[str] = "execution_state"
    version: ClassVar[SemVer] = SemVer(1, 0, 0)
    projection_kind: ClassVar[ProjectionKind] = ProjectionKind.BASE
    build_priority: ClassVar[int] = 90

    @staticmethod
    def reduce(
        events: list[EventRecord],
        known_decision_ids: list[str] | None = None,
    ) -> ExecutionState:
        """
        Fold SKILL_EXECUTED events into an ExecutionState.

        Parameters:
            events: All events from the Event Ledger (in sequence order).
            known_decision_ids: All DEC- IDs from the DecisionSet.
                                Used to determine pending decisions.
        """
        completed: list[ExecutionEntry] = []
        failed: list[ExecutionEntry] = []
        timeouts: list[ExecutionEntry] = []
        denied: list[ExecutionEntry] = []
        executed_decision_ids: set[str] = set()
        execution_counts: dict[str, int] = {}
        success_counts: dict[str, int] = {}
        durations: dict[str, list[int]] = {}

        for event in events:
            if event.event_type != EventType.SKILL_EXECUTED:
                continue

            payload = event.payload
            state = payload.get("state", "UNKNOWN")
            skill_id = payload.get("skill_id", "")
            decision_id = payload.get("decision_id", "")

            executed_decision_ids.add(decision_id)

            entry = ExecutionEntry(
                execution_id=payload.get("execution_id", ""),
                decision_id=decision_id,
                skill_id=skill_id,
                state=state,
                input_hash=payload.get("input_hash", ""),
                output_hash=payload.get("output_hash", ""),
                error=payload.get("error"),
                started_at=payload.get("started_at"),
                completed_at=payload.get("completed_at"),
                duration_ms=payload.get("duration_ms"),
            )

            # Count executions per skill
            execution_counts[skill_id] = execution_counts.get(skill_id, 0) + 1

            # Track durations per skill
            if entry.duration_ms is not None:
                if skill_id not in durations:
                    durations[skill_id] = []
                durations[skill_id].append(entry.duration_ms)

            # Classify by state
            if state == "COMPLETED":
                completed.append(entry)
                success_counts[skill_id] = success_counts.get(skill_id, 0) + 1
            elif state == "TIMEOUT":
                timeouts.append(entry)
            elif state == "DENIED":
                denied.append(entry)
            else:
                # FAILED or unknown
                failed.append(entry)

        # Determine pending decisions
        pending: list[str] = []
        if known_decision_ids is not None:
            pending = [
                did for did in known_decision_ids
                if did not in executed_decision_ids
            ]

        return ExecutionState(
            pending_decisions=pending,
            completed_executions=completed,
            failed_executions=failed,
            timeout_executions=timeouts,
            denied_executions=denied,
            execution_counts=execution_counts,
            success_counts=success_counts,
            durations=durations,
            total_executions=len(completed) + len(failed) + len(timeouts) + len(denied),
            total_completed=len(completed),
            total_failed=len(failed),
            total_timeout=len(timeouts),
            total_denied=len(denied),
        )

    @classmethod
    def build(
        cls,
        events: list[EventRecord],
        known_decision_ids: list[str] | None = None,
    ) -> ExecutionState:
        """Build an ExecutionState from events (class method entry point)."""
        return cls.reduce(events, known_decision_ids)
