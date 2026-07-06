from __future__ import annotations

from datetime import datetime
from rationalevault.memory.factory import get_memory_provider
from rationalevault.schema.events import EventMetadata, EventType, EventRecord


def handle_lifecycle_transitions(event: EventRecord) -> None:
    """
    Checks event types and automatically runs state transitions like supersession.
    If a DECISION_ACCEPTED payload contains a 'supersedes' field matching an existing
    memory ID or title/content, that memory's state is updated to 'superseded',
    and a MEMORY_SUPERSEDED event is logged to the ledger.
    """
    if event.event_type != EventType.DECISION_ACCEPTED:
        return

    payload = event.payload
    supersedes = payload.get("supersedes")
    if not supersedes:
        return

    provider = get_memory_provider()
    records = provider.get_all_records()

    # Locate the target record to supersede
    target_record = next(
        (r for r in records if r.id == supersedes or r.title.lower() == supersedes.lower() or r.content.lower() == supersedes.lower()),
        None
    )

    if target_record and target_record.lifecycle_status != "superseded":
        target_record.lifecycle_status = "superseded"
        provider.add_record(target_record)

        # Log MEMORY_SUPERSEDED event
        try:
            from rationalevault.db.event_store import EventStore
            store = EventStore()
            metadata = EventMetadata(actor=event.metadata.actor, source="lifecycle_manager")
            store.append_event(
                project_id=event.project_id,
                stream_id="decisions",
                event_type=EventType.MEMORY_SUPERSEDED,
                payload={
                    "memory_id": target_record.id,
                    "superseded_by_event_id": str(event.id),
                    "timestamp": datetime.now().isoformat()
                },
                metadata=metadata,
                parent_id=event.id
            )
        except Exception:
            pass
