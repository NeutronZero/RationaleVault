from __future__ import annotations

import json
import pytest
from rationalevault.evaluation.retrieval_evaluator import (
    RetrievalRankingEvaluator,
    RankingCalibrator,
    build_test_corpus,
    RetrievalMetrics,
    SignalMetrics,
    RegressionMetrics
)
from rationalevault.memory.hybrid_ranker import RankingConfig


def test_metrics_computation() -> None:
    # 1. Test MRR computation
    assert RetrievalRankingEvaluator.compute_mrr(["doc-a", "doc-b"], ["doc-b"]) == 0.5
    assert RetrievalRankingEvaluator.compute_mrr(["doc-a", "doc-b"], ["doc-c"]) == 0.0
    assert RetrievalRankingEvaluator.compute_mrr([], ["doc-a"]) == 0.0
    assert RetrievalRankingEvaluator.compute_mrr(["doc-a"], []) == 0.0

    # 2. Test Recall@K
    assert RetrievalRankingEvaluator.compute_recall_at_k(["doc-a", "doc-b"], ["doc-b", "doc-c"], 2) == 0.5
    assert RetrievalRankingEvaluator.compute_recall_at_k(["doc-a", "doc-b"], ["doc-c"], 2) == 0.0
    assert RetrievalRankingEvaluator.compute_recall_at_k(["doc-a", "doc-b"], [], 2) == 0.0


def test_empty_dataset_graceful_handling() -> None:
    evaluator = RetrievalRankingEvaluator()
    empty_dataset = {"dataset_version": "1.0.0", "cases": []}
    records, graph_state = build_test_corpus()

    report = evaluator.evaluate(empty_dataset, records, graph_state)
    assert report.dataset_version == "1.0.0"
    assert len(report.benchmark_results) == 0
    assert report.metrics.mrr == 0.0
    assert report.regression_metrics.regressed == 0


def test_schema_malformed_fail_fast() -> None:
    evaluator = RetrievalRankingEvaluator()
    records, graph_state = build_test_corpus()

    # Query key missing in one of the cases
    malformed_dataset = {
        "dataset_version": "1.0.0",
        "cases": [
            {"expected": ["doc-a"]} # Missing query
        ]
    }
    with pytest.raises(KeyError):
        evaluator.evaluate(malformed_dataset, records, graph_state)


def test_deterministic_calibration() -> None:
    records, graph_state = build_test_corpus()
    dataset = {
        "dataset_version": "1.0.0",
        "cases": [
            {
                "query": "continue sprint 34 where I left off",
                "expected": ["mem-continuation-s34"],
                "intent": "continuation",
                "difficulty": "easy"
            }
        ]
    }
    calibrator = RankingCalibrator()
    report1 = calibrator.calibrate(dataset, records, graph_state)
    report2 = calibrator.calibrate(dataset, records, graph_state)

    assert report1.best_config == report2.best_config
    assert report1.summary.total_experiments == report2.summary.total_experiments


def test_equal_configurations_tie_breaking() -> None:
    # Set up a dataset where all configurations yield identical scores/MRR
    # Verify deterministic tie-breaking picks the config with higher weight priority
    records, graph_state = build_test_corpus()
    dataset = {
        "dataset_version": "1.0.0",
        "cases": [
            {
                "query": "no match query",
                "expected": ["non-existent"],
                "intent": "general"
            }
        ]
    }
    calibrator = RankingCalibrator()
    report = calibrator.calibrate(dataset, records, graph_state)

    # With no matches, all configs yield 0.0 MRR.
    # Tie-breaking logic prefers larger lexical, then graph, then priority weights.
    # The highest values in choices [0.0, ..., 1.0] should be 1.0, 1.0, 1.0.
    assert report.best_config.lexical_weight == 1.0
    assert report.best_config.graph_weight == 1.0
    assert report.best_config.priority_weight == 1.0


def test_regression_detection() -> None:
    evaluator = RetrievalRankingEvaluator()
    records, graph_state = build_test_corpus()
    dataset = {
        "dataset_version": "1.0.0",
        "cases": [
            {
                "query": "database migration design",
                "expected": ["mem-db-migration-rules"],
                "intent": "knowledge_query"
            }
        ]
    }

    # Evaluate with default/good configuration
    baseline_config = RankingConfig(lexical_weight=0.8, graph_weight=0.1, priority_weight=0.1)
    baseline_report = evaluator.evaluate(dataset, records, graph_state, baseline_config)

    # Evaluate with a degraded configuration (e.g. ignoring lexical signal)
    degraded_config = RankingConfig(lexical_weight=0.0, graph_weight=1.0, priority_weight=0.0)
    degraded_report = evaluator.evaluate(dataset, records, graph_state, degraded_config, baseline_report=baseline_report)

    # Verify regression is reported
    assert degraded_report.regression_metrics.regressed > 0
    assert degraded_report.regression_metrics.improved == 0


def test_signal_attribution() -> None:
    evaluator = RetrievalRankingEvaluator()
    records, graph_state = build_test_corpus()
    
    # Query: "database migration rules" -> expected lexical match
    dataset = {
        "dataset_version": "1.0.0",
        "cases": [
            {
                "query": "database migration rules",
                "expected": ["mem-db-migration-rules"],
                "intent": "knowledge_query"
            }
        ]
    }
    
    config = RankingConfig(lexical_weight=1.0, graph_weight=0.0, priority_weight=0.0)
    report = evaluator.evaluate(dataset, records, graph_state, config)
    
    assert len(report.benchmark_results) == 1
    result = report.benchmark_results[0]
    assert result.dominant_signal == "lexical"
    assert result.lexical_contribution > 0.15
    assert result.graph_contribution == 0.0
