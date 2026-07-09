"""
RationaleVault Skill Platform — SkillExecutor.

Orchestrates the full execution pipeline. Delegates each step to
a dedicated component — never does work directly.

Design rules:
  - Executor owns orchestration only — not business logic.
  - Each step is a separate method for policy injection.
  - Steps: resolve → activate → build_input → authorize → execute → validate → record → emit
  - The executor never writes to the Event Ledger.
  - The executor never mutates projections or cognitive state.
"""
from __future__ import annotations

from rationalevault.logging import get_logger
logger = get_logger(__name__)


import time
from dataclasses import dataclass
from typing import Any, Callable

from rationalevault.skill_platform.activator import SkillActivator
from rationalevault.skill_platform.event_emitter import ExecutionSummary, SkillEventEmitter
from rationalevault.skill_platform.execution_plan import ExecutionPlan
from rationalevault.skill_platform.execution_report import ExecutionReport
from rationalevault.skill_platform.input_builder import SkillInputBuilder
from rationalevault.skill_platform.permissions import PermissionChecker
from rationalevault.skill_platform.provenance import Provenance
from rationalevault.skill_platform.resolver import SkillResolver
from rationalevault.skill_platform.result import SkillResult, SkillResultStatus
from rationalevault.skill_platform.sandbox import SkillSandbox
from rationalevault.skill_platform.skill_event import SkillExecutionEvent
from rationalevault.skill_platform.skill_output import SkillOutput
from rationalevault.skill_platform.validator import OutputValidator

# Phase C3 Imports
from rationalevault.skill_platform.gate import (
    ExecutionGate,
    ExecutionGatePolicy,
    ExecutionPromoter,
    PromotionDecisionType,
    ArtifactPromotionReport,
)
from rationalevault.skill_platform.artifact import (
    Artifact,
    ArtifactCandidate,
    ArtifactLineage,
    ArtifactKind,
    ArtifactReference,
)
from rationalevault.skill_platform.execution_state import ExecutionState, ExecutionEntry
from rationalevault.evaluation.thresholds import ExecutionThresholds
from rationalevault.evaluation.execution_evaluator import ExecutionEvaluator, ExecutionEvaluationInput



@dataclass(frozen=True)
class ExecutionStep:
    """Record of a single execution step for auditing."""
    step: str
    status: str                           # "ok" | "failed" | "skipped"
    detail: str = ""


class SkillExecutor:
    """
    Orchestrates the full execution pipeline.

    Delegates each step to a dedicated component. Never does work
    directly. Each step is a separate method for policy injection.
    """

    @staticmethod
    def execute(
        plan: ExecutionPlan,
        skill_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ) -> tuple[SkillResult, SkillExecutionEvent, list[ExecutionStep]]:
        """
        Execute a full skill execution plan.

        Steps:
          1. resolve   — manifest → SkillDescriptor
          2. activate  — SkillDescriptor → callable (if skill_fn not provided)
          3. build_input — DecisionItem + projections → SkillInput
          4. authorize — permission check
          5. execute   — skill_fn(SkillInput) → SkillOutput
          6. validate  — SkillOutput against output_schema
          7. record    — build SkillResult
          8. emit      — build SkillExecutionEvent

        Returns (SkillResult, SkillExecutionEvent, execution_steps).
        """
        steps: list[ExecutionStep] = []
        started_at = SkillExecutor._now_iso()
        exec_start = time.monotonic()

        # ── Step 1: Resolve ──
        descriptor = SkillResolver.resolve(plan.context.manifest)
        steps.append(ExecutionStep(step="resolve", status="ok"))

        # ── Step 2: Activate ──
        if skill_fn is None:
            try:
                skill_fn = SkillActivator.activate(descriptor)
                steps.append(ExecutionStep(step="activate", status="ok"))
            except Exception as e:
                steps.append(ExecutionStep(step="activate", status="failed", detail=str(e)))
                result = SkillResult.failure(
                    execution_id=plan.context.provenance.execution_id or "",
                    decision_id=plan.context.decision_id,
                    skill_id=plan.context.manifest.skill_id,
                    error=f"Activation failed: {e}",
                    duration_ms=0,
                    provenance=plan.context.provenance,
                )
                event = SkillExecutor._emit_event(plan, result, started_at, 0)
                return result, event, steps
        else:
            steps.append(ExecutionStep(step="activate", status="skipped", detail="skill_fn provided"))

        # ── Step 3: Build Input ──
        try:
            decision = plan.context.candidate.decision
            projections = plan.context.projections if hasattr(plan.context, 'projections') else None
            skill_input = SkillInputBuilder.build(decision, projections)
            steps.append(ExecutionStep(step="build_input", status="ok"))
        except Exception as e:
            steps.append(ExecutionStep(step="build_input", status="failed", detail=str(e)))
            result = SkillResult.failure(
                execution_id=plan.context.provenance.execution_id or "",
                decision_id=plan.context.decision_id,
                skill_id=plan.context.manifest.skill_id,
                error=f"Input build failed: {e}",
                duration_ms=0,
                provenance=plan.context.provenance,
            )
            event = SkillExecutor._emit_event(plan, result, started_at, 0)
            return result, event, steps

        # ── Step 4: Authorize ──
        perm_decision = PermissionChecker.check(
            plan.context.manifest.required_permissions, plan.context.capabilities
        )
        if not perm_decision.allowed:
            steps.append(ExecutionStep(step="authorize", status="failed", detail=perm_decision.denial_reason))
            result = SkillResult.denied(
                execution_id=plan.context.provenance.execution_id or "",
                decision_id=plan.context.decision_id,
                skill_id=plan.context.manifest.skill_id,
                denial_reason=perm_decision.denial_reason,
                provenance=plan.context.provenance,
            )
            event = SkillExecutor._emit_event(plan, result, started_at, 0)
            return result, event, steps
        steps.append(ExecutionStep(step="authorize", status="ok"))

        # ── Step 5: Execute (with cooperative sandbox) ──
        try:
            timeout = SkillSandbox.validate_timeout(
                plan.timeout_seconds, plan.context.manifest.timeout_seconds
            )
            output_dict = SkillSandbox.execute_with_timeout(
                skill_fn, skill_input.to_dict(), timeout
            )
            skill_output = SkillOutput.from_dict(output_dict)
            steps.append(ExecutionStep(step="execute", status="ok"))
        except Exception as e:
            exec_end = time.monotonic()
            duration_ms = int((exec_end - exec_start) * 1000)
            steps.append(ExecutionStep(step="execute", status="failed", detail=str(e)))
            result = SkillResult.failure(
                execution_id=plan.context.provenance.execution_id or "",
                decision_id=plan.context.decision_id,
                skill_id=plan.context.manifest.skill_id,
                error=str(e),
                duration_ms=duration_ms,
                provenance=plan.context.provenance,
            )
            event = SkillExecutor._emit_event(plan, result, started_at, duration_ms)
            return result, event, steps

        # ── Step 6: Validate Output ──
        validation = OutputValidator.validate(
            output_dict, plan.context.manifest.output_schema
        )
        if not validation.valid:
            exec_end = time.monotonic()
            duration_ms = int((exec_end - exec_start) * 1000)
            steps.append(ExecutionStep(step="validate", status="failed", detail=str(validation.errors)))
            result = SkillResult.failure(
                execution_id=plan.context.provenance.execution_id or "",
                decision_id=plan.context.decision_id,
                skill_id=plan.context.manifest.skill_id,
                error=f"Output validation failed: {validation.errors}",
                duration_ms=duration_ms,
                provenance=plan.context.provenance,
            )
            event = SkillExecutor._emit_event(plan, result, started_at, duration_ms)
            return result, event, steps
        steps.append(ExecutionStep(step="validate", status="ok"))

        # ── Step 7: Record (build SkillResult) ──
        exec_end = time.monotonic()
        duration_ms = int((exec_end - exec_start) * 1000)

        provenance = Provenance(
            execution_id=plan.context.provenance.execution_id or "",
            decision_id=plan.context.decision_id,
            synthesis_id=plan.context.synthesis_id,
            belief_id=plan.context.belief_id,
            source_event_ids=plan.context.source_event_ids,
            skill_version=plan.context.manifest.version,
            gate_policy_version=plan.context.gate_policy_version,
            input_snapshot_hash=plan.context.snapshot_hash,
            timestamp=plan.context.provenance.timestamp,
        )

        initial_result = SkillResult.success(
            execution_id=provenance.execution_id,
            decision_id=plan.context.decision_id,
            skill_id=plan.context.manifest.skill_id,
            outputs=output_dict,
            artifacts=[],
            metrics={"duration_ms": duration_ms, **skill_output.metrics},
            warnings=skill_output.warnings,
            duration_ms=duration_ms,
            provenance=provenance,
        )

        # ── Step 7b: Run Execution Evaluation & Gates ──
        report = ExecutionReport.from_results([initial_result])
        entry = ExecutionEntry(
            execution_id=initial_result.execution_id,
            decision_id=initial_result.decision_id,
            skill_id=initial_result.skill_id,
            state=initial_result.status.value,
            input_hash=plan.context.snapshot_hash,
            output_hash=initial_result.result_id,
            error=initial_result.error,
            started_at=started_at,
            completed_at=SkillExecutor._now_iso(),
            duration_ms=duration_ms,
        )
        execution_state = ExecutionState(
            pending_decisions=[],
            completed_executions=[entry] if initial_result.status == SkillResultStatus.COMPLETED else [],
            failed_executions=[entry] if initial_result.status != SkillResultStatus.COMPLETED else [],
            timeout_executions=[],
            denied_executions=[],
            execution_counts={initial_result.skill_id: 1},
            success_counts={initial_result.skill_id: 1} if initial_result.status == SkillResultStatus.COMPLETED else {},
            durations={initial_result.skill_id: [duration_ms]},
            total_executions=1,
            total_completed=1 if initial_result.status == SkillResultStatus.COMPLETED else 0,
            total_failed=1 if initial_result.status != SkillResultStatus.COMPLETED else 0,
            total_timeout=0,
            total_denied=0,
        )
        thresholds = ExecutionThresholds(
            profile_name="development",
            min_success_rate=0.90,
            max_timeout_rate=0.05,
            max_denial_rate=0.05,
            min_overall_score=0.90,
        )
        evaluator = ExecutionEvaluator()
        evaluation = evaluator.evaluate(
            ExecutionEvaluationInput(
                state=execution_state,
                report=report,
                thresholds=thresholds,
            )
        )
        policy = ExecutionGatePolicy(version=plan.context.gate_policy_version)
        gate_result = ExecutionGate.evaluate(evaluation, policy)

        # ── Step 7c: Promotion & Artifact Lineage ──
        candidates: list[ArtifactCandidate] = []
        raw_candidates = output_dict.get("artifact_candidates") or output_dict.get("artifacts")
        if isinstance(raw_candidates, list):
            for item in raw_candidates:
                if isinstance(item, dict):
                    try:
                        kind_str = item.get("kind", "OTHER")
                        ref_dict = item.get("reference", {})
                        ref = ArtifactReference(
                            scheme=ref_dict.get("scheme", "file"),
                            location=ref_dict.get("location", ""),
                        )
                        content_hash = item.get("hash", "unknown")
                        size = item.get("size", 0)
                        mime_type = item.get("mime_type", "text/plain")
                        cand_id = ArtifactCandidate.generate_candidate_id(
                            plan.context.manifest.skill_id,
                            initial_result.execution_id,
                            content_hash,
                        )
                        candidates.append(
                            ArtifactCandidate(
                                candidate_id=cand_id,
                                kind=ArtifactKind(kind_str),
                                reference=ref,
                                hash=content_hash,
                                size=size,
                                mime_type=mime_type,
                                metadata=item.get("metadata", {}),
                            )
                        )
                    except Exception as e:
                        logger.debug(f"Swallowed exception: {e}")

        promotion = ExecutionPromoter.promote(gate_result, candidates, policy.version)

        promoted_artifacts: list[Artifact] = []
        artifact_lineages: list[ArtifactLineage] = []

        if promotion.decision == PromotionDecisionType.PASS:
            for c in candidates:
                art_id = Artifact.generate_artifact_id(
                    plan.context.manifest.skill_id,
                    initial_result.execution_id,
                    c.hash,
                )
                promoted_artifacts.append(
                    Artifact(
                        artifact_id=art_id,
                        kind=c.kind,
                        reference=c.reference,
                        hash=c.hash,
                        size=c.size,
                        mime_type=c.mime_type,
                        created_at=SkillExecutor._now_iso(),
                    )
                )
                artifact_lineages.append(
                    ArtifactLineage(
                        artifact_id=art_id,
                        result_id=initial_result.result_id,
                        execution_id=initial_result.execution_id,
                        skill_id=plan.context.manifest.skill_id,
                        decision_id=plan.context.decision_id,
                        synthesis_id=plan.context.synthesis_id,
                        belief_id=plan.context.belief_id,
                        source_event_ids=plan.context.source_event_ids,
                        projection_snapshot_hash=plan.context.snapshot_hash,
                    )
                )

        # Build ArtifactPromotionReport
        rejected_candidates = candidates if promotion.decision != PromotionDecisionType.PASS else []
        promotion_report = ArtifactPromotionReport(
            promoted=promoted_artifacts,
            rejected=rejected_candidates,
            decision=promotion,
            gate_result=gate_result,
            evaluation=evaluation,
        )

        result = SkillResult.success(
            execution_id=provenance.execution_id,
            decision_id=plan.context.decision_id,
            skill_id=plan.context.manifest.skill_id,
            outputs=output_dict,
            artifacts=[art.artifact_id for art in promoted_artifacts],
            metrics={
                "duration_ms": duration_ms,
                "execution_score": evaluation.score,
                **skill_output.metrics,
            },
            warnings=skill_output.warnings + gate_result.warnings,
            duration_ms=duration_ms,
            provenance=provenance,
            artifact_lineages=artifact_lineages,
            promotion_report=promotion_report,
        )
        steps.append(ExecutionStep(step="record", status="ok"))

        # ── Step 8: Emit Event ──
        event = SkillExecutor._emit_event(plan, result, started_at, duration_ms)
        steps.append(ExecutionStep(step="emit", status="ok"))

        return result, event, steps

    @staticmethod
    def _emit_event(
        plan: ExecutionPlan,
        result: SkillResult,
        started_at: str,
        duration_ms: int,
    ) -> SkillExecutionEvent:
        """Build a SkillExecutionEvent from plan and result."""
        summary = ExecutionSummary(
            execution_id=result.execution_id,
            decision_id=plan.context.decision_id,
            skill_id=plan.context.manifest.skill_id,
            skill_name=plan.context.manifest.name,
            skill_version=plan.context.manifest.version,
            state=result.status.value,
            input_hash=plan.context.snapshot_hash,
            output_hash=result.result_id,  # simplified
            error=result.error,
            started_at=started_at,
            completed_at=SkillExecutor._now_iso(),
            duration_ms=duration_ms,
            provenance=plan.context.provenance,
            timeout_seconds=plan.timeout_seconds,
        )
        return SkillEventEmitter.emit(summary)

    @staticmethod
    def _now_iso() -> str:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def explain(
        plan: ExecutionPlan,
    ) -> dict[str, Any]:
        """
        Explain what would happen if this plan were executed.

        Used by `skill explain` CLI command for debugging.
        """
        descriptor = SkillResolver.resolve(plan.context.manifest)
        perm_decision = PermissionChecker.check(
            plan.context.manifest.required_permissions, plan.context.capabilities
        )

        return {
            "plan": plan.to_dict(),
            "descriptor": descriptor.to_dict(),
            "permission_check": perm_decision.to_dict(),
            "would_execute": perm_decision.allowed and not plan.candidate.blocked,
            "block_reason": plan.candidate.blocked_reason if plan.candidate.blocked else None,
            "deny_reason": perm_decision.denial_reason if not perm_decision.allowed else None,
        }
