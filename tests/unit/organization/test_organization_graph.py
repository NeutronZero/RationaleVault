"""Tests for I13.A — Organization Graph Projection structures and projection."""
from __future__ import annotations

import pytest

from rationalevault.organization.models import (
    CrossProjectConflict,
    KnowledgeLineage,
    OrganizationHealth,
    OrganizationState,
    SharedKnowledge,
    TransferabilityTelemetry,
)
from rationalevault.organization.graph import (
    OrganizationEdge,
    OrganizationGraphHealth,
    OrganizationGraphProjection,
    OrganizationGraphState,
    OrganizationNode,
)
from rationalevault.organization.relation_types import OrganizationRelationType


def _make_lineage(kid: str, origin: str, current: list[str]) -> KnowledgeLineage:
    return KnowledgeLineage(
        knowledge_id=kid,
        origin_project=origin,
        current_projects=current,
        transfer_path=[origin] + current,
        depth=len(current),
    )


def _make_shared(kid: str, title: str, projects: list[str]) -> SharedKnowledge:
    return SharedKnowledge(
        knowledge_id=kid,
        title=title,
        knowledge_type="principle",
        present_in_projects=projects,
        transfer_count=len(projects) - 1,
    )


def _make_conflict(
    a_id: str, b_id: str, pa: str, pb: str,
    title_a: str = "A", title_b: str = "B", confidence: float = 0.8,
) -> CrossProjectConflict:
    return CrossProjectConflict(
        conflict_id=f"{pa}_{pb}",
        knowledge_a_id=a_id,
        knowledge_b_id=b_id,
        project_a=pa,
        project_b=pb,
        knowledge_a_title=title_a,
        knowledge_b_title=title_b,
        confidence=confidence,
        reasons=["lexical_similarity"],
    )


class TestOrganizationRelationType:
    def test_all_values(self) -> None:
        assert len(OrganizationRelationType) == 5

    def test_from_str(self) -> None:
        assert OrganizationRelationType.from_str("transferred_to") == OrganizationRelationType.TRANSFERRED_TO
        assert OrganizationRelationType.from_str("DERIVES_FROM") == OrganizationRelationType.DERIVES_FROM

    def test_reserved_derives_from(self) -> None:
        assert OrganizationRelationType.DERIVES_FROM.value == "DERIVES_FROM"


class TestOrganizationNode:
    def test_frozen(self) -> None:
        node = OrganizationNode(project_id="a", name="A")
        with pytest.raises(AttributeError):
            node.project_id = "b"  # type: ignore[misc]


class TestOrganizationEdge:
    def test_frozen(self) -> None:
        edge = OrganizationEdge(source="a", target="b", relation_type=OrganizationRelationType.TRANSFERRED_TO)
        with pytest.raises(AttributeError):
            edge.source = "c"  # type: ignore[misc]

    def test_default_weights(self) -> None:
        edge = OrganizationEdge(source="a", target="b", relation_type=OrganizationRelationType.SHARED_BY)
        assert edge.weight == 1.0
        assert edge.confidence == 1.0


class TestOrganizationGraphState:
    def test_to_dict(self) -> None:
        state = OrganizationGraphState(compiled_at="2025-01-01")
        d = state.to_dict()
        assert d["compiled_at"] == "2025-01-01"
        assert d["health"]["connectivity"] == 0.0
        import json
        serialized = json.dumps(d)
        assert isinstance(serialized, str)


class TestOrganizationGraphProjectionBasic:
    def test_single_project(self) -> None:
        org = OrganizationState(
            compiled_at="2025-01-01",
            project_ids=["a"],
        )
        graph = OrganizationGraphProjection.project(org)
        assert len(graph.nodes) == 1
        assert "a" in graph.nodes
        assert graph.edges == []
        assert graph.density == 0.0

    def test_two_projects_no_edges(self) -> None:
        org = OrganizationState(
            compiled_at="2025-01-01",
            project_ids=["a", "b"],
        )
        graph = OrganizationGraphProjection.project(org)
        assert len(graph.nodes) == 2
        assert len(graph.edges) == 0


class TestOrganizationGraphTransferEdges:
    def test_linear_transfer(self) -> None:
        org = OrganizationState(
            compiled_at="2025-01-01",
            project_ids=["a", "b", "c"],
            active_lineages={
                "k1": _make_lineage("k1", "a", ["b"]),
                "k2": _make_lineage("k2", "b", ["c"]),
            },
        )
        graph = OrganizationGraphProjection.project(org)
        transfer_edges = [
            e for e in graph.edges
            if e.relation_type == OrganizationRelationType.TRANSFERRED_TO
        ]
        assert len(transfer_edges) == 2
        assert any(e.source == "a" and e.target == "b" for e in transfer_edges)
        assert any(e.source == "b" and e.target == "c" for e in transfer_edges)

    def test_branching_transfer(self) -> None:
        org = OrganizationState(
            compiled_at="2025-01-01",
            project_ids=["a", "b", "c"],
            active_lineages={
                "k1": _make_lineage("k1", "a", ["b"]),
                "k2": _make_lineage("k2", "a", ["c"]),
            },
        )
        graph = OrganizationGraphProjection.project(org)
        transfer_edges = [
            e for e in graph.edges
            if e.relation_type == OrganizationRelationType.TRANSFERRED_TO
        ]
        assert len(transfer_edges) == 2
        # Both from a
        assert all(e.source == "a" for e in transfer_edges)

    def test_aggregated_transfer_weight(self) -> None:
        org = OrganizationState(
            compiled_at="2025-01-01",
            project_ids=["a", "b"],
            active_lineages={
                "k1": _make_lineage("k1", "a", ["b"]),
                "k2": _make_lineage("k2", "a", ["b"]),
                "k3": _make_lineage("k3", "a", ["b"]),
            },
        )
        graph = OrganizationGraphProjection.project(org)
        transfer_edges = [
            e for e in graph.edges
            if e.relation_type == OrganizationRelationType.TRANSFERRED_TO
        ]
        assert len(transfer_edges) == 1
        assert transfer_edges[0].weight == 3.0


class TestOrganizationGraphSharedEdges:
    def test_shared_by(self) -> None:
        org = OrganizationState(
            compiled_at="2025-01-01",
            project_ids=["a", "b", "c"],
            shared_knowledge=[
                _make_shared("k1", "Knowledge 1", ["a", "b"]),
                _make_shared("k2", "Knowledge 2", ["a", "b", "c"]),
            ],
        )
        graph = OrganizationGraphProjection.project(org)
        shared_edges = [
            e for e in graph.edges
            if e.relation_type == OrganizationRelationType.SHARED_BY
        ]
        # Bidirectional: a-b (2), b-a (2), a-c (1), c-a (1), b-c (1), c-b (1) = 6
        assert len(shared_edges) == 6
        ab_edge = next(e for e in shared_edges if e.source == "a" and e.target == "b")
        ba_edge = next(e for e in shared_edges if e.source == "b" and e.target == "a")
        assert ab_edge.weight == 2.0
        assert ba_edge.weight == 2.0


class TestOrganizationGraphConflictEdges:
    def test_conflicts_with(self) -> None:
        org = OrganizationState(
            compiled_at="2025-01-01",
            project_ids=["a", "b"],
            cross_project_conflicts=[
                _make_conflict("k1", "k2", "a", "b", confidence=0.8),
                _make_conflict("k3", "k4", "a", "b", confidence=0.6),
            ],
        )
        graph = OrganizationGraphProjection.project(org)
        conflict_edges = [
            e for e in graph.edges
            if e.relation_type == OrganizationRelationType.CONFLICTS_WITH
        ]
        # Bidirectional: a->b and b->a = 2 edges
        assert len(conflict_edges) == 2
        ab_edge = next(e for e in conflict_edges if e.source == "a" and e.target == "b")
        ba_edge = next(e for e in conflict_edges if e.source == "b" and e.target == "a")
        assert ab_edge.weight == 2.0
        assert ba_edge.weight == 2.0
        assert ab_edge.confidence == pytest.approx(0.7)
        assert ba_edge.confidence == pytest.approx(0.7)


class TestOrganizationGraphClusterEdges:
    def test_in_cluster(self) -> None:
        org = OrganizationState(
            compiled_at="2025-01-01",
            project_ids=["a", "b", "c"],
            project_clusters=[["a", "b", "c"]],
            active_lineages={
                "k1": _make_lineage("k1", "a", ["a", "b"]),
                "k2": _make_lineage("k2", "b", ["b", "c"]),
            },
        )
        graph = OrganizationGraphProjection.project(org)
        cluster_edges = [
            e for e in graph.edges
            if e.relation_type == OrganizationRelationType.IN_CLUSTER
        ]
        # Bidirectional: a-b, b-a, a-c, c-a, b-c, c-b = 6
        assert len(cluster_edges) == 6


class TestOrganizationGraphAdjacency:
    def test_adjacency_built(self) -> None:
        org = OrganizationState(
            compiled_at="2025-01-01",
            project_ids=["a", "b"],
            active_lineages={
                "k1": _make_lineage("k1", "a", ["b"]),
            },
        )
        graph = OrganizationGraphProjection.project(org)
        assert "a" in graph.adjacency
        assert "b" in graph.adjacency
        assert len(graph.adjacency["a"]) >= 1
        assert len(graph.reverse_adjacency["b"]) >= 1


class TestOrganizationGraphDensity:
    def test_directed_density(self) -> None:
        org = OrganizationState(
            compiled_at="2025-01-01",
            project_ids=["a", "b", "c"],
            active_lineages={
                "k1": _make_lineage("k1", "a", ["b"]),
                "k2": _make_lineage("k2", "a", ["c"]),
            },
        )
        graph = OrganizationGraphProjection.project(org)
        # 3 nodes, 2 transfer edges: density = 2 / (3*2) = 0.333...
        assert graph.density == pytest.approx(2 / 6, abs=0.01)


class TestOrganizationGraphFlowBalance:
    def test_producer(self) -> None:
        org = OrganizationState(
            compiled_at="2025-01-01",
            project_ids=["a", "b", "c"],
            active_lineages={
                "k1": _make_lineage("k1", "a", ["b"]),
                "k2": _make_lineage("k2", "a", ["c"]),
            },
        )
        graph = OrganizationGraphProjection.project(org)
        assert graph.knowledge_flow_balance["a"] == 2  # producer
        assert graph.knowledge_flow_balance["b"] == -1  # consumer
        assert graph.knowledge_flow_balance["c"] == -1  # consumer

    def test_balanced(self) -> None:
        org = OrganizationState(
            compiled_at="2025-01-01",
            project_ids=["a", "b"],
            active_lineages={
                "k1": _make_lineage("k1", "a", ["b"]),
                "k2": _make_lineage("k2", "b", ["a"]),
            },
        )
        graph = OrganizationGraphProjection.project(org)
        assert graph.knowledge_flow_balance["a"] == 0
        assert graph.knowledge_flow_balance["b"] == 0


class TestOrganizationGraphDerivedMetrics:
    def test_producers_ranked(self) -> None:
        org = OrganizationState(
            compiled_at="2025-01-01",
            project_ids=["a", "b", "c"],
            active_lineages={
                "k1": _make_lineage("k1", "a", ["b"]),
                "k2": _make_lineage("k2", "a", ["c"]),
                "k3": _make_lineage("k3", "a", ["b"]),
            },
        )
        graph = OrganizationGraphProjection.project(org)
        assert len(graph.knowledge_producers) >= 1
        assert graph.knowledge_producers[0][0] == "a"

    def test_hotspots_ranked(self) -> None:
        org = OrganizationState(
            compiled_at="2025-01-01",
            project_ids=["a", "b", "c"],
            cross_project_conflicts=[
                _make_conflict("k1", "k2", "a", "b", confidence=0.8),
                _make_conflict("k3", "k4", "a", "b", confidence=0.6),
                _make_conflict("k5", "k6", "a", "c", confidence=0.9),
            ],
        )
        graph = OrganizationGraphProjection.project(org)
        assert len(graph.contradiction_hotspots) >= 1
        # a has 6 conflict edges total (3 pairs × 2 bidirectional directions)
        a_score = next(s for p, s in graph.contradiction_hotspots if p == "a")
        assert a_score == 6.0


class TestOrganizationGraphHealth:
    def test_health_computed(self) -> None:
        org = OrganizationState(
            compiled_at="2025-01-01",
            project_ids=["a", "b", "c"],
            active_lineages={
                "k1": _make_lineage("k1", "a", ["b"]),
            },
            project_clusters=[["a", "b", "c"]],
        )
        graph = OrganizationGraphProjection.project(org)
        assert graph.health.connectivity > 0
        assert graph.health.overall > 0
        assert 0 <= graph.health.producer_consumer_balance <= 1.0

    def test_health_single_project(self) -> None:
        org = OrganizationState(
            compiled_at="2025-01-01",
            project_ids=["a"],
        )
        graph = OrganizationGraphProjection.project(org)
        assert graph.health.density == 0.0
        assert graph.health.connectivity == 1.0


class TestOrganizationGraphDeterminism:
    def test_same_input_same_output(self) -> None:
        org = OrganizationState(
            compiled_at="2025-01-01",
            project_ids=["a", "b", "c"],
            active_lineages={
                "k1": _make_lineage("k1", "a", ["b"]),
                "k2": _make_lineage("k2", "a", ["c"]),
            },
            shared_knowledge=[
                _make_shared("k1", "Knowledge 1", ["a", "b"]),
            ],
            project_clusters=[["a", "b", "c"]],
        )
        g1 = OrganizationGraphProjection.project(org)
        g2 = OrganizationGraphProjection.project(org)
        assert len(g1.edges) == len(g2.edges)
        assert g1.density == g2.density
        assert g1.knowledge_flow_balance == g2.knowledge_flow_balance
        assert g1.health.overall == g2.health.overall
        # Compare structure, not timestamps
        d1 = g1.to_dict()
        d2 = g2.to_dict()
        d1.pop("compiled_at")
        d2.pop("compiled_at")
        assert d1 == d2


class TestOrganizationGraphOperations:
    def test_project_centrality(self) -> None:
        org = OrganizationState(
            compiled_at="2025-01-01",
            project_ids=["a", "b", "c"],
            active_lineages={
                "k1": _make_lineage("k1", "a", ["b"]),
                "k2": _make_lineage("k2", "a", ["c"]),
            },
        )
        graph = OrganizationGraphProjection.project(org)
        c = OrganizationGraphProjection.project_centrality(graph, "a")
        assert c > 0

    def test_blast_radius(self) -> None:
        org = OrganizationState(
            compiled_at="2025-01-01",
            project_ids=["a", "b", "c"],
            active_lineages={
                "k1": _make_lineage("k1", "a", ["b"]),
                "k2": _make_lineage("k2", "b", ["c"]),
            },
        )
        graph = OrganizationGraphProjection.project(org)
        radius = OrganizationGraphProjection.blast_radius(graph, "a")
        assert "a" in radius
        assert "b" in radius
        assert "c" in radius

    def test_shortest_transfer_path(self) -> None:
        org = OrganizationState(
            compiled_at="2025-01-01",
            project_ids=["a", "b", "c"],
            active_lineages={
                "k1": _make_lineage("k1", "a", ["b"]),
                "k2": _make_lineage("k2", "b", ["c"]),
            },
        )
        graph = OrganizationGraphProjection.project(org)
        path = OrganizationGraphProjection.shortest_transfer_path(graph, "a", "c")
        assert path == ["a", "b", "c"]

    def test_shortest_transfer_path_no_route(self) -> None:
        org = OrganizationState(
            compiled_at="2025-01-01",
            project_ids=["a", "b"],
        )
        graph = OrganizationGraphProjection.project(org)
        path = OrganizationGraphProjection.shortest_transfer_path(graph, "a", "b")
        assert path == []

    def test_filtered_traversal(self) -> None:
        org = OrganizationState(
            compiled_at="2025-01-01",
            project_ids=["a", "b", "c"],
            active_lineages={
                "k1": _make_lineage("k1", "a", ["b"]),
                "k2": _make_lineage("k2", "a", ["c"]),
            },
        )
        graph = OrganizationGraphProjection.project(org)
        visited = OrganizationGraphProjection.filtered_traversal(
            graph, "a", relation_types={OrganizationRelationType.TRANSFERRED_TO},
        )
        assert "a" in visited
        assert "b" in visited
        assert "c" in visited
