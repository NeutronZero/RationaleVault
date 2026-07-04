"""
RationaleVault Agent Runtime Contracts — Immutable data structures for the Agent Runtime subsystem.

The Agent Runtime is the platform layer between Workspace and external agents.
It owns session management, capability negotiation, workspace binding, and
context package streaming.

Contract hierarchy:
    AgentProfile (identity)
        ↓
    AgentSession (running instance)
        ↓
    WorkspaceBinding (workspace attachment)
        ↓
    RuntimeContext (compiled agent context)
        ↓
    SessionSnapshot (point-in-time session state)

Design rules:
  - All models are FROZEN dataclasses.
  - Domain models ≠ Event payloads (separation of concerns).
  - No behavior — contracts only.
  - Agent Profile is separate from Agent Session (identity ≠ running state).
  - Capabilities are composable (sets of capability flags).
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# =====================================================================
# Enums
# =====================================================================

class AgentVendor(str, Enum):
    """Known agent vendors."""
    ANTHROPIC = "ANTHROPIC"
    OPENAI = "OPENAI"
    GOOGLE = "GOOGLE"
    AZURE = "AZURE"
    LOCAL = "LOCAL"
    CUSTOM = "CUSTOM"


class AgentStatus(str, Enum):
    """Lifecycle states for an agent profile."""
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    DEPRECATED = "DEPRECATED"


class SessionStatus(str, Enum):
    """Lifecycle states for an agent session."""
    CREATED = "CREATED"
    ATTACHED = "ATTACHED"
    STREAMING = "STREAMING"
    PAUSED = "PAUSED"
    RESUMED = "RESUMED"
    DETACHED = "DETACHED"
    CLOSED = "CLOSED"


class Capability(str, Enum):
    """Composable capability flags for agents."""
    READ_WORKSPACE = "READ_WORKSPACE"
    READ_MEMORY = "READ_MEMORY"
    READ_LINEAGE = "READ_LINEAGE"
    READ_KNOWLEDGE = "READ_KNOWLEDGE"
    SUGGEST = "SUGGEST"
    EXECUTE_SKILLS = "EXECUTE_SKILLS"
    REQUEST_PROMOTION = "REQUEST_PROMOTION"
    CREATE_REFLECTION = "CREATE_REFLECTION"
    VIEW_SYSTEM = "VIEW_SYSTEM"
    EXPORT_PACKAGE = "EXPORT_PACKAGE"
    # Distributed capabilities (H7)
    CAN_HOST_REMOTE = "CAN_HOST_REMOTE"
    CAN_MIGRATE = "CAN_MIGRATE"
    CAN_AGGREGATE_TELEMETRY = "CAN_AGGREGATE_TELEMETRY"
    CAN_SIMULATE = "CAN_SIMULATE"
    CAN_VIEW_POLICY = "CAN_VIEW_POLICY"


class CapabilityProfile(str, Enum):
    """Predefined capability sets for common agent roles."""
    OBSERVER = "OBSERVER"
    PLANNER = "PLANNER"
    RESEARCHER = "RESEARCHER"
    EXECUTOR = "EXECUTOR"
    ADMINISTRATOR = "ADMINISTRATOR"


# =====================================================================
# Capability Profiles
# =====================================================================

CAPABILITY_PROFILES: dict[CapabilityProfile, frozenset[Capability]] = {
    CapabilityProfile.OBSERVER: frozenset({
        Capability.READ_WORKSPACE,
        Capability.READ_MEMORY,
        Capability.READ_LINEAGE,
        Capability.READ_KNOWLEDGE,
        Capability.VIEW_SYSTEM,
    }),
    CapabilityProfile.PLANNER: frozenset({
        Capability.READ_WORKSPACE,
        Capability.READ_MEMORY,
        Capability.READ_LINEAGE,
        Capability.READ_KNOWLEDGE,
        Capability.VIEW_SYSTEM,
        Capability.SUGGEST,
        Capability.REQUEST_PROMOTION,
    }),
    CapabilityProfile.RESEARCHER: frozenset({
        Capability.READ_WORKSPACE,
        Capability.READ_MEMORY,
        Capability.READ_LINEAGE,
        Capability.READ_KNOWLEDGE,
        Capability.VIEW_SYSTEM,
        Capability.SUGGEST,
        Capability.CREATE_REFLECTION,
        Capability.EXPORT_PACKAGE,
    }),
    CapabilityProfile.EXECUTOR: frozenset({
        Capability.READ_WORKSPACE,
        Capability.READ_MEMORY,
        Capability.READ_LINEAGE,
        Capability.READ_KNOWLEDGE,
        Capability.VIEW_SYSTEM,
        Capability.SUGGEST,
        Capability.EXECUTE_SKILLS,
        Capability.REQUEST_PROMOTION,
        Capability.CREATE_REFLECTION,
        Capability.EXPORT_PACKAGE,
    }),
    CapabilityProfile.ADMINISTRATOR: frozenset(frozenset(c for c in Capability)),
}


# =====================================================================
# Domain Models
# =====================================================================

@dataclass(frozen=True)
class AgentProfile:
    """
    Identity of an agent, separate from any running session.

    An AgentProfile represents WHO the agent is.
    An AgentSession represents WHAT the agent is doing right now.

    AGNT-[hash] — immutable identifier.
    """
    profile_id: str               # AGNT-[hash]
    name: str
    vendor: AgentVendor
    model_id: str                 # e.g. "claude-4", "gpt-4o", "gemini-2.5"
    capabilities: frozenset[Capability] = field(default_factory=frozenset)
    status: AgentStatus = AgentStatus.ACTIVE
    metadata: dict[str, str] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    @staticmethod
    def generate_profile_id(name: str, vendor: AgentVendor, created_at: str) -> str:
        data = f"agent_profile:{name}:{vendor.value}:{created_at}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"AGNT-{h}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "name": self.name,
            "vendor": self.vendor.value,
            "model_id": self.model_id,
            "capabilities": sorted(c.value for c in self.capabilities),
            "status": self.status.value,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True)
class AgentCapabilities:
    """
    Composable capability set for an agent.

    Defines what the agent CAN do in a workspace.
    Resolved from profile capabilities ∩ workspace permissions.
    """
    profile_id: str               # AGNT-[hash]
    granted: frozenset[Capability] = field(default_factory=frozenset)
    denied: frozenset[Capability] = field(default_factory=frozenset)
    resolved_at: str = ""

    @property
    def effective(self) -> frozenset[Capability]:
        """Capabilities that are granted and not denied."""
        return self.granted - self.denied

    def has(self, capability: Capability) -> bool:
        """Check if a specific capability is effective."""
        return capability in self.effective

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "granted": sorted(c.value for c in self.granted),
            "denied": sorted(c.value for c in self.denied),
            "effective": sorted(c.value for c in self.effective),
            "resolved_at": self.resolved_at,
        }


@dataclass(frozen=True)
class WorkspaceBinding:
    """
    Binding between an agent session and a workspace.

    Records which workspace the agent is attached to and what role it holds.
    WSB-[hash] — immutable.
    """
    binding_id: str               # WSB-[hash]
    session_id: str               # AGS-[hash]
    workspace_id: str             # WS-[hash]
    role: str                     # PRIMARY, ADVISOR, OBSERVER
    attached_at: str = ""
    detached_at: str | None = None

    @staticmethod
    def generate_binding_id(session_id: str, workspace_id: str) -> str:
        data = f"workspace_binding:{session_id}:{workspace_id}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"WSB-{h}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "binding_id": self.binding_id,
            "session_id": self.session_id,
            "workspace_id": self.workspace_id,
            "role": self.role,
            "attached_at": self.attached_at,
            "detached_at": self.detached_at,
        }


@dataclass(frozen=True)
class RuntimeContext:
    """
    Compiled context provided to an agent during a session.

    This is what the agent receives when it attaches to a workspace.
    Combines workspace state with agent-specific capabilities.
    RTC-[hash] — immutable.
    """
    context_id: str               # RTC-[hash]
    session_id: str               # AGS-[hash]
    binding_id: str               # WSB-[hash]
    workspace_id: str             # WS-[hash]
    agent_id: str                 # AGNT-[hash]
    goals: list[str] = field(default_factory=list)
    open_decisions: list[str] = field(default_factory=list)
    running_executions: list[str] = field(default_factory=list)
    pending_reflections: list[str] = field(default_factory=list)
    recent_knowledge: list[str] = field(default_factory=list)
    planner_policy_summary: str = ""
    memory_focus: list[str] = field(default_factory=list)
    lineage_summary: list[str] = field(default_factory=list)
    capabilities: frozenset[Capability] = field(default_factory=frozenset)
    created_at: str = ""

    @staticmethod
    def generate_context_id(session_id: str, created_at: str) -> str:
        data = f"runtime_context:{session_id}:{created_at}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"RTC-{h}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "context_id": self.context_id,
            "session_id": self.session_id,
            "binding_id": self.binding_id,
            "workspace_id": self.workspace_id,
            "agent_id": self.agent_id,
            "goals": self.goals,
            "open_decisions": self.open_decisions,
            "running_executions": self.running_executions,
            "pending_reflections": self.pending_reflections,
            "recent_knowledge": self.recent_knowledge,
            "planner_policy_summary": self.planner_policy_summary,
            "memory_focus": self.memory_focus,
            "lineage_summary": self.lineage_summary,
            "capabilities": sorted(c.value for c in self.capabilities),
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class SessionSnapshot:
    """
    Point-in-time snapshot of an agent session.

    Captures the complete session state at a moment in time.
    SSSN-[hash] — immutable.
    """
    snapshot_id: str              # SSSN-[hash]
    session_id: str               # AGS-[hash]
    workspace_id: str             # WS-[hash]
    agent_id: str                 # AGNT-[hash]
    status: str                   # SessionStatus value
    capabilities: frozenset[Capability] = field(default_factory=frozenset)
    packages_streamed: int = 0
    events_emitted: int = 0
    created_at: str = ""

    @staticmethod
    def generate_snapshot_id(session_id: str, created_at: str) -> str:
        data = f"session_snapshot:{session_id}:{created_at}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"SSSN-{h}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "session_id": self.session_id,
            "workspace_id": self.workspace_id,
            "agent_id": self.agent_id,
            "status": self.status,
            "capabilities": sorted(c.value for c in self.capabilities),
            "packages_streamed": self.packages_streamed,
            "events_emitted": self.events_emitted,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class AgentSession:
    """
    Running instance of an agent in a workspace.

    An AgentProfile is WHO the agent is.
    An AgentSession is WHAT the agent is doing right now.

    AGS-[hash] — immutable.
    """
    session_id: str               # AGS-[hash]
    profile_id: str               # AGNT-[hash]
    workspace_id: str             # WS-[hash]
    status: SessionStatus
    binding_id: str               # WSB-[hash]
    context_id: str | None = None # RTC-[hash]
    snapshot_id: str | None = None # SSSN-[hash]
    protocol_version: str = "1.0"
    started_at: str = ""
    last_active_at: str = ""
    ended_at: str | None = None

    @staticmethod
    def generate_session_id(profile_id: str, workspace_id: str, created_at: str) -> str:
        data = f"agent_session:{profile_id}:{workspace_id}:{created_at}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"AGS-{h}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "profile_id": self.profile_id,
            "workspace_id": self.workspace_id,
            "status": self.status.value,
            "binding_id": self.binding_id,
            "context_id": self.context_id,
            "snapshot_id": self.snapshot_id,
            "protocol_version": self.protocol_version,
            "started_at": self.started_at,
            "last_active_at": self.last_active_at,
            "ended_at": self.ended_at,
        }


@dataclass(frozen=True)
class ProtocolVersion:
    """
    Version compatibility for agent-runtime communication.

    Ensures agents and runtime are compatible before establishing sessions.
    """
    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, version_str: str) -> ProtocolVersion:
        parts = version_str.strip().split(".")
        if len(parts) != 3:
            raise ValueError(f"Invalid protocol version: {version_str}")
        return cls(int(parts[0]), int(parts[1]), int(parts[2]))

    def is_compatible(self, other: ProtocolVersion) -> bool:
        """Check if two protocol versions are compatible (same major)."""
        return self.major == other.major

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"
