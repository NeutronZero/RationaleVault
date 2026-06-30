"""Tests for I12.C — Retrieval Evaluator."""
from __future__ import annotations

import pytest

from rationalevault.evaluation.retrieval_evaluator import (
    RetrievalEvalResult,
    RetrievalEvaluator,
    RetrievalTestCase,
    check_retrieval_gates,
    RETRIEVAL_TEST_CORPUS,
)
from rationalevault.evaluation.thresholds import EvaluationThresholds
from rationalevault.retrieval.models import RetrievalIntent, RetrievalPlan
from rationalevault.retrieval.orchestrator import RetrievalOrchestrator


class TestRetrievalEvalResult:
    def test_passes_exit_gate(self) -> None:
        r = RetrievalEvalResult(
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
        r = RetrievalEvalResult(intent_accuracy=0.5)
        passed, failures = r.passes_exit_gate()
        assert not passed
        assert "intent_accuracy" in failures

    def test_to_dict(self) -> None:
        r = RetrievalEvalResult(
            intent_accuracy=1.0,
            projection_selection_accuracy=1.0,
            projection_efficiency=1.0,
            context_weight_accuracy=1.0,
            determinism=1.0,
            availability_handling_accuracy=1.0,
        )
        d = r.to_dict()
        assert "retrieval_orchestration_success_rate" in d
        assert "passed" in d
        assert d["passed"] is True


class TestRetrievalEvaluatorIntentAccuracy:
    def test_continuation_corpus(self) -> None:
        eval_ = RetrievalEvaluator()
        corpus = [
            RetrievalTestCase(query="continue sprint 34", expected_intent="continuation"),
            RetrievalTestCase(query="where I left off last session", expected_intent="continuation"),
        ]
        result = eval_.evaluate(corpus=corpus)
        assert result.intent_accuracy >= 0.8

    def test_knowledge_corpus(self) -> None:
        eval_ = RetrievalEvaluator()
        corpus = [
            RetrievalTestCase(query="what knowledge principle governs this", expected_intent="knowledge_query"),
        ]
        result = eval_.evaluate(corpus=corpus)
        assert result.intent_accuracy >= 0.8

    def test_impact_corpus(self) -> None:
        eval_ = RetrievalEvaluator()
        corpus = [
            RetrievalTestCase(query="what breaks if we change PostgreSQL", expected_intent="impact_analysis"),
        ]
        result = eval_.evaluate(corpus=corpus)
        assert result.intent_accuracy >= 0.8

    def test_general_fallback(self) -> None:
        eval_ = RetrievalEvaluator()
        corpus = [
            RetrievalTestCase(query="hello world", expected_intent="general"),
        ]
        result = eval_.evaluate(corpus=corpus)
        assert result.intent_accuracy >= 0.8


class TestRetrievalEvaluatorProjectionSelection:
    def test_single_intent_selection(self) -> None:
        eval_ = RetrievalEvaluator()
        corpus = [
            RetrievalTestCase(
                query="continue sprint 34",
                expected_intent="continuation",
                expected_projections={"continuation", "knowledge", "graph", "cross_project", "organization", "organization_graph"},
            ),
        ]
        result = eval_.evaluate(corpus=corpus)
        assert result.projection_selection_accuracy >= 0.8

    def test_hybrid_selection(self) -> None:
        eval_ = RetrievalEvaluator()
        corpus = [
            RetrievalTestCase(
                query="continue sprint 34 and show organizational flow",
                expected_intent="continuation",
                expected_projections={"continuation", "knowledge", "graph", "cross_project", "organization", "organization_graph"},
            ),
        ]
        result = eval_.evaluate(corpus=corpus)
        assert result.projection_selection_accuracy >= 0.8


class TestRetrievalEvaluatorProjectionEfficiency:
    def test_no_overselection(self) -> None:
        eval_ = RetrievalEvaluator()
        corpus = [
            RetrievalTestCase(
                query="continue sprint 34",
                expected_intent="continuation",
                expected_projections={"continuation", "knowledge", "graph", "cross_project", "organization", "organization_graph"},
            ),
        ]
        result = eval_.evaluate(corpus=corpus)
        assert result.projection_efficiency >= 0.8

    def test_full_corpus_efficiency(self) -> None:
        eval_ = RetrievalEvaluator()
        result = eval_.evaluate()
        assert result.projection_efficiency >= 0.7


class TestRetrievalEvaluatorDeterminism:
    def test_same_run_same_result(self) -> None:
        eval_ = RetrievalEvaluator()
        corpus = [
            RetrievalTestCase(query="continue sprint 34", expected_intent="continuation"),
        ]
        r1 = eval_.evaluate(corpus=corpus)
        # Re-run same corpus
        r2 = eval_.evaluate(corpus=corpus)
        assert r1.intent_accuracy == r2.intent_accuracy

    def test_previous_plans_determinism(self) -> None:
        eval_ = RetrievalEvaluator()
        orch = RetrievalOrchestrator()
        corpus = [
            RetrievalTestCase(query="continue sprint 34", expected_intent="continuation"),
            RetrievalTestCase(query="knowledge principle", expected_intent="knowledge_query"),
        ]
        plans1 = [orch.build_plan(tc.query) for tc in corpus]
        plans2 = [orch.build_plan(tc.query) for tc in corpus]
        result = eval_.evaluate(corpus=corpus, previous_plans=plans2)
        assert result.determinism == 1.0


class TestRetrievalEvaluatorAvailabilityHandling:
    def test_graceful_degradation(self) -> None:
        eval_ = RetrievalEvaluator()
        result = eval_.evaluate()
        assert result.availability_handling_accuracy >= 0.8


class TestCheckRetrievalGates:
    def test_all_pass(self) -> None:
        r = RetrievalEvalResult(
            intent_accuracy=1.0,
            projection_selection_accuracy=1.0,
            projection_efficiency=1.0,
            context_weight_accuracy=1.0,
            determinism=1.0,
            availability_handling_accuracy=1.0,
        )
        passed, failures = check_retrieval_gates(r)
        assert passed
        assert failures == []

    def test_one_failure(self) -> None:
        r = RetrievalEvalResult(intent_accuracy=0.5)
        passed, failures = check_retrieval_gates(r)
        assert not passed


class TestFullCorpus:
    def test_standard_corpus(self) -> None:
        eval_ = RetrievalEvaluator()
        result = eval_.evaluate()
        d = result.to_dict()
        assert d["passed"] is True, f"Failures: {d['failures']}"
        assert result.intent_accuracy >= 0.8
        assert result.projection_selection_accuracy >= 0.8
        assert result.determinism == 1.0
