import os
import tempfile
import uuid
import pytest
from uuid import UUID

from rationalevault.db.sqlite_store import SQLiteEventStore
from rationalevault.schema.events import EventMetadata, EventType
from rationalevault.cognitive_head.compiler import compile_cognitive_head


def meta() -> EventMetadata:
    return EventMetadata(actor="MigrationTester", source="test_suite",
                         session_id="sess_mig", correlation_id="corr_mig")


@pytest.fixture
def temp_dbs() -> tuple[str, str]:
    fd1, path1 = tempfile.mkstemp(suffix="_src.db")
    os.close(fd1)
    fd2, path2 = tempfile.mkstemp(suffix="_tgt.db")
    os.close(fd2)
    yield path1, path2
    for p in [path1, path2]:
        try:
            os.unlink(p)
        except OSError:
            pass


def test_storage_migration_replay_loop(temp_dbs):
    src_path, tgt_path = temp_dbs
    src_store = SQLiteEventStore(db_path=src_path)
    tgt_store = SQLiteEventStore(db_path=tgt_path)

    project_id = uuid.uuid4()
    m = meta()

    # 1. Seed source store
    src_store.append_event(project_id, "main", EventType.PROJECT_CREATED, {"name": "Migration Project"}, m)
    src_store.append_event(project_id, "main", EventType.PROJECT_GOAL_SET, {"goal": "Migrate database backends"}, m)
    src_store.append_event(project_id, "main", EventType.PROJECT_FOCUS_CHANGED, {"focus": "Replay testing"}, m)
    src_store.append_event(project_id, "tasks", EventType.TASK_CREATED, {"task_id": "t1", "details": {"summary": "Migrate records", "body": ""}}, m)
    src_store.append_event(project_id, "decisions", EventType.DECISION_PROPOSED, {"decision_id": "d1", "title": "Decision 1"}, m)
    src_store.append_event(project_id, "decisions", EventType.DECISION_ACCEPTED, {"decision_id": "d1"}, m)

    # 2. Migrate: Read from source, append to target
    events = src_store.get_project_stream(project_id)
    assert len(events) == 6

    # SQLite locks transactions, we append in order to target
    for ev in events:
        tgt_store.append_event(
            project_id=ev.project_id,
            stream_id=ev.stream_id,
            event_type=ev.event_type,
            payload=ev.payload,
            metadata=ev.metadata
        )

    # 3. Compare CognitiveHeads compiled from both backends
    head_src = compile_cognitive_head(project_id, store=src_store)
    head_tgt = compile_cognitive_head(project_id, store=tgt_store)

    assert head_src.project_name == head_tgt.project_name
    assert head_src.project_goal == head_tgt.project_goal
    assert head_src.current_focus == head_tgt.current_focus
    assert len(head_src.active_tasks) == len(head_tgt.active_tasks)
    assert len(head_src.active_decisions) == len(head_tgt.active_decisions)
    assert head_src.active_tasks[0].task_id == head_tgt.active_tasks[0].task_id
