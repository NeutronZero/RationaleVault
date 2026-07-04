"""
Unit tests for OrganizationActivityState serialization and backward compatibility.
"""
from __future__ import annotations

import json
from pathlib import Path
from rationalevault.organization.activity import OrganizationActivityState, ProjectActivity, OrgTransferEvent, OrgConflictEvent, KnowledgeSummary


def test_activity_state_serialization_invariants():
    state = OrganizationActivityState(
        compiled_at="2026-06-24T12:00:00Z",
        projection_version="1.0",
        activity_window_hours=72,
        project_count=1,
        active_projects=[ProjectActivity("proj-a", 5, "2026-06-24T11:00:00Z", 1, 1)],
        inactive_projects=["proj-b"],
        recent_transfers=[OrgTransferEvent("k-1", "Transfer title", "proj-b", "proj-a", "2026-06-24T10:00:00Z")],
        recent_conflicts=[OrgConflictEvent("c-1", "proj-a", "proj-b", "2026-06-24T10:30:00Z")],
        recent_knowledge=[KnowledgeSummary("k-1", "Transfer title", "proj-a", "FACT", "2026-06-24T10:00:00Z")],
        overall_activity_level=0.5,
    )

    # 1. Roundtrip Dict invariant
    serialized = state.to_dict()
    deserialized = OrganizationActivityState.from_dict(serialized)

    assert deserialized.compiled_at == state.compiled_at
    assert deserialized.projection_version == state.projection_version
    assert len(deserialized.active_projects) == 1
    assert deserialized.active_projects[0].project_id == "proj-a"

    # 2. JSON compatibility
    json_str = json.dumps(serialized)
    json_dict = json.loads(json_str)
    assert json_dict == serialized

    # 3. Normalization Invariant
    assert deserialized.to_dict() == serialized


def test_activity_state_v1_backward_compatibility():
    fixture_path = Path(__file__).parents[2] / "fixtures" / "schema_v1" / "activity_state_v1.json"
    assert fixture_path.exists(), "Activity state fixture v1 should exist"

    with open(fixture_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data.get("schema_version") == 1

    # Load from v1 dict
    state = OrganizationActivityState.from_dict(data)
    assert state.compiled_at == "2026-06-24T12:00:00Z"
    assert state.project_count == 2
    assert len(state.active_projects) == 1
    assert state.active_projects[0].project_id == "proj-a"

    # Verify serialization equivalence
    serialized_again = state.to_dict()
    loaded_again = OrganizationActivityState.from_dict(serialized_again)
    assert loaded_again.to_dict() == serialized_again


def test_activity_metrics_calculation() -> None:
    from rationalevault.organization.activity import OrganizationActivityProjection

    active, inactive = OrganizationActivityProjection._build_project_activity(
        project_ids=["proj-active", "proj-inactive"],
        recent_events_by_project={"proj-active": [object()]},
        recent_knowledge_by_project={},
        recent_memories_by_project={},
    )
    assert len(active) == 1
    assert active[0].project_id == "proj-active"
    assert inactive == ["proj-inactive"]


def test_empty_graph_edge_generation() -> None:
    from rationalevault.organization.graph import OrganizationGraphProjection
    from rationalevault.organization.models import OrganizationState

    org_state = OrganizationState(
        compiled_at="2026-06-24T12:00:00Z",
        project_ids=[],
        active_lineages={},
        shared_knowledge=[],
        cross_project_conflicts=[],
        project_clusters=[],
    )
    edges = OrganizationGraphProjection._build_edges(org_state)
    assert len(edges) == 0
