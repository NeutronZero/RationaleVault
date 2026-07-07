"""Tests for I15.2 — Recommendation engine."""
from __future__ import annotations

from rationalevault.organization.activity import OrganizationActivityState
from rationalevault.organization.graph import (
    OrganizationGraphHealth,
    OrganizationGraphState,
)
from rationalevault.organization.models import OrganizationState
from rationalevault.organization.recommendations.engine import (
    FLOW_IMBALANCE_THRESHOLD,
    MIN_CLUSTER_COHESION_FOR_REVIEW,
    MIN_INVARIANT_COUNT_FOR_REVIEW,
    RecommendationEngine,
)
from rationalevault.organization.recommendations.models import RecommendationCategory


def _empty_activity() -> OrganizationActivityState:
    return OrganizationActivityState(
        compiled_at="",
        inactive_projects=[],
        active_projects=[],
        project_count=0,
    )


def _empty_graph() -> OrganizationGraphState:
    return OrganizationGraphState(
        compiled_at="",
        clusters=[],
        contradiction_hotspots=[],
        knowledge_flow_balance={},
        health=OrganizationGraphHealth(cluster_cohesion=1.0),
    )


def _empty_org() -> OrganizationState:
    return OrganizationState(
        compiled_at="",
        invariants_across_projects=[],
    )


class TestRecommendationEngineEmpty:
    def test_no_states_produces_empty(self) -> None:
        rs = RecommendationEngine.generate()
        assert rs.recommendation_count == 0
        assert rs.attention_load == 0.0
        assert len(rs.recommendations) == 0

    def test_healthy_states_produce_empty(self) -> None:
        rs = RecommendationEngine.generate(
            activity_state=_empty_activity(),
            graph_state=_empty_graph(),
            org_state=_empty_org(),
        )
        assert rs.recommendation_count == 0
        assert rs.attention_load == 0.0
        assert len(rs.recommendations) == 0


class TestConflictResolution:
    def test_hotspot_generates_recommendation(self) -> None:
        gs = _empty_graph()
        gs.contradiction_hotspots = [("p1", 3.0)]
        rs = RecommendationEngine.generate(graph_state=gs)
        categories = {r.category for r in rs.recommendations}
        assert RecommendationCategory.CONFLICT_RESOLUTION in categories

    def test_hotspot_evidence_id(self) -> None:
        gs = _empty_graph()
        gs.contradiction_hotspots = [("p1", 3.0)]
        rs = RecommendationEngine.generate(graph_state=gs)
        rec = [r for r in rs.recommendations if r.category == RecommendationCategory.CONFLICT_RESOLUTION][0]
        assert any("hotspot:p1" in eid for eid in rec.evidence_ids)

    def test_no_hotspot_no_recommendation(self) -> None:
        rs = RecommendationEngine.generate(graph_state=_empty_graph())
        cats = {r.category for r in rs.recommendations}
        assert RecommendationCategory.CONFLICT_RESOLUTION not in cats

    def test_multiple_hotspots(self) -> None:
        gs = _empty_graph()
        gs.contradiction_hotspots = [("p1", 2.0), ("p2", 1.0)]
        rs = RecommendationEngine.generate(graph_state=gs)
        assert rs.recommendation_count == 2
        for rec in rs.recommendations:
            assert rec.category == RecommendationCategory.CONFLICT_RESOLUTION

    def test_duplicate_hotspot_deduplicated(self) -> None:
        gs = _empty_graph()
        gs.contradiction_hotspots = [("p1", 2.0), ("p1", 3.0)]
        rs = RecommendationEngine.generate(graph_state=gs)
        conflict_recs = [r for r in rs.recommendations if r.category == RecommendationCategory.CONFLICT_RESOLUTION]
        assert len(conflict_recs) == 1


class TestInactivityReview:
    def test_inactive_generates_recommendation(self) -> None:
        act = _empty_activity()
        act.inactive_projects = ["p1"]
        rs = RecommendationEngine.generate(activity_state=act)
        cats = {r.category for r in rs.recommendations}
        assert RecommendationCategory.INACTIVITY_REVIEW in cats

    def test_inactive_evidence_id(self) -> None:
        act = _empty_activity()
        act.inactive_projects = ["p1"]
        rs = RecommendationEngine.generate(activity_state=act)
        rec = [r for r in rs.recommendations if r.category == RecommendationCategory.INACTIVITY_REVIEW][0]
        assert any("inactive:p1" in eid for eid in rec.evidence_ids)

    def test_no_inactive_no_recommendation(self) -> None:
        rs = RecommendationEngine.generate(activity_state=_empty_activity())
        cats = {r.category for r in rs.recommendations}
        assert RecommendationCategory.INACTIVITY_REVIEW not in cats

    def test_multiple_inactive(self) -> None:
        act = _empty_activity()
        act.inactive_projects = ["p1", "p2"]
        rs = RecommendationEngine.generate(activity_state=act)
        inactive_recs = [r for r in rs.recommendations if r.category == RecommendationCategory.INACTIVITY_REVIEW]
        assert len(inactive_recs) == 2


class TestTransferFollowup:
    def test_transfer_generates_recommendation(self) -> None:
        act = _empty_activity()
        act.recent_transfers = [
            type("Transfer", (), {"knowledge_id": "k1", "knowledge_title": "Pattern X",
                                 "source_project": "p1", "target_project": "p2"})()
        ]
        rs = RecommendationEngine.generate(activity_state=act)
        cats = {r.category for r in rs.recommendations}
        assert RecommendationCategory.TRANSFER_FOLLOWUP in cats

    def test_transfer_evidence_id(self) -> None:
        act = _empty_activity()
        act.recent_transfers = [
            type("Transfer", (), {"knowledge_id": "k1", "knowledge_title": "Pattern X",
                                 "source_project": "p1", "target_project": "p2"})()
        ]
        rs = RecommendationEngine.generate(activity_state=act)
        rec = [r for r in rs.recommendations if r.category == RecommendationCategory.TRANSFER_FOLLOWUP][0]
        assert any("transfer:k1" in eid for eid in rec.evidence_ids)

    def test_no_transfer_no_recommendation(self) -> None:
        rs = RecommendationEngine.generate(activity_state=_empty_activity())
        cats = {r.category for r in rs.recommendations}
        assert RecommendationCategory.TRANSFER_FOLLOWUP not in cats


class TestFlowRebalancing:
    def test_imbalanced_flow_generates_recommendation(self) -> None:
        gs = _empty_graph()
        gs.knowledge_flow_balance = {"p1": -5}
        rs = RecommendationEngine.generate(graph_state=gs)
        cats = {r.category for r in rs.recommendations}
        assert RecommendationCategory.FLOW_REBALANCING in cats

    def test_flow_evidence_id(self) -> None:
        gs = _empty_graph()
        gs.knowledge_flow_balance = {"p1": -5}
        rs = RecommendationEngine.generate(graph_state=gs)
        rec = [r for r in rs.recommendations if r.category == RecommendationCategory.FLOW_REBALANCING][0]
        assert any("flow:p1" in eid for eid in rec.evidence_ids)

    def test_mild_imbalance_no_recommendation(self) -> None:
        gs = _empty_graph()
        gs.knowledge_flow_balance = {"p1": -2}
        rs = RecommendationEngine.generate(graph_state=gs)
        cats = {r.category for r in rs.recommendations}
        assert RecommendationCategory.FLOW_REBALANCING not in cats

    def test_no_flow_no_recommendation(self) -> None:
        rs = RecommendationEngine.generate(graph_state=_empty_graph())
        cats = {r.category for r in rs.recommendations}
        assert RecommendationCategory.FLOW_REBALANCING not in cats

    def test_positive_flow_no_recommendation(self) -> None:
        gs = _empty_graph()
        gs.knowledge_flow_balance = {"p1": 10}
        rs = RecommendationEngine.generate(graph_state=gs)
        cats = {r.category for r in rs.recommendations}
        assert RecommendationCategory.FLOW_REBALANCING not in cats


class TestClusterHealth:
    def test_low_cohesion_generates_recommendation(self) -> None:
        gs = _empty_graph()
        gs.clusters = [["p1", "p2"]]
        gs.health.cluster_cohesion = 0.3
        rs = RecommendationEngine.generate(graph_state=gs)
        cats = {r.category for r in rs.recommendations}
        assert RecommendationCategory.CLUSTER_HEALTH in cats

    def test_no_clusters_no_recommendation(self) -> None:
        gs = _empty_graph()
        gs.health.cluster_cohesion = 0.3
        rs = RecommendationEngine.generate(graph_state=gs)
        cats = {r.category for r in rs.recommendations}
        assert RecommendationCategory.CLUSTER_HEALTH not in cats

    def test_high_cohesion_no_recommendation(self) -> None:
        gs = _empty_graph()
        gs.clusters = [["p1", "p2"]]
        gs.health.cluster_cohesion = 0.8
        rs = RecommendationEngine.generate(graph_state=gs)
        cats = {r.category for r in rs.recommendations}
        assert RecommendationCategory.CLUSTER_HEALTH not in cats


class TestInvariantReview:
    def test_few_invariants_no_recommendation(self) -> None:
        org = _empty_org()
        from rationalevault.organization.models import SharedKnowledge
        org.invariants_across_projects = [
            SharedKnowledge(knowledge_id="inv-1", title="Inv A", knowledge_type="PROJECT_INVARIANT"),
        ]
        rs = RecommendationEngine.generate(org_state=org)
        cats = {r.category for r in rs.recommendations}
        assert RecommendationCategory.INVARIANT_REVIEW not in cats

    def test_many_invariants_generates_recommendation(self) -> None:
        org = _empty_org()
        from rationalevault.organization.models import SharedKnowledge
        org.invariants_across_projects = [
            SharedKnowledge(knowledge_id=f"inv-{i}", title=f"Inv {i}", knowledge_type="PROJECT_INVARIANT")
            for i in range(MIN_INVARIANT_COUNT_FOR_REVIEW)
        ]
        rs = RecommendationEngine.generate(org_state=org)
        cats = {r.category for r in rs.recommendations}
        assert RecommendationCategory.INVARIANT_REVIEW in cats

    def test_invariant_evidence_id(self) -> None:
        org = _empty_org()
        from rationalevault.organization.models import SharedKnowledge
        org.invariants_across_projects = [
            SharedKnowledge(knowledge_id="inv-1", title="Inv A", knowledge_type="PROJECT_INVARIANT",
                           present_in_projects=["p1", "p2"]),
            SharedKnowledge(knowledge_id="inv-2", title="Inv B", knowledge_type="PROJECT_INVARIANT",
                           present_in_projects=["p3"]),
            SharedKnowledge(knowledge_id="inv-3", title="Inv C", knowledge_type="PROJECT_INVARIANT",
                           present_in_projects=["p1"]),
        ]
        rs = RecommendationEngine.generate(org_state=org)
        rec = [r for r in rs.recommendations if r.category == RecommendationCategory.INVARIANT_REVIEW][0]
        assert any("invariant:inv-1" in eid for eid in rec.evidence_ids)


class TestSorting:
    def test_recommendations_sorted_by_priority(self) -> None:
        act = _empty_activity()
        act.inactive_projects = ["p1", "p2"]
        gs = _empty_graph()
        gs.contradiction_hotspots = [("p3", 2.0)]
        rs = RecommendationEngine.generate(activity_state=act, graph_state=gs)
        assert rs.recommendation_count >= 2
        for i in range(len(rs.recommendations) - 1):
            assert rs.recommendations[i].priority <= rs.recommendations[i + 1].priority

    def test_conflict_before_inactive(self) -> None:
        act = _empty_activity()
        act.inactive_projects = ["p1"]
        gs = _empty_graph()
        gs.contradiction_hotspots = [("p2", 2.0)]
        rs = RecommendationEngine.generate(activity_state=act, graph_state=gs)
        assert rs.recommendations[0].category == RecommendationCategory.CONFLICT_RESOLUTION


class TestDeduplication:
    def test_identical_signals_deduplicated(self) -> None:
        gs = _empty_graph()
        gs.contradiction_hotspots = [("p1", 2.0), ("p1", 3.0)]
        rs = RecommendationEngine.generate(graph_state=gs)
        conflict_recs = [r for r in rs.recommendations if r.category == RecommendationCategory.CONFLICT_RESOLUTION]
        assert len(conflict_recs) == 1


class TestDeterminism:
    def test_same_inputs_same_output(self) -> None:
        act = _empty_activity()
        act.inactive_projects = ["p1"]
        gs = _empty_graph()
        gs.contradiction_hotspots = [("p2", 2.0)]
        org = _empty_org()

        rs1 = RecommendationEngine.generate(activity_state=act, graph_state=gs, org_state=org)
        rs2 = RecommendationEngine.generate(activity_state=act, graph_state=gs, org_state=org)

        s1 = [r.to_dict() for r in rs1.recommendations]
        s2 = [r.to_dict() for r in rs2.recommendations]
        assert s1 == s2

    def test_deterministic_compiled_at(self) -> None:
        """Only compiled_at should differ between runs — recommendations are the same."""
        act = _empty_activity()
        act.inactive_projects = ["p1"]
        gs = _empty_graph()
        gs.contradiction_hotspots = [("p2", 2.0)]

        rs1 = RecommendationEngine.generate(activity_state=act, graph_state=gs)
        rs2 = RecommendationEngine.generate(activity_state=act, graph_state=gs)

        assert rs1.compiled_at != rs2.compiled_at
        assert [r.recommendation_id for r in rs1.recommendations] == [r.recommendation_id for r in rs2.recommendations]
