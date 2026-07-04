"""RationaleVault Knowledge Graph — Graph projection layer for synthesized knowledge.

Projects KnowledgeObjects and KnowledgeRelations into a deterministic graph.
No external database dependencies.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
import xml.etree.ElementTree as ET

from rationalevault.knowledge.models import KnowledgeObject, KnowledgeRelation
from rationalevault.knowledge.relation_types import RelationType


@dataclass
class KnowledgeNode:
    """A projected node representing a KnowledgeObject in the graph."""
    id: str
    title: str
    type: str
    domain: str
    confidence: float
    importance: str
    evidence_count: int
    source_event_count: int
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "type": self.type,
            "domain": self.domain,
            "confidence": self.confidence,
            "importance": self.importance,
            "evidence_count": self.evidence_count,
            "source_event_count": self.source_event_count,
            "tags": self.tags,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> KnowledgeNode:
        return cls(
            id=d["id"],
            title=d["title"],
            type=d["type"],
            domain=d["domain"],
            confidence=d["confidence"],
            importance=d["importance"],
            evidence_count=d["evidence_count"],
            source_event_count=d["source_event_count"],
            tags=d.get("tags", []),
            metadata=d.get("metadata", {}),
        )


@dataclass
class KnowledgeEdge:
    """A projected edge representing a KnowledgeRelation in the graph."""
    source: str
    target: str
    relation_type: RelationType
    confidence: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.relation_type, RelationType):
            raise TypeError(
                f"relation_type must be a RelationType, got {type(self.relation_type).__name__}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "relation_type": self.relation_type.value,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> KnowledgeEdge:
        rt = d["relation_type"]
        if isinstance(rt, str):
            rt = RelationType.from_str(rt)
        return cls(
            source=d["source"],
            target=d["target"],
            relation_type=rt,
            confidence=d["confidence"],
            metadata=d.get("metadata", {}),
        )


@dataclass
class GraphProjection:
    """Deterministic Knowledge Graph Projection."""
    graph_id: str
    version: int
    node_count: int
    edge_count: int
    generated_at: str
    nodes: list[KnowledgeNode] = field(default_factory=list)
    edges: list[KnowledgeEdge] = field(default_factory=list)

    @classmethod
    def build(
        cls,
        knowledge_objects: list[KnowledgeObject],
        relations: list[KnowledgeRelation],
        version: int = 1,
    ) -> GraphProjection:
        """Deterministically project knowledge objects and relations into a graph."""
        nodes_map: dict[str, KnowledgeNode] = {}
        # Keep track of mapping from old KnowledgeObject ID to new deterministic Node ID
        id_mapping: dict[str, str] = {}

        # 1. Project nodes
        for k in knowledge_objects:
            # node_id = sha256(knowledge_type + title + version)
            h = hashlib.sha256()
            h.update(f"{k.knowledge_type.value}:{k.title}:{k.version}".encode("utf-8"))
            node_id = h.hexdigest()
            id_mapping[k.id] = node_id

            evidence_count = k.provenance.evidence_count
            source_event_count = len(k.provenance.source_event_ids)

            node = KnowledgeNode(
                id=node_id,
                title=k.title,
                type=k.knowledge_type.value,
                domain=k.knowledge_domain.value,
                confidence=k.confidence.score,
                importance=k.importance,
                evidence_count=evidence_count,
                source_event_count=source_event_count,
                tags=k.tags,
                metadata={
                    "original_id": k.id,
                    "version": k.version,
                    "lifecycle_status": k.lifecycle_status,
                    "superseded_by": k.superseded_by,
                    "created_at": k.created_at,
                    "updated_at": k.updated_at,
                },
            )
            nodes_map[node_id] = node

        # 2. Project edges
        edges: list[KnowledgeEdge] = []
        for r in relations:
            src_node_id = id_mapping.get(r.source_id)
            tgt_node_id = id_mapping.get(r.target_id)

            # Skip edges pointing to non-existent nodes
            if not src_node_id or not tgt_node_id:
                continue

            edge = KnowledgeEdge(
                source=src_node_id,
                target=tgt_node_id,
                relation_type=r.relation_type,
                confidence=r.confidence,
                metadata={
                    "created_at": r.created_at,
                },
            )
            edges.append(edge)

        # 3. Compute deterministic Graph ID
        # Sort nodes and edges to enforce determinism
        sorted_nodes = sorted(nodes_map.values(), key=lambda n: n.id)
        sorted_edges = sorted(edges, key=lambda e: (e.source, e.target, e.relation_type))

        node_ids_str = ":".join(n.id for n in sorted_nodes)
        edge_ids_str = ":".join(f"{e.source}:{e.target}:{e.relation_type}" for e in sorted_edges)
        combined = f"{node_ids_str}::{edge_ids_str}"
        graph_id = hashlib.sha256(combined.encode("utf-8")).hexdigest()

        return cls(
            graph_id=graph_id,
            version=version,
            node_count=len(sorted_nodes),
            edge_count=len(sorted_edges),
            generated_at=datetime.now().isoformat(),
            nodes=sorted_nodes,
            edges=sorted_edges,
        )

    def query_node(self, node_id: str) -> Optional[KnowledgeNode]:
        """Query a single node by its projected ID."""
        for n in self.nodes:
            if n.id == node_id or n.id.startswith(node_id):
                return n
        return None

    def neighbors(self, node_id: str, depth: int = 1) -> GraphProjection:
        """Retrieve a sub-graph of nodes and edges within `depth` steps from `node_id` (undirected traversal)."""
        start_node = self.query_node(node_id)
        if not start_node:
            return GraphProjection(
                graph_id=hashlib.sha256(b"").hexdigest(),
                version=self.version,
                node_count=0,
                edge_count=0,
                generated_at=datetime.now().isoformat(),
                nodes=[],
                edges=[],
            )

        # BFS traversal treating edges as undirected
        visited = {start_node.id}
        queue = [(start_node.id, 0)]

        # Build adjacency mapping for undirected lookup
        adj: dict[str, set[str]] = {n.id: set() for n in self.nodes}
        for e in self.edges:
            if e.source in adj and e.target in adj:
                adj[e.source].add(e.target)
                adj[e.target].add(e.source)

        while queue:
            curr, curr_depth = queue.pop(0)
            if curr_depth >= depth:
                continue

            for neighbor in adj.get(curr, set()):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, curr_depth + 1))

        # Filter nodes and edges belonging to visited subset
        sub_nodes = [n for n in self.nodes if n.id in visited]
        sub_edges = [e for e in self.edges if e.source in visited and e.target in visited]

        # Deterministic sub-graph hashing
        sorted_sub_nodes = sorted(sub_nodes, key=lambda n: n.id)
        sorted_sub_edges = sorted(sub_edges, key=lambda e: (e.source, e.target, e.relation_type))
        node_ids_str = ":".join(n.id for n in sorted_sub_nodes)
        edge_ids_str = ":".join(f"{e.source}:{e.target}:{e.relation_type}" for e in sorted_sub_edges)
        sub_graph_id = hashlib.sha256(f"{node_ids_str}::{edge_ids_str}".encode("utf-8")).hexdigest()

        return GraphProjection(
            graph_id=sub_graph_id,
            version=self.version,
            node_count=len(sorted_sub_nodes),
            edge_count=len(sorted_sub_edges),
            generated_at=datetime.now().isoformat(),
            nodes=sorted_sub_nodes,
            edges=sorted_sub_edges,
        )

    def shortest_path(self, source: str, target: str) -> list[str]:
        """Compute the shortest path using directed BFS. Returns list of node IDs or empty list."""
        src_node = self.query_node(source)
        tgt_node = self.query_node(target)
        if not src_node or not tgt_node:
            return []

        # Find exact IDs
        src_id = src_node.id
        tgt_id = tgt_node.id

        if src_id == tgt_id:
            return [src_id]

        # Build directed adjacency
        adj: dict[str, list[str]] = {n.id: [] for n in self.nodes}
        for e in self.edges:
            if e.source in adj and e.target in adj:
                adj[e.source].append(e.target)

        # BFS queue storing (current_node, path_so_far)
        queue = [(src_id, [src_id])]
        visited = {src_id}

        while queue:
            curr, path = queue.pop(0)
            if curr == tgt_id:
                return path

            for neighbor in adj.get(curr, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))

        return []

    def stats(self) -> dict[str, Any]:
        """Compute graph statistics."""
        nodes_set = {n.id for n in self.nodes}
        v = len(nodes_set)
        e = len(self.edges)

        # Graph Density: simple directed density is E / (V * (V - 1))
        density = 0.0
        if v > 1:
            density = e / (v * (v - 1))

        # Calculate degrees
        in_degree: dict[str, int] = {nid: 0 for nid in nodes_set}
        out_degree: dict[str, int] = {nid: 0 for nid in nodes_set}
        for edge in self.edges:
            if edge.source in out_degree:
                out_degree[edge.source] += 1
            if edge.target in in_degree:
                in_degree[edge.target] += 1

        orphan_count = 0
        for nid in nodes_set:
            if in_degree[nid] == 0 and out_degree[nid] == 0:
                orphan_count += 1

        # Calculate connected components (weakly connected components, undirected edges)
        adj: dict[str, set[str]] = {nid: set() for nid in nodes_set}
        for edge in self.edges:
            if edge.source in adj and edge.target in adj:
                adj[edge.source].add(edge.target)
                adj[edge.target].add(edge.source)

        visited = set()
        components = []
        for nid in nodes_set:
            if nid not in visited:
                comp = set()
                q = [nid]
                visited.add(nid)
                while q:
                    curr = q.pop(0)
                    comp.add(curr)
                    for neighbor in adj.get(curr, set()):
                        if neighbor not in visited:
                            visited.add(neighbor)
                            q.append(neighbor)
                components.append(comp)

        component_count = len(components)
        largest_comp_size = max(len(c) for c in components) if components else 0
        largest_component_pct = (largest_comp_size / v) if v > 0 else 0.0

        return {
            "node_count": v,
            "edge_count": e,
            "density": density,
            "connected_components": component_count,
            "orphan_count": orphan_count,
            "orphan_pct": (orphan_count / v) if v > 0 else 0.0,
            "largest_component_pct": largest_component_pct,
        }

    # --- Exports ---

    def export_json(self) -> str:
        """Export graph to standard JSON format."""
        return json.dumps(self.to_dict(), indent=2)

    def export_graphml(self) -> str:
        """Export graph to standard GraphML XML format."""
        root = ET.Element("graphml", {
            "xmlns": "http://graphml.graphdrawing.org/xmlns",
            "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
            "xsi:schemaLocation": "http://graphml.graphdrawing.org/xmlns http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd"
        })

        # Define keys
        keys = [
            ("title", "node", "title", "string"),
            ("type", "node", "type", "string"),
            ("domain", "node", "domain", "string"),
            ("confidence", "node", "confidence", "double"),
            ("importance", "node", "importance", "string"),
            ("evidence_count", "node", "evidence_count", "integer"),
            ("source_event_count", "node", "source_event_count", "integer"),
            ("relation_type", "edge", "relation_type", "string"),
            ("edge_confidence", "edge", "confidence", "double"),
        ]
        for kid, kfor, kname, ktype in keys:
            ET.SubElement(root, "key", {
                "id": kid,
                "for": kfor,
                "attr.name": kname,
                "attr.type": ktype
            })

        graph = ET.SubElement(root, "graph", {
            "id": "G",
            "edgedefault": "directed"
        })

        # Nodes
        for n in self.nodes:
            node_el = ET.SubElement(graph, "node", {"id": n.id})
            for attr in ["title", "type", "domain", "importance"]:
                d_el = ET.SubElement(node_el, "data", {"key": attr})
                d_el.text = str(getattr(n, attr))
            for attr in ["confidence", "evidence_count", "source_event_count"]:
                d_el = ET.SubElement(node_el, "data", {"key": attr})
                d_el.text = str(getattr(n, attr))

        # Edges
        for i, e in enumerate(self.edges):
            edge_el = ET.SubElement(graph, "edge", {
                "id": f"e{i}",
                "source": e.source,
                "target": e.target
            })
            d_rel = ET.SubElement(edge_el, "data", {"key": "relation_type"})
            d_rel.text = e.relation_type.value
            d_conf = ET.SubElement(edge_el, "data", {"key": "edge_confidence"})
            d_conf.text = str(e.confidence)

        # ET.tostring returns bytes in Python, decode to string
        # To make it beautiful, we can write a helper but simple element tree write works:
        return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="utf-8").decode("utf-8")

    def export_mermaid(self) -> str:
        """Export graph to Mermaid flowchart syntax."""
        lines = ["graph TD"]
        # Declare nodes with labels
        for n in self.nodes:
            # Sanitize labels to be friendly with double quotes
            safe_title = n.title.replace('"', '\\"')
            lines.append(f'    {n.id}["[{n.type}] {safe_title}"]')
        # Declare connections
        for e in self.edges:
            lines.append(f'    {e.source} -->|{e.relation_type.value}| {e.target}')
        return "\n".join(lines)

    def export_networkx(self) -> dict[str, Any]:
        """Export graph to NetworkX-compatible json format dictionary."""
        return {
            "directed": True,
            "multigraph": False,
            "graph": {},
            "nodes": [n.to_dict() for n in self.nodes],
            "links": [
                {
                    "source": e.source,
                    "target": e.target,
                    "relation_type": e.relation_type.value,
                    "confidence": e.confidence,
                    "metadata": e.metadata,
                } for e in self.edges
            ]
        }

    # --- Serialization ---

    def to_dict(self) -> dict[str, Any]:
        return {
            "graph_id": self.graph_id,
            "version": self.version,
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "generated_at": self.generated_at,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> GraphProjection:
        return cls(
            graph_id=d["graph_id"],
            version=d.get("version", 1),
            node_count=d.get("node_count", 0),
            edge_count=d.get("edge_count", 0),
            generated_at=d.get("generated_at", ""),
            nodes=[KnowledgeNode.from_dict(n) for n in d.get("nodes", [])],
            edges=[KnowledgeEdge.from_dict(e) for e in d.get("edges", [])],
        )
