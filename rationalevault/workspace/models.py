"""
RationaleVault Workspace Contracts — Immutable data structures for the Workspace subsystem.

The workspace is the primary interface through which humans and AI agents
interact with the entire cognitive substrate.

Contract hierarchy:
    Workspace
        ↓
    WorkspaceSnapshot (point-in-time state)
        ↓
    WorkspaceSession (agent interaction instance)
        ↓
    WorkspaceContext (compiled context for an agent)
        ↓
    WorkspacePackage (resumable continuation envelope)

Design rules:
  - All models are FROZEN dataclasses.
  - Domain models ≠ Event payloads (separation of concerns).
  - No behavior — contracts only.
  - Workspace is the public face of the platform.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum
from typing import Any


# =====================================================================
# Enums
# =====================================================================

class WorkspaceStatus(str, Enum):
    """Lifecycle states for a workspace."""
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    ARCHIVED = "ARCHIVED"


class AgentRole(str, Enum):
    """Roles an agent can hold in a workspace."""
    PRIMARY = "PRIMARY"
    ADVISOR = "ADVISOR"
    OBSERVER = "OBSERVER"


class SessionStatus(str, Enum):
    """Status of a workspace session."""
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    SUSPENDED = "SUSPENDED"


# =====================================================================
# Domain Models
# =====================================================================

@dataclass(frozen=True)
class Workspace:
    """
    A workspace aggregates ledgers, beliefs, reflections, and skills
    into a coherent collaborative environment.

    WS-[hash] — immutable identifier.
    """
    workspace_id: str               # WS-[hash]
    name: str
    description: str
    status: WorkspaceStatus
    agent_ids: list[str]            # Agents participating in this workspace
    project_ids: list[str]          # Ledgers/projects aggregated
    created_at: str
    updated_at: str

    @staticmethod
    def generate_workspace_id(name: str, created_at: str) -> str:
        data = f"workspace:{name}:{created_at}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"WS-{h}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "workspace_id": self.workspace_id,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "agent_ids": self.agent_ids,
            "project_ids": self.project_ids,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Workspace:
        return cls(
            workspace_id=d["workspace_id"],
            name=d["name"],
            description=d.get("description", ""),
            status=WorkspaceStatus(d["status"]),
            agent_ids=d.get("agent_ids", []),
            project_ids=d.get("project_ids", []),
            created_at=d["created_at"],
            updated_at=d["updated_at"],
        )


@dataclass(frozen=True)
class WorkspaceSnapshot:
    """
    A point-in-time snapshot of workspace state.

    Captures the complete cognitive state at a moment in time.
    WSSNP-[hash] — immutable.
    """
    snapshot_id: str                # WSSNP-[hash]
    workspace_id: str               # WS-[hash]
    version: int
    active_decisions: list[str]     # DEC-[hash] IDs
    running_executions: list[str]   # SKE-[hash] IDs
    pending_reflections: list[str]  # RCAND-[hash] IDs
    active_knowledge: list[str]     # KNOW-[hash] IDs
    open_promotions: list[str]      # PROMO-[hash] IDs
    planner_policy_id: str | None   # PPOL-[hash]
    scheduler_jobs: list[str]       # CJOB-[hash] IDs
    created_at: str

    @staticmethod
    def generate_snapshot_id(workspace_id: str, created_at: str) -> str:
        data = f"workspace_snapshot:{workspace_id}:{created_at}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"WSSNP-{h}"

    def to_dict(self) -> dict[str, Any]:
        return {
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
    def from_dict(cls, d: dict[str, Any]) -> WorkspaceSnapshot:
        return cls(
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
class WorkspaceSession:
    """
    An agent interaction instance within a workspace.

    Tracks which agent is active, what role it holds, and session lifecycle.
    WSSSN-[hash] — immutable.
    """
    session_id: str                 # WSSSN-[hash]
    workspace_id: str               # WS-[hash]
    agent_id: str
    agent_role: AgentRole
    status: SessionStatus
    started_at: str
    ended_at: str | None
    snapshot_id: str | None         # WSSNP-[hash] at session start

    @staticmethod
    def generate_session_id(workspace_id: str, agent_id: str, created_at: str) -> str:
        data = f"workspace_session:{workspace_id}:{agent_id}:{created_at}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"WSSSN-{h}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "workspace_id": self.workspace_id,
            "agent_id": self.agent_id,
            "agent_role": self.agent_role.value,
            "status": self.status.value,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "snapshot_id": self.snapshot_id,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> WorkspaceSession:
        return cls(
            session_id=d["session_id"],
            workspace_id=d["workspace_id"],
            agent_id=d["agent_id"],
            agent_role=AgentRole(d["agent_role"]),
            status=SessionStatus(d["status"]),
            started_at=d["started_at"],
            ended_at=d.get("ended_at"),
            snapshot_id=d.get("snapshot_id"),
        )


@dataclass(frozen=True)
class WorkspaceContext:
    """
    A compiled context package for a specific agent session.

    This is what an agent receives when it joins a workspace.
    WSCTX-[hash] — immutable.
    """
    context_id: str                 # WSCTX-[hash]
    session_id: str                 # WSSSN-[hash]
    snapshot_id: str                # WSSNP-[hash]
    agent_id: str
    goals: list[str]                # Current goals
    open_decisions: list[str]       # DEC-[hash] IDs needing resolution
    running_executions: list[str]   # SKE-[hash] IDs in progress
    pending_reflections: list[str]  # RCAND-[hash] IDs awaiting processing
    recent_knowledge: list[str]     # KNOW-[hash] IDs recently promoted
    planner_policy_summary: str     # Text summary of current policy
    memory_focus: list[str]         # MEM-[hash] IDs in focus
    lineage_summary: list[str]      # Key lineage paths
    created_at: str

    @staticmethod
    def generate_context_id(session_id: str, created_at: str) -> str:
        data = f"workspace_context:{session_id}:{created_at}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"WSCTX-{h}"

    def to_dict(self) -> dict[str, Any]:
        return {
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
    def from_dict(cls, d: dict[str, Any]) -> WorkspaceContext:
        return cls(
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
class WorkspacePackage:
    """
    A resumable continuation envelope.

    This is what an agent loads to resume work. Not chat history —
    a structured, deterministic snapshot of cognitive state.

    WSPKG-[hash] — immutable.
    """
    package_id: str                 # WSPKG-[hash]
    workspace_id: str               # WS-[hash]
    context_id: str                 # WSCTX-[hash]
    snapshot_id: str                # WSSNP-[hash]
    agent_id: str
    goals: list[str]
    open_decisions: list[str]
    running_executions: list[str]
    pending_reflections: list[str]
    planner_policy_summary: str
    recent_knowledge: list[str]
    memory_focus: list[str]
    lineage_paths: list[str]        # Full lineage paths for key objects
    exported_at: str

    @staticmethod
    def generate_package_id(workspace_id: str, agent_id: str, created_at: str) -> str:
        data = f"workspace_package:{workspace_id}:{agent_id}:{created_at}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"WSPKG-{h}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "package_id": self.package_id,
            "workspace_id": self.workspace_id,
            "context_id": self.context_id,
            "snapshot_id": self.snapshot_id,
            "agent_id": self.agent_id,
            "goals": self.goals,
            "open_decisions": self.open_decisions,
            "running_executions": self.running_executions,
            "pending_reflections": self.pending_reflections,
            "planner_policy_summary": self.planner_policy_summary,
            "recent_knowledge": self.recent_knowledge,
            "memory_focus": self.memory_focus,
            "lineage_paths": self.lineage_paths,
            "exported_at": self.exported_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> WorkspacePackage:
        return cls(
            package_id=d["package_id"],
            workspace_id=d["workspace_id"],
            context_id=d["context_id"],
            snapshot_id=d["snapshot_id"],
            agent_id=d["agent_id"],
            goals=d.get("goals", []),
            open_decisions=d.get("open_decisions", []),
            running_executions=d.get("running_executions", []),
            pending_reflections=d.get("pending_reflections", []),
            planner_policy_summary=d.get("planner_policy_summary", ""),
            recent_knowledge=d.get("recent_knowledge", []),
            memory_focus=d.get("memory_focus", []),
            lineage_paths=d.get("lineage_paths", []),
            exported_at=d["exported_at"],
        )
