"""
Relay Event Schema — Canonical event type definitions and envelope structures.

Every event in Relay follows the same structure:

    EventMetadata  — who produced it, from where, and which session
    EventType      — what happened (canonical enum)
    payload        — event-specific data (free-form dict)
    sequencing     — assigned by the database (event_sequence, version)

Design rules:
  - event_sequence (BIGSERIAL) is the ONLY authoritative replay ordering key.
  - version is per-project monotonic, used only for optimistic concurrency.
  - Reducers MUST fold events in event_sequence ASC order.
  - Unknown event types are silently skipped by reducers (forward compatibility).

Project bootstrap requirement:
  Every project stream MUST begin with these three events in order:
    PROJECT_CREATED → PROJECT_GOAL_SET → PROJECT_FOCUS_CHANGED
  compile_cognitive_head() raises MissingProjectBootstrapError if violated.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID


class EventType(str, Enum):
    """
    Canonical set of all Relay event types.

    Grouped by domain. Add new event types here first, then update
    the relevant reducer. Never remove or rename existing values —
    doing so breaks replay of historical event streams.
    """

    # ── Project lifecycle ──────────────────────────────────────────────────
    # Every project stream MUST begin with these three events in this order:
    #   PROJECT_CREATED → PROJECT_GOAL_SET → PROJECT_FOCUS_CHANGED
    PROJECT_CREATED = "PROJECT_CREATED"
    PROJECT_GOAL_SET = "PROJECT_GOAL_SET"
    PROJECT_FOCUS_CHANGED = "PROJECT_FOCUS_CHANGED"

    # ── Task lifecycle ─────────────────────────────────────────────────────
    TASK_CREATED = "TASK_CREATED"
    TASK_MUTATED = "TASK_MUTATED"
    TASK_COMPLETED = "TASK_COMPLETED"

    # ── Decision lifecycle ─────────────────────────────────────────────────
    DECISION_PROPOSED = "DECISION_PROPOSED"
    DECISION_ACCEPTED = "DECISION_ACCEPTED"
    DECISION_SUPERSEDED = "DECISION_SUPERSEDED"

    # ── Open questions ─────────────────────────────────────────────────────
    OPEN_QUESTION_RAISED = "OPEN_QUESTION_RAISED"
    OPEN_QUESTION_RESOLVED = "OPEN_QUESTION_RESOLVED"

    # ── Knowledge stubs (R3 hooks — recorded now, compiled in a future phase)
    FACT_RECORDED = "FACT_RECORDED"
    RELATIONSHIP_CREATED = "RELATIONSHIP_CREATED"
    RELATIONSHIP_SUPERSEDED = "RELATIONSHIP_SUPERSEDED"

    # ── Reflection (R8 — recorded now, generated in a future phase) ────────
    REFLECTION_GENERATED = "REFLECTION_GENERATED"

    # ── Memory Integration (Sprint I1) ─────────────────────────────────────
    MEMORY_RECORDED = "MEMORY_RECORDED"
    MEMORY_CONSOLIDATED = "MEMORY_CONSOLIDATED"
    MEMORY_REFERENCED = "MEMORY_REFERENCED"
    MEMORY_SUPERSEDED = "MEMORY_SUPERSEDED"
    MEMORY_ARCHIVED = "MEMORY_ARCHIVED"
    MEMORY_RANKED = "MEMORY_RANKED"
    CONSOLIDATION_CANDIDATE = "CONSOLIDATION_CANDIDATE"
    RETRIEVAL_AUDITED = "RETRIEVAL_AUDITED"
    RETRIEVAL_EXECUTED = "RETRIEVAL_EXECUTED"

    # ── Failure Events ─────────────────────────────────────────────────────
    QUESTION_LOSS = "QUESTION_LOSS"
    CONTEXT_DRIFT = "CONTEXT_DRIFT"
    DECISION_MUTATION = "DECISION_MUTATION"
    DECISION_CONTRADICTION = "DECISION_CONTRADICTION"

    # ── Knowledge Synthesis (Sprint I4) ───────────────────────────────────
    KNOWLEDGE_SYNTHESIZED = "KNOWLEDGE_SYNTHESIZED"
    KNOWLEDGE_SUPERSEDED = "KNOWLEDGE_SUPERSEDED"
    KNOWLEDGE_CONTRADICTION = "KNOWLEDGE_CONTRADICTION"


@dataclass
class EventMetadata:
    """
    Standard metadata envelope attached to every event.

    Fields:
        actor:          Who produced this event.
                        Examples: "Claude", "ChatGPT", "Hermes", "Human", "seed_demo"

        source:         Which subsystem or tool emitted the event.
                        Examples: "ClaudeCompiler", "Manual", "seed_demo", "handoff_metrics"

        correlation_id: Groups events belonging to the same agent work unit.
                        Default: a fresh UUID per EventMetadata instance.

        session_id:     Unique per handoff session — changes on every agent switch.
                        Use the same session_id for all events written by one agent
                        in one continuous work session.
                        Default: a fresh UUID per EventMetadata instance.
    """

    actor: str
    source: str
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> dict[str, str]:
        return {
            "actor": self.actor,
            "source": self.source,
            "correlation_id": self.correlation_id,
            "session_id": self.session_id,
        }

    @classmethod
    def from_dict(cls, d: dict[str, str]) -> "EventMetadata":
        return cls(
            actor=d.get("actor", "unknown"),
            source=d.get("source", "unknown"),
            correlation_id=d.get("correlation_id", str(uuid.uuid4())),
            session_id=d.get("session_id", str(uuid.uuid4())),
        )


@dataclass
class EventRecord:
    """
    A fully hydrated event record as returned from the EventStore.

    Fields:
        event_sequence: Global monotonic ordering key (BIGSERIAL from PostgreSQL).
                        Replay ALWAYS uses ORDER BY event_sequence ASC.
                        This is the source of truth for event ordering.

        id:             Stable UUID for cross-linking (parent_id references, etc.)

        project_id:     The logical project this event belongs to.

        stream_id:      Sub-stream grouping key within a project.
                        Examples: "main", "tasks", "decisions", "questions", "knowledge"
                        Replay loads ALL streams; stream_id is for filtering only.

        version:        Per-project monotonic counter.
                        Used ONLY for optimistic concurrency — NOT for replay ordering.

        event_type:     What happened (matches EventType enum).

        metadata:       Structured envelope: actor, source, correlation_id, session_id.

        payload:        Event-specific data. Schema varies by event_type.
                        See reducer docstrings for expected payload fields.

        parent_id:      Optional UUID of the event that caused this one.
                        Useful for tracing chains of events across agents.

        recorded_at:    Wall-clock insertion time, set by PostgreSQL (DEFAULT now()).
                        Do NOT use recorded_at for replay ordering — use event_sequence.
    """

    event_sequence: int
    id: UUID
    project_id: UUID
    stream_id: str
    version: int
    event_type: EventType
    metadata: EventMetadata
    payload: dict[str, Any]
    parent_id: Optional[UUID]
    recorded_at: datetime

    def __repr__(self) -> str:
        return (
            f"EventRecord("
            f"seq={self.event_sequence}, "
            f"type={self.event_type.value}, "
            f"v={self.version}, "
            f"actor={self.metadata.actor!r}"
            f")"
        )
