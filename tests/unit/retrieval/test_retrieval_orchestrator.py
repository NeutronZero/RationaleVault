"""Tests for I12.A — Retrieval Models and Orchestrator."""
from __future__ import annotations

import json

import pytest

from rationalevault.retrieval.models import (
    INTENT_KEYWORDS,
    INTENT_PROJECTION_MAP,
    INTENT_WEIGHT_MAP,
    RetrievalIntent,
    RetrievalPlan,
    OrchestrationEvalResult,
)
from rationalevault.retrieval.orchestrator import RetrievalOrchestrator


class TestRetrievalIntent:
    def test_all_intents_have_projections(self) -> None:
        for intent in RetrievalIntent:
            assert intent in INTENT_PROJECTION_MAP

    def test_all_intents_have_weights(self) -> None:
        for intent in RetrievalIntent:
            assert intent in INTENT_WEIGHT_MAP

    def test_all_intents_have_keywords(self) -> None:
        for intent in RetrievalIntent:
            assert intent in INTENT_KEYWORDS

    def test_weight_maps_normalize(self) -> None:
        for intent, weights in INTENT_WEIGHT_MAP.items():
            total = sum(weights.values())
            assert abs(total - 1.0) < 0.02, f"{intent} weights sum to {total}"


class TestRetrievalPlan:
    def test_post_init_normalizes_weights(self) -> None:
        plan = RetrievalPlan(
            primary_intent=RetrievalIntent.GENERAL,
            context_weights={"knowledge": 2.0, "graph": 1.0},
        )
        total = sum(plan.context_weights.values())
        assert abs(total - 1.0) < 0.02

    def test_to_dict(self) -> None:
        plan = RetrievalPlan(
            primary_intent=RetrievalIntent.CONTINUATION,
            matched_intents=[RetrievalIntent.CONTINUATION],
            projections={"continuation": True, "knowledge": True},
            context_weights={"continuation": 0.6, "knowledge": 0.4},
            confidence=0.9,
            reasons=["continuation_keywords_detected"],
        )
        d = plan.to_dict()
        assert d["primary_intent"] == "continuation"
        assert d["confidence"] == 0.9
        serialized = json.dumps(d)
        assert isinstance(serialized, str)


class TestOrchestrationEvalResult:
    def test_passes_exit_gate(self) -> None:
        r = OrchestrationEvalResult(
            intent_accuracy=1.0,
            projection_selection_accuracy=1.0,
            projection_efficiency=1.0,
            context_weight_accuracy=1.0,
            determinism=1.0,
            availability_handling_accuracy=1.0,
        )
        passed, failures = r.passes_exit_gate()
        assert passed
        assert failures == []

    def test_fails_on_low_metric(self) -> None:
        r = OrchestrationEvalResult(
            intent_accuracy=0.5,
            projection_selection_accuracy=1.0,
            projection_efficiency=1.0,
            context_weight_accuracy=1.0,
            determinism=1.0,
            availability_handling_accuracy=1.0,
        )
        passed, failures = r.passes_exit_gate()
        assert not passed
        assert "intent_accuracy" in failures

    def test_to_dict(self) -> None:
        r = OrchestrationEvalResult()
        d = r.to_dict()
        assert "retrieval_orchestration_success_rate" in d
        assert "passed" in d


class TestOrchestratorIntentClassification:
    def test_continuation_query(self) -> None:
        o = RetrievalOrchestrator()
        plan = o.build_plan("continue sprint 34")
        assert plan.primary_intent == RetrievalIntent.CONTINUATION
        assert RetrievalIntent.CONTINUATION in plan.matched_intents

    def test_knowledge_query(self) -> None:
        o = RetrievalOrchestrator()
        plan = o.build_plan("what knowledge principle governs this?")
        assert plan.primary_intent == RetrievalIntent.KNOWLEDGE_QUERY

    def test_impact_analysis(self) -> None:
        o = RetrievalOrchestrator()
        plan = o.build_plan("what breaks if we change PostgreSQL?")
        assert plan.primary_intent == RetrievalIntent.IMPACT_ANALYSIS

    def test_cross_project(self) -> None:
        o = RetrievalOrchestrator()
        plan = o.build_plan("what knowledge is shared across projects?")
        assert RetrievalIntent.CROSS_PROJECT in plan.matched_intents

    def test_organizational(self) -> None:
        o = RetrievalOrchestrator()
        plan = o.build_plan("show organizational lineage flow")
        assert RetrievalIntent.ORGANIZATIONAL in plan.matched_intents

    def test_general_fallback(self) -> None:
        o = RetrievalOrchestrator()
        plan = o.build_plan("hello world")
        assert plan.primary_intent == RetrievalIntent.GENERAL

    def test_hybrid_query(self) -> None:
        o = RetrievalOrchestrator()
        plan = o.build_plan("continue sprint 34 and show shared knowledge across projects")
        assert plan.primary_intent == RetrievalIntent.CONTINUATION
        assert RetrievalIntent.CROSS_PROJECT in plan.matched_intents
        assert len(plan.matched_intents) >= 2


class TestOrchestratorProjectionSelection:
    def test_single_intent_projections(self) -> None:
        o = RetrievalOrchestrator()
        plan = o.build_plan("continue sprint 34")
        assert plan.projections.get("continuation") is True
        assert plan.projections.get("knowledge") is True
        assert plan.projections.get("graph") is True

    def test_hybrid_merges_projections(self) -> None:
        o = RetrievalOrchestrator()
        plan = o.build_plan("continue sprint 34 and show organizational flow")
        assert plan.projections.get("continuation") is True
        assert plan.projections.get("organization") is True

    def test_availability_filtering(self) -> None:
        o = RetrievalOrchestrator()
        plan = o.build_plan(
            "what is shared across projects?",
            available_projections={"cross_project": False, "organization": False},
        )
        assert plan.projections.get("cross_project") is False
        assert plan.projections.get("organization") is False
        assert plan.requested_projections.get("cross_project") is True

    def test_availability_reasons(self) -> None:
        o = RetrievalOrchestrator()
        plan = o.build_plan(
            "what is shared across projects?",
            available_projections={"cross_project": False, "organization": False},
        )
        assert any("cross_project_requested_but_unavailable" in r for r in plan.reasons)


class TestOrchestratorWeights:
    def test_single_intent_weights(self) -> None:
        o = RetrievalOrchestrator()
        plan = o.build_plan("continue sprint 34")
        total = sum(plan.context_weights.values())
        assert abs(total - 1.0) < 0.02

    def test_hybrid_weights_normalize(self) -> None:
        o = RetrievalOrchestrator()
        plan = o.build_plan("continue sprint 34 and show organizational flow")
        total = sum(plan.context_weights.values())
        assert abs(total - 1.0) < 0.02

    def test_weights_only_selected_projections(self) -> None:
        o = RetrievalOrchestrator()
        plan = o.build_plan("continue sprint 34")
        # Continuation lightly weights organization projections
        assert plan.context_weights.get("organization", 0.0) > 0.0


class TestOrchestratorConfidence:
    def test_high_confidence_for_specific_query(self) -> None:
        o = RetrievalOrchestrator()
        plan = o.build_plan("continue sprint 34 resume session")
        assert plan.confidence >= 0.7

    def test_low_confidence_for_general(self) -> None:
        o = RetrievalOrchestrator()
        plan = o.build_plan("hello")
        assert plan.confidence <= 0.6


class TestOrchestratorDeterminism:
    def test_same_query_same_plan(self) -> None:
        o = RetrievalOrchestrator()
        p1 = o.build_plan("continue sprint 34")
        p2 = o.build_plan("continue sprint 34")
        assert p1.primary_intent == p2.primary_intent
        assert p1.matched_intents == p2.matched_intents
        assert p1.projections == p2.projections
        assert p1.context_weights == p2.context_weights

    def test_to_dict_deterministic(self) -> None:
        o = RetrievalOrchestrator()
        d1 = o.build_plan("continue sprint 34").to_dict()
        d2 = o.build_plan("continue sprint 34").to_dict()
        assert d1 == d2
