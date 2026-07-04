"""RationaleVault Workspace Service — Deterministic service layer for workspace operations.

All methods are pure functions: frozen inputs → (frozen output, event_payload).
No I/O, no mutation, no side effects.

Methods:
  open()     — Create workspace → (Workspace, WorkspaceCreatedPayload)
  resume()   — PAUSED → ACTIVE → (Workspace, WorkspacePausedPayload → WorkspaceResumedPayload)
  pause()    — ACTIVE → PAUSED → (Workspace, WorkspacePausedPayload)
  snapshot() — Take point-in-time snapshot → (WorkspaceSnapshot, WorkspaceSnapshotTakenPayload)
  diff()     — Compare two snapshots → WorkspaceDiff
  export()   — Export as continuation envelope → (WorkspacePackage, WorkspacePackageExportedPayload)
  merge()    — Merge two workspaces → (Workspace, WorkspaceCreatedPayload)

Design rules:
  - No mutation of input objects (all frozen dataclasses).
  - Every mutating operation returns the new object + event payload.
  - Caller is responsible for emitting events to the ledger.
  - Status transitions are validated (OPEN → PAUSED → ACTIVE).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from rationalevault.workspace.events import (
    WorkspaceCreatedPayload,
    WorkspacePackageExportedPayload,
    WorkspaceSnapshotTakenPayload,
)
from rationalevault.workspace.models import (
    Workspace,
    WorkspaceContext,
    WorkspacePackage,
    WorkspaceSnapshot,
    WorkspaceStatus,
)


# ── Result Type ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Success:
    """Successful operation result."""
    value: Any

    def to_dict(self) -> dict[str, Any]:
        return {"value": self.value}

@dataclass(frozen=True)
class Error:
    """Failed operation result with reason."""
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {"reason": self.reason}

WorkspaceResult = Success | Error


# ── Diff Result ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class WorkspaceDiff:
    """Deterministic diff between two workspace snapshots.

    Lists IDs added/removed in each subsystem between two snapshot versions.
    """
    snapshot_a_id: str
    snapshot_b_id: str
    added_decisions: list[str] = field(default_factory=list)
    removed_decisions: list[str] = field(default_factory=list)
    added_executions: list[str] = field(default_factory=list)
    removed_executions: list[str] = field(default_factory=list)
    added_reflections: list[str] = field(default_factory=list)
    removed_reflections: list[str] = field(default_factory=list)
    added_knowledge: list[str] = field(default_factory=list)
    removed_knowledge: list[str] = field(default_factory=list)
    added_promotions: list[str] = field(default_factory=list)
    removed_promotions: list[str] = field(default_factory=list)
    added_jobs: list[str] = field(default_factory=list)
    removed_jobs: list[str] = field(default_factory=list)
    planner_changed: bool = False

    @property
    def has_changes(self) -> bool:
        return bool(
            self.added_decisions or self.removed_decisions
            or self.added_executions or self.removed_executions
            or self.added_reflections or self.removed_reflections
            or self.added_knowledge or self.removed_knowledge
            or self.added_promotions or self.removed_promotions
            or self.added_jobs or self.removed_jobs
            or self.planner_changed
        )

    @property
    def total_changes(self) -> int:
        return (
            len(self.added_decisions) + len(self.removed_decisions)
            + len(self.added_executions) + len(self.removed_executions)
            + len(self.added_reflections) + len(self.removed_reflections)
            + len(self.added_knowledge) + len(self.removed_knowledge)
            + len(self.added_promotions) + len(self.removed_promotions)
            + len(self.added_jobs) + len(self.removed_jobs)
            + (1 if self.planner_changed else 0)
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_a_id": self.snapshot_a_id,
            "snapshot_b_id": self.snapshot_b_id,
            "added_decisions": self.added_decisions,
            "removed_decisions": self.removed_decisions,
            "added_executions": self.added_executions,
            "removed_executions": self.removed_executions,
            "added_reflections": self.added_reflections,
            "removed_reflections": self.removed_reflections,
            "added_knowledge": self.added_knowledge,
            "removed_knowledge": self.removed_knowledge,
            "added_promotions": self.added_promotions,
            "removed_promotions": self.removed_promotions,
            "added_jobs": self.added_jobs,
            "removed_jobs": self.removed_jobs,
            "planner_changed": self.planner_changed,
            "has_changes": self.has_changes,
            "total_changes": self.total_changes,
        }


# ── WorkspaceService ─────────────────────────────────────────────────────

class WorkspaceService:
    """Deterministic service layer for workspace operations.

    Pure functions: frozen inputs → (frozen output, event_payload).
    """

    @staticmethod
    def open(
        name: str,
        description: str = "",
        agent_ids: list[str] | None = None,
        project_ids: list[str] | None = None,
        reference_time: datetime | None = None,
    ) -> tuple[Workspace, WorkspaceCreatedPayload]:
        """Create a new workspace.

        Returns:
            (Workspace, WorkspaceCreatedPayload) — caller emits the event.
        """
        now = (reference_time or datetime.now(timezone.utc)).isoformat()
        ws_id = Workspace.generate_workspace_id(name, now)

        workspace = Workspace(
            workspace_id=ws_id,
            name=name,
            description=description,
            status=WorkspaceStatus.ACTIVE,
            agent_ids=sorted(agent_ids or []),
            project_ids=sorted(project_ids or []),
            created_at=now,
            updated_at=now,
        )

        payload = WorkspaceCreatedPayload(
            workspace_id=ws_id,
            name=name,
            description=description,
            agent_ids=workspace.agent_ids,
            project_ids=workspace.project_ids,
            created_at=now,
        )

        return workspace, payload

    @staticmethod
    def resume(
        workspace: Workspace,
        reference_time: datetime | None = None,
    ) -> tuple[Workspace, WorkspaceCreatedPayload] | Error:
        """Resume a paused workspace (PAUSED → ACTIVE).

        Returns:
            (Workspace, WorkspaceCreatedPayload) or Error.
        """
        if workspace.status != WorkspaceStatus.PAUSED:
            return Error(
                f"Cannot resume workspace in {workspace.status.value} status "
                f"(must be PAUSED)"
            )

        now = (reference_time or datetime.now(timezone.utc)).isoformat()
        resumed = Workspace(
            workspace_id=workspace.workspace_id,
            name=workspace.name,
            description=workspace.description,
            status=WorkspaceStatus.ACTIVE,
            agent_ids=workspace.agent_ids,
            project_ids=workspace.project_ids,
            created_at=workspace.created_at,
            updated_at=now,
        )

        payload = WorkspaceCreatedPayload(
            workspace_id=resumed.workspace_id,
            name=resumed.name,
            description=resumed.description,
            agent_ids=resumed.agent_ids,
            project_ids=resumed.project_ids,
            created_at=now,
        )

        return resumed, payload

    @staticmethod
    def pause(
        workspace: Workspace,
        reference_time: datetime | None = None,
    ) -> tuple[Workspace, WorkspaceCreatedPayload] | Error:
        """Pause an active workspace (ACTIVE → PAUSED).

        Returns:
            (Workspace, WorkspaceCreatedPayload) or Error.
        """
        if workspace.status != WorkspaceStatus.ACTIVE:
            return Error(
                f"Cannot pause workspace in {workspace.status.value} status "
                f"(must be ACTIVE)"
            )

        now = (reference_time or datetime.now(timezone.utc)).isoformat()
        paused = Workspace(
            workspace_id=workspace.workspace_id,
            name=workspace.name,
            description=workspace.description,
            status=WorkspaceStatus.PAUSED,
            agent_ids=workspace.agent_ids,
            project_ids=workspace.project_ids,
            created_at=workspace.created_at,
            updated_at=now,
        )

        payload = WorkspaceCreatedPayload(
            workspace_id=paused.workspace_id,
            name=paused.name,
            description=paused.description,
            agent_ids=paused.agent_ids,
            project_ids=paused.project_ids,
            created_at=now,
        )

        return paused, payload

    @staticmethod
    def snapshot(
        workspace: Workspace,
        version: int,
        active_decisions: list[str] | None = None,
        running_executions: list[str] | None = None,
        pending_reflections: list[str] | None = None,
        active_knowledge: list[str] | None = None,
        open_promotions: list[str] | None = None,
        planner_policy_id: str | None = None,
        scheduler_jobs: list[str] | None = None,
        reference_time: datetime | None = None,
    ) -> tuple[WorkspaceSnapshot, WorkspaceSnapshotTakenPayload]:
        """Take a point-in-time snapshot of workspace state.

        Args:
            workspace: The workspace to snapshot.
            version: Snapshot version number (monotonically increasing).
            active_decisions: Open DEC-[hash] IDs.
            running_executions: Running SKE-[hash] IDs.
            pending_reflections: Pending RCAND-[hash] IDs.
            active_knowledge: Active KNOW-[hash] IDs.
            open_promotions: Open PROMO-[hash] IDs.
            planner_policy_id: Current PPOL-[hash] ID.
            scheduler_jobs: Pending/running CJOB-[hash] IDs.
            reference_time: Deterministic datetime override.

        Returns:
            (WorkspaceSnapshot, WorkspaceSnapshotTakenPayload).
        """
        now = (reference_time or datetime.now(timezone.utc)).isoformat()
        snap_id = WorkspaceSnapshot.generate_snapshot_id(
            workspace.workspace_id, now
        )

        decisions = sorted(active_decisions or [])
        executions = sorted(running_executions or [])
        reflections = sorted(pending_reflections or [])
        knowledge = sorted(active_knowledge or [])
        promotions = sorted(open_promotions or [])
        jobs = sorted(scheduler_jobs or [])

        snapshot_obj = WorkspaceSnapshot(
            snapshot_id=snap_id,
            workspace_id=workspace.workspace_id,
            version=version,
            active_decisions=decisions,
            running_executions=executions,
            pending_reflections=reflections,
            active_knowledge=knowledge,
            open_promotions=promotions,
            planner_policy_id=planner_policy_id,
            scheduler_jobs=jobs,
            created_at=now,
        )

        payload = WorkspaceSnapshotTakenPayload(
            snapshot_id=snap_id,
            workspace_id=workspace.workspace_id,
            version=version,
            active_decisions=decisions,
            running_executions=executions,
            pending_reflections=reflections,
            active_knowledge=knowledge,
            open_promotions=promotions,
            planner_policy_id=planner_policy_id,
            scheduler_jobs=jobs,
            created_at=now,
        )

        return snapshot_obj, payload

    @staticmethod
    def diff(
        snapshot_a: WorkspaceSnapshot,
        snapshot_b: WorkspaceSnapshot,
    ) -> WorkspaceDiff:
        """Compute deterministic diff between two snapshots.

        Lists IDs added/removed in each subsystem between snapshot_a and snapshot_b.
        """
        set_a_dec = set(snapshot_a.active_decisions)
        set_b_dec = set(snapshot_b.active_decisions)
        set_a_exec = set(snapshot_a.running_executions)
        set_b_exec = set(snapshot_b.running_executions)
        set_a_ref = set(snapshot_a.pending_reflections)
        set_b_ref = set(snapshot_b.pending_reflections)
        set_a_know = set(snapshot_a.active_knowledge)
        set_b_know = set(snapshot_b.active_knowledge)
        set_a_promo = set(snapshot_a.open_promotions)
        set_b_promo = set(snapshot_b.open_promotions)
        set_a_jobs = set(snapshot_a.scheduler_jobs)
        set_b_jobs = set(snapshot_b.scheduler_jobs)

        return WorkspaceDiff(
            snapshot_a_id=snapshot_a.snapshot_id,
            snapshot_b_id=snapshot_b.snapshot_id,
            added_decisions=sorted(set_b_dec - set_a_dec),
            removed_decisions=sorted(set_a_dec - set_b_dec),
            added_executions=sorted(set_b_exec - set_a_exec),
            removed_executions=sorted(set_a_exec - set_b_exec),
            added_reflections=sorted(set_b_ref - set_a_ref),
            removed_reflections=sorted(set_a_ref - set_b_ref),
            added_knowledge=sorted(set_b_know - set_a_know),
            removed_knowledge=sorted(set_a_know - set_b_know),
            added_promotions=sorted(set_b_promo - set_a_promo),
            removed_promotions=sorted(set_a_promo - set_b_promo),
            added_jobs=sorted(set_b_jobs - set_a_jobs),
            removed_jobs=sorted(set_a_jobs - set_b_jobs),
            planner_changed=(
                snapshot_a.planner_policy_id != snapshot_b.planner_policy_id
            ),
        )

    @staticmethod
    def export(
        workspace: Workspace,
        context: WorkspaceContext,
        snapshot: WorkspaceSnapshot,
        agent_id: str,
        lineage_paths: list[str] | None = None,
        reference_time: datetime | None = None,
    ) -> tuple[WorkspacePackage, WorkspacePackageExportedPayload]:
        """Export workspace as a resumable continuation package.

        Args:
            workspace: The workspace to export.
            context: Compiled context for the target agent.
            snapshot: Current workspace snapshot.
            agent_id: Target agent for the package.
            lineage_paths: Key lineage paths to include.
            reference_time: Deterministic datetime override.

        Returns:
            (WorkspacePackage, WorkspacePackageExportedPayload).
        """
        now = (reference_time or datetime.now(timezone.utc)).isoformat()
        pkg_id = WorkspacePackage.generate_package_id(
            workspace.workspace_id, agent_id, now
        )

        package = WorkspacePackage(
            package_id=pkg_id,
            workspace_id=workspace.workspace_id,
            context_id=context.context_id,
            snapshot_id=snapshot.snapshot_id,
            agent_id=agent_id,
            goals=context.goals,
            open_decisions=snapshot.active_decisions,
            running_executions=snapshot.running_executions,
            pending_reflections=snapshot.pending_reflections,
            planner_policy_summary=context.planner_policy_summary,
            recent_knowledge=context.recent_knowledge,
            memory_focus=context.memory_focus,
            lineage_paths=sorted(lineage_paths or []),
            exported_at=now,
        )

        payload = WorkspacePackageExportedPayload(
            package_id=pkg_id,
            workspace_id=workspace.workspace_id,
            context_id=context.context_id,
            snapshot_id=snapshot.snapshot_id,
            agent_id=agent_id,
            lineage_paths=sorted(lineage_paths or []),
            exported_at=now,
        )

        return package, payload

    @staticmethod
    def merge(
        workspace_a: Workspace,
        workspace_b: Workspace,
        name: str | None = None,
        reference_time: datetime | None = None,
    ) -> tuple[Workspace, WorkspaceCreatedPayload]:
        """Merge two workspaces into a new workspace.

        Creates a new workspace combining agents and projects from both.
        Status is ACTIVE. Workspace IDs are unique (not inherited).

        Args:
            workspace_a: First workspace.
            workspace_b: Second workspace.
            name: Name for the merged workspace (default: combined names).
            reference_time: Deterministic datetime override.

        Returns:
            (Workspace, WorkspaceCreatedPayload) — a NEW workspace.
        """
        now = (reference_time or datetime.now(timezone.utc)).isoformat()
        merged_name = name or f"{workspace_a.name} + {workspace_b.name}"

        merged_agents = sorted(
            set(workspace_a.agent_ids) | set(workspace_b.agent_ids)
        )
        merged_projects = sorted(
            set(workspace_a.project_ids) | set(workspace_b.project_ids)
        )

        ws_id = Workspace.generate_workspace_id(merged_name, now)

        merged = Workspace(
            workspace_id=ws_id,
            name=merged_name,
            description=(
                f"Merged from {workspace_a.name} and {workspace_b.name}"
            ),
            status=WorkspaceStatus.ACTIVE,
            agent_ids=merged_agents,
            project_ids=merged_projects,
            created_at=now,
            updated_at=now,
        )

        payload = WorkspaceCreatedPayload(
            workspace_id=ws_id,
            name=merged_name,
            description=merged.description,
            agent_ids=merged_agents,
            project_ids=merged_projects,
            created_at=now,
        )

        return merged, payload
