"""RationaleVault Package Streamer — Delivers context packages to agent sessions.

PackageStreamer produces deterministic WorkspacePackages and records streaming events.

Design rules:
  - Pure functions, no I/O.
  - Deterministic: same inputs → identical package.
  - Events are the only persistence boundary.
"""
from __future__ import annotations

from datetime import datetime, timezone

from rationalevault.projections.workspace import WorkspaceState
from rationalevault.runtime.models import AgentSession, RuntimeContext
from rationalevault.runtime.events import PackageStreamedPayload
from rationalevault.workspace.context_compiler import ContextCompiler
from rationalevault.workspace.models import Workspace, WorkspacePackage
from rationalevault.workspace.service import WorkspaceService


class PackageStreamer:
    """Delivers context packages to agent sessions."""

    @staticmethod
    def stream(
        session: AgentSession,
        workspace: Workspace,
        workspace_state: WorkspaceState,
        reference_time: datetime | None = None,
    ) -> tuple[RuntimeContext, WorkspacePackage, PackageStreamedPayload]:
        """Stream a context package to an agent session.

        Compiles a RuntimeContext from workspace state, then exports
        a WorkspacePackage for the agent.

        Args:
            session: Active agent session.
            workspace: The workspace to stream from.
            workspace_state: Current workspace state projection.
            reference_time: Deterministic datetime override.

        Returns:
            (RuntimeContext, WorkspacePackage, PackageStreamedPayload).
        """
        now = (reference_time or datetime.now(timezone.utc)).isoformat()

        # Step 1: Compile runtime context from workspace state
        ctx, _ = ContextCompiler.compile(
            workspace_state=workspace_state,
            agent_id=session.profile_id,
            snapshot_id=session.snapshot_id,
            reference_time=reference_time,
        )

        # Step 2: Take a snapshot for the package
        snap, _ = WorkspaceService.snapshot(
            workspace=workspace,
            version=1,
            active_decisions=workspace_state.active_decisions,
            running_executions=workspace_state.running_executions,
            pending_reflections=workspace_state.pending_reflections,
            active_knowledge=workspace_state.active_knowledge,
            open_promotions=workspace_state.open_promotions,
            planner_policy_id=workspace_state.planner_policy_id,
            scheduler_jobs=workspace_state.scheduler_jobs,
            reference_time=reference_time,
        )

        # Step 3: Export as package
        package, _ = WorkspaceService.export(
            workspace=workspace,
            context=ctx,
            snapshot=snap,
            agent_id=session.profile_id,
            reference_time=reference_time,
        )

        # Step 4: Produce streaming event
        payload = PackageStreamedPayload(
            session_id=session.session_id,
            package_id=package.package_id,
            context_id=ctx.context_id,
            agent_id=session.profile_id,
            streamed_at=now,
        )

        return ctx, package, payload

    @staticmethod
    def build_runtime_context(
        session: AgentSession,
        workspace_state: WorkspaceState,
        reference_time: datetime | None = None,
    ) -> RuntimeContext:
        """Build a RuntimeContext without producing a full package.

        Lightweight version for session initialization.
        """
        ctx, _ = ContextCompiler.compile(
            workspace_state=workspace_state,
            agent_id=session.profile_id,
            snapshot_id=session.snapshot_id,
            reference_time=reference_time,
        )

        return RuntimeContext(
            context_id=ctx.context_id,
            session_id=session.session_id,
            binding_id=session.binding_id,
            workspace_id=session.workspace_id,
            agent_id=session.profile_id,
            goals=ctx.goals,
            open_decisions=ctx.open_decisions,
            running_executions=ctx.running_executions,
            pending_reflections=ctx.pending_reflections,
            recent_knowledge=ctx.recent_knowledge,
            planner_policy_summary=ctx.planner_policy_summary,
            memory_focus=ctx.memory_focus,
            lineage_summary=ctx.lineage_summary,
            created_at=ctx.created_at,
        )
