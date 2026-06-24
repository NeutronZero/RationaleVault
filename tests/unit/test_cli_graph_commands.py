"""Tests for CLI graph subcommands: traverse, impact, path."""
from __future__ import annotations

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
from rationalevault.knowledge.relation_types import RelationType
from rationalevault.projections.graph import GraphProjection, GraphState
from rationalevault.projections.knowledge import (
    ConflictRecord,
    KnowledgeHealth,
    KnowledgeState,
    _make_conflict_id,
)


def _conf() -> KnowledgeConfidence:
    return KnowledgeConfidence(
        memory_count=3, source_event_count=2, contradiction_count=0,
        average_memory_confidence=0.9, score=0.9,
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


def _make_ks(
    nodes: list[tuple[str, str]],
    supports: list[tuple[str, str]] | None = None,
    derived: list[tuple[str, str]] | None = None,
    contradictions: list[tuple[str, str]] | None = None,
) -> KnowledgeState:
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


# ── Traverse Tests ───────────────────────────────────────────────────────────

class TestTraverse:
    def test_traverse_returns_subgraph(self):
        ks = _make_ks(
            nodes=[("a", "Alpha"), ("b", "Beta"), ("c", "Gamma")],
            supports=[("a", "b"), ("b", "c")],
        )
        gs = GraphProjection.project(ks)
        result = gs.filtered_traversal("a", max_depth=10)
        assert result.node_count == 3
        assert result.edge_count >= 2  # may have extra edges from detect_relations

    def test_traverse_forward_only(self):
        ks = _make_ks(
            nodes=[("a", "Alpha"), ("b", "Beta"), ("c", "Gamma")],
            supports=[("a", "b"), ("b", "c")],
        )
        gs = GraphProjection.project(ks)
        result = gs.filtered_traversal("c", direction="forward", max_depth=10)
        # c has no outgoing SUPPORTS edges
        assert result.node_count == 1  # only c itself

    def test_traverse_backward_only(self):
        ks = _make_ks(
            nodes=[("a", "Alpha"), ("b", "Beta"), ("c", "Gamma")],
            supports=[("a", "b"), ("b", "c")],
        )
        gs = GraphProjection.project(ks)
        result = gs.filtered_traversal("c", direction="backward", max_depth=10)
        # c is target of b->c, b is target of a->b
        assert result.node_count == 3

    def test_traverse_edge_type_filter(self):
        ks = _make_ks(
            nodes=[("a", "Alpha"), ("b", "Beta"), ("c", "Gamma")],
            supports=[("a", "b")],
            derived=[("c", "a")],
        )
        gs = GraphProjection.project(ks)
        result = gs.filtered_traversal("a", edge_types=[RelationType.SUPPORTS], max_depth=10)
        # a->b via SUPPORTS, but c->a via DERIVED_FROM is excluded
        assert result.node_count == 2  # a and b

    def test_traverse_min_confidence_filter(self):
        ks = _make_ks(
            nodes=[("a", "Alpha"), ("b", "Beta")],
            supports=[("a", "b")],
        )
        gs = GraphProjection.project(ks)
        # All edges have confidence 0.8 from _make_ks
        result = gs.filtered_traversal("a", min_confidence=0.9, max_depth=10)
        assert result.node_count == 1  # only a, b's edge below threshold

    def test_traverse_max_depth(self):
        ks = _make_ks(
            nodes=[("a", "Alpha"), ("b", "Beta"), ("c", "Gamma")],
            supports=[("a", "b"), ("b", "c")],
        )
        gs = GraphProjection.project(ks)
        result = gs.filtered_traversal("a", max_depth=1)
        # a->b at depth 1, b->c at depth 2 (excluded)
        assert result.node_count == 2


# ── Impact Tests ─────────────────────────────────────────────────────────────

class TestImpact:
    def test_impact_returns_upstream_downstream(self):
        ks = _make_ks(
            nodes=[("a", "Alpha"), ("b", "Beta"), ("c", "Gamma")],
            supports=[("a", "b"), ("b", "c")],
        )
        gs = GraphProjection.project(ks)
        result = gs.impact_analysis("b")
        assert "upstream" in result
        assert "downstream" in result
        assert "affected_by_contradiction" in result
        assert "a" in result["upstream"]
        assert "c" in result["downstream"]

    def test_impact_contradiction_analysis(self):
        ks = _make_ks(
            nodes=[("a", "Alpha"), ("b", "Beta"), ("c", "Gamma")],
            supports=[("a", "b")],
            contradictions=[("a", "c")],
        )
        gs = GraphProjection.project(ks)
        result = gs.impact_analysis("a")
        assert "c" in result["affected_by_contradiction"]

    def test_impact_depth_limit(self):
        ks = _make_ks(
            nodes=[("a", "Alpha"), ("b", "Beta"), ("c", "Gamma"), ("d", "Delta")],
            supports=[("a", "b"), ("b", "c"), ("c", "d")],
        )
        gs = GraphProjection.project(ks)
        result = gs.impact_analysis("a", depth=2)
        # BFS skips nodes at max_depth, so depth=2 only includes b (depth 1)
        assert "b" in result["downstream"]
        assert "c" not in result["downstream"]  # at depth 2, skipped
        assert "d" not in result["downstream"]

    def test_impact_relation_type_filter(self):
        ks = _make_ks(
            nodes=[("a", "Alpha"), ("b", "Beta"), ("c", "Gamma")],
            supports=[("a", "b")],
            derived=[("c", "a")],
        )
        gs = GraphProjection.project(ks)
        result = gs.impact_analysis("a", relation_types=[RelationType.SUPPORTS])
        # Only SUPPORTS edges: a->b downstream, nothing upstream via SUPPORTS
        assert "b" in result["downstream"]
        assert "c" not in result["upstream"]  # DERIVED_FROM excluded


# ── Path Tests ───────────────────────────────────────────────────────────────

class TestPath:
    def test_path_finds_all_paths(self):
        ks = _make_ks(
            nodes=[("a", "Alpha"), ("b", "Beta"), ("c", "Gamma")],
            supports=[("a", "b"), ("b", "c")],
        )
        gs = GraphProjection.project(ks)
        paths = gs.all_paths("a", "c")
        assert len(paths) >= 1
        assert paths[0] == ["a", "b", "c"]

    def test_path_no_connection(self):
        ks = _make_ks(
            nodes=[("a", "Alpha"), ("b", "Beta")],
        )
        gs = GraphProjection.project(ks)
        paths = gs.all_paths("a", "b")
        assert len(paths) == 0

    def test_path_multiple_routes(self):
        ks = _make_ks(
            nodes=[("a", "Alpha"), ("b", "Beta"), ("c", "Gamma"), ("d", "Delta")],
            supports=[("a", "b"), ("a", "c"), ("b", "d"), ("c", "d")],
        )
        gs = GraphProjection.project(ks)
        paths = gs.all_paths("a", "d")
        assert len(paths) == 2  # a->b->d and a->c->d

    def test_path_max_depth(self):
        ks = _make_ks(
            nodes=[("a", "Alpha"), ("b", "Beta"), ("c", "Gamma"), ("d", "Delta")],
            supports=[("a", "b"), ("b", "c"), ("c", "d")],
        )
        gs = GraphProjection.project(ks)
        paths = gs.all_paths("a", "d", max_depth=2)
        # a->b->c->d is depth 3, excluded
        assert len(paths) == 0

    def test_path_same_node(self):
        ks = _make_ks(
            nodes=[("a", "Alpha")],
        )
        gs = GraphProjection.project(ks)
        paths = gs.all_paths("a", "a")
        assert paths == [["a"]]


# ── edges_by_relation Tests ──────────────────────────────────────────────────

class TestEdgesByRelation:
    def test_edges_by_relation_prepopulated(self):
        ks = _make_ks(
            nodes=[("a", "Alpha"), ("b", "Beta")],
            supports=[("a", "b")],
        )
        gs = GraphProjection.project(ks)
        # All enum members should be present as keys
        for rt in RelationType:
            assert rt in gs.edges_by_relation

    def test_edges_by_relation_contains_correct_edges(self):
        ks = _make_ks(
            nodes=[("a", "Alpha"), ("b", "Beta"), ("c", "Gamma")],
            supports=[("a", "b")],
            derived=[("c", "a")],
        )
        gs = GraphProjection.project(ks)
        assert len(gs.edges_by_relation[RelationType.SUPPORTS]) == 1
        assert len(gs.edges_by_relation[RelationType.DERIVED_FROM]) == 1
        assert len(gs.edges_by_relation[RelationType.CONTRADICTS]) == 0

    def test_edges_by_relation_is_immutable(self):
        ks = _make_ks(
            nodes=[("a", "Alpha"), ("b", "Beta")],
            supports=[("a", "b")],
        )
        gs = GraphProjection.project(ks)
        # Tuples are immutable
        for rt, edges in gs.edges_by_relation.items():
            assert isinstance(edges, tuple)
