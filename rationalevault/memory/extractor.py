from __future__ import annotations

from rationalevault.memory.models import MemoryRecord, MemoryType, generate_memory_id
from rationalevault.schema.events import EventRecord, EventType


def extract_memories_from_event(event: EventRecord) -> list[MemoryRecord]:
    """
    Automatic memory emission rules. Maps EventType to MemoryRecord.
    """
    memories = []
    e_type = event.event_type
    payload = event.payload
    event_id = str(event.id)

    if e_type == EventType.DECISION_ACCEPTED:
        dec = payload.get("decision", "")
        rat = payload.get("rationale", "")

        # Decision Memory
        d_id = generate_memory_id(MemoryType.DECISION.value, "Decision Accepted", dec)
        memories.append(
            MemoryRecord(
                id=d_id,
                version=1,
                title="Decision Accepted",
                content=dec,
                memory_type=MemoryType.DECISION,
                importance="high",
                lifecycle_status="active",
                source_event_ids=[event_id],
                source_type="decision",
                confidence=1.0,
                project_id=str(event.project_id),
            )
        )

        # Rationale Memory
        if rat:
            r_id = generate_memory_id(MemoryType.DECISION_RATIONALE.value, "Decision Rationale", rat)
            memories.append(
                MemoryRecord(
                    id=r_id,
                    version=1,
                    title="Decision Rationale",
                    content=rat,
                    memory_type=MemoryType.DECISION_RATIONALE,
                    importance="high",
                    lifecycle_status="active",
                    source_event_ids=[event_id],
                    source_type="decision_rationale",
                    confidence=1.0,
                    project_id=str(event.project_id),
                )
            )

    elif e_type == EventType.REFLECTION_GENERATED:
        ref = payload.get("reflection", "")
        l_id = generate_memory_id(MemoryType.LESSON_LEARNED.value, "Reflection Lesson Learned", ref)
        memories.append(
            MemoryRecord(
                id=l_id,
                version=1,
                title="Reflection Lesson Learned",
                content=ref,
                memory_type=MemoryType.LESSON_LEARNED,
                importance="medium",
                lifecycle_status="active",
                source_event_ids=[event_id],
                source_type="reflection",
                confidence=1.0,
                project_id=str(event.project_id),
            )
        )

    elif e_type in [
        EventType.QUESTION_LOSS,
        EventType.CONTEXT_DRIFT,
        EventType.DECISION_MUTATION,
        EventType.DECISION_CONTRADICTION,
    ]:
        fail_desc = payload.get("description") or payload.get("observed") or f"Failure event: {e_type.value}"
        f_id = generate_memory_id(MemoryType.FAILURE.value, "Continuity Failure Recorded", fail_desc)
        memories.append(
            MemoryRecord(
                id=f_id,
                version=1,
                title="Continuity Failure Recorded",
                content=fail_desc,
                memory_type=MemoryType.FAILURE,
                importance="high",
                lifecycle_status="active",
                source_event_ids=[event_id],
                source_type="failure",
                confidence=1.0,
                project_id=str(event.project_id),
            )
        )

    elif e_type in [EventType.PROJECT_GOAL_SET, EventType.PROJECT_FOCUS_CHANGED]:
        arch = payload.get("goal") or payload.get("focus") or payload.get("name") or ""
        if arch:
            a_id = generate_memory_id(MemoryType.ARCHITECTURE.value, "Architecture Goal/Focus", arch)
            memories.append(
                MemoryRecord(
                    id=a_id,
                    version=1,
                    title="Architecture Goal/Focus",
                    content=arch,
                    memory_type=MemoryType.ARCHITECTURE,
                    importance="critical",
                    lifecycle_status="active",
                    source_event_ids=[event_id],
                    source_type="architecture",
                    confidence=1.0,
                    project_id=str(event.project_id),
                )
            )

    return memories
