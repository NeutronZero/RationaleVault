"""
RationaleVault Remote Sessions — Event payloads for distributed operations.

Separation of concerns:
  - Remote models define domain contracts (frozen dataclasses).
  - Event payloads define what happened (immutable records).
  - Remote models ≠ Event payloads.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# =====================================================================
# Node Events
# =====================================================================

@dataclass(frozen=True)
class NodeRegisteredPayload:
    """
    A runtime node was registered in the cluster.
    """
    node_id: str
    name: str
    transport_type: str
    endpoint: str
    workspace_ids: list[str] = field(default_factory=list)
    registered_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "name": self.name,
            "transport_type": self.transport_type,
            "endpoint": self.endpoint,
            "workspace_ids": self.workspace_ids,
            "registered_at": self.registered_at,
        }


@dataclass(frozen=True)
class NodeStatusChangedPayload:
    """
    A runtime node changed status (e.g., ONLINE → DRAINING).
    """
    node_id: str
    old_status: str
    new_status: str
    changed_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "old_status": self.old_status,
            "new_status": self.new_status,
            "changed_at": self.changed_at,
        }


# =====================================================================
# Migration Events
# =====================================================================

@dataclass(frozen=True)
class SessionMigratingPayload:
    """
    A remote session migration was initiated.
    """
    remote_session_id: str
    logical_session_id: str
    source_node_id: str
    target_node_id: str
    handoff_id: str
    handoff_type: str
    initiated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "remote_session_id": self.remote_session_id,
            "logical_session_id": self.logical_session_id,
            "source_node_id": self.source_node_id,
            "target_node_id": self.target_node_id,
            "handoff_id": self.handoff_id,
            "handoff_type": self.handoff_type,
            "initiated_at": self.initiated_at,
        }


@dataclass(frozen=True)
class SessionMigratedPayload:
    """
    A remote session migration completed successfully.
    """
    remote_session_id: str
    logical_session_id: str
    target_node_id: str
    handoff_id: str
    packages_transferred: int = 0
    events_transferred: int = 0
    completed_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "remote_session_id": self.remote_session_id,
            "logical_session_id": self.logical_session_id,
            "target_node_id": self.target_node_id,
            "handoff_id": self.handoff_id,
            "packages_transferred": self.packages_transferred,
            "events_transferred": self.events_transferred,
            "completed_at": self.completed_at,
        }


@dataclass(frozen=True)
class SessionHandoffFailedPayload:
    """
    A remote session migration failed.
    """
    remote_session_id: str
    source_node_id: str
    target_node_id: str
    handoff_id: str
    reason: str
    failed_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "remote_session_id": self.remote_session_id,
            "source_node_id": self.source_node_id,
            "target_node_id": self.target_node_id,
            "handoff_id": self.handoff_id,
            "reason": self.reason,
            "failed_at": self.failed_at,
        }


# =====================================================================
# Telemetry Events
# =====================================================================

@dataclass(frozen=True)
class CrossNodeTelemetryAggregatedPayload:
    """
    Telemetry from multiple nodes was aggregated.
    """
    aggregation_id: str
    source_node_ids: list[str]
    metric_type: str
    aggregation_method: str
    value: float
    sample_count: int
    aggregated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "aggregation_id": self.aggregation_id,
            "source_node_ids": self.source_node_ids,
            "metric_type": self.metric_type,
            "aggregation_method": self.aggregation_method,
            "value": self.value,
            "sample_count": self.sample_count,
            "aggregated_at": self.aggregated_at,
        }
