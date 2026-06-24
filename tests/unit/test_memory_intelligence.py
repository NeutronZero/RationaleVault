from __future__ import annotations

import os
import uuid
from pathlib import Path
from datetime import datetime, timedelta
from rationalevault.memory.models import MemoryRecord, MemoryType
from rationalevault.memory.ranking import compute_retrieval_score, RetrievalScore
from rationalevault.memory.reference_tracker import record_memory_reference
from rationalevault.memory.lifecycle import handle_lifecycle_transitions
from rationalevault.memory.consolidation import detect_consolidation_candidates, ConsolidationCandidate, jaccard_similarity
from rationalevault.memory.retrieval import retrieve_ranked_memories
from rationalevault.memory.markdown_provider import MarkdownMemoryProvider
from rationalevault.db.event_store import EventStore
from rationalevault.schema.events import EventMetadata, EventRecord, EventType


def test_jaccard_similarity() -> None:
    text1 = "Use PostgreSQL for routing database client connections"
    text2 = "PostgreSQL routing client database connections config"
    sim = jaccard_similarity(text1, text2)
    assert sim > 0.5
    
    sim_zero = jaccard_similarity("", "FastAPI routes")
    assert sim_zero == 0.0


def test_retrieval_score_lifecycle_and_decay() -> None:
    rec = MemoryRecord(
        id="m1",
        version=1,
        title="Postgres Dec",
        content="PostgreSQL chosen for scalability",
        memory_type=MemoryType.DECISION,
        importance="critical",
        lifecycle_status="active",
        source_event_ids=["evt-1"],
        source_type="decision",
        reference_count=10,
        last_referenced_at=(datetime.now() - timedelta(days=5)).isoformat(),
        created_at=(datetime.now() - timedelta(days=10)).isoformat(),
        project_id="test",
    )
    
    score = compute_retrieval_score(rec)
    assert score.priority == 5.0
    assert score.recency < 1.0
    assert score.references > 0.0
    assert score.lifecycle_penalty == 0.0
    assert score.total > 5.0
    
    # Test superseded penalty
    rec.lifecycle_status = "superseded"
    score_sup = compute_retrieval_score(rec)
    assert score_sup.lifecycle_penalty == -5.0


def test_reference_tracker(tmp_path: Path, monkeypatch) -> None:
    file_path = tmp_path / "memory.md"
    provider = MarkdownMemoryProvider(file_path=file_path)
    
    rec = MemoryRecord(
        id="mem-ref",
        version=1,
        title="Test Reference",
        content="Testing reference counter",
        memory_type=MemoryType.RESEARCH,
        importance="low",
        lifecycle_status="active",
        source_event_ids=["e1"],
        source_type="manual",
        project_id="test",
    )
    provider.add_record(rec)
    
    monkeypatch.setattr("rationalevault.memory.reference_tracker.get_memory_provider", lambda: provider)
    
    # Trigger reference tracking
    record_memory_reference("mem-ref", uuid.uuid4(), actor="tester")
    
    records = provider.get_all_records()
    assert len(records) == 1
    assert records[0].reference_count == 1
    assert records[0].last_referenced_at is not None


def test_automatic_supersession(tmp_path: Path, monkeypatch) -> None:
    file_path = tmp_path / "memory.md"
    provider = MarkdownMemoryProvider(file_path=file_path)
    
    rec1 = MemoryRecord(
        id="sqlite-mem",
        version=1,
        title="Use SQLite",
        content="SQLite chosen for local development",
        memory_type=MemoryType.DECISION,
        importance="medium",
        lifecycle_status="active",
        source_event_ids=["e1"],
        source_type="decision",
        project_id="test",
    )
    provider.add_record(rec1)
    
    monkeypatch.setattr("rationalevault.memory.lifecycle.get_memory_provider", lambda: provider)
    
    # Simulate a superseding event acceptance
    evt = EventRecord(
        event_sequence=42,
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        stream_id="decisions",
        version=2,
        event_type=EventType.DECISION_ACCEPTED,
        metadata=EventMetadata(actor="tester", source="cli"),
        payload={
            "decision": "Use PostgreSQL database client",
            "supersedes": "sqlite-mem"
        },
        parent_id=None,
        recorded_at=datetime.now(),
    )
    
    handle_lifecycle_transitions(evt)
    
    records = provider.get_all_records()
    assert len(records) == 1
    assert records[0].lifecycle_status == "superseded"


def test_consolidation_candidates_detection(tmp_path: Path, monkeypatch) -> None:
    file_path = tmp_path / "memory.md"
    provider = MarkdownMemoryProvider(file_path=file_path)
    
    # 2 overlapping decisions
    rec1 = MemoryRecord(
        id="postgres-a",
        version=1,
        title="Use Postgres",
        content="PostgreSQL is the default database routing manager client",
        memory_type=MemoryType.DECISION,
        importance="high",
        lifecycle_status="active",
        source_event_ids=["e1"],
        source_type="decision",
        project_id="test",
    )
    rec2 = MemoryRecord(
        id="postgres-b",
        version=1,
        title="Database postgres option",
        content="PostgreSQL default database routing manager client option",
        memory_type=MemoryType.DECISION,
        importance="high",
        lifecycle_status="active",
        source_event_ids=["e2"],
        source_type="decision",
        project_id="test",
    )
    provider.add_record(rec1)
    provider.add_record(rec2)
    
    monkeypatch.setattr("rationalevault.memory.consolidation.get_memory_provider", lambda: provider)
    
    candidates = detect_consolidation_candidates()
    assert len(candidates) == 1
    assert candidates[0].cluster_size == 2
    assert "postgres-a" in candidates[0].memory_ids
    assert "postgres-b" in candidates[0].memory_ids
    assert candidates[0].similarity_score > 0.5
