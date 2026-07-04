"""
RationaleVault Remote Sessions — Contracts for distributed cognition.

The Remote Sessions layer introduces the contracts for multiple runtime nodes
sharing workspaces, agents migrating between nodes, and telemetry aggregated
across nodes.

Design rules:
  - The Event Ledger remains the only source of truth.
  - Nodes are execution environments, not authorities.
  - Runtime contracts define identity and movement, not consistency semantics.
  - Conflict resolution is deferred to a later milestone.
  - Cross-node memory is a separate concern (H8).
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# =====================================================================
# Enums
# =====================================================================

class NodeStatus(str, Enum):
    """Lifecycle states for a runtime node."""
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    DRAINING = "DRAINING"


class RemoteSessionStatus(str, Enum):
    """Lifecycle states for a remote session."""
    ACTIVE = "ACTIVE"
    MIGRATING = "MIGRATING"
    SUSPENDED = "SUSPENDED"


class HandoffStatus(str, Enum):
    """Lifecycle states for a session handoff."""
    INITIATED = "INITIATED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class HandoffType(str, Enum):
    """Reason for session handoff."""
    MIGRATION = "MIGRATION"
    LOAD_BALANCE = "LOAD_BALANCE"
    FAILOVER = "FAILOVER"


# =====================================================================
# Node Health
# =====================================================================

@dataclass(frozen=True)
class NodeHealth:
    """
    Operational health of a runtime node.

    Separate from RuntimeNode (identity) so health and identity
    evolve at different rates.
    """
    node_id: str
    heartbeat_time: str = ""
    latency_ms: float = 0.0
    load: float = 0.0            # 0.0-1.0, CPU/memory pressure
    active_sessions: int = 0
    memory_pressure: float = 0.0  # 0.0-1.0
    telemetry_delay_seconds: float = 0.0
    status: NodeStatus = NodeStatus.ONLINE

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "heartbeat_time": self.heartbeat_time,
            "latency_ms": self.latency_ms,
            "load": self.load,
            "active_sessions": self.active_sessions,
            "memory_pressure": self.memory_pressure,
            "telemetry_delay_seconds": self.telemetry_delay_seconds,
            "status": self.status.value,
        }


# =====================================================================
# Runtime Node
# =====================================================================

@dataclass(frozen=True)
class RuntimeNode:
    """
    Identity of a runtime instance in a distributed deployment.

    Describes WHO exists, not HOW they're performing (see NodeHealth).

    RSES-NODE-[hash] — immutable node identifier.
    """
    node_id: str                # RSES-NODE-[hash]
    name: str
    transport_type: str         # MCP, REST, WEBSOCKET
    endpoint: str               # URL or address
    capabilities: frozenset[str] = field(default_factory=frozenset)
    workspace_ids: list[str] = field(default_factory=list)
    max_concurrent_sessions: int = 10
    metadata: dict[str, str] = field(default_factory=dict)

    @staticmethod
    def generate_node_id(name: str, endpoint: str) -> str:
        data = f"runtime_node:{name}:{endpoint}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"RSES-NODE-{h}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "name": self.name,
            "transport_type": self.transport_type,
            "endpoint": self.endpoint,
            "capabilities": sorted(self.capabilities),
            "workspace_ids": self.workspace_ids,
            "max_concurrent_sessions": self.max_concurrent_sessions,
        }


# =====================================================================
# Remote Session
# =====================================================================

@dataclass(frozen=True)
class RemoteSession:
    """
    An agent session that may span multiple nodes.

    Tracks the logical session across physical locations.
    Migration history is reconstructed from SessionHandoff records
    in the Event Ledger, not from mutable fields.

    RSES-RS-[hash] — immutable remote session identifier.
    """
    remote_session_id: str      # RSES-RS-[hash]
    logical_session_id: str     # AGS-[hash] (the canonical session)
    agent_id: str               # AGNT-[hash]
    workspace_id: str           # WS-[hash]
    current_node_id: str        # RSES-NODE-[hash]
    status: RemoteSessionStatus = RemoteSessionStatus.ACTIVE
    handoff_count: int = 0
    created_at: str = ""
    last_active_at: str = ""

    @staticmethod
    def generate_remote_session_id(
        logical_session_id: str, node_id: str,
    ) -> str:
        data = f"remote_session:{logical_session_id}:{node_id}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"RSES-RS-{h}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "remote_session_id": self.remote_session_id,
            "logical_session_id": self.logical_session_id,
            "agent_id": self.agent_id,
            "workspace_id": self.workspace_id,
            "current_node_id": self.current_node_id,
            "status": self.status.value,
            "handoff_count": self.handoff_count,
            "created_at": self.created_at,
            "last_active_at": self.last_active_at,
        }


# =====================================================================
# Session Handoff
# =====================================================================

@dataclass(frozen=True)
class SessionHandoff:
    """
    Immutable record of a session transfer between nodes.

    Every migration attempt produces an immutable record.
    Retries produce new SessionHandoff records, not state mutations.

    State machine: INITIATED → IN_PROGRESS → COMPLETED | FAILED
    Failed handoffs can be followed by new handoff records.

    RSES-HO-[hash] — immutable handoff identifier.
    """
    handoff_id: str             # RSES-HO-[hash]
    remote_session_id: str      # RSES-RS-[hash]
    source_node_id: str         # RSES-NODE-[hash]
    target_node_id: str         # RSES-NODE-[hash]
    handoff_type: HandoffType = HandoffType.MIGRATION
    status: HandoffStatus = HandoffStatus.INITIATED
    packages_transferred: int = 0
    events_transferred: int = 0
    initiated_at: str = ""
    completed_at: str | None = None
    reason: str = ""

    @staticmethod
    def generate_handoff_id(
        remote_session_id: str, source_node_id: str, target_node_id: str,
    ) -> str:
        data = f"session_handoff:{remote_session_id}:{source_node_id}:{target_node_id}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"RSES-HO-{h}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "handoff_id": self.handoff_id,
            "remote_session_id": self.remote_session_id,
            "source_node_id": self.source_node_id,
            "target_node_id": self.target_node_id,
            "handoff_type": self.handoff_type.value,
            "status": self.status.value,
            "packages_transferred": self.packages_transferred,
            "events_transferred": self.events_transferred,
            "initiated_at": self.initiated_at,
            "completed_at": self.completed_at,
            "reason": self.reason,
        }


# =====================================================================
# Node Registry
# =====================================================================

@dataclass(frozen=True)
class NodeRegistry:
    """
    Registry of all known runtime nodes.

    Immutable snapshot. Mutations produce new registry instances.

    RSES-NR-[hash] — registry identifier.
    """
    registry_id: str = ""       # RSES-NR-[hash]
    nodes: tuple[RuntimeNode, ...] = ()
    health: tuple[NodeHealth, ...] = ()
    compiled_at: str = ""

    @staticmethod
    def generate_registry_id(compiled_at: str) -> str:
        data = f"node_registry:{compiled_at}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"RSES-NR-{h}"

    @property
    def online_nodes(self) -> list[RuntimeNode]:
        """All nodes with ONLINE health status."""
        online_ids = {
            h.node_id for h in self.health
            if h.status == NodeStatus.ONLINE
        }
        return [n for n in self.nodes if n.node_id in online_ids]

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def online_count(self) -> int:
        return len(self.online_nodes)

    def get_node(self, node_id: str) -> RuntimeNode | None:
        for n in self.nodes:
            if n.node_id == node_id:
                return n
        return None

    def get_health(self, node_id: str) -> NodeHealth | None:
        for h in self.health:
            if h.node_id == node_id:
                return h
        return None

    def get_nodes_for_workspace(self, workspace_id: str) -> list[RuntimeNode]:
        return [
            n for n in self.nodes
            if workspace_id in n.workspace_ids
        ]

    def add_node(
        self, node: RuntimeNode, health: NodeHealth | None = None,
    ) -> NodeRegistry:
        """Return a new registry with the node added."""
        new_health = self.health + (health,) if health else self.health
        return NodeRegistry(
            registry_id=self.registry_id,
            nodes=self.nodes + (node,),
            health=new_health,
            compiled_at=self.compiled_at,
        )

    def update_node(self, node: RuntimeNode) -> NodeRegistry:
        """Return a new registry with the node updated (matched by node_id)."""
        updated_nodes = tuple(
            node if n.node_id == node.node_id else n
            for n in self.nodes
        )
        return NodeRegistry(
            registry_id=self.registry_id,
            nodes=updated_nodes,
            health=self.health,
            compiled_at=self.compiled_at,
        )

    def update_health(self, node_health: NodeHealth) -> NodeRegistry:
        """Return a new registry with health updated (matched by node_id)."""
        updated_health = tuple(
            node_health if h.node_id == node_health.node_id else h
            for h in self.health
        )
        return NodeRegistry(
            registry_id=self.registry_id,
            nodes=self.nodes,
            health=updated_health,
            compiled_at=self.compiled_at,
        )

    def remove_node(self, node_id: str) -> NodeRegistry:
        """Return a new registry with the node and its health removed."""
        return NodeRegistry(
            registry_id=self.registry_id,
            nodes=tuple(n for n in self.nodes if n.node_id != node_id),
            health=tuple(h for h in self.health if h.node_id != node_id),
            compiled_at=self.compiled_at,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "registry_id": self.registry_id,
            "node_count": self.node_count,
            "online_count": self.online_count,
            "nodes": [n.to_dict() for n in self.nodes],
            "health": [h.to_dict() for h in self.health],
            "compiled_at": self.compiled_at,
        }
