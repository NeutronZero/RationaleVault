"""RationaleVault Continuation Engine — Orchestrates workspace resumption.

ContinuationEngine.resume() → WorkspacePackage

The continuation engine is the final orchestrator that ties together:
  1. WorkspaceStateProjection (what is happening)
  2. ContextCompiler (what does the agent need to know)
  3. WorkspaceService.export (produce the resumable envelope)

Workflow:
  workspace + subsystem data → WorkspaceState → WorkspaceContext → WorkspacePackage

Design rules:
  - No search, no retrieval, just resume.
  - Deterministic: same inputs → identical WorkspacePackage.
  - All steps are pure functions — no I/O.
"""
from __future__ import annotations

from datetime import datetime, timezone

from rationalevault.projections.workspace import WorkspaceStateProjection
from rationalevault.workspace.context_compiler import ContextCompiler
from rationalevault.workspace.events import WorkspacePackageExportedPayload
from rationalevault.workspace.models import Workspace, WorkspacePackage
from rationalevault.workspace.service import WorkspaceService


# ── ContinuationEngine ──────────────────────────────────────────────────

class ContinuationEngine:
    """Orchestrates workspace resumption into a WorkspacePackage.

    Chains: WorkspaceState → Context → Package.
    No search, no retrieval, just resume.
    """

    @staticmethod
    def resume(
        workspace: Workspace,
        agent_id: str,
        goals: list[str] | None = None,
        active_decisions: list[str] | None = None,
        running_executions: list[str] | None = None,
        pending_reflections: list[str] | None = None,
        active_knowledge: list[str] | None = None,
        open_promotions: list[str] | None = None,
        planner_policy_id: str | None = None,
        scheduler_jobs: list[str] | None = None,
        lineage_paths: list[str] | None = None,
        reference_time: datetime | None = None,
    ) -> tuple[WorkspacePackage, WorkspacePackageExportedPayload]:
        """Resume work in a workspace — produce a resumable continuation package.

        Args:
            workspace: The workspace to resume.
            agent_id: Target agent.
            goals: Current goals.
            active_decisions: Open DEC-[hash] IDs.
            running_executions: Running SKE-[hash] IDs.
            pending_reflections: Pending RCAND-[hash] IDs.
            active_knowledge: Active KNOW-[hash] IDs.
            open_promotions: Open PROMO-[hash] IDs.
            planner_policy_id: Current PPOL-[hash] ID.
            scheduler_jobs: Pending/running CJOB-[hash] IDs.
            lineage_paths: Key lineage paths.
            reference_time: Deterministic datetime override.

        Returns:
            (WorkspacePackage, WorkspacePackageExportedPayload).
        """
        now = (reference_time or datetime.now(timezone.utc)).isoformat()

        # Step 1: Project workspace state
        state = WorkspaceStateProjection.project(
            workspace=workspace,
            active_decisions=active_decisions,
            running_executions=running_executions,
            pending_reflections=pending_reflections,
            active_knowledge=active_knowledge,
            open_promotions=open_promotions,
            planner_policy_id=planner_policy_id,
            scheduler_jobs=scheduler_jobs,
            reference_time=reference_time,
        )

        # Step 2: Take a snapshot
        snap, _ = WorkspaceService.snapshot(
            workspace=workspace,
            version=1,
            active_decisions=active_decisions,
            running_executions=running_executions,
            pending_reflections=pending_reflections,
            active_knowledge=active_knowledge,
            open_promotions=open_promotions,
            planner_policy_id=planner_policy_id,
            scheduler_jobs=scheduler_jobs,
            reference_time=reference_time,
        )

        # Step 3: Compile context
        ctx, _ = ContextCompiler.compile(
            workspace_state=state,
            agent_id=agent_id,
            goals=goals,
            snapshot_id=snap.snapshot_id,
            reference_time=reference_time,
        )

        # Step 4: Export as package
        package, payload = WorkspaceService.export(
            workspace=workspace,
            context=ctx,
            snapshot=snap,
            agent_id=agent_id,
            lineage_paths=lineage_paths,
            reference_time=reference_time,
        )

        return package, payload
