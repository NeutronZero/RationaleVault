"""RationaleVault Organization Graph Projection — Project-centric organizational graph.

OrganizationState → OrganizationGraphState

Projects are nodes. Relationships between projects are edges.
All edges traceable to existing OrganizationState data.
DERIVES_FROM is reserved — not built until explicit project-lineage metadata exists.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from itertools import combinations
from rationalevault.organization.models import OrganizationState
from rationalevault.organization.relation_types import OrganizationRelationType
from rationalevault.organization.utils import resolve_compiled_at
from rationalevault.projections.base import BaseProjection, ProjectionKind, SemVer
from rationalevault.organization.projection import OrganizationProjection
from typing import ClassVar


@dataclass(frozen=True)
class OrganizationNode:
    """A project node in the organization graph."""
    project_id: str
    name: str
    knowledge_count: int = 0
    transferable_count: int = 0
    shared_count: int = 0
    conflict_count: int = 0
    is_cluster_center: bool = False
    health_score: float = 0.0


@dataclass(frozen=True)
class OrganizationEdge:
    """A relationship between two projects in the organization graph.

    weight = cardinality / magnitude
    confidence = certainty / similarity strength
    """
    source: str
    target: str
    relation_type: OrganizationRelationType
    weight: float = 1.0
    confidence: float = 1.0


@dataclass
class OrganizationGraphHealth:
    """Health metrics for the organization graph projection."""
    connectivity: float = 0.0
    density: float = 0.0
    conflict_density: float = 0.0
    cluster_cohesion: float = 0.0
    producer_consumer_balance: float = 0.0
    overall: float = 0.0


@dataclass
class OrganizationGraphState:
    """Project-centric organizational graph projection.

    First-class projection state with health, following the pattern of
    KnowledgeState, GraphState, CrossProjectState, and OrganizationState.
    """
    compiled_at: str
    projection_version: str = "1.0"
    nodes: dict[str, OrganizationNode] = field(default_factory=dict)
    edges: list[OrganizationEdge] = field(default_factory=list)
    adjacency: dict[str, list[OrganizationEdge]] = field(default_factory=dict)
    reverse_adjacency: dict[str, list[OrganizationEdge]] = field(default_factory=dict)
    clusters: list[list[str]] = field(default_factory=list)
    density: float = 0.0
    conflicted_nodes: set[str] = field(default_factory=set)
    edges_by_relation: dict[OrganizationRelationType, tuple[OrganizationEdge, ...]] = field(default_factory=dict)
    knowledge_flow_balance: dict[str, int] = field(default_factory=dict)
    knowledge_producers: list[tuple[str, float]] = field(default_factory=list)
    knowledge_consumers: list[tuple[str, float]] = field(default_factory=list)
    contradiction_hotspots: list[tuple[str, float]] = field(default_factory=list)
    health: OrganizationGraphHealth = field(default_factory=OrganizationGraphHealth)

    def to_dict(self) -> dict[str, Any]:
        return {
            "compiled_at": self.compiled_at,
            "projection_version": self.projection_version,
            "nodes": {pid: {
                "project_id": n.project_id,
                "name": n.name,
                "knowledge_count": n.knowledge_count,
                "transferable_count": n.transferable_count,
                "shared_count": n.shared_count,
                "conflict_count": n.conflict_count,
                "is_cluster_center": n.is_cluster_center,
                "health_score": n.health_score,
            } for pid, n in self.nodes.items()},
            "edges": [{
                "source": e.source,
                "target": e.target,
                "relation_type": e.relation_type.value,
                "weight": e.weight,
                "confidence": e.confidence,
            } for e in self.edges],
            "clusters": self.clusters,
            "density": round(self.density, 4),
            "conflicted_nodes": sorted(self.conflicted_nodes),
            "edges_by_relation": {
                rt.value: len(edges) for rt, edges in self.edges_by_relation.items()
            },
            "knowledge_flow_balance": self.knowledge_flow_balance,
            "knowledge_producers": [list(x) for x in self.knowledge_producers],
            "knowledge_consumers": [list(x) for x in self.knowledge_consumers],
            "contradiction_hotspots": [list(x) for x in self.contradiction_hotspots],
            "health": {
                "connectivity": round(self.health.connectivity, 4),
                "density": round(self.health.density, 4),
                "conflict_density": round(self.health.conflict_density, 4),
                "cluster_cohesion": round(self.health.cluster_cohesion, 4),
                "producer_consumer_balance": round(self.health.producer_consumer_balance, 4),
                "overall": round(self.health.overall, 4),
            },
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> OrganizationGraphState:
        # Deserialize nodes
        nodes = {}
        for pid, n in d.get("nodes", {}).items():
            nodes[pid] = OrganizationNode(
                project_id=n["project_id"],
                name=n["name"],
                knowledge_count=n["knowledge_count"],
                transferable_count=n["transferable_count"],
                shared_count=n["shared_count"],
                conflict_count=n["conflict_count"],
                is_cluster_center=n["is_cluster_center"],
                health_score=n["health_score"],
            )

        # Deserialize edges
        edges = []
        for e in d.get("edges", []):
            edges.append(OrganizationEdge(
                source=e["source"],
                target=e["target"],
                relation_type=OrganizationRelationType(e["relation_type"]),
                weight=e["weight"],
                confidence=e["confidence"],
            ))

        # Recompute adjacency and reverse adjacency dynamically
        adjacency: dict[str, list[OrganizationEdge]] = {pid: [] for pid in nodes}
        reverse_adjacency: dict[str, list[OrganizationEdge]] = {pid: [] for pid in nodes}
        for edge in edges:
            if edge.source in adjacency:
                adjacency[edge.source].append(edge)
            if edge.target in reverse_adjacency:
                reverse_adjacency[edge.target].append(edge)

        # Deserialize health
        h = d.get("health", {})
        health = OrganizationGraphHealth(
            connectivity=h.get("connectivity", 0.0),
            density=h.get("density", 0.0),
            conflict_density=h.get("conflict_density", 0.0),
            cluster_cohesion=h.get("cluster_cohesion", 0.0),
            producer_consumer_balance=h.get("producer_consumer_balance", 0.0),
            overall=h.get("overall", 0.0),
        )

        # Reconstruct edges_by_relation grouping
        edges_by_relation = {}
        for edge in edges:
            edges_by_relation.setdefault(edge.relation_type, []).append(edge)
        edges_by_relation = {rt: tuple(el) for rt, el in edges_by_relation.items()}

        knowledge_producers = [
            (item[0], float(item[1])) for item in d.get("knowledge_producers", [])
        ]
        knowledge_consumers = [
            (item[0], float(item[1])) for item in d.get("knowledge_consumers", [])
        ]
        contradiction_hotspots = [
            (item[0], float(item[1])) for item in d.get("contradiction_hotspots", [])
        ]

        return cls(
            compiled_at=d["compiled_at"],
            projection_version=d.get("projection_version", "1.0"),
            nodes=nodes,
            edges=edges,
            adjacency=adjacency,
            reverse_adjacency=reverse_adjacency,
            clusters=d.get("clusters", []),
            density=d.get("density", 0.0),
            conflicted_nodes=set(d.get("conflicted_nodes", [])),
            edges_by_relation=edges_by_relation,
            knowledge_flow_balance=d.get("knowledge_flow_balance", {}),
            knowledge_producers=knowledge_producers,
            knowledge_consumers=knowledge_consumers,
            contradiction_hotspots=contradiction_hotspots,
            health=health,
        )


class OrganizationGraphProjection(BaseProjection):
    """Projects OrganizationState into a project-centric graph.

    Nodes = projects. Edges = relationships between projects.
    All edges traceable to existing OrganizationState data.
    """
    projection_name: ClassVar[str] = "OrganizationGraph"
    version: ClassVar[SemVer] = SemVer(1, 0, 0)
    projection_kind: ClassVar[ProjectionKind] = ProjectionKind.DERIVED
    dependencies: ClassVar[list[type[BaseProjection]]] = [OrganizationProjection]
    architectural_dependencies: ClassVar[list[str]] = []
    build_priority: ClassVar[int] = 60

    @staticmethod
    def project(
        org_state: OrganizationState,
        reference_time: datetime | None = None,
    ) -> OrganizationGraphState:
        """Build the organization graph from OrganizationState."""
        nodes = OrganizationGraphProjection._build_nodes(org_state)
        edges = OrganizationGraphProjection._build_edges(org_state)
        adjacency, reverse_adjacency = OrganizationGraphProjection._build_adjacency(edges, nodes)
        clusters = org_state.project_clusters
        density = OrganizationGraphProjection._compute_density(nodes, edges)
        edges_by_relation = OrganizationGraphProjection._compute_edges_by_relation(edges)
        knowledge_flow_balance = OrganizationGraphProjection._compute_flow_balance(adjacency, reverse_adjacency)
        conflicted_nodes = OrganizationGraphProjection._compute_conflicted_nodes(org_state)
        producers, consumers, hotspots = OrganizationGraphProjection._compute_derived_metrics(
            adjacency, reverse_adjacency, edges_by_relation, knowledge_flow_balance,
        )
        health = OrganizationGraphProjection._compute_health(
            nodes, edges, adjacency, reverse_adjacency, clusters, conflicted_nodes,
            knowledge_flow_balance,
        )

        return OrganizationGraphState(
            compiled_at=resolve_compiled_at(reference_time),
            nodes=nodes,
            edges=edges,
            adjacency=adjacency,
            reverse_adjacency=reverse_adjacency,
            clusters=clusters,
            density=density,
            conflicted_nodes=conflicted_nodes,
            edges_by_relation=edges_by_relation,
            knowledge_flow_balance=knowledge_flow_balance,
            knowledge_producers=producers,
            knowledge_consumers=consumers,
            contradiction_hotspots=hotspots,
            health=health,
        )

    @staticmethod
    def _build_nodes(org_state: OrganizationState) -> dict[str, OrganizationNode]:
        """Build one node per project with metadata from lineages/shared/conflicts."""
        nodes: dict[str, OrganizationNode] = {}

        # Count knowledge per project from lineages
        knowledge_counts: dict[str, int] = {}
        transferable_counts: dict[str, int] = {}
        for kid, lineage in org_state.active_lineages.items():
            for pid in lineage.current_projects:
                knowledge_counts[pid] = knowledge_counts.get(pid, 0) + 1
            if lineage.origin_project:
                transferable_counts[lineage.origin_project] = transferable_counts.get(lineage.origin_project, 0) + 1

        # Count shared knowledge per project
        shared_counts: dict[str, int] = {}
        for sk in org_state.shared_knowledge:
            for pid in sk.present_in_projects:
                shared_counts[pid] = shared_counts.get(pid, 0) + 1

        # Count conflicts per project
        conflict_counts: dict[str, int] = {}
        for conflict in org_state.cross_project_conflicts:
            conflict_counts[conflict.project_a] = conflict_counts.get(conflict.project_a, 0) + 1
            conflict_counts[conflict.project_b] = conflict_counts.get(conflict.project_b, 0) + 1

        # Determine cluster centers (first project in each cluster)
        cluster_centers: set[str] = set()
        for cluster in org_state.project_clusters:
            if cluster:
                cluster_centers.add(cluster[0])

        # Build nodes
        for pid in org_state.project_ids:
            name = pid  # Default name is the ID
            nodes[pid] = OrganizationNode(
                project_id=pid,
                name=name,
                knowledge_count=knowledge_counts.get(pid, 0),
                transferable_count=transferable_counts.get(pid, 0),
                shared_count=shared_counts.get(pid, 0),
                conflict_count=conflict_counts.get(pid, 0),
                is_cluster_center=pid in cluster_centers,
                health_score=org_state.health.overall,
            )

        return nodes

    @staticmethod
    def _build_edges(org_state: OrganizationState) -> list[OrganizationEdge]:
        """Build edges from lineages, shared knowledge, conflicts, and clusters.

        DERIVES_FROM is reserved — not built until explicit project-lineage metadata exists.
        Bidirectional relationships (SHARED_BY, CONFLICTS_WITH, IN_CLUSTER) produce
        edges in both directions for symmetric traversal.
        """
        edges: list[OrganizationEdge] = []
        valid_ids = set(org_state.project_ids)

        # Aggregate weights before building frozen edges
        transfer_agg: dict[tuple[str, str], int] = {}
        for kid, lineage in org_state.active_lineages.items():
            for current_pid in lineage.current_projects:
                if current_pid != lineage.origin_project:
                    key = (lineage.origin_project, current_pid)
                    transfer_agg[key] = transfer_agg.get(key, 0) + 1

        shared_agg: dict[tuple[str, str], int] = {}
        for sk in org_state.shared_knowledge:
            projects = sorted(sk.present_in_projects)
            for src, tgt in combinations(projects, 2):
                key = (src, tgt)
                shared_agg[key] = shared_agg.get(key, 0) + 1

        conflict_agg: dict[tuple[str, str], dict[str, float]] = {}
        for conflict in org_state.cross_project_conflicts:
            pair = tuple(sorted([conflict.project_a, conflict.project_b]))
            if pair not in conflict_agg:
                conflict_agg[pair] = {"count": 0, "total_confidence": 0.0}
            conflict_agg[pair]["count"] += 1
            conflict_agg[pair]["total_confidence"] += conflict.confidence

        # Build TRANSFERRED_TO edges (directional — origin to current)
        for (src, tgt), count in transfer_agg.items():
            edges.append(OrganizationEdge(
                source=src, target=tgt,
                relation_type=OrganizationRelationType.TRANSFERRED_TO,
                weight=float(count), confidence=1.0,
            ))

        # Build SHARED_BY edges (bidirectional)
        for (src, tgt), count in shared_agg.items():
            edges.extend((
                OrganizationEdge(
                    source=src, target=tgt,
                    relation_type=OrganizationRelationType.SHARED_BY,
                    weight=float(count), confidence=1.0,
                ),
                OrganizationEdge(
                    source=tgt, target=src,
                    relation_type=OrganizationRelationType.SHARED_BY,
                    weight=float(count), confidence=1.0,
                ),
            ))

        # Build CONFLICTS_WITH edges (bidirectional)
        for (pa, pb), data in conflict_agg.items():
            conf = data["total_confidence"] / data["count"] if data["count"] > 0 else 1.0
            edges.extend((
                OrganizationEdge(
                    source=pa, target=pb,
                    relation_type=OrganizationRelationType.CONFLICTS_WITH,
                    weight=data["count"], confidence=conf,
                ),
                OrganizationEdge(
                    source=pb, target=pa,
                    relation_type=OrganizationRelationType.CONFLICTS_WITH,
                    weight=data["count"], confidence=conf,
                ),
            ))

        # Pre-compute project knowledge sets
        project_knowledge_sets: dict[str, set[str]] = {}
        for kid, lineage in org_state.active_lineages.items():
            if lineage.origin_project:
                project_knowledge_sets.setdefault(lineage.origin_project, set()).add(kid)
            for pid in lineage.current_projects:
                project_knowledge_sets.setdefault(pid, set()).add(kid)

        project_knowledge_sizes = {pid: len(s) for pid, s in project_knowledge_sets.items()}

        # Build IN_CLUSTER edges (bidirectional)
        for cluster in org_state.project_clusters:
            for p_a, p_b in combinations(cluster, 2):
                a_kids = project_knowledge_sets.get(p_a, set())
                b_kids = project_knowledge_sets.get(p_b, set())
                intersection = len(a_kids & b_kids)
                a_size = project_knowledge_sizes.get(p_a, 0)
                b_size = project_knowledge_sizes.get(p_b, 0)
                union = a_size + b_size - intersection
                jaccard = intersection / union if union > 0 else 0.0

                edges.extend((
                    OrganizationEdge(
                        source=p_a, target=p_b,
                        relation_type=OrganizationRelationType.IN_CLUSTER,
                        weight=float(intersection), confidence=jaccard,
                    ),
                    OrganizationEdge(
                        source=p_b, target=p_a,
                        relation_type=OrganizationRelationType.IN_CLUSTER,
                        weight=float(intersection), confidence=jaccard,
                    ),
                ))

        # Filter orphaned edges (HIGH-4: source/target not in project_ids)
        edges = [e for e in edges if e.source in valid_ids and e.target in valid_ids]

        return edges

    @staticmethod
    def _build_adjacency(
        edges: list[OrganizationEdge],
        nodes: dict[str, OrganizationNode],
    ) -> tuple[dict[str, list[OrganizationEdge]], dict[str, list[OrganizationEdge]]]:
        """Build adjacency and reverse adjacency dicts."""
        adjacency: dict[str, list[OrganizationEdge]] = {pid: [] for pid in nodes}
        reverse_adjacency: dict[str, list[OrganizationEdge]] = {pid: [] for pid in nodes}

        for edge in edges:
            if edge.source in adjacency:
                adjacency[edge.source].append(edge)
            if edge.target in reverse_adjacency:
                reverse_adjacency[edge.target].append(edge)

        return adjacency, reverse_adjacency

    @staticmethod
    def _compute_density(
        nodes: dict[str, OrganizationNode],
        edges: list[OrganizationEdge],
    ) -> float:
        """Directed density: |edges| / (n * (n - 1))."""
        n = len(nodes)
        if n <= 1:
            return 0.0
        return len(edges) / (n * (n - 1))

    @staticmethod
    def _compute_edges_by_relation(
        edges: list[OrganizationEdge],
    ) -> dict[OrganizationRelationType, tuple[OrganizationEdge, ...]]:
        """Index edges by relation type."""
        by_type: dict[OrganizationRelationType, list[OrganizationEdge]] = {}
        for edge in edges:
            by_type.setdefault(edge.relation_type, []).append(edge)
        return {rt: tuple(edge_list) for rt, edge_list in by_type.items()}

    @staticmethod
    def _compute_flow_balance(
        adjacency: dict[str, list[OrganizationEdge]],
        reverse_adjacency: dict[str, list[OrganizationEdge]],
    ) -> dict[str, int]:
        """Compute knowledge flow balance: outbound_transfer_weight - inbound_transfer_weight."""
        balance: dict[str, int] = {}
        for pid in adjacency:
            outbound = sum(
                int(e.weight) for e in adjacency[pid]
                if e.relation_type == OrganizationRelationType.TRANSFERRED_TO
            )
            inbound = sum(
                int(e.weight) for e in reverse_adjacency.get(pid, [])
                if e.relation_type == OrganizationRelationType.TRANSFERRED_TO
            )
            balance[pid] = outbound - inbound
        return balance

    @staticmethod
    def _compute_conflicted_nodes(org_state: OrganizationState) -> set[str]:
        """Projects involved in cross-project conflicts."""
        conflicted: set[str] = set()
        for conflict in org_state.cross_project_conflicts:
            conflicted.add(conflict.project_a)
            conflicted.add(conflict.project_b)
        return conflicted

    @staticmethod
    def _compute_derived_metrics(
        adjacency: dict[str, list[OrganizationEdge]],
        reverse_adjacency: dict[str, list[OrganizationEdge]],
        edges_by_relation: dict[OrganizationRelationType, tuple[OrganizationEdge, ...]],
        flow_balance: dict[str, int],
    ) -> tuple[
        list[tuple[str, float]],
        list[tuple[str, float]],
        list[tuple[str, float]],
    ]:
        """Compute producers, consumers, and hotspots as ranked lists."""
        # Producers: positive flow balance, sorted descending
        producers = sorted(
            [(pid, float(balance)) for pid, balance in flow_balance.items() if balance > 0],
            key=lambda x: x[1],
            reverse=True,
        )

        # Consumers: negative flow balance, sorted ascending (most negative first)
        consumers = sorted(
            [(pid, float(abs(balance))) for pid, balance in flow_balance.items() if balance < 0],
            key=lambda x: x[1],
            reverse=True,
        )

        # Contradiction hotspots: projects with most conflict edge weight
        conflict_edges = edges_by_relation.get(OrganizationRelationType.CONFLICTS_WITH, ())
        hotspot_scores: dict[str, float] = {}
        for edge in conflict_edges:
            hotspot_scores[edge.source] = hotspot_scores.get(edge.source, 0.0) + edge.weight
            hotspot_scores[edge.target] = hotspot_scores.get(edge.target, 0.0) + edge.weight
        hotspots = sorted(
            [(pid, score) for pid, score in hotspot_scores.items()],
            key=lambda x: x[1],
            reverse=True,
        )

        return producers, consumers, hotspots

    @staticmethod
    def _compute_health(
        nodes: dict[str, OrganizationNode],
        edges: list[OrganizationEdge],
        adjacency: dict[str, list[OrganizationEdge]],
        reverse_adjacency: dict[str, list[OrganizationEdge]],
        clusters: list[list[str]],
        conflicted_nodes: set[str],
        flow_balance: dict[str, int],
    ) -> OrganizationGraphHealth:
        """Compute health metrics for the organization graph."""
        n = len(nodes)

        # Connectivity: BFS from first node; % reachable
        if n == 0:
            connectivity = 1.0
        else:
            start = next(iter(nodes))
            visited = OrganizationGraphProjection._bfs(start, adjacency)
            connectivity = len(visited) / n

        # Density
        density = OrganizationGraphProjection._compute_density(nodes, edges)

        # Conflict density: conflicted nodes / total nodes
        conflict_density = len(conflicted_nodes) / n if n > 0 else 0.0

        # Cluster cohesion: intra-cluster edges / total edges
        cluster_cohesion = OrganizationGraphProjection._compute_cluster_cohesion_ratio(edges, clusters)

        # Producer-consumer balance
        total_positive = sum(v for v in flow_balance.values() if v > 0)
        total_negative = sum(abs(v) for v in flow_balance.values() if v < 0)
        total_flow = total_positive + total_negative
        if total_flow > 0:
            producer_consumer_balance = 1.0 - (abs(total_positive - total_negative) / total_flow)
        else:
            producer_consumer_balance = 1.0

        # Overall: geometric mean of metrics (excluding conflict_density)
        metrics = [connectivity, cluster_cohesion, producer_consumer_balance]
        if metrics:
            overall = (metrics[0] * metrics[1] * metrics[2]) ** (1.0 / len(metrics))
        else:
            overall = 0.0

        return OrganizationGraphHealth(
            connectivity=connectivity,
            density=density,
            conflict_density=conflict_density,
            cluster_cohesion=cluster_cohesion,
            producer_consumer_balance=producer_consumer_balance,
            overall=overall,
        )

    @staticmethod
    def _compute_cluster_cohesion_ratio(
        edges: list[OrganizationEdge],
        clusters: list[list[str]],
    ) -> float:
        """Helper to compute intra-cluster edges / total edges ratio."""
        if not edges:
            return 0.0
        intra = 0
        cluster_node_sets = [set(c) for c in clusters]
        for edge in edges:
            for cluster_set in cluster_node_sets:
                if edge.source in cluster_set and edge.target in cluster_set:
                    intra += 1
                    break
        return intra / len(edges)

    @staticmethod
    def _bfs(start: str, adjacency: dict[str, list[OrganizationEdge]]) -> set[str]:
        """BFS traversal returning all reachable nodes."""
        visited: set[str] = {start}
        queue = deque([start])
        while queue:
            node = queue.popleft()
            for edge in adjacency.get(node, []):
                if edge.target not in visited:
                    visited.add(edge.target)
                    queue.append(edge.target)
        return visited

    # ── Operations ────────────────────────────────────────────────────────

    @staticmethod
    def project_centrality(
        state: OrganizationGraphState,
        project_id: str,
    ) -> float:
        """Degree centrality: (in + out) / (n - 1)."""
        n = len(state.nodes)
        if n <= 1:
            return 0.0
        out_degree = len(state.adjacency.get(project_id, []))
        in_degree = len(state.reverse_adjacency.get(project_id, []))
        return (in_degree + out_degree) / (n - 1)

    @staticmethod
    def blast_radius(
        state: OrganizationGraphState,
        project_id: str,
    ) -> set[str]:
        """BFS reach via TRANSFERRED_TO edges only."""
        visited: set[str] = {project_id}
        queue = deque([project_id])
        while queue:
            node = queue.popleft()
            for edge in state.adjacency.get(node, []):
                if (edge.relation_type == OrganizationRelationType.TRANSFERRED_TO
                        and edge.target not in visited):
                    visited.add(edge.target)
                    queue.append(edge.target)
        return visited

    @staticmethod
    def shortest_transfer_path(
        state: OrganizationGraphState,
        source: str,
        target: str,
    ) -> list[str]:
        """BFS shortest path using TRANSFERRED_TO edges only."""
        if source == target:
            return [source]
        visited: set[str] = {source}
        queue: deque[str] = deque([source])
        parent: dict[str, str] = {}
        while queue:
            node = queue.popleft()
            if node == target:
                break
            for edge in state.adjacency.get(node, []):
                if (edge.relation_type == OrganizationRelationType.TRANSFERRED_TO
                        and edge.target not in visited):
                    visited.add(edge.target)
                    parent[edge.target] = node
                    queue.append(edge.target)
        if target in visited:
            path = []
            curr = target
            while curr != source:
                path.append(curr)
                curr = parent[curr]
            path.append(source)
            path.reverse()
            return path
        return []

    @staticmethod
    def filtered_traversal(
        state: OrganizationGraphState,
        start: str,
        relation_types: set[OrganizationRelationType] | None = None,
        confidence_min: float = 0.0,
    ) -> list[str]:
        """BFS traversal with relation-type and confidence filters."""
        visited: list[str] = []
        visited_set: set[str] = {start}
        queue = deque([start])
        while queue:
            node = queue.popleft()
            visited.append(node)
            for edge in state.adjacency.get(node, []):
                if (edge.target not in visited_set
                        and (relation_types is None or edge.relation_type in relation_types)
                        and edge.confidence >= confidence_min):
                    visited_set.add(edge.target)
                    queue.append(edge.target)
        return visited

    @staticmethod
    def cluster_cohesion(state: OrganizationGraphState) -> float:
        """Intra-cluster edges / total edges."""
        return OrganizationGraphProjection._compute_cluster_cohesion_ratio(state.edges, state.clusters)

    @staticmethod
    def contradiction_hotspots(
        state: OrganizationGraphState,
        top_n: int = 5,
    ) -> list[tuple[str, float]]:
        """Top N projects by conflict edge weight."""
        return state.contradiction_hotspots[:top_n]

    @staticmethod
    def knowledge_producers(
        state: OrganizationGraphState,
        top_n: int = 5,
    ) -> list[tuple[str, float]]:
        """Top N projects by positive flow balance."""
        return state.knowledge_producers[:top_n]

    @staticmethod
    def knowledge_consumers(
        state: OrganizationGraphState,
        top_n: int = 5,
    ) -> list[tuple[str, float]]:
        """Top N projects by negative flow balance (absolute value)."""
        return state.knowledge_consumers[:top_n]
