"""RationaleVault Graph Operations Benchmark — Verifies GraphState correctness.

Tests all graph operations:
  - filtered_traversal (edge type, confidence, direction)
  - dependency_chain (linear, cycle detection)
  - topological_sort (DAG, cycles)
  - detect_cycles (found, none)
  - impact_analysis (upstream, downstream, contradiction)
  - blast_radius (depth, sorting)
  - cluster (single, multiple components)
  - all_paths (linear, multiple, max depth)
  - weighted_shortest_path (preference, no connection)
  - determinism (same graph → same results)
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from rationalevault.knowledge.models import (
    KnowledgeConfidence,
    KnowledgeDomain,
    KnowledgeLifecycle,
    KnowledgeObject,
    KnowledgeType,
    ProvenanceChain,
)
from rationalevault.projections.graph import (
    GraphEdge,
    GraphNode,
    GraphProjection,
    GraphState,
    MAX_PATHS,
)
from rationalevault.knowledge.relation_types import RelationType
from rationalevault.projections.knowledge import (
    ConflictRecord,
    KnowledgeHealth,
    KnowledgeState,
    _make_conflict_id,
)


def _conf(score: float = 0.8) -> KnowledgeConfidence:
    return KnowledgeConfidence(
        memory_count=3, source_event_count=3,
        contradiction_count=0, average_memory_confidence=score,
        score=score,
    )


def _prov(kid: str) -> ProvenanceChain:
    return ProvenanceChain(
        knowledge_id=kid, source_memory_ids=["m1"],
        source_event_ids=["100", "101"], synthesis_event_id="syn-1",
        confidence=_conf(), evidence_count=1,
    )


def _k(kid: str, title: str, ktype: KnowledgeType = KnowledgeType.ARCHITECTURE_PRINCIPLE) -> KnowledgeObject:
    return KnowledgeObject(
        id=kid, version=1, title=title, content=f"content for {title}",
        knowledge_type=ktype, knowledge_domain=KnowledgeDomain.ARCHITECTURE,
        confidence=_conf(), importance="high", provenance=_prov(kid),
        supporting_memory_ids=[f"m-{kid}"], lifecycle_status=KnowledgeLifecycle.ACTIVE.value,
        project_id="test",
    )


def _make_knowledge_state(
    nodes: list[tuple[str, str]],
    supports: list[tuple[str, str]] | None = None,
    derived: list[tuple[str, str]] | None = None,
    contradictions: list[tuple[str, str]] | None = None,
) -> KnowledgeState:
    """Build a KnowledgeState from minimal spec."""
    knowledge = [_k(kid, title) for kid, title in nodes]

    support_graph: dict[str, list[str]] = {}
    for src, tgt in (supports or []):
        support_graph.setdefault(src, []).append(tgt)

    derivation_chains: dict[str, list[str]] = {}
    for src, dep in (derived or []):
        derivation_chains.setdefault(src, []).append(dep)

    conflict_queue = []
    for a_id, b_id in (contradictions or []):
        a_obj = next((k for k in knowledge if k.id == a_id), None)
        b_obj = next((k for k in knowledge if k.id == b_id), None)
        if a_obj and b_obj:
            conflict_queue.append(ConflictRecord(
                conflict_id=_make_conflict_id(a_id, b_id),
                knowledge_a_id=a_id, knowledge_b_id=b_id,
                knowledge_a_title=a_obj.title, knowledge_b_title=b_obj.title,
                confidence=0.9, raised_at=datetime.now(timezone.utc).isoformat(),
            ))

    return KnowledgeState(
        project_id="test-proj",
        compiled_at=datetime.now(timezone.utc).isoformat(),
        active_knowledge=knowledge,
        support_graph=support_graph,
        derivation_chains=derivation_chains,
        conflict_queue=conflict_queue,
        health=KnowledgeHealth(
            confidence=0.8, contradiction_rate=0.0, invariant_ratio=0.0,
            stale_ratio=0.0, active_count=len(knowledge), total_count=len(knowledge),
            overall=0.7,
        ),
    )


# ── GraphProjection Build Tests ─────────────────────────────────────────────

class TestGraphProjectionBuild:
    def test_empty_knowledge(self):
        ks = KnowledgeState(
            project_id="p1", compiled_at="now",
            active_knowledge=[], support_graph={}, derivation_chains={},
        )
        gs = GraphProjection.project(ks)
        assert gs.node_count == 0
        assert gs.edge_count == 0

    def test_nodes_from_knowledge(self):
        ks = _make_knowledge_state([("a", "A"), ("b", "B")])
        gs = GraphProjection.project(ks)
        assert gs.node_count == 2
        assert "a" in gs.nodes
        assert "b" in gs.nodes

    def test_edges_from_support_graph(self):
        ks = _make_knowledge_state(
            [("a", "A"), ("b", "B")],
            supports=[("a", "b")],
        )
        gs = GraphProjection.project(ks)
        assert gs.edge_count == 1
        assert gs.edges[0].relation_type == RelationType.SUPPORTS

    def test_edges_from_derivation_chains(self):
        ks = _make_knowledge_state(
            [("a", "A"), ("b", "B")],
            derived=[("a", "b")],
        )
        gs = GraphProjection.project(ks)
        assert gs.edge_count == 1
        assert gs.edges[0].relation_type == RelationType.DERIVED_FROM

    def test_edges_from_contradictions(self):
        ks = _make_knowledge_state(
            [("a", "A"), ("b", "B")],
            contradictions=[("a", "b")],
        )
        gs = GraphProjection.project(ks)
        # Contradictions are bidirectional
        assert gs.edge_count == 2
        assert all(e.relation_type == RelationType.CONTRADICTS for e in gs.edges)

    def test_clusters_computed(self):
        ks = _make_knowledge_state(
            [("a", "A"), ("b", "B"), ("c", "C")],
            supports=[("a", "b")],
        )
        gs = GraphProjection.project(ks)
        assert len(gs.clusters) == 2  # {a,b} and {c}

    def test_density_computed(self):
        ks = _make_knowledge_state(
            [("a", "A"), ("b", "B")],
            supports=[("a", "b")],
        )
        gs = GraphProjection.project(ks)
        assert gs.density > 0

    def test_adjacency_edge_aware(self):
        ks = _make_knowledge_state(
            [("a", "A"), ("b", "B")],
            supports=[("a", "b")],
        )
        gs = GraphProjection.project(ks)
        edges = gs.adjacency.get("a", [])
        assert len(edges) == 1
        assert isinstance(edges[0], GraphEdge)
        assert edges[0].relation_type == RelationType.SUPPORTS

    def test_determinism(self):
        ks = _make_knowledge_state(
            [("a", "A"), ("b", "B"), ("c", "C")],
            supports=[("a", "b"), ("b", "c")],
        )
        gs1 = GraphProjection.project(ks)
        gs2 = GraphProjection.project(ks)
        assert gs1.node_count == gs2.node_count
        assert gs1.edge_count == gs2.edge_count
        assert set(gs1.nodes.keys()) == set(gs2.nodes.keys())

    def test_to_dict(self):
        ks = _make_knowledge_state([("a", "A")])
        gs = GraphProjection.project(ks)
        d = gs.to_dict()
        assert d["project_id"] == "test-proj"
        assert d["node_count"] == 1
        assert "nodes" in d
        assert "edges" in d


# ── Filtered Traversal Tests ────────────────────────────────────────────────

class TestFilteredTraversal:
    @pytest.fixture
    def chain_graph(self):
        """A→B→C→D with SUPPORTS edges."""
        ks = _make_knowledge_state(
            [("a", "A"), ("b", "B"), ("c", "C"), ("d", "D")],
            supports=[("a", "b"), ("b", "c"), ("c", "d")],
        )
        return GraphProjection.project(ks)

    def test_full_traversal(self, chain_graph):
        sub = chain_graph.filtered_traversal("a", max_depth=10)
        assert len(sub.nodes) == 4

    def test_depth_limit(self, chain_graph):
        sub = chain_graph.filtered_traversal("a", max_depth=1)
        assert len(sub.nodes) == 2  # a, b only

    def test_by_edge_type(self, chain_graph):
        sub = chain_graph.filtered_traversal("a", edge_types=[RelationType.SUPPORTS])
        assert len(sub.nodes) == 4

    def test_by_confidence(self, chain_graph):
        sub = chain_graph.filtered_traversal("a", min_confidence=0.95)
        # All edges have confidence 0.8, so none pass
        assert len(sub.nodes) == 1  # just the start node

    def test_backward_direction(self, chain_graph):
        sub = chain_graph.filtered_traversal("d", direction="backward", max_depth=10)
        assert len(sub.nodes) == 4

    def test_unknown_node(self, chain_graph):
        sub = chain_graph.filtered_traversal("zzz")
        assert sub.node_count == 0


# ── Dependency Chain Tests ──────────────────────────────────────────────────

class TestDependencyChain:
    def test_linear_chain(self):
        ks = _make_knowledge_state(
            [("a", "A"), ("b", "B"), ("c", "C")],
            derived=[("a", "b"), ("b", "c")],
        )
        gs = GraphProjection.project(ks)
        chain = gs.dependency_chain("a", relation_type=RelationType.DERIVED_FROM)
        assert chain[0]["node_id"] == "a"
        assert len(chain) == 3

    def test_cycle_detection(self):
        ks = _make_knowledge_state(
            [("a", "A"), ("b", "B")],
            derived=[("a", "b"), ("b", "a")],
        )
        gs = GraphProjection.project(ks)
        with pytest.raises(ValueError, match="Cycle detected"):
            gs.dependency_chain("a", relation_type=RelationType.DERIVED_FROM)

    def test_no_dependencies(self):
        ks = _make_knowledge_state([("a", "A")])
        gs = GraphProjection.project(ks)
        chain = gs.dependency_chain("a")
        assert len(chain) == 1
        assert chain[0]["depth"] == 0


# ── Topological Sort Tests ──────────────────────────────────────────────────

class TestTopologicalSort:
    def test_dag_no_cycles(self):
        ks = _make_knowledge_state(
            [("a", "A"), ("b", "B"), ("c", "C")],
            derived=[("a", "b"), ("b", "c")],
        )
        gs = GraphProjection.project(ks)
        order, cycles = gs.topological_sort(RelationType.DERIVED_FROM)
        assert len(cycles) == 0
        assert len(order) == 3
        # a should come after b and c (dependencies first)
        assert order.index("c") < order.index("b") < order.index("a")

    def test_cycle_detected(self):
        ks = _make_knowledge_state(
            [("a", "A"), ("b", "B")],
            derived=[("a", "b"), ("b", "a")],
        )
        gs = GraphProjection.project(ks)
        order, cycles = gs.topological_sort(RelationType.DERIVED_FROM)
        assert len(cycles) > 0


# ── Cycle Detection Tests ──────────────────────────────────────────────────

class TestDetectCycles:
    def test_no_cycles(self):
        ks = _make_knowledge_state(
            [("a", "A"), ("b", "B"), ("c", "C")],
            supports=[("a", "b"), ("b", "c")],
        )
        gs = GraphProjection.project(ks)
        cycles = gs.detect_cycles()
        assert len(cycles) == 0

    def test_cycle_found(self):
        ks = _make_knowledge_state(
            [("a", "A"), ("b", "B"), ("c", "C")],
            supports=[("a", "b"), ("b", "c"), ("c", "a")],
        )
        gs = GraphProjection.project(ks)
        cycles = gs.detect_cycles()
        assert len(cycles) > 0

    def test_lazy_caching(self):
        ks = _make_knowledge_state(
            [("a", "A"), ("b", "B")],
            supports=[("a", "b"), ("b", "a")],
        )
        gs = GraphProjection.project(ks)
        assert gs.cycles is None
        cycles1 = gs.detect_cycles()
        assert gs.cycles is not None
        cycles2 = gs.detect_cycles()
        assert cycles1 == cycles2

    def test_filter_by_relation_type(self):
        ks = _make_knowledge_state(
            [("a", "A"), ("b", "B"), ("c", "C")],
            supports=[("a", "b"), ("b", "c"), ("c", "a")],
            derived=[("a", "c")],
        )
        gs = GraphProjection.project(ks)
        # SUPPORTS has a cycle, DERIVED_FROM does not
        cycles_supports = gs.detect_cycles(RelationType.SUPPORTS)
        cycles_derived = gs.detect_cycles(RelationType.DERIVED_FROM)
        assert len(cycles_supports) > 0
        assert len(cycles_derived) == 0


# ── Impact Analysis Tests ──────────────────────────────────────────────────

class TestImpactAnalysis:
    @pytest.fixture
    def impact_graph(self):
        ks = _make_knowledge_state(
            [("a", "A"), ("b", "B"), ("c", "C"), ("d", "D")],
            supports=[("a", "b"), ("a", "c"), ("b", "d")],
        )
        return GraphProjection.project(ks)

    def test_downstream(self, impact_graph):
        result = impact_graph.impact_analysis("a", depth=3)
        assert "b" in result["downstream"]
        assert "c" in result["downstream"]
        assert "d" in result["downstream"]

    def test_upstream(self, impact_graph):
        result = impact_graph.impact_analysis("d", depth=3)
        assert "b" in result["upstream"]
        assert "a" in result["upstream"]

    def test_contradiction(self):
        ks = _make_knowledge_state(
            [("a", "A"), ("b", "B")],
            contradictions=[("a", "b")],
        )
        gs = GraphProjection.project(ks)
        result = gs.impact_analysis("a")
        assert "b" in result["affected_by_contradiction"]

    def test_depth_limit(self, impact_graph):
        result = impact_graph.impact_analysis("a", depth=1)
        assert "d" not in result["downstream"]


# ── Blast Radius Tests ─────────────────────────────────────────────────────

class TestBlastRadius:
    def test_depth_1(self):
        ks = _make_knowledge_state(
            [("a", "A"), ("b", "B"), ("c", "C")],
            supports=[("a", "b"), ("b", "c")],
        )
        gs = GraphProjection.project(ks)
        result = gs.blast_radius("a", depth=1)
        assert len(result) == 1
        assert result[0]["node_id"] == "b"
        assert result[0]["distance"] == 1

    def test_depth_2(self):
        ks = _make_knowledge_state(
            [("a", "A"), ("b", "B"), ("c", "C")],
            supports=[("a", "b"), ("b", "c")],
        )
        gs = GraphProjection.project(ks)
        result = gs.blast_radius("a", depth=2)
        assert len(result) == 2
        distances = [r["distance"] for r in result]
        assert distances == sorted(distances)

    def test_sorted_by_distance(self):
        ks = _make_knowledge_state(
            [("a", "A"), ("b", "B"), ("c", "C"), ("d", "D")],
            supports=[("a", "b"), ("a", "c"), ("b", "d")],
        )
        gs = GraphProjection.project(ks)
        result = gs.blast_radius("a", depth=3)
        distances = [r["distance"] for r in result]
        assert distances == sorted(distances)

    def test_unknown_node(self):
        ks = _make_knowledge_state([("a", "A")])
        gs = GraphProjection.project(ks)
        result = gs.blast_radius("zzz")
        assert result == []

    def test_bidirectional(self):
        ks = _make_knowledge_state(
            [("a", "A"), ("b", "B"), ("c", "C")],
            supports=[("b", "a"), ("c", "a")],
        )
        gs = GraphProjection.project(ks)
        result = gs.blast_radius("a", depth=2)
        node_ids = [r["node_id"] for r in result]
        assert "b" in node_ids
        assert "c" in node_ids


# ── Cluster Tests ──────────────────────────────────────────────────────────

class TestCluster:
    def test_single_component(self):
        ks = _make_knowledge_state(
            [("a", "A"), ("b", "B"), ("c", "C")],
            supports=[("a", "b"), ("b", "c")],
        )
        gs = GraphProjection.project(ks)
        assert len(gs.clusters) == 1

    def test_multiple_components(self):
        ks = _make_knowledge_state(
            [("a", "A"), ("b", "B"), ("c", "C"), ("d", "D")],
            supports=[("a", "b"), ("c", "d")],
        )
        gs = GraphProjection.project(ks)
        assert len(gs.clusters) == 2

    def test_all_orphans(self):
        ks = _make_knowledge_state([("a", "A"), ("b", "B")])
        gs = GraphProjection.project(ks)
        assert len(gs.clusters) == 2


# ── All Paths Tests ────────────────────────────────────────────────────────

class TestAllPaths:
    def test_linear_chain(self):
        ks = _make_knowledge_state(
            [("a", "A"), ("b", "B"), ("c", "C")],
            supports=[("a", "b"), ("b", "c")],
        )
        gs = GraphProjection.project(ks)
        paths = gs.all_paths("a", "c")
        assert len(paths) == 1
        assert paths[0] == ["a", "b", "c"]

    def test_multiple_paths(self):
        ks = _make_knowledge_state(
            [("a", "A"), ("b", "B"), ("c", "C")],
            supports=[("a", "b"), ("a", "c"), ("b", "c")],
        )
        gs = GraphProjection.project(ks)
        paths = gs.all_paths("a", "c")
        assert len(paths) >= 2

    def test_max_depth(self):
        ks = _make_knowledge_state(
            [("a", "A"), ("b", "B"), ("c", "C"), ("d", "D")],
            supports=[("a", "b"), ("b", "c"), ("c", "d")],
        )
        gs = GraphProjection.project(ks)
        paths = gs.all_paths("a", "d", max_depth=2)
        assert len(paths) == 0

    def test_no_connection(self):
        ks = _make_knowledge_state(
            [("a", "A"), ("b", "B")],
        )
        gs = GraphProjection.project(ks)
        paths = gs.all_paths("a", "b")
        assert paths == []

    def test_unknown_node(self):
        ks = _make_knowledge_state([("a", "A")])
        gs = GraphProjection.project(ks)
        paths = gs.all_paths("a", "zzz")
        assert paths == []


# ── Weighted Shortest Path Tests ───────────────────────────────────────────

class TestWeightedShortestPath:
    def test_direct_path(self):
        ks = _make_knowledge_state(
            [("a", "A"), ("b", "B")],
            supports=[("a", "b")],
        )
        gs = GraphProjection.project(ks)
        path, weight = gs.weighted_shortest_path("a", "b")
        assert path == ["a", "b"]
        assert weight > 0

    def test_preferred_high_confidence(self):
        # Two paths: a→b (low conf) and a→c→b (high conf)
        # The direct path should be preferred due to high confidence
        ks = _make_knowledge_state(
            [("a", "A"), ("b", "B"), ("c", "C")],
            supports=[("a", "b"), ("a", "c"), ("c", "b")],
        )
        gs = GraphProjection.project(ks)
        # Override confidence on edges
        for e in gs.adjacency.get("a", []):
            if e.target == "b":
                e.confidence = 0.3  # low confidence = high weight
            elif e.target == "c":
                e.confidence = 0.95  # high confidence = low weight
        for e in gs.adjacency.get("c", []):
            if e.target == "b":
                e.confidence = 0.95

        path, weight = gs.weighted_shortest_path("a", "b")
        # a→c→b should be preferred (lower total weight)
        assert path == ["a", "c", "b"]

    def test_no_connection(self):
        ks = _make_knowledge_state(
            [("a", "A"), ("b", "B")],
        )
        gs = GraphProjection.project(ks)
        path, weight = gs.weighted_shortest_path("a", "b")
        assert path == []
        assert weight == float("inf")

    def test_same_node(self):
        ks = _make_knowledge_state([("a", "A")])
        gs = GraphProjection.project(ks)
        path, weight = gs.weighted_shortest_path("a", "a")
        assert path == ["a"]
        assert weight == 0.0

    def test_unknown_source(self):
        ks = _make_knowledge_state([("a", "A")])
        gs = GraphProjection.project(ks)
        path, weight = gs.weighted_shortest_path("zzz", "a")
        assert path == []


# ── Determinism Tests ──────────────────────────────────────────────────────

class TestDeterminism:
    def test_filtered_traversal_deterministic(self):
        ks = _make_knowledge_state(
            [("a", "A"), ("b", "B"), ("c", "C")],
            supports=[("a", "b"), ("b", "c")],
        )
        gs = GraphProjection.project(ks)
        sub1 = gs.filtered_traversal("a")
        sub2 = gs.filtered_traversal("a")
        assert set(sub1.nodes.keys()) == set(sub2.nodes.keys())
        assert len(sub1.edges) == len(sub2.edges)

    def test_impact_analysis_deterministic(self):
        ks = _make_knowledge_state(
            [("a", "A"), ("b", "B"), ("c", "C")],
            supports=[("a", "b"), ("b", "c")],
        )
        gs = GraphProjection.project(ks)
        r1 = gs.impact_analysis("a")
        r2 = gs.impact_analysis("a")
        assert r1 == r2

    def test_blast_radius_deterministic(self):
        ks = _make_knowledge_state(
            [("a", "A"), ("b", "B"), ("c", "C")],
            supports=[("a", "b"), ("b", "c")],
        )
        gs = GraphProjection.project(ks)
        r1 = gs.blast_radius("a")
        r2 = gs.blast_radius("a")
        assert r1 == r2

    def test_all_paths_deterministic(self):
        ks = _make_knowledge_state(
            [("a", "A"), ("b", "B"), ("c", "C")],
            supports=[("a", "b"), ("a", "c"), ("b", "c")],
        )
        gs = GraphProjection.project(ks)
        p1 = gs.all_paths("a", "c")
        p2 = gs.all_paths("a", "c")
        assert p1 == p2
