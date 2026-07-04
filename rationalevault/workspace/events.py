"""
RationaleVault Workspace Event Payloads — Immutable event-sourced contracts for the Workspace subsystem.

Every workspace event follows:
    Domain Object → Event Payload → Event Ledger → Projection → State

Event hierarchy:
    WORKSPACE_CREATED
        ↓
    WORKSPACE_SNAPSHOT_TAKEN
        ↓
    WORKSPACE_SESSION_OPENED
        ↓
    WORKSPACE_CONTEXT_COMPILED
        ↓
    WORKSPACE_PACKAGE_EXPORTED

Design rules:
  - Payloads are FROZEN dataclasses, never reused as domain objects.
  - Every payload includes schema_version for forward compatibility.
  - Domain models remain separate from event payloads.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class WorkspaceCreatedPayload:
    """
    Emitted when a new workspace is created.

    Event: WORKSPACE_CREATED
    """
    schema_version: str = SCHEMA_VERSION
    workspace_id: str = ""          # WS-[hash]
    name: str = ""
    description: str = ""
    agent_ids: list[str] = field(default_factory=list)
    project_ids: list[str] = field(default_factory=list)
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "workspace_id": self.workspace_id,
            "name": self.name,
            "description": self.description,
            "agent_ids": self.agent_ids,
            "project_ids": self.project_ids,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> WorkspaceCreatedPayload:
        return cls(
            schema_version=d.get("schema_version", SCHEMA_VERSION),
            workspace_id=d["workspace_id"],
            name=d["name"],
            description=d.get("description", ""),
            agent_ids=d.get("agent_ids", []),
            project_ids=d.get("project_ids", []),
            created_at=d["created_at"],
        )


@dataclass(frozen=True)
class WorkspaceSnapshotTakenPayload:
    """
    Emitted when a workspace snapshot is taken.

    Event: WORKSPACE_SNAPSHOT_TAKEN
    """
    schema_version: str = SCHEMA_VERSION
    snapshot_id: str = ""           # WSSNP-[hash]
    workspace_id: str = ""          # WS-[hash]
    version: int = 1
    active_decisions: list[str] = field(default_factory=list)
    running_executions: list[str] = field(default_factory=list)
    pending_reflections: list[str] = field(default_factory=list)
    active_knowledge: list[str] = field(default_factory=list)
    open_promotions: list[str] = field(default_factory=list)
    planner_policy_id: str | None = None
    scheduler_jobs: list[str] = field(default_factory=list)
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "snapshot_id": self.snapshot_id,
            "workspace_id": self.workspace_id,
            "version": self.version,
            "active_decisions": self.active_decisions,
            "running_executions": self.running_executions,
            "pending_reflections": self.pending_reflections,
            "active_knowledge": self.active_knowledge,
            "open_promotions": self.open_promotions,
            "planner_policy_id": self.planner_policy_id,
            "scheduler_jobs": self.scheduler_jobs,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> WorkspaceSnapshotTakenPayload:
        return cls(
            schema_version=d.get("schema_version", SCHEMA_VERSION),
            snapshot_id=d["snapshot_id"],
            workspace_id=d["workspace_id"],
            version=d.get("version", 1),
            active_decisions=d.get("active_decisions", []),
            running_executions=d.get("running_executions", []),
            pending_reflections=d.get("pending_reflections", []),
            active_knowledge=d.get("active_knowledge", []),
            open_promotions=d.get("open_promotions", []),
            planner_policy_id=d.get("planner_policy_id"),
            scheduler_jobs=d.get("scheduler_jobs", []),
            created_at=d["created_at"],
        )


@dataclass(frozen=True)
class WorkspaceSessionOpenedPayload:
    """
    Emitted when an agent opens a session in a workspace.

    Event: WORKSPACE_SESSION_OPENED
    """
    schema_version: str = SCHEMA_VERSION
    session_id: str = ""            # WSSSN-[hash]
    workspace_id: str = ""          # WS-[hash]
    agent_id: str = ""
    agent_role: str = ""            # PRIMARY, ADVISOR, OBSERVER
    snapshot_id: str | None = None
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "session_id": self.session_id,
            "workspace_id": self.workspace_id,
            "agent_id": self.agent_id,
            "agent_role": self.agent_role,
            "snapshot_id": self.snapshot_id,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> WorkspaceSessionOpenedPayload:
        return cls(
            schema_version=d.get("schema_version", SCHEMA_VERSION),
            session_id=d["session_id"],
            workspace_id=d["workspace_id"],
            agent_id=d["agent_id"],
            agent_role=d["agent_role"],
            snapshot_id=d.get("snapshot_id"),
            created_at=d["created_at"],
        )


@dataclass(frozen=True)
class WorkspaceContextCompiledPayload:
    """
    Emitted when a workspace context is compiled for an agent.

    Event: WORKSPACE_CONTEXT_COMPILED
    """
    schema_version: str = SCHEMA_VERSION
    context_id: str = ""            # WSCTX-[hash]
    session_id: str = ""            # WSSSN-[hash]
    snapshot_id: str = ""           # WSSNP-[hash]
    agent_id: str = ""
    goals: list[str] = field(default_factory=list)
    open_decisions: list[str] = field(default_factory=list)
    running_executions: list[str] = field(default_factory=list)
    pending_reflections: list[str] = field(default_factory=list)
    recent_knowledge: list[str] = field(default_factory=list)
    planner_policy_summary: str = ""
    memory_focus: list[str] = field(default_factory=list)
    lineage_summary: list[str] = field(default_factory=list)
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "context_id": self.context_id,
            "session_id": self.session_id,
            "snapshot_id": self.snapshot_id,
            "agent_id": self.agent_id,
            "goals": self.goals,
            "open_decisions": self.open_decisions,
            "running_executions": self.running_executions,
            "pending_reflections": self.pending_reflections,
            "recent_knowledge": self.recent_knowledge,
            "planner_policy_summary": self.planner_policy_summary,
            "memory_focus": self.memory_focus,
            "lineage_summary": self.lineage_summary,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> WorkspaceContextCompiledPayload:
        return cls(
            schema_version=d.get("schema_version", SCHEMA_VERSION),
            context_id=d["context_id"],
            session_id=d["session_id"],
            snapshot_id=d["snapshot_id"],
            agent_id=d["agent_id"],
            goals=d.get("goals", []),
            open_decisions=d.get("open_decisions", []),
            running_executions=d.get("running_executions", []),
            pending_reflections=d.get("pending_reflections", []),
            recent_knowledge=d.get("recent_knowledge", []),
            planner_policy_summary=d.get("planner_policy_summary", ""),
            memory_focus=d.get("memory_focus", []),
            lineage_summary=d.get("lineage_summary", []),
            created_at=d["created_at"],
        )


@dataclass(frozen=True)
class WorkspacePackageExportedPayload:
    """
    Emitted when a workspace package is exported for an agent.

    Event: WORKSPACE_PACKAGE_EXPORTED
    """
    schema_version: str = SCHEMA_VERSION
    package_id: str = ""            # WSPKG-[hash]
    workspace_id: str = ""          # WS-[hash]
    context_id: str = ""            # WSCTX-[hash]
    snapshot_id: str = ""           # WSSNP-[hash]
    agent_id: str = ""
    lineage_paths: list[str] = field(default_factory=list)
    exported_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "package_id": self.package_id,
            "workspace_id": self.workspace_id,
            "context_id": self.context_id,
            "snapshot_id": self.snapshot_id,
            "agent_id": self.agent_id,
            "lineage_paths": self.lineage_paths,
            "exported_at": self.exported_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> WorkspacePackageExportedPayload:
        return cls(
            schema_version=d.get("schema_version", SCHEMA_VERSION),
            package_id=d["package_id"],
            workspace_id=d["workspace_id"],
            context_id=d["context_id"],
            snapshot_id=d["snapshot_id"],
            agent_id=d["agent_id"],
            lineage_paths=d.get("lineage_paths", []),
            exported_at=d["exported_at"],
        )
