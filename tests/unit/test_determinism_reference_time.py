"""Tests for reference_time determinism in I13, I14, and I15."""
from __future__ import annotations

from datetime import datetime, timezone
import pytest

from rationalevault.organization.activity import OrganizationActivityProjection
from rationalevault.organization.continuation import OrganizationContinuationProjection
from rationalevault.organization.graph import (
    OrganizationGraphProjection,
    OrganizationEdge,
    OrganizationRelationType,
)
from rationalevault.organization.models import OrganizationState
from rationalevault.recommendations.engine import RecommendationEngine


def test_reference_time_determinism() -> None:
    # Set up some static objects
    ref_time = datetime(2026, 6, 24, 12, 0, 0, tzinfo=timezone.utc)
    org_state = OrganizationState(
        compiled_at="2026-06-24T12:00:00+00:00",
        project_ids=["proj_a", "proj_b"],
    )

    # 1. OrganizationGraphProjection
    graph_state = OrganizationGraphProjection.project(org_state, reference_time=ref_time)
    assert graph_state.compiled_at == "2026-06-24T12:00:00+00:00"

    # 2. OrganizationActivityProjection
    activity_state = OrganizationActivityProjection.project(
        project_ids=["proj_a", "proj_b"],
        recent_events_by_project={},
        recent_knowledge_by_project={},
        recent_memories_by_project={},
        org_state=org_state,
        reference_time=ref_time,
    )
    assert activity_state.compiled_at == "2026-06-24T12:00:00+00:00"

    # 3. OrganizationContinuationProjection
    continuation_state = OrganizationContinuationProjection.project(
        org_state=org_state,
        graph_state=graph_state,
        activity_state=activity_state,
        reference_time=ref_time,
    )
    assert continuation_state.compiled_at == "2026-06-24T12:00:00+00:00"

    # 4. RecommendationEngine
    recs = RecommendationEngine.generate(
        org_state=org_state,
        graph_state=graph_state,
        activity_state=activity_state,
        reference_time=ref_time,
    )
    assert recs.compiled_at == "2026-06-24T12:00:00+00:00"


def test_shortest_transfer_path_edge_cases() -> None:
    # Verify the optimized BFS shortest path
    org_state = OrganizationState(
        compiled_at="2026-06-24T12:00:00+00:00",
        project_ids=["a", "b", "c", "d"],
    )
    graph_state = OrganizationGraphProjection.project(org_state)
    # Add manual edges
    graph_state.adjacency["a"] = [
        OrganizationEdge("a", "b", OrganizationRelationType.TRANSFERRED_TO),
        OrganizationEdge("a", "c", OrganizationRelationType.TRANSFERRED_TO),
    ]
    graph_state.adjacency["b"] = [
        OrganizationEdge("b", "d", OrganizationRelationType.TRANSFERRED_TO),
    ]
    graph_state.adjacency["c"] = [
        OrganizationEdge("c", "d", OrganizationRelationType.TRANSFERRED_TO),
    ]

    path = OrganizationGraphProjection.shortest_transfer_path(graph_state, "a", "d")
    # Should find shortest path
    assert path in (["a", "b", "d"], ["a", "c", "d"])

    # Path to self
    assert OrganizationGraphProjection.shortest_transfer_path(graph_state, "a", "a") == ["a"]

    # Unreachable
    assert OrganizationGraphProjection.shortest_transfer_path(graph_state, "d", "a") == []
