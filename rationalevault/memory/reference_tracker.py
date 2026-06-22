from __future__ import annotations

from datetime import datetime
import uuid
from rationalevault.memory.factory import get_memory_provider
from rationalevault.db.event_store import EventStore
from rationalevault.schema.events import EventMetadata, EventType


def record_memory_reference(memory_id: str, project_id: uuid.UUID, actor: str = "agent") -> None:
    """
    Increments reference count and updates last_referenced_at timestamp,
    then logs a MEMORY_REFERENCED event to the event ledger.
    """
    provider = get_memory_provider()
    records = provider.get_all_records()
    record = next((r for r in records if r.id == memory_id), None)
    if not record:
        return

    # Update memory record
    record.reference_count += 1
    now_str = datetime.now().isoformat()
    record.last_referenced_at = now_str
    
    # Persist updated memory
    provider.add_record(record)
    
    # Append MEMORY_REFERENCED event
    try:
        store = EventStore()
        metadata = EventMetadata(actor=actor, source="reference_tracker")
        store.append_event(
            project_id=project_id,
            stream_id="memory_references",
            event_type=EventType.MEMORY_REFERENCED,
            payload={
                "memory_id": memory_id,
                "timestamp": now_str,
                "current_reference_count": record.reference_count
            },
            metadata=metadata
        )
    except Exception:
        pass
