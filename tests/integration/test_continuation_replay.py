"""
Integration tests for continuation replay deterministic reconstruction.
"""
from __future__ import annotations

import json
import os
import tempfile
import uuid
from pathlib import Path
import pytest

from rationalevault.db.sqlite_store import SQLiteEventStore
from rationalevault.schema.events import EventMetadata, EventType
from rationalevault.organization.models import OrganizationState
from rationalevault.organization.activity import OrganizationActivityState, OrganizationActivityProjection
from rationalevault.organization.graph import OrganizationGraphState, OrganizationGraphProjection
from rationalevault.knowledge.project_registry import ProjectRegistry, ProjectEntry
from rationalevault.projections.cross_project import CrossProjectState, CrossProjectHealth


@pytest.fixture
def temp_db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    try:
        os.unlink(path)
    except OSError:
        pass


def test_continuation_replay_determinism(temp_db_path):
    store = SQLiteEventStore(db_path=temp_db_path)
    pid = uuid.uuid4()
    meta = EventMetadata(actor="agent", source="integration_test", session_id="session-xyz")

    # Append events
    store.append_event(pid, "main", EventType.PROJECT_CREATED, {"name": "Integration Project"}, meta)
    store.append_event(pid, "main", EventType.PROJECT_GOAL_SET, {"goal": "Complete Sprint I10"}, meta)
    store.append_event(pid, "main", EventType.PROJECT_FOCUS_CHANGED, {"focus": "Integration testing"}, meta)

    # 1. Build Projection A
    events_a = list(store.replay_stream(pid))
    
    # Mock minimal OrganizationState and cross_project mapping to satisfy projections
    org_state = OrganizationState(
        compiled_at="2026-06-24T12:00:00Z",
        project_ids=[str(pid)],
    )
    
    activity_a = OrganizationActivityProjection.project(
        project_ids=[str(pid)],
        recent_events_by_project={str(pid): events_a},
        recent_knowledge_by_project={},
        recent_memories_by_project={},
        org_state=org_state,
        reference_time=None,
    )

    graph_a = OrganizationGraphProjection.project(
        org_state=org_state,
        reference_time=None,
    )

    # 2. Build Projection B
    events_b = list(store.replay_stream(pid))
    activity_b = OrganizationActivityProjection.project(
        project_ids=[str(pid)],
        recent_events_by_project={str(pid): events_b},
        recent_knowledge_by_project={},
        recent_memories_by_project={},
        org_state=org_state,
        reference_time=None,
    )

    graph_b = OrganizationGraphProjection.project(
        org_state=org_state,
        reference_time=None,
    )

    # Re-compiled times might slightly vary if reference_time is None, so override for exact structural check
    activity_a.compiled_at = "2026-06-24T12:00:00Z"
    activity_b.compiled_at = "2026-06-24T12:00:00Z"
    graph_a.compiled_at = "2026-06-24T12:00:00Z"
    graph_b.compiled_at = "2026-06-24T12:00:00Z"

    # Assert canonical JSON equality: projection A == projection B
    json_act_a = json.dumps(activity_a.to_dict(), sort_keys=True)
    json_act_b = json.dumps(activity_b.to_dict(), sort_keys=True)
    assert json_act_a == json_act_b

    json_grp_a = json.dumps(graph_a.to_dict(), sort_keys=True)
    json_grp_b = json.dumps(graph_b.to_dict(), sort_keys=True)
    assert json_grp_a == json_grp_b


def test_replay_stability_from_fixture(temp_db_path):
    # Load canonical event stream v1
    fixture_path = Path(__file__).parents[1] / "fixtures" / "replay_streams" / "continuation_v1.json"
    assert fixture_path.exists(), f"Replay stream fixture v1 should exist at {fixture_path.resolve()}"

    with open(fixture_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    store = SQLiteEventStore(db_path=temp_db_path)
    pid = uuid.uuid4()

    for event_data in data["events"]:
        meta = EventMetadata(actor="agent", source="fixture", session_id=event_data["session_id"])
        store.append_event(
            pid,
            event_data["stream_id"],
            EventType(event_data["event_type"]),
            event_data["payload"],
            meta
        )

    # Verify event replay count
    replayed = list(store.replay_stream(pid))
    assert len(replayed) == 3
    assert replayed[0].event_type == EventType.PROJECT_CREATED
    assert replayed[-1].event_type == EventType.PROJECT_FOCUS_CHANGED
