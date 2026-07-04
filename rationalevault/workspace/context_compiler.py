"""RationaleVault Workspace Context Compiler — Compiles WorkspaceContext from WorkspaceState.

ContextCompiler.compile(workspace_state, agent_id, goals) → WorkspaceContext

Bridges WorkspaceState (projection) → WorkspaceContext (resumable context).
The Context Compiler is the final step before an agent receives work context.

Design rules:
  - No I/O (all data from WorkspaceState, no external calls).
  - Deterministic: same WorkspaceState + agent_id + goals → identical context.
  - Produces a WorkspaceContext that the service.export() method wraps into a WorkspacePackage.
"""
from __future__ import annotations

from datetime import datetime, timezone

from rationalevault.projections.workspace import WorkspaceState
from rationalevault.workspace.events import WorkspaceContextCompiledPayload
from rationalevault.workspace.models import WorkspaceContext


# ── ContextCompiler ──────────────────────────────────────────────────────

class ContextCompiler:
    """Compiles a WorkspaceContext from WorkspaceState.

    Extracts the relevant slice of subsystem state for a specific agent,
    producing a resumable context envelope.

    Deterministic: same inputs → identical WorkspaceContext.
    """

    @staticmethod
    def compile(
        workspace_state: WorkspaceState,
        agent_id: str,
        goals: list[str] | None = None,
        session_id: str | None = None,
        snapshot_id: str | None = None,
        reference_time: datetime | None = None,
    ) -> tuple[WorkspaceContext, WorkspaceContextCompiledPayload]:
        """Compile a WorkspaceContext from workspace state.

        Args:
            workspace_state: Current workspace state projection.
            agent_id: Target agent for this context.
            goals: Current goals for the agent.
            session_id: Optional session ID (WSSSN-[hash]).
            snapshot_id: Optional snapshot ID (WSSNP-[hash]).
            reference_time: Deterministic datetime override.

        Returns:
            (WorkspaceContext, WorkspaceContextCompiledPayload).
        """
        now = (reference_time or datetime.now(timezone.utc)).isoformat()
        ctx_id = WorkspaceContext.generate_context_id(
            session_id or f"none-{agent_id}", now
        )

        context = WorkspaceContext(
            context_id=ctx_id,
            session_id=session_id or "",
            snapshot_id=snapshot_id or "",
            agent_id=agent_id,
            goals=sorted(goals or []),
            open_decisions=workspace_state.active_decisions,
            running_executions=workspace_state.running_executions,
            pending_reflections=workspace_state.pending_reflections,
            recent_knowledge=workspace_state.active_knowledge,
            planner_policy_summary=_summarize_planner(workspace_state),
            memory_focus=[],
            lineage_summary=[],
            created_at=now,
        )

        payload = WorkspaceContextCompiledPayload(
            context_id=ctx_id,
            session_id=session_id or "",
            snapshot_id=snapshot_id or "",
            agent_id=agent_id,
            goals=sorted(goals or []),
            open_decisions=workspace_state.active_decisions,
            running_executions=workspace_state.running_executions,
            pending_reflections=workspace_state.pending_reflections,
            recent_knowledge=workspace_state.active_knowledge,
            planner_policy_summary=_summarize_planner(workspace_state),
            memory_focus=[],
            lineage_summary=[],
            created_at=now,
        )

        return context, payload


def _summarize_planner(state: WorkspaceState) -> str:
    """Produce a human-readable summary of planner state."""
    if state.planner_policy_id:
        return f"Active policy: {state.planner_policy_id}"
    return "No active planner policy"
