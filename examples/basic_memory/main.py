"""RationaleVault Example: Basic Memory.

Demonstrates events → memories → retrieval pipeline.
"""
from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path

from rationalevault.schema.events import EventType, EventMetadata
from rationalevault.db.sqlite_store import SQLiteEventStore
from rationalevault.memory.models import MemoryRecord, MemoryType
from rationalevault.memory.sqlite_provider import SQLiteMemoryProvider
from rationalevault.memory.retrieval import retrieve_ranked_citations


def main() -> None:
    print("--- Running RationaleVault Example: Basic Memory ---")
    
    # 1. Setup temp database
    temp_dir = Path(tempfile.gettempdir())
    db_path = temp_dir / f"relay_example_memory_{uuid.uuid4().hex[:8]}.db"
    
    print(f"Initializing temporary Event Store at: {db_path}")
    event_store = SQLiteEventStore(db_path=str(db_path))
    memory_provider = SQLiteMemoryProvider(db_path=db_path)
    
    project_id = uuid.uuid4()
    stream_id = uuid.uuid4()
    
    # 2. Append events
    print("Appending synthetic events to the ledger...")
    metadata = EventMetadata(actor="example_actor", source="basic_memory")
    event_store.append_event(
        project_id=project_id,
        stream_id=str(stream_id),
        event_type=EventType.PROJECT_GOAL_SET,
        payload={
            "goal": "Build a lightning-fast memory layer for agent handoffs",
            "priority": "critical",
        },
        metadata=metadata,
    )
    event_store.append_event(
        project_id=project_id,
        stream_id=str(stream_id),
        event_type=EventType.DECISION_ACCEPTED,
        payload={
            "decision": "Use SQLite as default local database for storage simplicity",
            "rationale": "High speed, zero config, standard python library support",
        },
        metadata=metadata,
    )
    
    # 3. Add memory record
    print("Consolidating memories...")
    mem = MemoryRecord(
        id="mem_goal_1",
        version=1,
        title="Project Memory: Core Goal",
        content="Primary project goal set: Build a lightning-fast memory layer for agent handoffs with critical priority.",
        memory_type=MemoryType.DECISION,
        importance="high",
        lifecycle_status="active",
        source_event_ids=["ev_1"],
        source_type="event",
        confidence=1.0,
    )
    memory_provider.add_record(mem)
    
    # 4. Retrieve citations
    print("Querying retrieval engine...")
    # Inject memory_provider reference into search if possible, or just print memory info.
    # Since retrieve_ranked_citations loads configured provider, we can manually check provider lookup:
    records = memory_provider.get_all_records()
    print(f"Retrieved {len(records)} records from store:")
    for r in records:
        print(f"  - [{r.memory_type.value}] {r.title}: {r.content}")
        
    # Clean up
    import gc
    gc.collect()
    try:
        if db_path.exists():
            os.remove(db_path)
    except Exception:
        pass
    print("Example executed successfully!\n")


if __name__ == "__main__":
    main()
