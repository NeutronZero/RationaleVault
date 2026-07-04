"""RationaleVault Workspace State Projection — Deterministic workspace state projection.

WorkspaceState = WorkspaceStateProjection.project(workspace, ...)

Answers "What is happening in this workspace right now?"

Aggregates active subsystem state:
  - Decisions: open/active decision IDs
  - Executions: running skill execution IDs
  - Reflections: pending reflection candidate IDs
  - Knowledge: active knowledge object IDs
  - Promotions: open promotion pipeline IDs
  - Planner: current policy ID
  - Scheduler: pending/running job IDs

Produces a compiled WorkspaceState with:
  - All active subsystem IDs (deterministic, sorted)
  - Derived counts and metrics
  - Activity summary (human-readable)
  - Last activity timestamp

Design constraints:
  - No I/O during projection (all data passed in)
  - Deterministic: same input → identical WorkspaceState
  - Replayable: state recomputed from inputs on every projection
  - Workspace is frozen; WorkspaceState is derived
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from rationalevault.projections.base import BaseProjection, ProjectionKind, SemVer
from rationalevault.workspace.models import Workspace


# ── WorkspaceState ─────────────────────────────────────────────────────────

@dataclass(frozen=True)
class WorkspaceState:
    """Compiled state of what is happening in a workspace right now.

    Aggregates active subsystem state into a single deterministic snapshot.
    Produced by WorkspaceStateProjection.project().
    """
    workspace_id: str
    workspace_name: str
    workspace_status: str
    compiled_at: str
    projection_version: str = "1.0"

    # Active subsystem IDs (sorted, deterministic)
    active_decisions: list[str] = field(default_factory=list)
    running_executions: list[str] = field(default_factory=list)
    pending_reflections: list[str] = field(default_factory=list)
    active_knowledge: list[str] = field(default_factory=list)
    open_promotions: list[str] = field(default_factory=list)
    planner_policy_id: str | None = None
    scheduler_jobs: list[str] = field(default_factory=list)

    # Derived counts
    decision_count: int = 0
    execution_count: int = 0
    reflection_count: int = 0
    knowledge_count: int = 0
    promotion_count: int = 0
    job_count: int = 0

    # Activity summary
    last_activity_at: str | None = None
    activity_summary: str = ""
    total_active_items: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "workspace_id": self.workspace_id,
            "workspace_name": self.workspace_name,
            "workspace_status": self.workspace_status,
            "compiled_at": self.compiled_at,
            "projection_version": self.projection_version,
            "active_decisions": self.active_decisions,
            "running_executions": self.running_executions,
            "pending_reflections": self.pending_reflections,
            "active_knowledge": self.active_knowledge,
            "open_promotions": self.open_promotions,
            "planner_policy_id": self.planner_policy_id,
            "scheduler_jobs": self.scheduler_jobs,
            "decision_count": self.decision_count,
            "execution_count": self.execution_count,
            "reflection_count": self.reflection_count,
            "knowledge_count": self.knowledge_count,
            "promotion_count": self.promotion_count,
            "job_count": self.job_count,
            "last_activity_at": self.last_activity_at,
            "activity_summary": self.activity_summary,
            "total_active_items": self.total_active_items,
        }


# ── WorkspaceStateProjection ──────────────────────────────────────────────

class WorkspaceStateProjection(BaseProjection):
    """Derives WorkspaceState from workspace and subsystem data.

    Answers "What is happening in this workspace right now?"
    Aggregates decisions, executions, reflections, knowledge, promotions,
    planner policy, and scheduler jobs into a single deterministic snapshot.

    Deterministic: same input → identical WorkspaceState.
    """
    projection_name: ClassVar[str] = "workspace_state"
    version: ClassVar[SemVer] = SemVer(1, 0, 0)
    projection_kind: ClassVar[ProjectionKind] = ProjectionKind.COMPOSITE
    dependencies: ClassVar[list[type[BaseProjection]]] = []
    architectural_dependencies: ClassVar[list[str]] = [
        "KnowledgeProjection",
        "ReflectionStateProjection",
    ]
    build_priority: ClassVar[int] = 5

    @staticmethod
    def project(
        workspace: Workspace,
        active_decisions: list[str] | None = None,
        running_executions: list[str] | None = None,
        pending_reflections: list[str] | None = None,
        active_knowledge: list[str] | None = None,
        open_promotions: list[str] | None = None,
        planner_policy_id: str | None = None,
        scheduler_jobs: list[str] | None = None,
        reference_time: datetime | None = None,
    ) -> WorkspaceState:
        """Project workspace state from workspace and subsystem data.

        Args:
            workspace: The workspace to project state for.
            active_decisions: Open/active DEC-[hash] IDs.
            running_executions: Running SKE-[hash] IDs.
            pending_reflections: Pending RCAND-[hash] IDs.
            active_knowledge: Active KNOW-[hash] IDs.
            open_promotions: Open PROMO-[hash] IDs.
            planner_policy_id: Current PPOL-[hash] ID.
            scheduler_jobs: Pending/running CJOB-[hash] IDs.
            reference_time: Deterministic datetime override.

        Returns:
            WorkspaceState with all active subsystem state.
        """
        from rationalevault.organization.utils import resolve_compiled_at
        now = resolve_compiled_at(reference_time)

        # Normalize inputs (None → empty lists)
        decisions = sorted(active_decisions or [])
        executions = sorted(running_executions or [])
        reflections = sorted(pending_reflections or [])
        knowledge = sorted(active_knowledge or [])
        promotions = sorted(open_promotions or [])
        jobs = sorted(scheduler_jobs or [])

        # Derived counts
        decision_count = len(decisions)
        execution_count = len(executions)
        reflection_count = len(reflections)
        knowledge_count = len(knowledge)
        promotion_count = len(promotions)
        job_count = len(jobs)

        total_active = (
            decision_count + execution_count + reflection_count
            + knowledge_count + promotion_count + job_count
        )

        # Last activity: workspace updated_at is the baseline
        last_activity = workspace.updated_at

        # Activity summary: human-readable description of workspace state
        summary_parts: list[str] = []

        if decision_count > 0:
            summary_parts.append(f"{decision_count} open decision{'s' if decision_count != 1 else ''}")
        if execution_count > 0:
            summary_parts.append(f"{execution_count} running execution{'s' if execution_count != 1 else ''}")
        if reflection_count > 0:
            summary_parts.append(f"{reflection_count} pending reflection{'s' if reflection_count != 1 else ''}")
        if knowledge_count > 0:
            summary_parts.append(f"{knowledge_count} active knowledge {'items' if knowledge_count != 1 else 'item'}")
        if promotion_count > 0:
            summary_parts.append(f"{promotion_count} open promotion{'s' if promotion_count != 1 else ''}")
        if planner_policy_id:
            summary_parts.append("planner active")
        if job_count > 0:
            summary_parts.append(f"{job_count} scheduled job{'s' if job_count != 1 else ''}")

        if not summary_parts:
            activity_summary = "Workspace is quiet — no active items"
        else:
            activity_summary = "Workspace active: " + ", ".join(summary_parts)

        return WorkspaceState(
            workspace_id=workspace.workspace_id,
            workspace_name=workspace.name,
            workspace_status=workspace.status.value,
            compiled_at=now,
            active_decisions=decisions,
            running_executions=executions,
            pending_reflections=reflections,
            active_knowledge=knowledge,
            open_promotions=promotions,
            planner_policy_id=planner_policy_id,
            scheduler_jobs=jobs,
            decision_count=decision_count,
            execution_count=execution_count,
            reflection_count=reflection_count,
            knowledge_count=knowledge_count,
            promotion_count=promotion_count,
            job_count=job_count,
            last_activity_at=last_activity,
            activity_summary=activity_summary,
            total_active_items=total_active,
        )
