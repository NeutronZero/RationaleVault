"""Timeline normalizer — declarative mapping from events to narrative entries.

Separation of concerns:
- normalize_event(): deterministic mapping (event → TimelineEntry or None)
- render_summary(): human-readable formatting (entry → summary string)

The projection calls normalize_event(). render_summary() is called internally
by normalize_event() to populate the summary field. This separation means
the summary format can be swapped (concise, verbose, localized, AI-generated)
without affecting conformance or state correctness.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from rationalevault.schema.events import EventRecord, EventType
from rationalevault.timeline.state import TimelineCategory, TimelineEntry


@dataclass(frozen=True)
class TimelineMapping:
    """Declarative mapping for a single EventType.

    Each field is a callable that extracts information from an EventRecord.
    This makes adding new event types purely declarative — no new methods.
    """

    category: TimelineCategory
    actor_extractor: Callable[[EventRecord], str | None]
    subject_extractor: Callable[[EventRecord], str | None]
    reference_extractor: Callable[[EventRecord], list[int]]
    summary_renderer: Callable[[EventRecord], str]


def _extract_payload_actor(event: EventRecord) -> str | None:
    return event.payload.get("actor", event.metadata.actor)


def _extract_metadata_actor(event: EventRecord) -> str | None:
    return event.metadata.actor


def _title(event: EventRecord, default: str = "untitled") -> str:
    return event.payload.get("title", default)


def _subject(event: EventRecord, key: str) -> str | None:
    return event.payload.get(key)


# ── Mapping registry ─────────────────────────────────────────────────────────
# Add new narratively significant events here. No code changes elsewhere.

MAPPINGS: dict[EventType, TimelineMapping] = {
    # ── Project milestones ───────────────────────────────────────────────
    EventType.PROJECT_CREATED: TimelineMapping(
        category=TimelineCategory.MILESTONE,
        actor_extractor=_extract_metadata_actor,
        subject_extractor=lambda e: str(e.project_id),
        reference_extractor=lambda e: [],
        summary_renderer=lambda e: "Project created",
    ),
    EventType.PROJECT_GOAL_SET: TimelineMapping(
        category=TimelineCategory.MILESTONE,
        actor_extractor=_extract_metadata_actor,
        subject_extractor=lambda e: str(e.project_id),
        reference_extractor=lambda e: [],
        summary_renderer=lambda e: (
            "Project goal set: " + e.payload.get("goal", "")
        ),
    ),
    EventType.PROJECT_FOCUS_CHANGED: TimelineMapping(
        category=TimelineCategory.MILESTONE,
        actor_extractor=_extract_metadata_actor,
        subject_extractor=lambda e: str(e.project_id),
        reference_extractor=lambda e: [],
        summary_renderer=lambda e: (
            "Project focus changed: "
            + e.payload.get("focus", "")
        ),
    ),
    # ── Tasks ────────────────────────────────────────────────────────────
    EventType.TASK_CREATED: TimelineMapping(
        category=TimelineCategory.TASK,
        actor_extractor=_extract_payload_actor,
        subject_extractor=lambda e: _subject(e, "task_id"),
        reference_extractor=lambda e: [],
        summary_renderer=lambda e: "Task created: " + _title(e),
    ),
    EventType.TASK_COMPLETED: TimelineMapping(
        category=TimelineCategory.TASK,
        actor_extractor=_extract_payload_actor,
        subject_extractor=lambda e: _subject(e, "task_id"),
        reference_extractor=lambda e: [],
        summary_renderer=lambda e: "Task completed: " + _title(e),
    ),
    # ── Decisions ────────────────────────────────────────────────────────
    EventType.DECISION_PROPOSED: TimelineMapping(
        category=TimelineCategory.DECISION,
        actor_extractor=_extract_payload_actor,
        subject_extractor=lambda e: _subject(e, "decision_id"),
        reference_extractor=lambda e: [],
        summary_renderer=lambda e: (
            "Decision proposed: " + _title(e)
        ),
    ),
    EventType.DECISION_ACCEPTED: TimelineMapping(
        category=TimelineCategory.DECISION,
        actor_extractor=_extract_payload_actor,
        subject_extractor=lambda e: _subject(e, "decision_id"),
        reference_extractor=lambda e: [],
        summary_renderer=lambda e: (
            "Decision accepted: " + _title(e)
        ),
    ),
    EventType.DECISION_SUPERSEDED: TimelineMapping(
        category=TimelineCategory.DECISION,
        actor_extractor=_extract_payload_actor,
        subject_extractor=lambda e: _subject(e, "decision_id"),
        reference_extractor=lambda e: [],
        summary_renderer=lambda e: (
            "Decision superseded: " + _title(e)
        ),
    ),
    # ── Questions ────────────────────────────────────────────────────────
    EventType.OPEN_QUESTION_RAISED: TimelineMapping(
        category=TimelineCategory.QUESTION,
        actor_extractor=_extract_metadata_actor,
        subject_extractor=lambda e: _subject(e, "question_id"),
        reference_extractor=lambda e: [],
        summary_renderer=lambda e: (
            "Question raised: "
            + e.payload.get("question", "")
        ),
    ),
    EventType.OPEN_QUESTION_RESOLVED: TimelineMapping(
        category=TimelineCategory.QUESTION,
        actor_extractor=_extract_metadata_actor,
        subject_extractor=lambda e: _subject(e, "question_id"),
        reference_extractor=lambda e: [],
        summary_renderer=lambda e: (
            "Question resolved: "
            + e.payload.get("question", "")
        ),
    ),
    # ── Knowledge ────────────────────────────────────────────────────────
    EventType.KNOWLEDGE_CREATED: TimelineMapping(
        category=TimelineCategory.KNOWLEDGE,
        actor_extractor=_extract_metadata_actor,
        subject_extractor=lambda e: _subject(
            e, "knowledge_id",
        ) or _subject(e, "id"),
        reference_extractor=lambda e: [],
        summary_renderer=lambda e: (
            "Knowledge created: " + _title(e)
        ),
    ),
    EventType.KNOWLEDGE_UPDATED: TimelineMapping(
        category=TimelineCategory.KNOWLEDGE,
        actor_extractor=_extract_metadata_actor,
        subject_extractor=lambda e: _subject(
            e, "knowledge_id",
        ) or _subject(e, "id"),
        reference_extractor=lambda e: [],
        summary_renderer=lambda e: (
            "Knowledge updated: " + _title(e)
        ),
    ),
    EventType.KNOWLEDGE_DELETED: TimelineMapping(
        category=TimelineCategory.KNOWLEDGE,
        actor_extractor=_extract_metadata_actor,
        subject_extractor=lambda e: _subject(
            e, "knowledge_id",
        ) or _subject(e, "id"),
        reference_extractor=lambda e: [],
        summary_renderer=lambda e: (
            "Knowledge deleted: " + _title(e)
        ),
    ),
    EventType.KNOWLEDGE_SYNTHESIZED: TimelineMapping(
        category=TimelineCategory.KNOWLEDGE,
        actor_extractor=_extract_metadata_actor,
        subject_extractor=lambda e: _subject(
            e, "knowledge_id",
        ) or _subject(e, "id"),
        reference_extractor=lambda e: [],
        summary_renderer=lambda e: (
            "Knowledge synthesized: " + _title(e)
        ),
    ),
    # ── Knowledge promotion milestones ───────────────────────────────────
    EventType.KNOWLEDGE_PROMOTION_APPROVED: TimelineMapping(
        category=TimelineCategory.MILESTONE,
        actor_extractor=_extract_metadata_actor,
        subject_extractor=lambda e: _subject(e, "knowledge_id"),
        reference_extractor=lambda e: [],
        summary_renderer=lambda e: (
            "Knowledge promotion approved: " + _title(e)
        ),
    ),
    EventType.KNOWLEDGE_PROMOTION_REJECTED: TimelineMapping(
        category=TimelineCategory.MILESTONE,
        actor_extractor=_extract_metadata_actor,
        subject_extractor=lambda e: _subject(e, "knowledge_id"),
        reference_extractor=lambda e: [],
        summary_renderer=lambda e: (
            "Knowledge promotion rejected: " + _title(e)
        ),
    ),
    # ── Memory ───────────────────────────────────────────────────────────
    EventType.MEMORY_RECORDED: TimelineMapping(
        category=TimelineCategory.MEMORY,
        actor_extractor=_extract_metadata_actor,
        subject_extractor=lambda e: _subject(e, "memory_id"),
        reference_extractor=lambda e: [],
        summary_renderer=lambda e: (
            "Memory recorded: "
            + e.payload.get("content", "")[:80]
        ),
    ),
    # ── Governance ───────────────────────────────────────────────────────
    EventType.GOVERNANCE_DECISION_RECORDED: TimelineMapping(
        category=TimelineCategory.DECISION,
        actor_extractor=_extract_metadata_actor,
        subject_extractor=lambda e: _subject(
            e, "governance_id",
        ),
        reference_extractor=lambda e: [],
        summary_renderer=lambda e: (
            "Governance decision: "
            + e.payload.get("action", "")
        ),
    ),
    # ── System ───────────────────────────────────────────────────────────
    EventType.SKILL_EXECUTED: TimelineMapping(
        category=TimelineCategory.SYSTEM,
        actor_extractor=_extract_metadata_actor,
        subject_extractor=lambda e: _subject(e, "skill_name"),
        reference_extractor=lambda e: [],
        summary_renderer=lambda e: (
            "Skill executed: "
            + e.payload.get("skill_name", "unknown")
        ),
    ),
}


# ── Public API ───────────────────────────────────────────────────────────────


def render_summary(entry: TimelineEntry) -> str:
    """Render a human-readable summary from a normalized entry.

    This is the presentation layer — it can be swapped for concise,
    verbose, localized, or AI-generated summaries without affecting
    conformance or state correctness.
    """
    mapping = MAPPINGS.get(entry.event_type)
    if mapping is not None:
        return mapping.summary_renderer(
            EventRecord(
                event_sequence=entry.sequence,
                id=entry.subject_entity or "",
                project_id=entry.subject_entity or "",
                stream_id="",
                version=1,
                event_type=entry.event_type,
                metadata=type(
                    "M", (), {"actor": entry.actor or ""},
                )(),
                payload={},
                parent_id=None,
                recorded_at=entry.timestamp,
            ),
        )
    ts = entry.timestamp.isoformat() if entry.timestamp else "?"
    return f"{entry.event_type.value} at {ts}"


def normalize_event(event: EventRecord) -> TimelineEntry | None:
    """Deterministic mapping: event → TimelineEntry or None.

    Returns None if the event is not narratively significant.
    This is the function tested by the Conformance Suite.
    """
    mapping = MAPPINGS.get(event.event_type)
    if mapping is None:
        return None

    return TimelineEntry(
        sequence=event.event_sequence,
        timestamp=event.recorded_at,
        event_type=event.event_type,
        category=mapping.category,
        actor=mapping.actor_extractor(event),
        subject_entity=mapping.subject_extractor(event),
        summary=mapping.summary_renderer(event),
        references=mapping.reference_extractor(event),
    )
