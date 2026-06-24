"""Tests for CrossProjectProjection."""
from __future__ import annotations

from rationalevault.knowledge.models import (
    KnowledgeObject,
    KnowledgeTransferability,
    KnowledgeType,
)
from rationalevault.projections.cross_project import (
    CrossProjectKnowledge,
    CrossProjectProjection,
    CrossProjectState,
    _score_relevance,
    _compute_related_projects,
)
from rationalevault.evaluation.cross_project_benchmark import _k, build_benchmark_corpus


class TestCrossProjectProjection:
    def test_empty_targets(self) -> None:
        state = CrossProjectProjection.project(
            current_project_id="proj_a",
            current_knowledge=[],
            target_knowledge={},
        )
        assert state.project_id == "proj_a"
        assert len(state.transferable_knowledge) == 0
        assert state.health is not None
        assert state.health.total_projects == 0

    def test_basic_transfer(self) -> None:
        k1 = _k("k1", "Use PostgreSQL", "proj_b",
                KnowledgeTransferability.REUSABLE.value)
        state = CrossProjectProjection.project(
            current_project_id="proj_a",
            current_knowledge=[],
            target_knowledge={"proj_b": [k1]},
            query="database",
        )
        assert len(state.transferable_knowledge) == 1
        assert state.transferable_knowledge[0].source_project_id == "proj_b"
        assert state.transferable_knowledge[0].title == "Use PostgreSQL"

    def test_local_only_excluded(self) -> None:
        k1 = _k("k1", "Use PostgreSQL", "proj_b",
                KnowledgeTransferability.REUSABLE.value)
        k2 = _k("k2", "Internal bug fix", "proj_b",
                KnowledgeTransferability.LOCAL_ONLY.value)
        state = CrossProjectProjection.project(
            current_project_id="proj_a",
            current_knowledge=[],
            target_knowledge={"proj_b": [k1, k2]},
        )
        titles = [k.title for k in state.transferable_knowledge]
        assert "Use PostgreSQL" in titles
        assert "Internal bug fix" not in titles

    def test_organizational_always_transfers(self) -> None:
        k1 = _k("k1", "All projects use CI/CD", "proj_b",
                KnowledgeTransferability.ORGANIZATIONAL.value)
        state = CrossProjectProjection.project(
            current_project_id="proj_a",
            current_knowledge=[],
            target_knowledge={"proj_b": [k1]},
        )
        assert len(state.transferable_knowledge) == 1
        assert state.transferable_knowledge[0].transferability == KnowledgeTransferability.ORGANIZATIONAL.value

    def test_provenance_preserved(self) -> None:
        k1 = _k("k1", "Use PostgreSQL", "proj_b",
                KnowledgeTransferability.REUSABLE.value)
        state = CrossProjectProjection.project(
            current_project_id="proj_a",
            current_knowledge=[],
            target_knowledge={"proj_b": [k1]},
        )
        assert state.provenance_map["k1"] == "proj_b"

    def test_knowledge_by_project(self) -> None:
        k1 = _k("k1", "Use PostgreSQL", "proj_b",
                KnowledgeTransferability.REUSABLE.value)
        k2 = _k("k2", "Use Redis", "proj_c",
                KnowledgeTransferability.REUSABLE.value)
        state = CrossProjectProjection.project(
            current_project_id="proj_a",
            current_knowledge=[],
            target_knowledge={"proj_b": [k1], "proj_c": [k2]},
        )
        assert "proj_b" in state.knowledge_by_project
        assert "proj_c" in state.knowledge_by_project
        assert "k1" in state.knowledge_by_project["proj_b"]
        assert "k2" in state.knowledge_by_project["proj_c"]

    def test_related_projects(self) -> None:
        current = [_k("c1", "database storage", "proj_a")]
        target = {"proj_b": [_k("b1", "database caching", "proj_b")]}
        state = CrossProjectProjection.project(
            current_project_id="proj_a",
            current_knowledge=current,
            target_knowledge=target,
        )
        assert "proj_b" in state.related_projects
        assert state.related_projects["proj_b"] > 0.0

    def test_transferability_filter(self) -> None:
        k1 = _k("k1", "Use PostgreSQL", "proj_b",
                KnowledgeTransferability.REUSABLE.value)
        k2 = _k("k2", "All projects use CI/CD", "proj_b",
                KnowledgeTransferability.ORGANIZATIONAL.value)
        state = CrossProjectProjection.project(
            current_project_id="proj_a",
            current_knowledge=[],
            target_knowledge={"proj_b": [k1, k2]},
            transferability_filter=["ORGANIZATIONAL"],
        )
        titles = [k.title for k in state.transferable_knowledge]
        assert "All projects use CI/CD" in titles
        assert "Use PostgreSQL" not in titles

    def test_determinism(self) -> None:
        k1 = _k("k1", "Use PostgreSQL", "proj_b",
                KnowledgeTransferability.REUSABLE.value)
        kwargs = dict(
            current_project_id="proj_a",
            current_knowledge=[],
            target_knowledge={"proj_b": [k1]},
            query="database",
        )
        state1 = CrossProjectProjection.project(**kwargs)
        state2 = CrossProjectProjection.project(**kwargs)
        assert len(state1.transferable_knowledge) == len(state2.transferable_knowledge)
        assert state1.health.coverage == state2.health.coverage

    def test_health_metrics(self) -> None:
        k1 = _k("k1", "Use PostgreSQL", "proj_b",
                KnowledgeTransferability.REUSABLE.value)
        k2 = _k("k2", "Internal fix", "proj_b",
                KnowledgeTransferability.LOCAL_ONLY.value)
        state = CrossProjectProjection.project(
            current_project_id="proj_a",
            current_knowledge=[],
            target_knowledge={"proj_b": [k1, k2]},
        )
        assert state.health.total_projects == 1
        assert state.health.reusable_count == 1
        assert state.health.coverage == 0.5  # 1 transferable / 2 total

    def test_matched_terms_populated(self) -> None:
        k1 = _k("k1", "Use PostgreSQL for database storage", "proj_b",
                KnowledgeTransferability.REUSABLE.value)
        state = CrossProjectProjection.project(
            current_project_id="proj_a",
            current_knowledge=[],
            target_knowledge={"proj_b": [k1]},
            query="database",
        )
        assert len(state.transferable_knowledge) == 1
        assert len(state.transferable_knowledge[0].matched_terms) > 0

    def test_to_dict(self) -> None:
        k1 = _k("k1", "Use PostgreSQL", "proj_b",
                KnowledgeTransferability.REUSABLE.value)
        state = CrossProjectProjection.project(
            current_project_id="proj_a",
            current_knowledge=[],
            target_knowledge={"proj_b": [k1]},
        )
        d = state.to_dict()
        assert d["project_id"] == "proj_a"
        assert d["transferable_knowledge_count"] == 1
        assert d["health"] is not None

    def test_benchmark_scenarios(self) -> None:
        """Run all benchmark scenarios through the projection."""
        corpus = build_benchmark_corpus()
        for scenario in corpus.scenarios:
            state = CrossProjectProjection.project(
                current_project_id="current",
                current_knowledge=[],
                target_knowledge=scenario.projects,
                query=scenario.query,
                transferability_filter=scenario.transferability_filter,
            )
            transferred_titles = [k.title for k in state.transferable_knowledge]

            for expected in scenario.expected_transferred_titles:
                assert expected in transferred_titles, (
                    f"Scenario '{scenario.name}': expected '{expected}' in transferred"
                )
            for excluded in scenario.expected_excluded_titles:
                assert excluded not in transferred_titles, (
                    f"Scenario '{scenario.name}': expected '{excluded}' NOT in transferred"
                )


class TestScoreRelevance:
    def test_empty_query(self) -> None:
        k = _k("k1", "Use PostgreSQL", "proj")
        score, matched = _score_relevance(k, "")
        assert score == 0.5
        assert matched == []

    def test_exact_match(self) -> None:
        k = _k("k1", "Use PostgreSQL for storage", "proj")
        score, matched = _score_relevance(k, "PostgreSQL")
        assert score > 0.0
        assert "postgresql" in matched

    def test_no_match(self) -> None:
        k = _k("k1", "Use PostgreSQL", "proj")
        score, matched = _score_relevance(k, "machine learning")
        assert score == 0.0
        assert matched == []

    def test_multiple_terms(self) -> None:
        k = _k("k1", "Use PostgreSQL for database storage", "proj")
        score, matched = _score_relevance(k, "database storage")
        assert score > 0.5
        assert "database" in matched
        assert "storage" in matched


class TestComputeRelatedProjects:
    def test_empty_current(self) -> None:
        target = {"proj_b": [_k("b1", "Use PostgreSQL", "proj_b")]}
        result = _compute_related_projects([], target)
        assert result["proj_b"] == 0.0

    def test_shared_terms(self) -> None:
        current = [_k("c1", "database storage", "proj_a")]
        target = {"proj_b": [_k("b1", "database caching", "proj_b")]}
        result = _compute_related_projects(current, target)
        assert result["proj_b"] > 0.0

    def test_no_overlap(self) -> None:
        current = [_k("c1", "machine learning", "proj_a")]
        target = {"proj_b": [_k("b1", "database storage", "proj_b")]}
        result = _compute_related_projects(current, target)
        assert result["proj_b"] == 0.0

    def test_empty_target(self) -> None:
        current = [_k("c1", "database", "proj_a")]
        result = _compute_related_projects(current, {})
        assert result == {}
