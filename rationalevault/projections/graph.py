"""RationaleVault Graph Projection — Navigable relationship layer.

GraphState = GraphProjection.project(knowledge_state)

Produces a navigable graph from KnowledgeState, enabling:
  - Filtered traversal (by edge type, confidence, direction)
  - Dependency chain walking
  - Topological sort
  - Cycle detection (lazy)
  - Impact analysis (upstream/downstream)
  - Blast radius computation
  - Connected component clustering
  - All paths enumeration
  - Weighted shortest path (by confidence)

Design constraints:
  - Deterministic: same KnowledgeState → identical GraphState
  - Replayable: no persisted state outside event store + knowledge store
  - Edge-aware adjacency: stores GraphEdge objects for O(1) metadata access
  - Lazy cycle detection: computed on demand, not during projection build
  - MAX_PATHS cap: prevents exponential blowup in dense graphs
"""
from __future__ import annotations

import heapq
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional, ClassVar
from rationalevault.projections.base import BaseProjection, ProjectionKind, SemVer

from rationalevault.knowledge.models import KnowledgeLifecycle, KnowledgeObject
from rationalevault.projections.knowledge import ConflictRecord, KnowledgeState, KnowledgeProjection


MAX_PATHS = 100
MAX_BLAST_DEPTH = 10


# ── Graph Data Structures ────────────────────────────────────────────────────

@dataclass
class GraphNode:
    """A projected node from a KnowledgeObject."""
    id: str
    title: str
    knowledge_type: str
    domain: str
    confidence: float
    importance: str
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "knowledge_type": self.knowledge_type,
            "domain": self.domain,
            "confidence": self.confidence,
            "importance": self.importance,
            "tags": self.tags,
        }


from rationalevault.knowledge.relation_types import RelationType


@dataclass
class GraphEdge:
    """A projected edge from a KnowledgeRelation or adjacency structure."""
    source: str
    target: str
    relation_type: RelationType
    confidence: float

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
        }


# ── GraphState ───────────────────────────────────────────────────────────────

@dataclass
class GraphState:
    """Compiled graph state of a project.

    Built from KnowledgeState by GraphProjection.
    All graph operations live on this class.

    Edge-aware adjacency: adjacency[node] returns list[GraphEdge],
    enabling O(1) access to relation_type and confidence during traversal.
    """
    project_id: str
    compiled_at: str
    projection_version: str = "1.0"

    # Core graph
    nodes: dict[str, GraphNode] = field(default_factory=dict)
    edges: list[GraphEdge] = field(default_factory=list)

    # Edge-aware adjacency
    adjacency: dict[str, list[GraphEdge]] = field(default_factory=dict)
    reverse_adjacency: dict[str, list[GraphEdge]] = field(default_factory=dict)

    # Derived (clusters computed eagerly, cycles lazy)
    clusters: list[list[str]] = field(default_factory=list)
    cycles: Optional[list[list[str]]] = field(default=None)

    # Stats
    node_count: int = 0
    edge_count: int = 0
    density: float = 0.0

    # Contradiction-derived
    conflicted_nodes: set[str] = field(default_factory=set)

    # Relation-type index for O(1) subgraph access
    edges_by_relation: dict[RelationType, tuple[GraphEdge, ...]] = field(
        default_factory=lambda: {rt: () for rt in RelationType}
    )

    # Provenance
    provenance: dict[str, list[int]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "compiled_at": self.compiled_at,
            "projection_version": self.projection_version,
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "density": round(self.density, 4),
            "cluster_count": len(self.clusters),
            "clusters": self.clusters,
            "cycles": self.cycles,
            "conflicted_nodes": sorted(self.conflicted_nodes),
            "edges_by_relation": {
                rt.value: len(edges) for rt, edges in self.edges_by_relation.items()
            },
            "nodes": {nid: n.to_dict() for nid, n in self.nodes.items()},
            "edges": [e.to_dict() for e in self.edges],
        }

    # ── Tier 1: Core Operations ──────────────────────────────────────────

    def filtered_traversal(
        self,
        node_id: str,
        edge_types: list[str] | None = None,
        min_confidence: float = 0.0,
        direction: str = "both",
        max_depth: int = 10,
    ) -> GraphState:
        """BFS traversal with edge-type and confidence filters.

        Returns a sub-graph containing only matching nodes and edges.

        Args:
            node_id: Starting node ID.
            edge_types: If provided, only follow these relation types.
            min_confidence: Minimum edge confidence to follow.
            direction: "both", "forward", or "backward".
            max_depth: Maximum traversal depth.

        Returns:
            GraphState sub-graph with matching nodes and edges.
        """
        if node_id not in self.nodes:
            return GraphState(
                project_id=self.project_id,
                compiled_at=self.compiled_at,
            )

        visited: set[str] = set()
        result_nodes: dict[str, GraphNode] = {}
        result_edges: list[GraphEdge] = []
        queue: deque[tuple[str, int]] = deque([(node_id, 0)])

        while queue:
            current, depth = queue.popleft()
            if current in visited or depth > max_depth:
                continue
            visited.add(current)
            result_nodes[current] = self.nodes[current]

            # Forward edges
            if direction in ("both", "forward"):
                for edge in self.adjacency.get(current, []):
                    if edge_types and edge.relation_type not in edge_types:
                        continue
                    if edge.confidence < min_confidence:
                        continue
                    result_edges.append(edge)
                    if edge.target not in visited:
                        queue.append((edge.target, depth + 1))

            # Backward edges
            if direction in ("both", "backward"):
                for edge in self.reverse_adjacency.get(current, []):
                    if edge_types and edge.relation_type not in edge_types:
                        continue
                    if edge.confidence < min_confidence:
                        continue
                    result_edges.append(edge)
                    if edge.source not in visited:
                        queue.append((edge.source, depth + 1))

        return self._build_subgraph(result_nodes, result_edges)

    def dependency_chain(
        self,
        node_id: str,
        relation_type: RelationType = RelationType.DERIVED_FROM,
    ) -> list[dict[str, Any]]:
        """Walk transitive dependencies via specified relation type.

        Returns ordered list from leaf to root (dependencies first).
        Each entry: {"node_id": str, "depth": int}

        Raises ValueError if cycle detected.
        """
        chain: list[dict[str, Any]] = []
        visited: set[str] = set()

        first_neighbors = [
            edge.source for edge in self.reverse_adjacency.get(node_id, [])
            if edge.relation_type == relation_type
        ]
        
        stack = [[node_id, first_neighbors, 0, 0]]
        visited.add(node_id)
        chain.append({"node_id": node_id, "depth": 0})

        while stack:
            frame = stack[-1]
            u, neighbors, idx, depth = frame[0], frame[1], frame[2], frame[3]

            if idx < len(neighbors):
                frame[2] += 1
                v = neighbors[idx]
                
                if v in visited:
                    raise ValueError(f"Cycle detected at node {v}")
                
                visited.add(v)
                chain.append({"node_id": v, "depth": depth + 1})
                
                next_neighbors = [
                    edge.source for edge in self.reverse_adjacency.get(v, [])
                    if edge.relation_type == relation_type
                ]
                stack.append([v, next_neighbors, 0, depth + 1])
            else:
                stack.pop()

        return chain

    def impact_analysis(
        self,
        node_id: str,
        depth: int = 3,
        relation_types: list[str] | None = None,
    ) -> dict[str, list[str]]:
        """Analyze upstream and downstream impact of a node.

        Returns:
            {
                "upstream": [node_ids that depend on this node],
                "downstream": [node_ids this node depends on],
                "affected_by_contradiction": [node_ids connected via CONTRADICTS],
            }
        """
        upstream = self._bfs_directional(node_id, "reverse", depth, relation_types)
        downstream = self._bfs_directional(node_id, "forward", depth, relation_types)

        # Find contradiction-connected nodes
        contradicted: set[str] = set()
        for edge in self.adjacency.get(node_id, []):
            if edge.relation_type == RelationType.CONTRADICTS:
                contradicted.add(edge.target)
        for edge in self.reverse_adjacency.get(node_id, []):
            if edge.relation_type == RelationType.CONTRADICTS:
                contradicted.add(edge.source)

        return {
            "upstream": sorted(upstream),
            "downstream": sorted(downstream),
            "affected_by_contradiction": sorted(contradicted),
        }

    def weighted_shortest_path(
        self,
        source: str,
        target: str,
    ) -> tuple[list[str], float]:
        """Dijkstra shortest path weighted by 1/confidence.

        Higher confidence edges are preferred (lower weight).
        Returns (path, total_weight). Empty path if no connection.
        """
        if source not in self.nodes or target not in self.nodes:
            return ([], float("inf"))

        if source == target:
            return ([source], 0.0)

        dist: dict[str, float] = {source: 0.0}
        prev: dict[str, str | None] = {source: None}
        heap: list[tuple[float, str]] = [(0.0, source)]
        visited: set[str] = set()

        while heap:
            d, current = heapq.heappop(heap)
            if current in visited:
                continue
            visited.add(current)

            if current == target:
                break

            for edge in self.adjacency.get(current, []):
                weight = 1.0 / max(edge.confidence, 0.01)
                new_dist = d + weight
                if new_dist < dist.get(edge.target, float("inf")):
                    dist[edge.target] = new_dist
                    prev[edge.target] = current
                    heapq.heappush(heap, (new_dist, edge.target))

        if target not in prev:
            return ([], float("inf"))

        # Reconstruct path
        path: list[str] = []
        node: str | None = target
        while node is not None:
            path.append(node)
            node = prev[node]
        path.reverse()

        return (path, dist[target])

    # ── Tier 2: Diagnostic Operations ────────────────────────────────────

    def topological_sort(
        self,
        relation_type: RelationType = RelationType.DERIVED_FROM,
    ) -> tuple[list[str], list[list[str]]]:
        """Topological sort of nodes connected by specified relation type.

        Returns (ordered_nodes, cycles) where cycles is list of cycle paths.
        If no cycles, cycles is empty.
        """
        # Build subgraph for this relation type
        in_degree: dict[str, int] = {nid: 0 for nid in self.nodes}
        sub_adj: dict[str, list[str]] = {nid: [] for nid in self.nodes}

        for edge in self.edges:
            if edge.relation_type == relation_type:
                sub_adj[edge.source].append(edge.target)
                in_degree[edge.target] = in_degree.get(edge.target, 0) + 1

        # Kahn's algorithm
        queue: deque[str] = deque()
        for nid, deg in in_degree.items():
            if deg == 0:
                queue.append(nid)

        order: list[str] = []
        while queue:
            node = queue.popleft()
            order.append(node)
            for neighbor in sub_adj.get(node, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # Remaining nodes are in cycles
        cycles: list[list[str]] = []
        remaining = set(self.nodes.keys()) - set(order)
        if remaining:
            cycles = self._find_cycles_in_subset(remaining, relation_type)

        return (order, cycles)

    def detect_cycles(
        self,
        relation_type: str | None = None,
    ) -> list[list[str]]:
        """Find all simple cycles in the graph.

        Lazy computation: caches result in self.cycles on first call.
        If relation_type is specified, only consider edges of that type.
        """
        if self.cycles is not None and relation_type is None:
            return self.cycles

        edges_to_check = self.edges
        if relation_type:
            edges_to_check = [e for e in self.edges if e.relation_type == relation_type]

        # Build adjacency for cycle detection
        adj: dict[str, list[str]] = {}
        for e in edges_to_check:
            adj.setdefault(e.source, []).append(e.target)

        cycles: list[list[str]] = []
        visited_global: set[str] = set()

        for start_node in adj:
            if start_node in visited_global:
                continue
            self._dfs_cycles(start_node, adj, set(), [], cycles, visited_global)

        if relation_type is None:
            self.cycles = cycles

        return cycles

    def cluster(self) -> list[list[str]]:
        """Identify connected components in the graph.

        Returns list of clusters, each cluster is a list of node IDs.
        """
        return self.clusters

    # ── Tier 3: Advanced Operations ──────────────────────────────────────

    def all_paths(
        self,
        source: str,
        target: str,
        max_depth: int = 10,
    ) -> list[list[str]]:
        """Find all simple paths from source to target.

        Returns list of paths, each path is a list of node IDs.
        Capped at MAX_PATHS to prevent exponential blowup.
        """
        if source not in self.nodes or target not in self.nodes:
            return []

        if source == target:
            return [[source]]

        paths: list[list[str]] = []
        path = [source]
        visited = {source}
        
        initial_children = [edge.target for edge in self.adjacency.get(source, [])]
        stack = [(source, iter(initial_children))]
        
        while stack:
            if len(paths) >= MAX_PATHS:
                break
            
            curr, children_iter = stack[-1]
            
            try:
                nxt = next(children_iter)
                if nxt not in visited:
                    if nxt == target:
                        paths.append(path + [nxt])
                    elif len(path) < max_depth:
                        visited.add(nxt)
                        path.append(nxt)
                        next_children = [edge.target for edge in self.adjacency.get(nxt, [])]
                        stack.append((nxt, iter(next_children)))
            except StopIteration:
                stack.pop()
                visited.remove(curr)
                path.pop()

        return paths

    def blast_radius(
        self,
        node_id: str,
        depth: int = 2,
    ) -> list[dict[str, Any]]:
        """Compute all nodes affected within N hops.

        Returns list of {"node_id", "distance", "confidence"} dicts,
        sorted by distance then confidence descending.
        """
        if node_id not in self.nodes:
            return []

        result: list[dict[str, Any]] = []
        visited: set[str] = {node_id}
        queue: deque[tuple[str, int, float]] = deque([(node_id, 0, 1.0)])

        while queue:
            current, dist, min_conf = queue.popleft()
            if dist > 0:
                result.append({
                    "node_id": current,
                    "distance": dist,
                    "confidence": min_conf,
                })
            if dist >= depth:
                continue

            for edge in self.adjacency.get(current, []):
                if edge.target not in visited:
                    visited.add(edge.target)
                    queue.append((edge.target, dist + 1, min(min_conf, edge.confidence)))

            for edge in self.reverse_adjacency.get(current, []):
                if edge.source not in visited:
                    visited.add(edge.source)
                    queue.append((edge.source, dist + 1, min(min_conf, edge.confidence)))

        result.sort(key=lambda x: (x["distance"], -x["confidence"]))
        return result

    # ── Internal Helpers ─────────────────────────────────────────────────

    def _bfs_directional(
        self,
        node_id: str,
        direction: str,
        max_depth: int,
        relation_types: list[str] | None,
    ) -> set[str]:
        """BFS in one direction, returning reachable node IDs."""
        visited: set[str] = set()
        queue: deque[tuple[str, int]] = deque([(node_id, 0)])
        adj = self.adjacency if direction == "forward" else self.reverse_adjacency

        while queue:
            current, depth = queue.popleft()
            if current in visited or depth >= max_depth:
                continue
            visited.add(current)
            for edge in adj.get(current, []):
                if relation_types and edge.relation_type not in relation_types:
                    continue
                next_node = edge.target if direction == "forward" else edge.source
                if next_node not in visited:
                    queue.append((next_node, depth + 1))

        visited.discard(node_id)
        return visited

    def _build_subgraph(
        self,
        nodes: dict[str, GraphNode],
        edges: list[GraphEdge],
    ) -> GraphState:
        """Build a GraphState from a subset of nodes and edges."""
        adj: dict[str, list[GraphEdge]] = {}
        rev_adj: dict[str, list[GraphEdge]] = {}

        for e in edges:
            adj.setdefault(e.source, []).append(e)
            rev_adj.setdefault(e.target, []).append(e)

        # Clusters for subgraph
        sub_node_ids = set(nodes.keys())
        visited: set[str] = set()
        clusters: list[list[str]] = []
        for nid in sub_node_ids:
            if nid not in visited:
                component = self._bfs_component(nid, adj, sub_node_ids, visited)
                clusters.append(sorted(component))

        # Density
        n = len(nodes)
        e = len(edges)
        density = e / (n * (n - 1)) if n > 1 else 0.0

        return GraphState(
            project_id=self.project_id,
            compiled_at=self.compiled_at,
            projection_version=self.projection_version,
            nodes=nodes,
            edges=edges,
            adjacency=adj,
            reverse_adjacency=rev_adj,
            clusters=clusters,
            node_count=n,
            edge_count=e,
            density=density,
        )

    def _bfs_component(
        self,
        start: str,
        adj: dict[str, list[GraphEdge]],
        allowed: set[str],
        visited: set[str],
    ) -> set[str]:
        """BFS to find connected component containing start."""
        component: set[str] = set()
        queue: deque[str] = deque([start])
        while queue:
            node = queue.popleft()
            if node in visited or node not in allowed:
                continue
            visited.add(node)
            component.add(node)
            for edge in adj.get(node, []):
                next_node = edge.target
                if next_node not in visited and next_node in allowed:
                    queue.append(next_node)
            # Also check reverse edges for undirected connectivity
            for edge in self.reverse_adjacency.get(node, []):
                next_node = edge.source
                if next_node not in visited and next_node in allowed:
                    queue.append(next_node)
        return component

    def _dfs_cycles(
        self,
        start_node: str,
        adj: dict[str, list[str]],
        path: set[str],
        path_list: list[str],
        cycles: list[list[str]],
        visited_global: set[str],
    ) -> None:
        """DFS-based cycle detection (iterative)."""
        if start_node in path:
            cycle_start = path_list.index(start_node)
            cycle = path_list[cycle_start:] + [start_node]
            cycles.append(cycle)
            return
        if start_node in visited_global:
            return

        path.add(start_node)
        path_list.append(start_node)
        visited_global.add(start_node)

        stack = [(start_node, iter(adj.get(start_node, [])))]

        while stack:
            curr, neighbors_iter = stack[-1]
            try:
                nxt = next(neighbors_iter)
                if nxt in path:
                    cycle_start = path_list.index(nxt)
                    cycle = path_list[cycle_start:] + [nxt]
                    cycles.append(cycle)
                elif nxt not in visited_global:
                    path.add(nxt)
                    path_list.append(nxt)
                    visited_global.add(nxt)
                    stack.append((nxt, iter(adj.get(nxt, []))))
            except StopIteration:
                stack.pop()
                path.discard(curr)
                path_list.pop()

    def _find_cycles_in_subset(
        self,
        node_ids: set[str],
        relation_type: str,
    ) -> list[list[str]]:
        """Find cycles within a subset of nodes."""
        adj: dict[str, list[str]] = {}
        for e in self.edges:
            if e.relation_type == relation_type and e.source in node_ids and e.target in node_ids:
                adj.setdefault(e.source, []).append(e.target)

        cycles: list[list[str]] = []
        visited_global: set[str] = set()
        for start in adj:
            if start not in visited_global:
                self._dfs_cycles(start, adj, set(), [], cycles, visited_global)
        return cycles


# ── GraphProjection ──────────────────────────────────────────────────────────

class GraphProjection(BaseProjection):
    """Builds GraphState from KnowledgeState.

    Relations are derived from KnowledgeState adjacency structures:
      - support_graph → SUPPORTS edges
      - derivation_chains → DERIVED_FROM edges
      - conflict_queue → CONTRADICTS edges
    """
    projection_name: ClassVar[str] = "Knowledge Graph"
    version: ClassVar[SemVer] = SemVer(1, 0, 0)
    projection_kind: ClassVar[ProjectionKind] = ProjectionKind.DERIVED
    dependencies: ClassVar[list[type[BaseProjection]]] = [KnowledgeProjection]
    architectural_dependencies: ClassVar[list[str]] = []
    build_priority: ClassVar[int] = 30

    @staticmethod
    def project(knowledge_state: KnowledgeState, reference_time: Optional[datetime] = None) -> GraphState:
        """Project a navigable graph from KnowledgeState.

        Args:
            knowledge_state: Output from KnowledgeProjection.project().
            reference_time: Optional reference time to run projection deterministically.

        Returns:
            GraphState with nodes, edges, adjacency, and clusters.
        """
        from rationalevault.organization.utils import resolve_compiled_at
        now = resolve_compiled_at(reference_time)

        # 1. Build nodes from active knowledge
        nodes: dict[str, GraphNode] = {}
        for k in knowledge_state.active_knowledge:
            nodes[k.id] = GraphNode(
                id=k.id,
                title=k.title,
                knowledge_type=k.knowledge_type.value,
                domain=k.knowledge_domain.value,
                confidence=k.confidence.score,
                importance=k.importance,
                tags=list(k.tags),
            )

        # 2. Build edges from adjacency structures
        edges: list[GraphEdge] = []
        seen_edges: set[tuple[str, str, str]] = set()

        # SUPPORTS edges from support_graph
        for source_id, target_ids in knowledge_state.support_graph.items():
            for target_id in target_ids:
                key = (source_id, target_id, RelationType.SUPPORTS)
                if key not in seen_edges and source_id in nodes and target_id in nodes:
                    edges.append(GraphEdge(
                        source=source_id,
                        target=target_id,
                        relation_type=RelationType.SUPPORTS,
                        confidence=0.8,
                    ))
                    seen_edges.add(key)

        # DERIVED_FROM edges from derivation_chains
        # Edge direction: dep_id → source_id (dependency → derived)
        # So walking reverse_adjacency from a derived node finds its dependencies
        for source_id, dep_ids in knowledge_state.derivation_chains.items():
            for dep_id in dep_ids:
                key = (dep_id, source_id, RelationType.DERIVED_FROM)
                if key not in seen_edges and source_id in nodes and dep_id in nodes:
                    edges.append(GraphEdge(
                        source=dep_id,
                        target=source_id,
                        relation_type=RelationType.DERIVED_FROM,
                        confidence=0.9,
                    ))
                    seen_edges.add(key)

        # CONTRADICTS edges from conflict_queue
        for conflict in knowledge_state.conflict_queue:
            key = (conflict.knowledge_a_id, conflict.knowledge_b_id, RelationType.CONTRADICTS)
            if key not in seen_edges and conflict.knowledge_a_id in nodes and conflict.knowledge_b_id in nodes:
                edges.append(GraphEdge(
                    source=conflict.knowledge_a_id,
                    target=conflict.knowledge_b_id,
                    relation_type=RelationType.CONTRADICTS,
                    confidence=conflict.confidence,
                ))
                seen_edges.add(key)
                # Bidirectional for contradiction
                key_rev = (conflict.knowledge_b_id, conflict.knowledge_a_id, RelationType.CONTRADICTS)
                if key_rev not in seen_edges:
                    edges.append(GraphEdge(
                        source=conflict.knowledge_b_id,
                        target=conflict.knowledge_a_id,
                        relation_type=RelationType.CONTRADICTS,
                        confidence=conflict.confidence,
                    ))
                    seen_edges.add(key_rev)

        # 3. Build edge-aware adjacency, conflicted nodes, and relation index
        adjacency: dict[str, list[GraphEdge]] = {}
        reverse_adjacency: dict[str, list[GraphEdge]] = {}
        conflicted_nodes: set[str] = set()
        edges_by_relation: dict[RelationType, list[GraphEdge]] = {rt: [] for rt in RelationType}
        for e in edges:
            adjacency.setdefault(e.source, []).append(e)
            reverse_adjacency.setdefault(e.target, []).append(e)
            edges_by_relation[e.relation_type].append(e)
            if e.relation_type == RelationType.CONTRADICTS:
                conflicted_nodes.add(e.source)
                conflicted_nodes.add(e.target)
        # Freeze to tuples for immutability
        edges_by_relation_frozen: dict[RelationType, tuple[GraphEdge, ...]] = {
            rt: tuple(edge_list) for rt, edge_list in edges_by_relation.items()
        }

        # 4. Compute connected components (clusters)
        visited: set[str] = set()
        clusters: list[list[str]] = []
        for nid in nodes:
            if nid not in visited:
                component = _bfs_undirected(nid, adjacency, reverse_adjacency, set(nodes.keys()), visited)
                clusters.append(sorted(component))

        # 5. Compute density
        n = len(nodes)
        e = len(edges)
        density = e / (n * (n - 1)) if n > 1 else 0.0

        # 6. Build provenance
        provenance: dict[str, list[int]] = {}
        for k in knowledge_state.active_knowledge:
            if k.provenance and k.provenance.source_event_ids:
                provenance[k.id] = [
                    int(eid) for eid in k.provenance.source_event_ids
                    if eid.isdigit()
                ]

        return GraphState(
            project_id=knowledge_state.project_id,
            compiled_at=now,
            nodes=nodes,
            edges=edges,
            adjacency=adjacency,
            reverse_adjacency=reverse_adjacency,
            clusters=clusters,
            node_count=n,
            edge_count=e,
            density=density,
            conflicted_nodes=conflicted_nodes,
            edges_by_relation=edges_by_relation_frozen,
            provenance=provenance,
        )


def _bfs_undirected(
    start: str,
    adj: dict[str, list[GraphEdge]],
    rev_adj: dict[str, list[GraphEdge]],
    allowed: set[str],
    visited: set[str],
) -> set[str]:
    """BFS for undirected connectivity (follows both forward and reverse edges)."""
    component: set[str] = set()
    queue: deque[str] = deque([start])
    while queue:
        node = queue.popleft()
        if node in visited or node not in allowed:
            continue
        visited.add(node)
        component.add(node)
        for edge in adj.get(node, []):
            if edge.target not in visited and edge.target in allowed:
                queue.append(edge.target)
        for edge in rev_adj.get(node, []):
            if edge.source not in visited and edge.source in allowed:
                queue.append(edge.source)
    return component
