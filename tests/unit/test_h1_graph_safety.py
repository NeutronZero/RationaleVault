"""Unit tests for H1-GraphSafety iterative DFS implementations."""
from __future__ import annotations

import pytest
from rationalevault.projections.graph import GraphState, GraphNode, GraphEdge
from rationalevault.knowledge.models import RelationType


def make_graph_state(nodes: dict[str, GraphNode], edges: list[GraphEdge]) -> GraphState:
    adjacency: dict[str, list[GraphEdge]] = {}
    reverse_adjacency: dict[str, list[GraphEdge]] = {}
    for e in edges:
        adjacency.setdefault(e.source, []).append(e)
        reverse_adjacency.setdefault(e.target, []).append(e)
    return GraphState(
        project_id="test",
        compiled_at="now",
        nodes=nodes,
        edges=edges,
        adjacency=adjacency,
        reverse_adjacency=reverse_adjacency,
    )


def test_dependency_chain_iterative_order() -> None:
    # Build a simple GraphState
    nodes = {nid: GraphNode(nid, f"Node {nid}", "ARCHITECTURE_PRINCIPLE", "ARCHITECTURE", 0.9, "high")
             for nid in ["a", "b", "c", "d"]}
    # a -> b, b -> c, c -> d (dependency -> derived)
    # Walking reverse_adjacency from d finds dependencies: c -> b -> a
    edges = [
        GraphEdge("a", "b", RelationType.DERIVED_FROM, 1.0),
        GraphEdge("b", "c", RelationType.DERIVED_FROM, 1.0),
        GraphEdge("c", "d", RelationType.DERIVED_FROM, 1.0),
    ]
    gs = make_graph_state(nodes, edges)
    
    # Run dependency_chain on "d" (walking reverse adjacency edges)
    # Expected order: d -> c -> b -> a
    chain = gs.dependency_chain("d", RelationType.DERIVED_FROM)
    assert [x["node_id"] for x in chain] == ["d", "c", "b", "a"]
    assert [x["depth"] for x in chain] == [0, 1, 2, 3]


def test_dependency_chain_cycle_error() -> None:
    nodes = {nid: GraphNode(nid, f"Node {nid}", "ARCHITECTURE_PRINCIPLE", "ARCHITECTURE", 0.9, "high")
             for nid in ["a", "b"]}
    edges = [
        GraphEdge("a", "b", RelationType.DERIVED_FROM, 1.0),
        GraphEdge("b", "a", RelationType.DERIVED_FROM, 1.0),
    ]
    gs = make_graph_state(nodes, edges)
    
    with pytest.raises(ValueError, match="Cycle detected"):
        gs.dependency_chain("a", RelationType.DERIVED_FROM)


def test_all_paths_iterator() -> None:
    nodes = {nid: GraphNode(nid, f"Node {nid}", "ARCHITECTURE_PRINCIPLE", "ARCHITECTURE", 0.9, "high")
             for nid in ["a", "b", "c", "d", "target"]}
    edges = [
        GraphEdge("a", "b", RelationType.SUPPORTS, 1.0),
        GraphEdge("b", "target", RelationType.SUPPORTS, 1.0),
        GraphEdge("a", "c", RelationType.SUPPORTS, 1.0),
        GraphEdge("c", "target", RelationType.SUPPORTS, 1.0),
        GraphEdge("a", "d", RelationType.SUPPORTS, 1.0),  # Dead end
    ]
    gs = make_graph_state(nodes, edges)
    
    paths = gs.all_paths("a", "target")
    assert sorted(paths) == [["a", "b", "target"], ["a", "c", "target"]]


def test_dfs_cycles_parity() -> None:
    # Helper to run iterative cycle detection on a given adjacency dict
    def run_iterative(adj: dict[str, list[str]]) -> list[list[str]]:
        nodes = {nid: GraphNode(nid, f"Node {nid}", "ARCHITECTURE_PRINCIPLE", "ARCHITECTURE", 0.9, "high")
                 for nid in adj}
        edges = []
        for src, targets in adj.items():
            for target in targets:
                edges.append(GraphEdge(src, target, RelationType.DERIVED_FROM, 1.0))
        
        gs = make_graph_state(nodes, edges)
        return gs._find_cycles_in_subset(set(adj.keys()), RelationType.DERIVED_FROM.value)

    # 1. No cycles
    assert run_iterative({"a": ["b"], "b": ["c"], "c": []}) == []

    # 2. Single cycle
    c1 = run_iterative({"a": ["b"], "b": ["c"], "c": ["a"]})
    assert len(c1) == 1
    assert c1[0] == ["a", "b", "c", "a"]

    # 3. Multiple disjoint cycles
    c2 = run_iterative({
        "a": ["b"], "b": ["c"], "c": ["a"],
        "d": ["e"], "e": ["f"], "f": ["d"],
    })
    # Sort cycles by start node to be stable
    c2_sorted = sorted(c2, key=lambda x: x[0])
    assert len(c2_sorted) == 2
    assert c2_sorted[0] == ["a", "b", "c", "a"]
    assert c2_sorted[1] == ["d", "e", "f", "d"]

    # 4. Nested / shared-node cycles
    c3 = run_iterative({
        "a": ["b", "c"],
        "b": ["a"],
        "c": ["a"],
    })
    assert len(c3) == 2
    assert ["a", "b", "a"] in c3
    assert ["a", "c", "a"] in c3


def test_deep_linear_graph_safety() -> None:
    # Deep linear graph with 1050 nodes
    # We construct: 1 -> 2 -> 3 -> ... -> 1050 (dependency -> derived)
    # Walking reverse_adjacency from 1050 to 1 should find all nodes.
    depth = 1050
    nodes = {str(i): GraphNode(str(i), f"Node {i}", "ARCHITECTURE_PRINCIPLE", "ARCHITECTURE", 0.9, "high")
             for i in range(1, depth + 1)}
    edges = [GraphEdge(str(i), str(i + 1), RelationType.DERIVED_FROM, 1.0) for i in range(1, depth)]
    
    gs = make_graph_state(nodes, edges)
    
    # Run dependency_chain from depth (1050)
    chain = gs.dependency_chain(str(depth), RelationType.DERIVED_FROM)
    assert len(chain) == depth
    assert chain[-1]["node_id"] == "1"
