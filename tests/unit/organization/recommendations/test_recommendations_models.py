"""Tests for I15.1 — Recommendation models."""
from __future__ import annotations

import hashlib

import pytest

from rationalevault.organization.recommendations.models import (
    CATEGORY_PRIORITY,
    EvidenceType,
    Recommendation,
    RecommendationCategory,
    RecommendationSet,
    make_recommendation,
)


class TestRecommendationCategory:
    def test_has_six_categories(self) -> None:
        assert len(RecommendationCategory) == 6

    def test_all_categories_have_priorities(self) -> None:
        for cat in RecommendationCategory:
            assert cat in CATEGORY_PRIORITY


class TestCATEGORY_PRIORITY:
    def test_conflict_is_highest_priority(self) -> None:
        assert CATEGORY_PRIORITY[RecommendationCategory.CONFLICT_RESOLUTION] == 1

    def test_invariant_is_lowest(self) -> None:
        assert CATEGORY_PRIORITY[RecommendationCategory.INVARIANT_REVIEW] == 6

    def test_all_priorities_are_unique(self) -> None:
        priorities = list(CATEGORY_PRIORITY.values())
        assert len(set(priorities)) == len(priorities)


class TestEvidenceType:
    def test_all_have_prefixes(self) -> None:
        assert EvidenceType.HOTSPOT.value == "hotspot"
        assert EvidenceType.INACTIVE.value == "inactive"
        assert EvidenceType.TRANSFER.value == "transfer"
        assert EvidenceType.FLOW.value == "flow"
        assert EvidenceType.CLUSTER.value == "cluster"
        assert EvidenceType.INVARIANT.value == "invariant"


class TestRecommendation:
    def test_frozen(self) -> None:
        r = make_recommendation(
            category=RecommendationCategory.INACTIVITY_REVIEW,
            title="Test",
            evidence_ids=["inactive:project_a"],
        )
        with pytest.raises(AttributeError):
            r.title = "Mutated"  # type: ignore[misc]

    def test_to_dict(self) -> None:
        r = make_recommendation(
            category=RecommendationCategory.CONFLICT_RESOLUTION,
            title="Resolve conflict in project_a",
            rationale=["Test rationale"],
            affected_projects=["project_a"],
            evidence_ids=["hotspot:project_a"],
        )
        d = r.to_dict()
        assert d["category"] == "CONFLICT_RESOLUTION"
        assert d["priority"] == 1
        assert d["confidence"] == 1.0
        assert r.recommendation_id in d["recommendation_id"]
        assert len(d["evidence_ids"]) == 1

    def test_id_deterministic(self) -> None:
        r1 = make_recommendation(
            category=RecommendationCategory.INACTIVITY_REVIEW,
            title="Test",
            affected_projects=["p1"],
            evidence_ids=["inactive:p1"],
        )
        r2 = make_recommendation(
            category=RecommendationCategory.INACTIVITY_REVIEW,
            title="Test",
            affected_projects=["p1"],
            evidence_ids=["inactive:p1"],
        )
        assert r1.recommendation_id == r2.recommendation_id

    def test_id_differs_by_category(self) -> None:
        r1 = make_recommendation(
            category=RecommendationCategory.INACTIVITY_REVIEW,
            title="Test",
            affected_projects=["p1"],
            evidence_ids=["inactive:p1"],
        )
        r2 = make_recommendation(
            category=RecommendationCategory.CONFLICT_RESOLUTION,
            title="Test",
            affected_projects=["p1"],
            evidence_ids=["hotspot:p1"],
        )
        assert r1.recommendation_id != r2.recommendation_id

    def test_id_includes_evidence(self) -> None:
        r1 = make_recommendation(
            category=RecommendationCategory.CONFLICT_RESOLUTION,
            title="Test",
            affected_projects=["p1"],
            evidence_ids=["hotspot:p1"],
        )
        r2 = make_recommendation(
            category=RecommendationCategory.CONFLICT_RESOLUTION,
            title="Test",
            affected_projects=["p1"],
            evidence_ids=["hotspot:p1", "inactive:p1"],
        )
        assert r1.recommendation_id != r2.recommendation_id

    def test_evidence_ids_must_be_nonempty(self) -> None:
        r = make_recommendation(
            category=RecommendationCategory.CONFLICT_RESOLUTION,
            title="Test",
            evidence_ids=["hotspot:project_a"],
        )
        assert len(r.evidence_ids) > 0

    def test_priority_from_category(self) -> None:
        r = make_recommendation(
            category=RecommendationCategory.TRANSFER_FOLLOWUP,
            title="Test",
            evidence_ids=["transfer:k1"],
        )
        assert r.priority == 2


class TestRecommendationSet:
    def test_empty(self) -> None:
        rs = RecommendationSet()
        assert rs.recommendation_count == 0
        assert rs.attention_load == 0.0

    def test_with_recommendations(self) -> None:
        r = make_recommendation(
            category=RecommendationCategory.CONFLICT_RESOLUTION,
            title="Test",
            evidence_ids=["hotspot:p1"],
        )
        rs = RecommendationSet(recommendations=[r])
        assert rs.recommendation_count == 1
        assert rs.attention_load > 0.0

    def test_to_dict(self) -> None:
        r = make_recommendation(
            category=RecommendationCategory.CONFLICT_RESOLUTION,
            title="Test",
            evidence_ids=["hotspot:p1"],
        )
        rs = RecommendationSet(recommendations=[r])
        d = rs.to_dict()
        assert "recommendations" in d
        assert d["recommendation_count"] == 1
        assert "attention_load" in d
