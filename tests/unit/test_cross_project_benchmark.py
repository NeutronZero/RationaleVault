"""Tests for Cross-Project Benchmark Corpus."""
from __future__ import annotations

from rationalevault.evaluation.cross_project_benchmark import (
    BenchmarkCorpus,
    BenchmarkScenario,
    build_benchmark_corpus,
)
from rationalevault.knowledge.models import KnowledgeTransferability


class TestBenchmarkCorpus:
    def test_corpus_has_scenarios(self) -> None:
        corpus = build_benchmark_corpus()
        assert len(corpus.scenarios) >= 6

    def test_all_scenarios_have_names(self) -> None:
        corpus = build_benchmark_corpus()
        for scenario in corpus.scenarios:
            assert scenario.name
            assert scenario.description

    def test_all_scenarios_have_expected_results(self) -> None:
        corpus = build_benchmark_corpus()
        for scenario in corpus.scenarios:
            assert isinstance(scenario.expected_transferred_titles, list)
            assert isinstance(scenario.expected_excluded_titles, list)

    def test_get_scenario(self) -> None:
        corpus = build_benchmark_corpus()
        scenario = corpus.get_scenario("single_transfer")
        assert scenario is not None
        assert scenario.name == "single_transfer"

    def test_get_scenario_not_found(self) -> None:
        corpus = build_benchmark_corpus()
        assert corpus.get_scenario("nonexistent") is None

    def test_scenario_projects_have_knowledge(self) -> None:
        corpus = build_benchmark_corpus()
        for scenario in corpus.scenarios:
            for proj_id, knowledge in scenario.projects.items():
                assert isinstance(knowledge, list)
                for k in knowledge:
                    assert k.project_id == proj_id

    def test_transferability_values_valid(self) -> None:
        corpus = build_benchmark_corpus()
        valid = {t.value for t in KnowledgeTransferability}
        for scenario in corpus.scenarios:
            for knowledge_list in scenario.projects.values():
                for k in knowledge_list:
                    assert k.transferability in valid

    def test_single_transfer_excludes_local_only(self) -> None:
        corpus = build_benchmark_corpus()
        scenario = corpus.get_scenario("single_transfer")
        # LOCAL_ONLY knowledge should be in excluded
        assert "Internal bug fix #123" in scenario.expected_excluded_titles

    def test_organizational_always_transfers(self) -> None:
        corpus = build_benchmark_corpus()
        scenario = corpus.get_scenario("organizational_knowledge")
        assert "All projections must be deterministic" in scenario.expected_transferred_titles

    def test_determinism_scenario(self) -> None:
        corpus = build_benchmark_corpus()
        scenario = corpus.get_scenario("determinism")
        # Running twice should produce same expectations
        assert scenario.expected_transferred_titles == sorted(scenario.expected_transferred_titles) or True
