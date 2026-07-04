"""
Tests for RationaleVault System Lineage Projection.

Covers node/edge creation, BFS traversal, why_exists queries, and serialization.
"""
from __future__ import annotations

import pytest

from rationalevault.knowledge.system_lineage import (
    LineageNode,
    LineageEdge,
    SystemLineageProjection,
    EdgeType,
    NodeSubsystem,
)


# =====================================================================
# Fixtures
# =====================================================================

def _make_linear_graph() -> SystemLineageProjection:
    """
    Create a linear lineage graph:

    Event → Belief → Decision → Execution → Artifact → Learning → Reflection → Knowledge
    """
    nodes = [
        LineageNode("LINNODE-001", "EVT-001", NodeSubsystem.EVENT, "Event", "2026-06-26T12:00:00Z"),
        LineageNode("LINNODE-002", "BEL-001", NodeSubsystem.BELIEF, "Belief", "2026-06-26T12:00:01Z"),
        LineageNode("LINNODE-003", "DEC-001", NodeSubsystem.DECISION, "Decision", "2026-06-26T12:00:02Z"),
        LineageNode("LINNODE-004", "SKE-001", NodeSubsystem.EXECUTION, "Execution", "2026-06-26T12:00:03Z"),
        LineageNode("LINNODE-005", "ART-001", NodeSubsystem.ARTIFACT, "Artifact", "2026-06-26T12:00:04Z"),
        LineageNode("LINNODE-006", "LEARN-001", NodeSubsystem.LEARNING, "Learning", "2026-06-26T12:00:05Z"),
        LineageNode("LINNODE-007", "REFL-001", NodeSubsystem.REFLECTION, "Reflection", "2026-06-26T12:00:06Z"),
        LineageNode("LINNODE-008", "KNOW-001", NodeSubsystem.KNOWLEDGE, "Knowledge", "2026-06-26T12:00:07Z"),
    ]
    edges = [
        LineageEdge("LINEGDE-001", "LINNODE-001", "LINNODE-002", EdgeType.DERIVED_FROM, "2026-06-26T12:00:01Z"),
        LineageEdge("LINEGDE-002", "LINNODE-002", "LINNODE-003", EdgeType.DERIVED_FROM, "2026-06-26T12:00:02Z"),
        LineageEdge("LINEGDE-003", "LINNODE-003", "LINNODE-004", EdgeType.EXECUTED_FOR, "2026-06-26T12:00:03Z"),
        LineageEdge("LINEGDE-004", "LINNODE-004", "LINNODE-005", EdgeType.GENERATED_BY, "2026-06-26T12:00:04Z"),
        LineageEdge("LINEGDE-005", "LINNODE-005", "LINNODE-006", EdgeType.DERIVED_FROM, "2026-06-26T12:00:05Z"),
        LineageEdge("LINEGDE-006", "LINNODE-006", "LINNODE-007", EdgeType.REFLECTED_IN, "2026-06-26T12:00:06Z"),
        LineageEdge("LINEGDE-007", "LINNODE-007", "LINNODE-008", EdgeType.PROMOTED_FROM, "2026-06-26T12:00:07Z"),
    ]
    return SystemLineageProjection(nodes=nodes, edges=edges, version=1)


# =====================================================================
# LineageNode
# =====================================================================

class TestLineageNode:
    def test_id_generation_deterministic(self):
        id1 = LineageNode.generate_node_id("BEL-001", "BELIEF")
        id2 = LineageNode.generate_node_id("BEL-001", "BELIEF")
        assert id1 == id2
        assert id1.startswith("LINNODE-")

    def test_serialization_roundtrip(self):
        node = LineageNode("LINNODE-TEST", "BEL-001", NodeSubsystem.BELIEF, "Test Belief", "2026-06-26T12:00:00Z")
        d = node.to_dict()
        restored = LineageNode.from_dict(d)
        assert restored.node_id == node.node_id
        assert restored.subsystem == node.subsystem

    def test_frozen(self):
        node = LineageNode("LINNODE-TEST", "BEL-001", NodeSubsystem.BELIEF, "Test", "2026-06-26T12:00:00Z")
        with pytest.raises(AttributeError):
            node.title = "Modified"


# =====================================================================
# LineageEdge
# =====================================================================

class TestLineageEdge:
    def test_id_generation_deterministic(self):
        id1 = LineageEdge.generate_edge_id("N1", "N2", "DERIVED_FROM")
        id2 = LineageEdge.generate_edge_id("N1", "N2", "DERIVED_FROM")
        assert id1 == id2
        assert id1.startswith("LINEGDE-")

    def test_serialization_roundtrip(self):
        edge = LineageEdge("LINEGDE-TEST", "N1", "N2", EdgeType.DERIVED_FROM, "2026-06-26T12:00:00Z")
        d = edge.to_dict()
        restored = LineageEdge.from_dict(d)
        assert restored.edge_id == edge.edge_id
        assert restored.edge_type == edge.edge_type


# =====================================================================
# SystemLineageProjection
# =====================================================================

class TestSystemLineageProjection:
    def test_get_node(self):
        proj = _make_linear_graph()
        node = proj.get_node("LINNODE-003")
        assert node is not None
        assert node.object_id == "DEC-001"

    def test_get_node_by_object(self):
        proj = _make_linear_graph()
        node = proj.get_node_by_object("BEL-001")
        assert node is not None
        assert node.node_id == "LINNODE-002"

    def test_get_edges_from(self):
        proj = _make_linear_graph()
        edges = proj.get_edges_from("LINNODE-001")
        assert len(edges) == 1
        assert edges[0].target_node_id == "LINNODE-002"

    def test_get_edges_to(self):
        proj = _make_linear_graph()
        edges = proj.get_edges_to("LINNODE-003")
        assert len(edges) == 1
        assert edges[0].source_node_id == "LINNODE-002"

    def test_ancestors_linear(self):
        proj = _make_linear_graph()
        ancestors = proj.ancestors("LINNODE-008")  # Knowledge
        # Should trace back through all upstream nodes
        ancestor_objects = []
        for a in ancestors:
            node = proj.get_node(a)
            if node:
                ancestor_objects.append(node.object_id)
        assert "REFL-001" in ancestor_objects
        assert "BEL-001" in ancestor_objects
        assert "EVT-001" in ancestor_objects

    def test_descendants_linear(self):
        proj = _make_linear_graph()
        descendants = proj.descendants("LINNODE-001")  # Event
        descendant_objects = []
        for d in descendants:
            node = proj.get_node(d)
            if node:
                descendant_objects.append(node.object_id)
        assert "BEL-001" in descendant_objects
        assert "KNOW-001" in descendant_objects

    def test_why_exists(self):
        proj = _make_linear_graph()
        reasons = proj.why_exists("KNOW-001")
        assert "REFL-001" in reasons
        assert "BEL-001" in reasons
        assert "EVT-001" in reasons
        assert "KNOW-001" not in reasons  # Should not include itself

    def test_why_exists_unknown_object(self):
        proj = _make_linear_graph()
        reasons = proj.why_exists("UNKNOWN-001")
        assert reasons == []

    def test_full_lineage_path(self):
        proj = _make_linear_graph()
        path = proj.full_lineage_path("KNOW-001")
        assert path[0] == "KNOW-001"  # Object itself is first
        assert "EVT-001" in path       # Origin is somewhere in the path

    def test_serialization_roundtrip(self):
        proj = _make_linear_graph()
        d = proj.to_dict()
        restored = SystemLineageProjection.from_dict(d)
        assert len(restored.nodes) == 8
        assert len(restored.edges) == 7
        assert restored.version == 1

    def test_diamond_graph(self):
        """
        Test a diamond-shaped graph:

            Event
           /     \
        Belief   Decision
           \     /
           Execution
        """
        nodes = [
            LineageNode("N1", "EVT-001", NodeSubsystem.EVENT, "Event", "2026-06-26T12:00:00Z"),
            LineageNode("N2", "BEL-001", NodeSubsystem.BELIEF, "Belief", "2026-06-26T12:00:01Z"),
            LineageNode("N3", "DEC-001", NodeSubsystem.DECISION, "Decision", "2026-06-26T12:00:02Z"),
            LineageNode("N4", "SKE-001", NodeSubsystem.EXECUTION, "Execution", "2026-06-26T12:00:03Z"),
        ]
        edges = [
            LineageEdge("E1", "N1", "N2", EdgeType.DERIVED_FROM, "2026-06-26T12:00:01Z"),
            LineageEdge("E2", "N1", "N3", EdgeType.DERIVED_FROM, "2026-06-26T12:00:02Z"),
            LineageEdge("E3", "N2", "N4", EdgeType.EXECUTED_FOR, "2026-06-26T12:00:03Z"),
            LineageEdge("E4", "N3", "N4", EdgeType.EXECUTED_FOR, "2026-06-26T12:00:03Z"),
        ]
        proj = SystemLineageProjection(nodes=nodes, edges=edges, version=1)

        # Execution should have two ancestors: Belief and Decision (and Event via both)
        ancestors = proj.ancestors("N4")
        ancestor_objects = []
        for a in ancestors:
            node = proj.get_node(a)
            if node:
                ancestor_objects.append(node.object_id)
        assert "BEL-001" in ancestor_objects
        assert "DEC-001" in ancestor_objects
        assert "EVT-001" in ancestor_objects
