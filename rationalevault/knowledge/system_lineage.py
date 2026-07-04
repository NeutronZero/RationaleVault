"""
RationaleVault System Lineage Projection — Unified cross-subsystem lineage graph.

Creates one graph that connects:
    Event → Belief → Decision → Execution → Artifact → Learning → Reflection
    → Promotion → Knowledge → Planner → Memory → Scheduler

Every object can answer "Why do I exist?" with a single graph traversal.

Design rules:
  - Deterministic — same events produce same lineage graph.
  - Append-only — edges are never removed.
  - Typed edges — each edge carries a relationship type.
  - Queryable — BFS/DFS from any node.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum
from typing import Any


# =====================================================================
# Enums
# =====================================================================

class EdgeType(str, Enum):
    """Types of lineage relationships."""
    DERIVED_FROM = "DERIVED_FROM"           # General derivation
    CAUSED_BY = "CAUSED_BY"                 # Causal relationship
    PROMOTED_FROM = "PROMOTED_FROM"         # Knowledge promotion
    VALIDATED_BY = "VALIDATED_BY"           # Knowledge validation
    EVOLVED_INTO = "EVOLVED_INTO"           # Knowledge evolution
    EXECUTED_FOR = "EXECUTED_FOR"           # Skill execution
    GENERATED_BY = "GENERATED_BY"           # Artifact generation
    REFLECTED_IN = "REFLECTED_IN"           # Reflection reference
    ADVISED_BY = "ADVISED_BY"               # AI advisory
    ADJUSTED_BY = "ADJUSTED_BY"             # Planner adjustment
    TRANSITIONED_VIA = "TRANSITIONED_VIA"   # Memory lifecycle
    SCHEDULED_BY = "SCHEDULED_BY"           # Cognitive scheduling


class NodeSubsystem(str, Enum):
    """Subsystem classification for lineage nodes."""
    EVENT = "EVENT"
    BELIEF = "BELIEF"
    DECISION = "DECISION"
    EXECUTION = "EXECUTION"
    ARTIFACT = "ARTIFACT"
    LEARNING = "LEARNING"
    REFLECTION = "REFLECTION"
    PROMOTION = "PROMOTION"
    KNOWLEDGE = "KNOWLEDGE"
    PLANNER = "PLANNER"
    MEMORY = "MEMORY"
    SCHEDULER = "SCHEDULER"
    ADVISORY = "ADVISORY"


# =====================================================================
# Domain Models
# =====================================================================

@dataclass(frozen=True)
class LineageNode:
    """
    A node in the system lineage graph.

    LINNODE-[hash] — immutable.
    """
    node_id: str                    # LINNODE-[hash]
    object_id: str                  # The actual object ID (BEL-, DEC-, etc.)
    subsystem: NodeSubsystem
    title: str
    created_at: str

    @staticmethod
    def generate_node_id(object_id: str, subsystem: str) -> str:
        data = f"lineage_node:{object_id}:{subsystem}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"LINNODE-{h}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "object_id": self.object_id,
            "subsystem": self.subsystem.value,
            "title": self.title,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> LineageNode:
        return cls(
            node_id=d["node_id"],
            object_id=d["object_id"],
            subsystem=NodeSubsystem(d["subsystem"]),
            title=d.get("title", ""),
            created_at=d.get("created_at", ""),
        )


@dataclass(frozen=True)
class LineageEdge:
    """
    An edge in the system lineage graph.

    LINEGDE-[hash] — immutable, append-only.
    """
    edge_id: str                    # LINEGDE-[hash]
    source_node_id: str             # LINNODE-[hash]
    target_node_id: str             # LINNODE-[hash]
    edge_type: EdgeType
    created_at: str

    @staticmethod
    def generate_edge_id(source_id: str, target_id: str, edge_type: str) -> str:
        data = f"lineage_edge:{source_id}:{target_id}:{edge_type}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"LINEGDE-{h}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "source_node_id": self.source_node_id,
            "target_node_id": self.target_node_id,
            "edge_type": self.edge_type.value,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> LineageEdge:
        return cls(
            edge_id=d["edge_id"],
            source_node_id=d["source_node_id"],
            target_node_id=d["target_node_id"],
            edge_type=EdgeType(d["edge_type"]),
            created_at=d.get("created_at", ""),
        )


@dataclass(frozen=True)
class SystemLineageProjection:
    """
    The unified cross-subsystem lineage graph.

    Contains all nodes and edges. Queryable via BFS/DFS.
    """
    nodes: list[LineageNode]
    edges: list[LineageEdge]
    version: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SystemLineageProjection:
        return cls(
            nodes=[LineageNode.from_dict(n) for n in d.get("nodes", [])],
            edges=[LineageEdge.from_dict(e) for e in d.get("edges", [])],
            version=d.get("version", 1),
        )

    def get_node(self, node_id: str) -> LineageNode | None:
        """Get a node by ID."""
        for n in self.nodes:
            if n.node_id == node_id:
                return n
        return None

    def get_node_by_object(self, object_id: str) -> LineageNode | None:
        """Get a node by its object ID."""
        for n in self.nodes:
            if n.object_id == object_id:
                return n
        return None

    def get_edges_from(self, node_id: str) -> list[LineageEdge]:
        """Get all outgoing edges from a node."""
        return [e for e in self.edges if e.source_node_id == node_id]

    def get_edges_to(self, node_id: str) -> list[LineageEdge]:
        """Get all incoming edges to a node."""
        return [e for e in self.edges if e.target_node_id == node_id]

    def ancestors(self, node_id: str) -> list[str]:
        """BFS traversal to find all ancestors (upstream nodes)."""
        visited: set[str] = set()
        queue = [node_id]
        result: list[str] = []
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            if current != node_id:
                result.append(current)
            for edge in self.get_edges_to(current):
                queue.append(edge.source_node_id)
        return result

    def descendants(self, node_id: str) -> list[str]:
        """BFS traversal to find all descendants (downstream nodes)."""
        visited: set[str] = set()
        queue = [node_id]
        result: list[str] = []
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            if current != node_id:
                result.append(current)
            for edge in self.get_edges_from(current):
                queue.append(edge.target_node_id)
        return result

    def why_exists(self, object_id: str) -> list[str]:
        """
        Answer "Why do I exist?" for any object.

        Returns the chain of ancestor object IDs explaining lineage.
        """
        node = self.get_node_by_object(object_id)
        if node is None:
            return []
        ancestor_nodes = self.ancestors(node.node_id)
        result = []
        for ancestor_id in ancestor_nodes:
            ancestor_node = self.get_node(ancestor_id)
            if ancestor_node:
                result.append(ancestor_node.object_id)
        return result

    def full_lineage_path(self, object_id: str) -> list[str]:
        """
        Get the full lineage path from this object back to its origins.

        Returns object IDs in dependency order (this object first, origins last).
        """
        node = self.get_node_by_object(object_id)
        if node is None:
            return [object_id]
        ancestor_nodes = self.ancestors(node.node_id)
        result = [object_id]
        for ancestor_id in ancestor_nodes:
            ancestor_node = self.get_node(ancestor_id)
            if ancestor_node:
                result.append(ancestor_node.object_id)
        return result
