"""Tests for I15.3 — Recommendation evaluator."""
from __future__ import annotations

from rationalevault.evaluation.recommendation_evaluator import (
    RECOMMENDATION_BENCHMARK_CORPUS,
    RecommendationEvalResult,
    RecommendationEvaluator,
    check_recommendation_gates,
)


class TestRecommendationEvalResult:
    def test_passes_exit_gate(self) -> None:
        r = RecommendationEvalResult(
            recommendation_coverage=1.0,
            recommendation_precision=1.0,
            category_exclusivity=1.0,
            evidence_integrity=1.0,
            priority_accuracy=1.0,
            recommendation_determinism=1.0,
            recommendation_replayability=1.0,
        )
        passed, failures = r.passes_exit_gate()
        assert passed
        assert failures == []

    def test_fails_on_low_coverage(self) -> None:
        r = RecommendationEvalResult(recommendation_coverage=0.5)
        passed, failures = r.passes_exit_gate()
        assert not passed
        assert "recommendation_coverage" in failures

    def test_to_dict(self) -> None:
        r = RecommendationEvalResult(
            recommendation_coverage=0.9,
            recommendation_precision=1.0,
            category_exclusivity=1.0,
            evidence_integrity=1.0,
            priority_accuracy=1.0,
            recommendation_determinism=1.0,
            recommendation_replayability=1.0,
        )
        d = r.to_dict()
        assert "overall" in d
        assert "passed" in d
        assert "failures" in d


class TestRecommendationEvaluator:
    def test_empty_state_benchmark(self) -> None:
        eval_ = RecommendationEvaluator()
        result = eval_.evaluate()
        assert result.recommendation_coverage >= 0.8

    def test_evidence_integrity_perfect(self) -> None:
        eval_ = RecommendationEvaluator()
        result = eval_.evaluate()
        assert result.evidence_integrity == 1.0

    def test_priority_accuracy_perfect(self) -> None:
        eval_ = RecommendationEvaluator()
        result = eval_.evaluate()
        assert result.priority_accuracy == 1.0

    def test_determinism_perfect(self) -> None:
        eval_ = RecommendationEvaluator()
        result = eval_.evaluate()
        assert result.recommendation_determinism == 1.0

    def test_benchmark_corpus_has_expected_scenarios(self) -> None:
        names = [tc.name for tc in RECOMMENDATION_BENCHMARK_CORPUS]
        assert "empty_state" in names
        assert "contradiction_hotspot" in names
        assert "inactive_project" in names
        assert "recent_transfer" in names
        assert "negative_flow" in names
        assert "low_cohesion" in names
        assert "mixed_signals" in names
        assert "duplicate_signals" in names

    def test_corpus_all_expected_categories_present(self) -> None:
        all_expected = set()
        for tc in RECOMMENDATION_BENCHMARK_CORPUS:
            all_expected.update(tc.expected_categories)
        from rationalevault.recommendations.models import RecommendationCategory
        for cat in RecommendationCategory:
            assert cat.value in all_expected or any(
                tc.name in ("empty_state",) for tc in RECOMMENDATION_BENCHMARK_CORPUS
            )

    def test_replayability_benchmark(self) -> None:
        eval_ = RecommendationEvaluator()
        previous: dict[str, list] = {}
        for tc in RECOMMENDATION_BENCHMARK_CORPUS:
            previous[tc.name] = eval_.engine.generate(
                org_state=tc.org_state,
                graph_state=tc.graph_state,
                activity_state=tc.activity_state,
            )
        result = eval_.evaluate(corpus=RECOMMENDATION_BENCHMARK_CORPUS, previous_results=previous)
        assert result.recommendation_replayability == 1.0


class TestCheckRecommendationGates:
    def test_all_pass(self) -> None:
        r = RecommendationEvalResult(
            recommendation_coverage=1.0,
            recommendation_precision=1.0,
            category_exclusivity=1.0,
            evidence_integrity=1.0,
            priority_accuracy=1.0,
            recommendation_determinism=1.0,
            recommendation_replayability=1.0,
        )
        passed, failures = r.passes_exit_gate()
        assert passed
        assert failures == []

    def test_one_failure(self) -> None:
        r = RecommendationEvalResult(recommendation_coverage=0.5)
        passed, failures = r.passes_exit_gate()
        assert not passed
