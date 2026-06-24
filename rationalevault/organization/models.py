"""RationaleVault Organization Models — Types for organizational knowledge visibility.

OrganizationState = OrganizationProjection.project(registry, cross_project_states, knowledge_by_project)

No new persistence layer. Replayable from primary state.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TransferabilityTelemetry:
    """Telemetry on knowledge transferability distribution across the organization."""
    local_only_count: int = 0
    reusable_count: int = 0
    organizational_count: int = 0
    transfer_attempts: int = 0
    transfer_matches: int = 0
    acceptance_rate: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "local_only_count": self.local_only_count,
            "reusable_count": self.reusable_count,
            "organizational_count": self.organizational_count,
            "transfer_attempts": self.transfer_attempts,
            "transfer_matches": self.transfer_matches,
            "acceptance_rate": round(self.acceptance_rate, 4),
        }


@dataclass
class KnowledgeLineage:
    """Lineage for transferred knowledge. transfer_path is best-effort in I11."""
    knowledge_id: str
    origin_project: str
    current_projects: list[str] = field(default_factory=list)
    transfer_path: list[str] = field(default_factory=list)
    depth: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "knowledge_id": self.knowledge_id,
            "origin_project": self.origin_project,
            "current_projects": self.current_projects,
            "transfer_path": self.transfer_path,
            "depth": self.depth,
        }


@dataclass
class SharedKnowledge:
    """Knowledge present in multiple projects. Independent from KnowledgeLineage."""
    knowledge_id: str
    title: str
    knowledge_type: str
    present_in_projects: list[str] = field(default_factory=list)
    transfer_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "knowledge_id": self.knowledge_id,
            "title": self.title,
            "knowledge_type": self.knowledge_type,
            "present_in_projects": self.present_in_projects,
            "transfer_count": self.transfer_count,
        }


@dataclass
class CrossProjectConflict:
    """A contradiction detected across projects."""
    conflict_id: str
    knowledge_a_id: str
    knowledge_b_id: str
    project_a: str
    project_b: str
    knowledge_a_title: str
    knowledge_b_title: str
    confidence: float = 0.0
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "conflict_id": self.conflict_id,
            "knowledge_a_id": self.knowledge_a_id,
            "knowledge_b_id": self.knowledge_b_id,
            "project_a": self.project_a,
            "project_b": self.project_b,
            "knowledge_a_title": self.knowledge_a_title,
            "knowledge_b_title": self.knowledge_b_title,
            "confidence": round(self.confidence, 4),
            "reasons": self.reasons,
        }


@dataclass
class OrganizationHealth:
    """Health metrics for organizational knowledge visibility."""
    total_projects: int = 0
    total_knowledge: int = 0
    transferable_knowledge: int = 0
    shared_knowledge_count: int = 0
    knowledge_adoption_rate: float = 0.0
    cross_project_conflicts: int = 0
    invariant_count: int = 0
    lineage_depth_avg: float = 0.0
    overall: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_projects": self.total_projects,
            "total_knowledge": self.total_knowledge,
            "transferable_knowledge": self.transferable_knowledge,
            "shared_knowledge_count": self.shared_knowledge_count,
            "knowledge_adoption_rate": round(self.knowledge_adoption_rate, 4),
            "cross_project_conflicts": self.cross_project_conflicts,
            "invariant_count": self.invariant_count,
            "lineage_depth_avg": round(self.lineage_depth_avg, 4),
            "overall": round(self.overall, 4),
        }


@dataclass
class OrganizationState:
    """Compiled organizational knowledge state.

    Built by OrganizationProjection from CrossProjectStates and raw KnowledgeObjects.
    No new persistence layer. Replayable from primary state.
    """
    compiled_at: str
    projection_version: str = "1.0"
    project_ids: list[str] = field(default_factory=list)
    active_lineages: dict[str, KnowledgeLineage] = field(default_factory=dict)
    shared_knowledge: list[SharedKnowledge] = field(default_factory=list)
    cross_project_conflicts: list[CrossProjectConflict] = field(default_factory=list)
    invariants_across_projects: list[SharedKnowledge] = field(default_factory=list)
    project_clusters: list[list[str]] = field(default_factory=list)
    transferability_telemetry: TransferabilityTelemetry = field(default_factory=TransferabilityTelemetry)
    health: OrganizationHealth = field(default_factory=OrganizationHealth)

    def to_dict(self) -> dict[str, Any]:
        return {
            "compiled_at": self.compiled_at,
            "projection_version": self.projection_version,
            "project_ids": self.project_ids,
            "active_lineage_count": len(self.active_lineages),
            "active_lineages": {k: v.to_dict() for k, v in self.active_lineages.items()},
            "shared_knowledge_count": len(self.shared_knowledge),
            "shared_knowledge": [s.to_dict() for s in self.shared_knowledge],
            "cross_project_conflicts": [c.to_dict() for c in self.cross_project_conflicts],
            "invariants_across_projects": [i.to_dict() for i in self.invariants_across_projects],
            "project_clusters": self.project_clusters,
            "transferability_telemetry": self.transferability_telemetry.to_dict(),
            "health": self.health.to_dict(),
        }
