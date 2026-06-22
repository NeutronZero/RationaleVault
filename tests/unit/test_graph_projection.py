"""Unit tests for RationaleVault Knowledge Graph Projection (Sprint I7.5)."""
from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET

from rationalevault.knowledge.models import (
    KnowledgeObject,
    KnowledgeType,
    KnowledgeDomain,
    KnowledgeConfidence,
    ProvenanceChain,
    KnowledgeRelation,
)
from rationalevault.knowledge.graph import GraphProjection, KnowledgeNode, KnowledgeEdge
from rationalevault.knowledge.graph_evaluation import evaluate_graph_projection, check_graph_gates


def _create_mock_knowledge(
    kid: str,
    title: str,
    content: str,
    ktype: KnowledgeType,
    version: int = 1,
    evidence_count: int = 5,
    event_ids: list[str] = None,
) -> KnowledgeObject:
    event_ids = event_ids or ["event1", "event2"]
    confidence = KnowledgeConfidence(
        memory_count=3,
        source_event_count=len(event_ids),
        contradiction_count=0,
        average_memory_confidence=0.8,
    )
    provenance = ProvenanceChain(
        knowledge_id=kid,
        source_memory_ids=["mem1", "mem2"],
        source_event_ids=event_ids,
        synthesis_event_id="synth1",
        confidence=confidence,
        evidence_count=evidence_count,
    )
    return KnowledgeObject(
        id=kid,
        version=version,
        title=title,
        content=content,
        knowledge_type=ktype,
        knowledge_domain=KnowledgeDomain.ARCHITECTURE,
        confidence=confidence,
        importance="high",
        provenance=provenance,
        tags=["tag1", "tag2"],
        supporting_memory_ids=["mem1", "mem2"],
        created_at="2026-06-22T00:00:00",
        updated_at="2026-06-22T00:00:00",
    )


def test_graph_projection_build() -> None:
    # 1. Setup mock knowledge objects and relations
    k1 = _create_mock_knowledge(
        "k1_id", "Title One", "Content One", KnowledgeType.ARCHITECTURE_PRINCIPLE, version=1
    )
    k2 = _create_mock_knowledge(
        "k2_id", "Title Two", "Content Two", KnowledgeType.PROJECT_INVARIANT, version=2
    )
    k3 = _create_mock_knowledge(
        "k3_id", "Title Three", "Content Three", KnowledgeType.LESSON, version=1
    )

    r1 = KnowledgeRelation(source_id="k1_id", target_id="k2_id", relation_type="SUPPORTS", confidence=0.8)
    r2 = KnowledgeRelation(source_id="k2_id", target_id="k3_id", relation_type="CONTRADICTS", confidence=0.9)
    # Relation with missing endpoint (should be skipped deterministically)
    r_missing = KnowledgeRelation(source_id="k1_id", target_id="nonexistent", relation_type="RELATED_TO", confidence=0.5)

    knowledge_list = [k1, k2, k3]
    relations_list = [r1, r2, r_missing]

    # 2. Build graph projection
    projection = GraphProjection.build(knowledge_list, relations_list)

    # 3. Assertions
    assert projection.node_count == 3
    assert projection.edge_count == 2  # r_missing should be ignored

    # Check stable node IDs
    expected_n1_id = hashlib.sha256(f"{KnowledgeType.ARCHITECTURE_PRINCIPLE.value}:Title One:1".encode("utf-8")).hexdigest()
    expected_n2_id = hashlib.sha256(f"{KnowledgeType.PROJECT_INVARIANT.value}:Title Two:2".encode("utf-8")).hexdigest()
    expected_n3_id = hashlib.sha256(f"{KnowledgeType.LESSON.value}:Title Three:1".encode("utf-8")).hexdigest()

    node_ids = {n.id for n in projection.nodes}
    assert expected_n1_id in node_ids
    assert expected_n2_id in node_ids
    assert expected_n3_id in node_ids

    # Check attributes mapping
    n1 = next(n for n in projection.nodes if n.id == expected_n1_id)
    assert n1.title == "Title One"
    assert n1.type == KnowledgeType.ARCHITECTURE_PRINCIPLE.value
    assert n1.confidence == k1.confidence.score
    assert n1.evidence_count == 5
    assert n1.source_event_count == 2
    assert n1.tags == ["tag1", "tag2"]
    assert n1.metadata["original_id"] == "k1_id"
    assert n1.metadata["version"] == 1

    # Check edge mappings (sources and targets must match the new node IDs)
    e1 = next(e for e in projection.edges if e.relation_type == "SUPPORTS")
    assert e1.source == expected_n1_id
    assert e1.target == expected_n2_id
    assert e1.confidence == 0.8


def test_graph_determinism() -> None:
    k1 = _create_mock_knowledge("k1_id", "Title One", "Content One", KnowledgeType.ARCHITECTURE_PRINCIPLE)
    k2 = _create_mock_knowledge("k2_id", "Title Two", "Content Two", KnowledgeType.PROJECT_INVARIANT)
    r1 = KnowledgeRelation(source_id="k1_id", target_id="k2_id", relation_type="SUPPORTS", confidence=0.8)

    # Build graph multiple times
    proj1 = GraphProjection.build([k1, k2], [r1])
    proj2 = GraphProjection.build([k1, k2], [r1])
    # Build with permuted order of inputs
    proj3 = GraphProjection.build([k2, k1], [r1])

    assert proj1.graph_id == proj2.graph_id
    assert proj1.graph_id == proj3.graph_id

    # Change version to break determinism
    k2_v2 = _create_mock_knowledge("k2_id", "Title Two", "Content Two", KnowledgeType.PROJECT_INVARIANT, version=2)
    proj4 = GraphProjection.build([k1, k2_v2], [r1])
    assert proj1.graph_id != proj4.graph_id


def test_graph_queries() -> None:
    k1 = _create_mock_knowledge("k1", "N1", "C1", KnowledgeType.ARCHITECTURE_PRINCIPLE)
    k2 = _create_mock_knowledge("k2", "N2", "C2", KnowledgeType.PROJECT_INVARIANT)
    k3 = _create_mock_knowledge("k3", "N3", "C3", KnowledgeType.LESSON)
    k4 = _create_mock_knowledge("k4", "N4", "C4", KnowledgeType.FAILURE_PATTERN)

    # Chain: N1 -> N2 -> N3 -> N4
    r1 = KnowledgeRelation(source_id="k1", target_id="k2", relation_type="SUPPORTS", confidence=0.8)
    r2 = KnowledgeRelation(source_id="k2", target_id="k3", relation_type="SUPPORTS", confidence=0.8)
    r3 = KnowledgeRelation(source_id="k3", target_id="k4", relation_type="SUPPORTS", confidence=0.8)

    projection = GraphProjection.build([k1, k2, k3, k4], [r1, r2, r3])

    n1_id = next(n.id for n in projection.nodes if n.title == "N1")
    n2_id = next(n.id for n in projection.nodes if n.title == "N2")
    n3_id = next(n.id for n in projection.nodes if n.title == "N3")
    n4_id = next(n.id for n in projection.nodes if n.title == "N4")

    # Test query_node
    assert projection.query_node(n1_id[:8]).title == "N1"

    # Test neighbors traversal
    # Depth 1 neighborhood of N2 should contain N1, N2, N3 and edges between them
    sub_graph_d1 = projection.neighbors(n2_id, depth=1)
    sub_node_ids = {n.id for n in sub_graph_d1.nodes}
    assert sub_graph_d1.node_count == 3
    assert n1_id in sub_node_ids
    assert n2_id in sub_node_ids
    assert n3_id in sub_node_ids
    assert n4_id not in sub_node_ids
    assert sub_graph_d1.edge_count == 2

    # Test shortest path BFS logic
    # Path from N1 to N4: N1 -> N2 -> N3 -> N4
    path_1_to_4 = projection.shortest_path(n1_id, n4_id)
    assert path_1_to_4 == [n1_id, n2_id, n3_id, n4_id]

    # No reverse path because it's a directed shortest path
    path_4_to_1 = projection.shortest_path(n4_id, n1_id)
    assert path_4_to_1 == []


def test_graph_statistics() -> None:
    k1 = _create_mock_knowledge("k1", "N1", "C1", KnowledgeType.ARCHITECTURE_PRINCIPLE)
    k2 = _create_mock_knowledge("k2", "N2", "C2", KnowledgeType.PROJECT_INVARIANT)
    k3 = _create_mock_knowledge("k3", "N3", "C3", KnowledgeType.LESSON)
    k_orphan = _create_mock_knowledge("k_orphan", "Orphan", "C_orphan", KnowledgeType.LESSON)

    r1 = KnowledgeRelation(source_id="k1", target_id="k2", relation_type="SUPPORTS", confidence=0.8)
    r2 = KnowledgeRelation(source_id="k2", target_id="k3", relation_type="SUPPORTS", confidence=0.8)

    projection = GraphProjection.build([k1, k2, k3, k_orphan], [r1, r2])
    stats = projection.stats()

    assert stats["node_count"] == 4
    assert stats["edge_count"] == 2
    assert stats["orphan_count"] == 1
    assert stats["orphan_pct"] == 0.25
    assert stats["connected_components"] == 2  # Component 1: {N1, N2, N3}, Component 2: {Orphan}
    assert stats["largest_component_pct"] == 0.75  # 3/4 nodes


def test_graph_exports() -> None:
    k1 = _create_mock_knowledge("k1", "N1", "C1", KnowledgeType.ARCHITECTURE_PRINCIPLE)
    k2 = _create_mock_knowledge("k2", "N2", "C2", KnowledgeType.PROJECT_INVARIANT)
    r1 = KnowledgeRelation(source_id="k1", target_id="k2", relation_type="SUPPORTS", confidence=0.8)

    projection = GraphProjection.build([k1, k2], [r1])

    # 1. Export JSON
    js = projection.export_json()
    data = json.loads(js)
    assert data["graph_id"] == projection.graph_id
    assert len(data["nodes"]) == 2

    # 2. Export GraphML
    gml = projection.export_graphml()
    # Should parse successfully as XML
    root = ET.fromstring(gml)
    assert root.tag.endswith("graphml")

    # 3. Export Mermaid
    mermaid = projection.export_mermaid()
    assert "graph TD" in mermaid
    assert "-->|SUPPORTS|" in mermaid

    # 4. Export NetworkX
    nx = projection.export_networkx()
    assert nx["directed"] is True
    assert len(nx["nodes"]) == 2
    assert nx["links"][0]["relation_type"] == "SUPPORTS"


def test_graph_evaluation_and_gates() -> None:
    k1 = _create_mock_knowledge("k1", "N1", "C1", KnowledgeType.ARCHITECTURE_PRINCIPLE)
    k2 = _create_mock_knowledge("k2", "N2", "C2", KnowledgeType.PROJECT_INVARIANT)
    r1 = KnowledgeRelation(source_id="k1", target_id="k2", relation_type="SUPPORTS", confidence=0.8)

    projection = GraphProjection.build([k1, k2], [r1])
    projection2 = GraphProjection.build([k1, k2], [r1])

    eval_result = evaluate_graph_projection(
        projection, [k1, k2], [r1], previous_projection=projection2
    )

    assert eval_result.node_coverage == 1.0
    assert eval_result.edge_coverage == 1.0
    assert eval_result.referential_integrity == 1.0
    assert eval_result.determinism_score == 1.0
    assert eval_result.density == 0.5  # E / (V * (V-1)) = 1 / (2 * 1) = 0.5
    assert eval_result.connected_components == 1
    assert eval_result.orphan_count == 0

    passed, failures = check_graph_gates(eval_result)
    assert passed is True
    assert len(failures) == 0
