"""Tests for I15.5 — Compiler integration."""
from __future__ import annotations

from rationalevault.compilers.claude_context import ClaudeContextCompiler
from rationalevault.knowledge.context_compiler import ContextPackage
from rationalevault.recommendations.models import (
    RecommendationSet,
    make_recommendation,
    RecommendationCategory,
)


def _make_package(recommendations: RecommendationSet | None = None) -> ContextPackage:
    package = ContextPackage(
        context_id="test-ctx",
        query="test",
        profile="GENERAL_SEARCH",
        created_at="2024-01-01T00:00:00",
    )
    package.recommendations = recommendations
    return package


class TestCompilerRecommendations:
    def test_no_recommendations_no_section(self) -> None:
        package = _make_package()
        compiler = ClaudeContextCompiler()
        output = compiler.compile(package)
        assert "Recommended Actions" not in output.rendered_content

    def test_with_recommendations_renders_section(self) -> None:
        rec = make_recommendation(
            category=RecommendationCategory.CONFLICT_RESOLUTION,
            title="Resolve conflict in project_a",
            rationale=["Test rationale"],
            affected_projects=["project_a"],
            evidence_ids=["hotspot:project_a"],
        )
        rs = RecommendationSet(recommendations=[rec])
        package = _make_package(recommendations=rs)
        compiler = ClaudeContextCompiler()
        output = compiler.compile(package)
        assert "Recommended Actions" in output.rendered_content
        assert "Resolve conflict in project_a" in output.rendered_content

    def test_max_bounded(self) -> None:
        recs = [
            make_recommendation(
                category=RecommendationCategory.CONFLICT_RESOLUTION,
                title=f"Conflict {i}",
                affected_projects=[f"p{i}"],
                evidence_ids=[f"hotspot:p{i}"],
            )
            for i in range(15)
        ]
        rs = RecommendationSet(recommendations=recs)
        package = _make_package(recommendations=rs)
        compiler = ClaudeContextCompiler()
        output = compiler.compile(package)
        # Should show at most 10 recommendations
        assert output.rendered_content.count("Recommended Actions") == 1

    def test_deterministic(self) -> None:
        rec = make_recommendation(
            category=RecommendationCategory.INACTIVITY_REVIEW,
            title="Review inactive",
            affected_projects=["p1"],
            evidence_ids=["inactive:p1"],
        )
        rs = RecommendationSet(recommendations=[rec])
        package = _make_package(recommendations=rs)
        compiler = ClaudeContextCompiler()
        o1 = compiler.compile(package)
        o2 = compiler.compile(package)
        assert o1.rendered_content == o2.rendered_content

    def test_to_dict_includes_recommendations(self) -> None:
        rec = make_recommendation(
            category=RecommendationCategory.TRANSFER_FOLLOWUP,
            title="Follow up on transfer",
            affected_projects=["p1", "p2"],
            evidence_ids=["transfer:k1"],
        )
        rs = RecommendationSet(recommendations=[rec])
        package = _make_package(recommendations=rs)
        d = package.to_dict()
        assert d["recommendations"] is not None
        assert d["recommendations"]["recommendation_count"] == 1

    def test_to_dict_None_when_no_recommendations(self) -> None:
        package = _make_package()
        d = package.to_dict()
        assert d["recommendations"] is None
