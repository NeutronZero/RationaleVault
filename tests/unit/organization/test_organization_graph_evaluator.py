"""Tests for I13.B — Organization Graph Evaluator."""
from __future__ import annotations

import pytest

from rationalevault.evaluation.organization_graph_evaluator import (
    OrganizationGraphEvalResult,
    OrganizationGraphEvaluator,
    check_organization_graph_gates,
)
from rationalevault.organization.graph import OrganizationGraphProjection
from rationalevault.organization.models import (
    CrossProjectConflict,
    KnowledgeLineage,
    OrganizationState,
    SharedKnowledge,
)


def _make_lineage(kid: str, origin: str, current: list[str]) -> KnowledgeLineage:
    return KnowledgeLineage(
        knowledge_id=kid, origin_project=origin,
        current_projects=current, transfer_path=[origin] + current, depth=len(current),
    )


def _make_shared(kid: str, title: str, projects: list[str]) -> SharedKnowledge:
    return SharedKnowledge(
        knowledge_id=kid, title=title, knowledge_type="principle",
        present_in_projects=projects, transfer_count=len(projects) - 1,
    )


def _make_conflict(pa: str, pb: str, confidence: float = 0.8) -> CrossProjectConflict:
    return CrossProjectConflict(
        conflict_id=f"{pa}_{pb}", knowledge_a_id=f"k_{pa}", knowledge_b_id=f"k_{pb}",
        project_a=pa, project_b=pb, knowledge_a_title="A", knowledge_b_title="B",
        confidence=confidence, reasons=["lexical_similarity"],
    )


class TestOrganizationGraphEvalResult:
    def test_passes_exit_gate(self) -> None:
        r = OrganizationGraphEvalResult(
            connectivity=1.0, referential_integrity=1.0, determinism=1.0,
            edge_completeness=1.0, cluster_consistency=1.0,
            metadata_accuracy=1.0, flow_balance_accuracy=1.0,
        )
        passed, failures = r.passes_exit_gate()
        assert passed
        assert failures == []

    def test_fails_on_low_metric(self) -> None:
        r = OrganizationGraphEvalResult(connectivity=0.3)
        passed, failures = r.passes_exit_gate()
        assert not passed
        assert "connectivity" in failures

    def test_to_dict(self) -> None:
        r = OrganizationGraphEvalResult(
            connectivity=1.0, referential_integrity=1.0, determinism=1.0,
            edge_completeness=1.0, cluster_consistency=1.0,
            metadata_accuracy=1.0, flow_balance_accuracy=1.0,
        )
        d = r.to_dict()
        assert "org_graph_success_rate" in d
        assert d["passed"] is True


class TestOrganizationGraphEvaluatorConnectivity:
    def test_single_project(self) -> None:
        org = OrganizationState(compiled_at="2025-01-01", project_ids=["a"])
        graph = OrganizationGraphProjection.project(org)
        eval_ = OrganizationGraphEvaluator()
        result = eval_.evaluate(graph, org)
        assert result.connectivity == 1.0

    def test_connected_graph(self) -> None:
        org = OrganizationState(
            compiled_at="2025-01-01", project_ids=["a", "b", "c"],
            active_lineages={
                "k1": _make_lineage("k1", "a", ["b"]),
                "k2": _make_lineage("k2", "b", ["c"]),
            },
        )
        graph = OrganizationGraphProjection.project(org)
        eval_ = OrganizationGraphEvaluator()
        result = eval_.evaluate(graph, org)
        assert result.connectivity == 1.0

    def test_disconnected_graph(self) -> None:
        org = OrganizationState(compiled_at="2025-01-01", project_ids=["a", "b"])
        graph = OrganizationGraphProjection.project(org)
        eval_ = OrganizationGraphEvaluator()
        result = eval_.evaluate(graph, org)
        assert result.connectivity == 0.5  # only 'a' reachable from 'a'


class TestOrganizationGraphEvaluatorReferentialIntegrity:
    def test_all_edges_valid(self) -> None:
        org = OrganizationState(
            compiled_at="2025-01-01", project_ids=["a", "b"],
            active_lineages={"k1": _make_lineage("k1", "a", ["b"])},
        )
        graph = OrganizationGraphProjection.project(org)
        eval_ = OrganizationGraphEvaluator()
        result = eval_.evaluate(graph, org)
        assert result.referential_integrity == 1.0


class TestOrganizationGraphEvaluatorDeterminism:
    def test_same_projection(self) -> None:
        org = OrganizationState(
            compiled_at="2025-01-01", project_ids=["a", "b"],
            active_lineages={"k1": _make_lineage("k1", "a", ["b"])},
        )
        g1 = OrganizationGraphProjection.project(org)
        g2 = OrganizationGraphProjection.project(org)
        eval_ = OrganizationGraphEvaluator()
        result = eval_.evaluate(g1, org, previous_graph_state=g2)
        assert result.determinism == 1.0


class TestOrganizationGraphEvaluatorEdgeCompleteness:
    def test_all_transfers_found(self) -> None:
        org = OrganizationState(
            compiled_at="2025-01-01", project_ids=["a", "b"],
            active_lineages={"k1": _make_lineage("k1", "a", ["b"])},
        )
        graph = OrganizationGraphProjection.project(org)
        eval_ = OrganizationGraphEvaluator()
        result = eval_.evaluate(graph, org)
        assert result.edge_completeness == 1.0

    def test_all_conflicts_found(self) -> None:
        org = OrganizationState(
            compiled_at="2025-01-01", project_ids=["a", "b"],
            cross_project_conflicts=[_make_conflict("a", "b")],
        )
        graph = OrganizationGraphProjection.project(org)
        eval_ = OrganizationGraphEvaluator()
        result = eval_.evaluate(graph, org)
        assert result.edge_completeness == 1.0


class TestOrganizationGraphEvaluatorClusterConsistency:
    def test_clusters_match(self) -> None:
        org = OrganizationState(
            compiled_at="2025-01-01", project_ids=["a", "b", "c"],
            project_clusters=[["a", "b", "c"]],
            active_lineages={
                "k1": _make_lineage("k1", "a", ["a", "b"]),
                "k2": _make_lineage("k2", "b", ["b", "c"]),
            },
        )
        graph = OrganizationGraphProjection.project(org)
        eval_ = OrganizationGraphEvaluator()
        result = eval_.evaluate(graph, org)
        assert result.cluster_consistency == 1.0

    def test_no_clusters(self) -> None:
        org = OrganizationState(compiled_at="2025-01-01", project_ids=["a", "b"])
        graph = OrganizationGraphProjection.project(org)
        eval_ = OrganizationGraphEvaluator()
        result = eval_.evaluate(graph, org)
        assert result.cluster_consistency == 1.0


class TestOrganizationGraphEvaluatorMetadataAccuracy:
    def test_metadata_matches(self) -> None:
        org = OrganizationState(
            compiled_at="2025-01-01", project_ids=["a", "b"],
            active_lineages={"k1": _make_lineage("k1", "a", ["b"])},
        )
        graph = OrganizationGraphProjection.project(org)
        eval_ = OrganizationGraphEvaluator()
        result = eval_.evaluate(graph, org)
        assert result.metadata_accuracy == 1.0


class TestOrganizationGraphEvaluatorFlowBalance:
    def test_flow_balance_accurate(self) -> None:
        org = OrganizationState(
            compiled_at="2025-01-01", project_ids=["a", "b", "c"],
            active_lineages={
                "k1": _make_lineage("k1", "a", ["b"]),
                "k2": _make_lineage("k2", "a", ["c"]),
            },
        )
        graph = OrganizationGraphProjection.project(org)
        eval_ = OrganizationGraphEvaluator()
        result = eval_.evaluate(graph, org)
        assert result.flow_balance_accuracy == 1.0


class TestCheckOrganizationGraphGates:
    def test_all_pass(self) -> None:
        r = OrganizationGraphEvalResult(
            connectivity=1.0, referential_integrity=1.0, determinism=1.0,
            edge_completeness=1.0, cluster_consistency=1.0,
            metadata_accuracy=1.0, flow_balance_accuracy=1.0,
        )
        passed, failures = check_organization_graph_gates(r)
        assert passed

    def test_one_failure(self) -> None:
        r = OrganizationGraphEvalResult(connectivity=0.3)
        passed, failures = check_organization_graph_gates(r)
        assert not passed


class TestFullEvaluation:
    def test_full_org_graph(self) -> None:
        org = OrganizationState(
            compiled_at="2025-01-01",
            project_ids=["a", "b", "c", "d"],
            active_lineages={
                "k1": _make_lineage("k1", "a", ["b"]),
                "k2": _make_lineage("k2", "a", ["c"]),
                "k3": _make_lineage("k3", "b", ["d"]),
            },
            shared_knowledge=[
                _make_shared("k1", "Knowledge 1", ["a", "b"]),
            ],
            cross_project_conflicts=[_make_conflict("a", "d")],
            project_clusters=[["a", "b", "c", "d"]],
        )
        graph = OrganizationGraphProjection.project(org)
        eval_ = OrganizationGraphEvaluator()
        result = eval_.evaluate(graph, org)
        d = result.to_dict()
        assert d["passed"] is True, f"Failures: {d['failures']}"
        assert result.referential_integrity == 1.0
        assert result.determinism == 1.0
        assert result.flow_balance_accuracy == 1.0
