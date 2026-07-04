from __future__ import annotations

import os
import uuid
from pathlib import Path
from rationalevault.db.event_store import EventStore
from rationalevault.schema.events import EventMetadata, EventRecord, EventType
from rationalevault.memory.models import MemoryRecord, MemoryType, generate_memory_id
from rationalevault.memory.factory import get_memory_provider
from rationalevault.memory.markdown_provider import MarkdownMemoryProvider
from rationalevault.memory.sqlite_provider import SQLiteMemoryProvider
from rationalevault.memory.extractor import extract_memories_from_event
from rationalevault.memory.compiler import compile_memory_context

def test_memory_record_id_and_priority() -> None:
    content = "SQLite chosen for simplicity."
    title = "Decision SQLite"
    m_id = generate_memory_id(MemoryType.DECISION.value, title, content)
    
    rec = MemoryRecord(
        id=m_id,
        version=1,
        title=title,
        content=content,
        memory_type=MemoryType.DECISION,
        importance="critical",
        lifecycle_status="active",
        source_event_ids=["evt-123"],
        source_type="decision",
        project_id="test",
    )
    
    assert rec.id == m_id
    assert rec.retrieval_priority == 5.0 # critical weight
    
    # Test from_dict and to_dict
    d = rec.to_dict()
    assert d["importance"] == "critical"
    assert d["retrieval_priority"] == 5.0
    
    rec2 = MemoryRecord.from_dict(d)
    assert rec2.title == title
    assert rec2.retrieval_priority == 5.0

def test_markdown_provider_crud(tmp_path: Path) -> None:
    file_path = tmp_path / "test_memory.md"
    provider = MarkdownMemoryProvider(file_path=file_path)
    
    rec1 = MemoryRecord(
        id="mem1",
        version=1,
        title="Test Dec",
        content="Test content",
        memory_type=MemoryType.DECISION,
        importance="low",
        lifecycle_status="active",
        source_event_ids=["e1"],
        source_type="test",
        project_id="test",
    )
    
    provider.add_record(rec1)
    
    records = provider.get_all_records()
    assert len(records) == 1
    assert records[0].id == "mem1"
    assert records[0].version == 1
    
    # Test update (version increment)
    rec1_updated = MemoryRecord(
        id="mem1",
        version=1,
        title="Test Dec",
        content="Test content updated",
        memory_type=MemoryType.DECISION,
        importance="low",
        lifecycle_status="active",
        source_event_ids=["e1"],
        source_type="test",
        project_id="test",
    )
    provider.add_record(rec1_updated)
    
    records2 = provider.get_all_records()
    assert len(records2) == 1
    assert records2[0].version == 2
    assert records2[0].content == "Test content updated"

def test_sqlite_provider_crud(tmp_path: Path) -> None:
    db_path = tmp_path / "test_relay.db"
    provider = SQLiteMemoryProvider(db_path=db_path)
    
    rec1 = MemoryRecord(
        id="mem1",
        version=1,
        title="Test SQLite",
        content="Testing sqlite persistence",
        memory_type=MemoryType.DECISION_RATIONALE,
        importance="medium",
        lifecycle_status="active",
        source_event_ids=["e2"],
        source_type="test",
        project_id="test",
    )
    
    provider.add_record(rec1)
    
    records = provider.get_all_records()
    assert len(records) == 1
    assert records[0].id == "mem1"
    assert records[0].version == 1
    
    # Test search
    res = provider.search_records("persistence", limit=5)
    assert len(res) == 1
    assert res[0].id == "mem1"

def test_extraction_rules() -> None:
    # Test EventType.DECISION_ACCEPTED extraction
    event = EventRecord(
        event_sequence=1,
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        stream_id="decisions",
        version=1,
        event_type=EventType.DECISION_ACCEPTED,
        metadata=EventMetadata(actor="test", source="test"),
        payload={
            "decision": "Use PostgreSQL",
            "rationale": "For scale."
        },
        parent_id=None,
        recorded_at=None,
    )
    
    memories = extract_memories_from_event(event)
    assert len(memories) == 2
    assert memories[0].memory_type == MemoryType.DECISION
    assert memories[0].content == "Use PostgreSQL"
    assert memories[1].memory_type == MemoryType.DECISION_RATIONALE
    assert memories[1].content == "For scale."

def test_compile_memory_context(tmp_path: Path, monkeypatch) -> None:
    # Mock memory.md for testing compiler
    file_path = tmp_path / "memory.md"
    provider = MarkdownMemoryProvider(file_path=file_path)
    
    rec = MemoryRecord(
        id="mem-arch",
        version=1,
        title="Arch Goal",
        content="Use clean architecture",
        memory_type=MemoryType.ARCHITECTURE,
        importance="critical",
        lifecycle_status="active",
        source_event_ids=["e1"],
        source_type="project",
        project_id="test",
    )
    provider.add_record(rec)
    
    # Patch get_memory_provider to return our provider
    monkeypatch.setattr("rationalevault.memory.factory.get_memory_provider", lambda: provider)
    monkeypatch.setattr("rationalevault.memory.retrieval.get_memory_provider", lambda: provider)
    
    ctx = compile_memory_context("architecture")
    assert len(ctx["ARCHITECTURE"]) == 1
    assert ctx["ARCHITECTURE"][0][0].id == "mem-arch"


def test_sqlite_provider_pagination(tmp_path: Path) -> None:
    from rationalevault.memory.sqlite_provider import SQLiteMemoryProvider
    db_path = tmp_path / "pagination_test.db"
    provider = SQLiteMemoryProvider(db_path=db_path)
    for i in range(15):
        provider.add_record(MemoryRecord(
            id=f"mem{i}",
            version=1,
            title=f"Title {i}",
            content="Some persistence testing text",
            memory_type=MemoryType.DECISION,
            importance="medium",
            lifecycle_status="active",
            source_event_ids=["e"],
            source_type="test",
            project_id="test",
        ))
    res = provider.search_records("persistence", limit=10)
    assert len(res) == 10


def test_semantic_search_empty_query() -> None:
    from rationalevault.memory.semantic_search import search_memories_rrf
    recs = [MemoryRecord(
        id="mem1",
        version=1,
        title="Title",
        content="Content",
        memory_type=MemoryType.DECISION,
        importance="medium",
        lifecycle_status="active",
        source_event_ids=["e"],
        source_type="test",
        project_id="test",
    )]
    assert len(search_memories_rrf("", recs)) == 1
    assert len(search_memories_rrf("   ", recs)) == 1
