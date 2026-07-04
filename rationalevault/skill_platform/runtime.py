"""
RationaleVault Skill Platform — SkillRuntime.

The runtime orchestrates skill execution through a deterministic lifecycle
state machine. It is ledger-ignorant: it produces SkillExecutionRecord
objects that the caller converts into SKILL_EXECUTED events.

Design rules:
  - The runtime never knows how events are persisted.
  - It produces immutable SkillExecutionRecord convertible to event payload.
  - Lifecycle: SELECTED → AUTHORIZED → EXECUTING → COMPLETED/FAILED → RESULT_CREATED
  - RECORDED is NOT part of the runtime lifecycle (depends on external subsystem).
  - Permission check at AUTHORIZED state.
  - Timeout enforcement at EXECUTING state.
  - skill_fn is a callable provided by the caller — no plugin loading in C1.
  - The runtime accepts a single ExecutionContext — the interface does not
    expand with each new C2/C3/C4 requirement.
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

from rationalevault.skill_platform.context import ExecutionContext
from rationalevault.skill_platform.permissions import (
    PermissionChecker,
    PermissionDecision,
)
from rationalevault.skill_platform.provenance import Provenance, compute_snapshot_hash


class SkillState(str, Enum):
    """Lifecycle states for skill execution."""
    SELECTED = "SELECTED"
    AUTHORIZED = "AUTHORIZED"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RESULT_CREATED = "RESULT_CREATED"


@dataclass(frozen=True)
class SkillExecutionRecord:
    """
    Immutable record produced by the SkillRuntime.

    Convertible to a SKILL_EXECUTED event payload. The runtime never
    writes to the ledger — the caller handles persistence.

    Carries the full ExecutionContext for downstream use (auditing,
    replay, provenance exploration).
    """
    execution_id: str                      # SKE-[hash]
    state: SkillState                      # final lifecycle state
    context: ExecutionContext               # full execution inputs
    output_snapshot: dict[str, Any] | None # frozen outputs (None until COMPLETED)
    error: str | None                      # error message (None until FAILED)
    started_at: str | None                 # ISO timestamp
    completed_at: str | None               # ISO timestamp
    permission_decision: PermissionDecision  # result of permission check
    timeout_seconds: int                   # from manifest

    def to_event_payload(self) -> dict[str, Any]:
        """Convert to a SKILL_EXECUTED event payload dict."""
        return {
            "execution_id": self.execution_id,
            "decision_id": self.context.decision_id,
            "skill_id": self.context.manifest.skill_id,
            "skill_name": self.context.manifest.name,
            "skill_version": self.context.manifest.version,
            "state": self.state.value,
            "input_hash": self.context.snapshot_hash,
            "output_hash": compute_snapshot_hash(self.output_snapshot or {}),
            "error": self.error,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "permission_decision": self.permission_decision.to_dict(),
            "provenance": self.context.provenance.to_dict(),
            "timeout_seconds": self.timeout_seconds,
        }

    def to_dict(self) -> dict[str, Any]:
        return self.to_event_payload()


class SkillRuntimeError(Exception):
    """Base exception for skill runtime errors."""
    pass


class SandboxViolation(SkillRuntimeError):
    """Raised when a skill violates sandbox constraints."""
    pass


class SkillRuntime:
    """
    Orchestrates skill execution through the lifecycle state machine.

    The runtime is ledger-ignorant. It produces SkillExecutionRecord
    objects that the caller converts into SKILL_EXECUTED events.

    The runtime accepts a single ExecutionContext — the interface does
    not expand with each new C2/C3/C4 requirement.
    """

    @staticmethod
    def _generate_execution_id(
        skill_id: str, decision_id: str, policy_version: str
    ) -> str:
        data = f"execution:{skill_id}:{decision_id}:{policy_version}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"SKE-{h}"

    @staticmethod
    def _now_iso() -> str:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def execute(
        skill_fn: Callable[[dict[str, Any]], dict[str, Any]],
        context: ExecutionContext,
    ) -> SkillExecutionRecord:
        """
        Execute a skill through the full lifecycle.

        Parameters:
            skill_fn: Callable that takes input dict, returns output dict.
                      The runtime wraps it with permission checks, timeout,
                      and provenance. No plugin loading in C1.
            context:  Immutable ExecutionContext carrying all execution inputs.

        Returns:
            SkillExecutionRecord in RESULT_CREATED state.
        """
        started_at = SkillRuntime._now_iso()
        execution_id = SkillRuntime._generate_execution_id(
            context.manifest.skill_id,
            context.decision_id,
            context.gate_policy_version,
        )

        # ── Update provenance with execution_id ──
        provenance = Provenance(
            execution_id=execution_id,
            decision_id=context.provenance.decision_id,
            synthesis_id=context.provenance.synthesis_id,
            belief_id=context.provenance.belief_id,
            source_event_ids=context.provenance.source_event_ids,
            skill_version=context.provenance.skill_version,
            gate_policy_version=context.provenance.gate_policy_version,
            input_snapshot_hash=context.provenance.input_snapshot_hash,
            timestamp=context.provenance.timestamp,
        )

        # ── Create updated context with correct provenance ──
        # ExecutionContext is frozen, so we construct a new one
        updated_context = ExecutionContext(
            decision_id=context.decision_id,
            synthesis_id=context.synthesis_id,
            belief_id=context.belief_id,
            source_event_ids=context.source_event_ids,
            manifest=context.manifest,
            candidate=context.candidate,
            input_snapshot=context.input_snapshot,
            provenance=provenance,
            capabilities=context.capabilities,
            gate_policy_version=context.gate_policy_version,
            runtime_config=context.runtime_config,
            snapshot_hash=context.snapshot_hash,
        )

        # ── SELECTED → AUTHORIZED ──
        perm_decision = PermissionChecker.check(
            context.manifest.required_permissions, context.capabilities
        )

        if not perm_decision.allowed:
            completed_at = SkillRuntime._now_iso()
            return SkillExecutionRecord(
                execution_id=execution_id,
                state=SkillState.RESULT_CREATED,
                context=updated_context,
                output_snapshot=None,
                error=perm_decision.denial_reason,
                started_at=started_at,
                completed_at=completed_at,
                permission_decision=perm_decision,
                timeout_seconds=context.manifest.timeout_seconds,
            )

        # ── AUTHORIZED → EXECUTING ──
        exec_start = time.monotonic()
        try:
            output = skill_fn(context.input_snapshot)
            exec_end = time.monotonic()
            duration_ms = int((exec_end - exec_start) * 1000)

            # ── Timeout check ──
            if (
                context.manifest.timeout_seconds > 0
                and duration_ms > context.manifest.timeout_seconds * 1000
            ):
                completed_at = SkillRuntime._now_iso()
                return SkillExecutionRecord(
                    execution_id=execution_id,
                    state=SkillState.RESULT_CREATED,
                    context=updated_context,
                    output_snapshot=None,
                    error=f"Execution exceeded timeout of {context.manifest.timeout_seconds}s",
                    started_at=started_at,
                    completed_at=completed_at,
                    permission_decision=perm_decision,
                    timeout_seconds=context.manifest.timeout_seconds,
                )

            # ── COMPLETED ──
            completed_at = SkillRuntime._now_iso()
            return SkillExecutionRecord(
                execution_id=execution_id,
                state=SkillState.RESULT_CREATED,
                context=updated_context,
                output_snapshot=output,
                error=None,
                started_at=started_at,
                completed_at=completed_at,
                permission_decision=perm_decision,
                timeout_seconds=context.manifest.timeout_seconds,
            )

        except Exception as exc:
            exec_end = time.monotonic()
            duration_ms = int((exec_end - exec_start) * 1000)
            completed_at = SkillRuntime._now_iso()
            return SkillExecutionRecord(
                execution_id=execution_id,
                state=SkillState.RESULT_CREATED,
                context=updated_context,
                output_snapshot=None,
                error=str(exc),
                started_at=started_at,
                completed_at=completed_at,
                permission_decision=perm_decision,
                timeout_seconds=context.manifest.timeout_seconds,
            )
