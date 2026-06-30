"""Tests for GraphProjectionEvaluator and related I9.5 functionality."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from rationalevault.evaluation.graph_projection_evaluator import (
    GraphProjectionEvaluator,
    GraphProjectionEvalResult,
    check_graph_projection_gates,
)
from rationalevault.evaluation.thresholds import CCS_WEIGHTS, EvaluationThresholds
from rationalevault.projections.graph import GraphProjection, GraphState, GraphNode, GraphEdge
from rationalevault.projections.knowledge import KnowledgeProjection, KnowledgeState, ConflictRecord, _make_conflict_id
from rationalevault.knowledge.models import (
    KnowledgeObject,
    KnowledgeType,
    KnowledgeDomain,
    KnowledgeConfidence,
    KnowledgeLifecycle,
    ProvenanceChain,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

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


def _make_knowledge(
    items: list[tuple[str, str]],
    support: list[tuple[str, str]] | None = None,
    derived: list[tuple[str, str]] | None = None,
    contradictions: list[tuple[str, str]] | None = None,
) -> KnowledgeState:
    """Build a KnowledgeState for testing."""
    knowledge = [_k(kid, title) for kid, title in items]

    support_graph: dict[str, list[str]] = {}
    for src, tgt in (support or []):
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
    )


# ── Tests: conflicted_nodes ─────────────────────────────────────────────────

class TestConflictedNodes:
    def test_contradiction_edges_produce_conflicted_nodes(self):
        ks = _make_knowledge(
            [("a", "A"), ("b", "B")],
            contradictions=[("a", "b")],
        )
        gs = GraphProjection.project(ks)
        assert "a" in gs.conflicted_nodes
        assert "b" in gs.conflicted_nodes

    def test_no_contradictions_empty_conflicted_nodes(self):
        ks = _make_knowledge([("a", "A"), ("b", "B")])
        gs = GraphProjection.project(ks)
        assert len(gs.conflicted_nodes) == 0

    def test_conflicted_nodes_in_to_dict(self):
        ks = _make_knowledge(
            [("a", "A"), ("b", "B")],
            contradictions=[("a", "b")],
        )
        gs = GraphProjection.project(ks)
        d = gs.to_dict()
        assert "conflicted_nodes" in d
        assert "a" in d["conflicted_nodes"]
        assert "b" in d["conflicted_nodes"]


# ── Tests: GraphProjectionEvaluator ─────────────────────────────────────────

class TestGraphProjectionEvaluator:
    def setup_method(self):
        self.evaluator = GraphProjectionEvaluator()

    def test_empty_graph(self):
        ks = _make_knowledge([])
        gs = GraphProjection.project(ks)
        result = self.evaluator.evaluate(gs)
        assert result.graph_connectivity == 1.0
        assert result.referential_integrity == 1.0
        assert result.determinism == 1.0
        assert result.orphan_rate == 0.0
        assert result.adjacency_consistency == 1.0
        assert result.provenance_completeness == 1.0
        assert result.cluster_consistency == 1.0

    def test_clean_graph(self):
        ks = _make_knowledge(
            [("a", "A"), ("b", "B"), ("c", "C")],
            support=[("a", "b"), ("b", "c")],
        )
        gs = GraphProjection.project(ks)
        result = self.evaluator.evaluate(gs)
        assert result.referential_integrity == 1.0
        assert result.adjacency_consistency == 1.0
        assert result.cluster_consistency == 1.0
        assert result.orphan_rate < 0.5

    def test_determinism_with_duplicate(self):
        ks = _make_knowledge(
            [("a", "A"), ("b", "B")],
            support=[("a", "b")],
        )
        gs1 = GraphProjection.project(ks)
        gs2 = GraphProjection.project(ks)
        result = self.evaluator.evaluate(gs1, previous_state=gs2)
        assert result.determinism == 1.0

    def test_determinism_fails_with_different_graph(self):
        ks1 = _make_knowledge([("a", "A"), ("b", "B")], support=[("a", "b")])
        ks2 = _make_knowledge([("a", "A"), ("c", "C")], support=[("a", "c")])
        gs1 = GraphProjection.project(ks1)
        gs2 = GraphProjection.project(ks2)
        result = self.evaluator.evaluate(gs1, previous_state=gs2)
        assert result.determinism == 0.0

    def test_connectivity_single_cluster(self):
        ks = _make_knowledge(
            [("a", "A"), ("b", "B"), ("c", "C")],
            support=[("a", "b"), ("b", "c")],
        )
        gs = GraphProjection.project(ks)
        result = self.evaluator.evaluate(gs)
        assert result.graph_connectivity == 1.0

    def test_connectivity_multiple_clusters(self):
        ks = _make_knowledge(
            [("a", "A"), ("b", "B"), ("c", "C"), ("d", "D")],
            support=[("a", "b")],  # c and d are isolated
        )
        gs = GraphProjection.project(ks)
        result = self.evaluator.evaluate(gs)
        # Largest cluster has 2 nodes out of 4
        assert result.graph_connectivity == 0.5

    def test_provenance_completeness(self):
        ks = _make_knowledge([("a", "A")])
        gs = GraphProjection.project(ks)
        result = self.evaluator.evaluate(gs)
        # a has provenance
        assert result.provenance_completeness == 1.0

    def test_cluster_consistency_disjoint(self):
        ks = _make_knowledge(
            [("a", "A"), ("b", "B"), ("c", "C")],
            support=[("a", "b")],
        )
        gs = GraphProjection.project(ks)
        result = self.evaluator.evaluate(gs)
        assert result.cluster_consistency == 1.0


# ── Tests: Gate checks ──────────────────────────────────────────────────────

class TestGraphProjectionGates:
    def test_gate_pass(self):
        result = GraphProjectionEvalResult(
            graph_connectivity=0.95,
            referential_integrity=1.0,
            determinism=1.0,
            orphan_rate=0.1,
            adjacency_consistency=1.0,
            provenance_completeness=0.9,
            cluster_consistency=1.0,
        )
        passed, failures = check_graph_projection_gates(result)
        assert passed
        assert len(failures) == 0

    def test_gate_fail_connectivity(self):
        result = GraphProjectionEvalResult(
            graph_connectivity=0.5,
            referential_integrity=1.0,
            determinism=1.0,
            orphan_rate=0.1,
            adjacency_consistency=1.0,
            provenance_completeness=0.9,
            cluster_consistency=1.0,
        )
        passed, failures = check_graph_projection_gates(result)
        assert not passed
        assert "graph_connectivity" in failures

    def test_gate_fail_orphan_rate(self):
        result = GraphProjectionEvalResult(
            graph_connectivity=0.95,
            referential_integrity=1.0,
            determinism=1.0,
            orphan_rate=0.5,  # exceeds 0.20 threshold
            adjacency_consistency=1.0,
            provenance_completeness=0.9,
            cluster_consistency=1.0,
        )
        passed, failures = check_graph_projection_gates(result)
        assert not passed
        assert "orphan_rate" in failures

    def test_to_dict_includes_success_rate(self):
        result = GraphProjectionEvalResult(
            graph_connectivity=0.95,
            referential_integrity=1.0,
            determinism=1.0,
            orphan_rate=0.1,
            adjacency_consistency=1.0,
            provenance_completeness=0.9,
            cluster_consistency=1.0,
        )
        d = result.to_dict()
        assert "graph_projection_success_rate" in d
        assert d["graph_projection_success_rate"] >= 0.9


# ── Tests: CCS ──────────────────────────────────────────────────────────────

class TestCCS:
    def test_ccs_weights_sum_to_one(self):
        assert abs(sum(CCS_WEIGHTS.values()) - 1.0) < 0.001

    def test_ccs_weights_keys(self):
        assert "continuation" in CCS_WEIGHTS
        assert "knowledge" in CCS_WEIGHTS
        assert "graph" in CCS_WEIGHTS

    def test_ccs_computation(self):
        # Mock metrics
        continuation_rate = 1.0
        knowledge_rate = 0.95
        graph_rate = 0.9

        ccs = (
            CCS_WEIGHTS["continuation"] * continuation_rate
            + CCS_WEIGHTS["knowledge"] * knowledge_rate
            + CCS_WEIGHTS["graph"] * graph_rate
        )
        expected = 0.4 * 1.0 + 0.3 * 0.95 + 0.3 * 0.9
        assert abs(ccs - expected) < 0.001

    def test_ccs_grade_excellent(self):
        ccs = 0.95
        if ccs >= 0.95:
            grade = "EXCELLENT"
        elif ccs >= 0.85:
            grade = "GOOD"
        elif ccs >= 0.70:
            grade = "FAIR"
        else:
            grade = "POOR"
        assert grade == "EXCELLENT"

    def test_ccs_grade_good(self):
        ccs = 0.90
        if ccs >= 0.95:
            grade = "EXCELLENT"
        elif ccs >= 0.85:
            grade = "GOOD"
        elif ccs >= 0.70:
            grade = "FAIR"
        else:
            grade = "POOR"
        assert grade == "GOOD"

    def test_ccs_grade_fair(self):
        ccs = 0.75
        if ccs >= 0.95:
            grade = "EXCELLENT"
        elif ccs >= 0.85:
            grade = "GOOD"
        elif ccs >= 0.70:
            grade = "FAIR"
        else:
            grade = "POOR"
        assert grade == "FAIR"

    def test_ccs_grade_poor(self):
        ccs = 0.50
        if ccs >= 0.95:
            grade = "EXCELLENT"
        elif ccs >= 0.85:
            grade = "GOOD"
        elif ccs >= 0.70:
            grade = "FAIR"
        else:
            grade = "POOR"
        assert grade == "POOR"


# ── Tests: Thresholds ───────────────────────────────────────────────────────

class TestThresholds:
    def test_gp_thresholds_exist(self):
        t = EvaluationThresholds()
        assert hasattr(t, "MIN_GP_CONNECTIVITY")
        assert hasattr(t, "MIN_GP_REFERENTIAL_INTEGRITY")
        assert hasattr(t, "MIN_GP_DETERMINISM")
        assert hasattr(t, "MIN_GP_ORPHAN_RATE")
        assert hasattr(t, "MIN_GP_ADJACENCY_CONSISTENCY")
        assert hasattr(t, "MIN_GP_PROVENANCE_COMPLETENESS")
        assert hasattr(t, "MIN_GP_CLUSTER_CONSISTENCY")
        assert hasattr(t, "MIN_GP_OVERALL")

    def test_gp_orphan_rate_is_max(self):
        t = EvaluationThresholds()
        # Orphan rate threshold should be a maximum (lower is better)
        assert t.MIN_GP_ORPHAN_RATE <= 0.5


# ── Tests: related_knowledge_ids on TaskState ───────────────────────────────

class TestTaskStateRelatedKnowledgeIds:
    def test_default_empty(self):
        from rationalevault.cognitive_head.reducers import TaskState
        task = TaskState(task_id="t1", title="Test Task")
        assert task.related_knowledge_ids == []

    def test_can_set(self):
        from rationalevault.cognitive_head.reducers import TaskState
        task = TaskState(task_id="t1", title="Test Task", related_knowledge_ids=["k1", "k2"])
        assert task.related_knowledge_ids == ["k1", "k2"]


# ── Tests: Dependency Context in Compilers ──────────────────────────────────

class TestDependencyContext:
    def _make_package_with_graph(self):
        """Create a ContextPackage with graph_state for testing."""
        from rationalevault.knowledge.context_compiler import ContextPackage

        ks = _make_knowledge(
            [("kp", "KnowledgeProjection"), ("gp", "GraphProjection"), ("cp", "ContextPackage")],
            derived=[("gp", "kp"), ("cp", "gp")],
        )
        gs = GraphProjection.project(ks)

        # Mock continuation state
        from rationalevault.cognitive_head.reducers import TaskState
        from rationalevault.projections.continuation import ContinuationState

        task = TaskState(
            task_id="t1",
            title="GraphProjection",
            status="in_progress",
            priority="high",
            related_knowledge_ids=[],
        )

        cont_state = ContinuationState(
            project_id="test",
            project_name="Test",
            project_goal="Test goal",
            current_focus="Testing",
            compiled_at="2026-01-01T00:00:00",
            last_session=None,
            in_progress_tasks=[task],
            open_tasks=[],
            recent_decisions=[],
            open_questions=[],
            blockers=[],
            recent_events=[],
            context_snapshots=[],
            next_actions=[],
            provenance={},
        )

        return ContextPackage(
            context_id="test",
            query="test",
            profile="project_overview",
            created_at="2026-01-01T00:00:00",
            mode="continuation",
            continuation_state=cont_state,
            graph_state=gs,
        )

    def test_claude_compiler_dependency_context(self):
        from rationalevault.compilers.claude_context import ClaudeContextCompiler
        package = self._make_package_with_graph()
        compiler = ClaudeContextCompiler()
        output = compiler.compile(package)
        assert "Dependency Context" in output.rendered_content
        assert "GraphProjection" in output.rendered_content

    def test_opencode_compiler_dependency_context(self):
        from rationalevault.compilers.opencode_context import OpenCodeContextCompiler
        package = self._make_package_with_graph()
        compiler = OpenCodeContextCompiler()
        output = compiler.compile(package)
        assert "Dependency Context" in output.rendered_content

    def test_cursor_compiler_dependency_context(self):
        from rationalevault.compilers.cursor_context import CursorContextCompiler
        package = self._make_package_with_graph()
        compiler = CursorContextCompiler()
        output = compiler.compile(package)
        assert "dependency_context" in output.rendered_content

    def test_dependency_context_empty_when_no_tasks(self):
        from rationalevault.knowledge.context_compiler import ContextPackage
        from rationalevault.projections.continuation import ContinuationState

        ks = _make_knowledge([("a", "A")])
        gs = GraphProjection.project(ks)

        cont_state = ContinuationState(
            project_id="test",
            project_name="Test",
            project_goal="Test goal",
            current_focus="Testing",
            compiled_at="2026-01-01T00:00:00",
            last_session=None,
            in_progress_tasks=[],
            open_tasks=[],
            recent_decisions=[],
            open_questions=[],
            blockers=[],
            recent_events=[],
            context_snapshots=[],
            next_actions=[],
            provenance={},
        )

        package = ContextPackage(
            context_id="test",
            query="test",
            profile="project_overview",
            created_at="2026-01-01T00:00:00",
            mode="continuation",
            continuation_state=cont_state,
            graph_state=gs,
        )

        from rationalevault.compilers.claude_context import ClaudeContextCompiler
        compiler = ClaudeContextCompiler()
        output = compiler.compile(package)
        assert "Dependency Context" not in output.rendered_content

    def test_dependency_context_uses_related_knowledge_ids(self):
        from rationalevault.knowledge.context_compiler import ContextPackage
        from rationalevault.cognitive_head.reducers import TaskState
        from rationalevault.projections.continuation import ContinuationState

        ks = _make_knowledge(
            [("kp", "KnowledgeProjection"), ("gp", "GraphProjection")],
            derived=[("gp", "kp")],
        )
        gs = GraphProjection.project(ks)

        task = TaskState(
            task_id="t1",
            title="Some Task",
            status="in_progress",
            related_knowledge_ids=["gp"],  # explicit link
        )

        cont_state = ContinuationState(
            project_id="test",
            project_name="Test",
            project_goal="Test goal",
            current_focus="Testing",
            compiled_at="2026-01-01T00:00:00",
            last_session=None,
            in_progress_tasks=[task],
            open_tasks=[],
            recent_decisions=[],
            open_questions=[],
            blockers=[],
            recent_events=[],
            context_snapshots=[],
            next_actions=[],
            provenance={},
        )

        package = ContextPackage(
            context_id="test",
            query="test",
            profile="project_overview",
            created_at="2026-01-01T00:00:00",
            mode="continuation",
            continuation_state=cont_state,
            graph_state=gs,
        )

        from rationalevault.compilers.claude_context import ClaudeContextCompiler
        compiler = ClaudeContextCompiler()
        output = compiler.compile(package)
        assert "Dependency Context" in output.rendered_content
        assert "Some Task" in output.rendered_content


# ── RelationType Rejection Tests ─────────────────────────────────────────────

class TestRelationTypeRejection:
    """Verify that RelationType enum rejects invalid values at construction."""

    def test_relation_type_rejects_lowercase(self) -> None:
        from rationalevault.knowledge.relation_types import RelationType
        with pytest.raises(ValueError):
            RelationType("supports")

    def test_relation_type_rejects_arbitrary_string(self) -> None:
        from rationalevault.knowledge.relation_types import RelationType
        with pytest.raises(ValueError):
            RelationType("INVALID_TYPE")

    def test_relation_type_from_str_case_insensitive(self) -> None:
        from rationalevault.knowledge.relation_types import RelationType
        assert RelationType.from_str("supports") == RelationType.SUPPORTS
        assert RelationType.from_str("Contradicts") == RelationType.CONTRADICTS
        assert RelationType.from_str("DERIVED_FROM") == RelationType.DERIVED_FROM

    def test_knowledge_relation_rejects_string(self) -> None:
        from rationalevault.knowledge.models import KnowledgeRelation
        with pytest.raises(TypeError):
            KnowledgeRelation(
                source_id="a", target_id="b",
                relation_type="SUPPORTS",  # type: ignore
                confidence=0.8,
            )

    def test_graph_edge_rejects_string(self) -> None:
        with pytest.raises(TypeError):
            GraphEdge(
                source="a", target="b",
                relation_type="SUPPORTS",  # type: ignore
                confidence=0.8,
            )

    def test_knowledge_edge_rejects_string(self) -> None:
        from rationalevault.knowledge.graph import KnowledgeEdge
        with pytest.raises(TypeError):
            KnowledgeEdge(
                source="a", target="b",
                relation_type="SUPPORTS",  # type: ignore
                confidence=0.8,
            )
