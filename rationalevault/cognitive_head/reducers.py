"""
RationaleVault Cognitive Head — State Reducers.

Each reducer is a pure fold over an event stream.
Same input events always produce identical output state.

Design rules:
  - No I/O. No side effects. No exceptions from unknown event types.
  - Unknown event types are silently skipped (forward compatibility).
  - Events MUST be passed in event_sequence ASC order (as returned by EventStore).
  - Reducers do not call EventStore. They operate on lists of EventRecord.

Reducer contract:
    reduce(events, initial_state=None) -> State
    reduce([]) -> empty/default state

    If initial_state is provided, it must be a state previously produced
    by the same reducer from a prefix of the event stream. The reducer
    applies only the given events on top of that state.

    Only ReplayEngine is permitted to supply initial_state.

State dataclasses use Python @dataclass for simplicity and inspectability.
They are intentionally not frozen — reducers mutate fields in-place during folding.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from rationalevault.schema.events import EventRecord, EventType


# ── State dataclasses ──────────────────────────────────────────────────────────

@dataclass
class ProjectState:
    """Compiled state from PROJECT_* events."""
    name: str = ""
    goal: str = ""
    current_focus: str = ""
    created_at: Optional[str] = None
    created_by: str = ""


@dataclass
class TaskState:
    """
    Compiled state for a single task.

    Lifecycle:  open → in_progress → completed (or blocked at any point)
    Priority:   low | normal | high | critical
    """
    task_id: str
    title: str
    description: str = ""
    status: str = "open"
    assignee: Optional[str] = None
    priority: str = "normal"
    tags: list[str] = field(default_factory=list)
    blocked_by: list[str] = field(default_factory=list)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    completed_at: Optional[str] = None
    created_by: str = ""
    progress_notes: list[dict] = field(default_factory=list)
# Each entry: {"note": str, "timestamp": str, "actor": str, "source_event_seq": int}
    related_knowledge_ids: list[str] = field(default_factory=list)
    # Future-ready: links task to knowledge nodes for dependency context



@dataclass
class DecisionState:
    """
    State of a single decision, folded from DECISION_* events.

    Fields:
        decision_id:  Unique identifier
        title:        Human-readable title
        description:  Longer explanation
        status:       "proposed" | "accepted" | "superseded"
        rationale:    Reasoning behind the decision
        context:      Additional context (canonical v2)
        category:     Decision category (canonical v2, default "general")
        superseded_by: decision_id that superseded this one, if any
        created_at:   ISO timestamp of DECISION_PROPOSED
        accepted_at:  ISO timestamp of DECISION_ACCEPTED
        created_by:   Actor who proposed the decision
    """
    decision_id: str
    title: str
    description: str = ""
    status: str = "proposed"
    rationale: str = ""
    context: str = ""
    category: str = "general"
    superseded_by: Optional[str] = None
    created_at: Optional[str] = None
    accepted_at: Optional[str] = None
    created_by: str = ""


@dataclass
class QuestionState:
    """
    Compiled state for a single open question.

    Lifecycle:  open → resolved
    Priority:   low | normal | high | critical
    """
    question_id: str
    title: str
    description: str = ""
    status: str = "open"
    priority: str = "normal"
    resolution: Optional[str] = None
    blocks_task_ids: list[str] = field(default_factory=list)
    raised_at: Optional[str] = None
    resolved_at: Optional[str] = None
    raised_by: str = ""


# ── Reducers ───────────────────────────────────────────────────────────────────

class ProjectReducer:
    """
    Folds PROJECT_* events into a single ProjectState.

    Relevant events:
        PROJECT_CREATED       payload: { name }
        PROJECT_GOAL_SET      payload: { goal }
        PROJECT_FOCUS_CHANGED payload: { focus }

    All other event types are silently ignored.
    """

    @staticmethod
    def reduce(
        events: list[EventRecord],
        initial_state: Optional[ProjectState] = None,
    ) -> ProjectState:
        state = initial_state if initial_state is not None else ProjectState()
        for event in events:
            et = event.event_type
            p = event.payload

            if et == EventType.PROJECT_CREATED:
                state.name = p.get("name", "")
                state.created_at = (
                    event.recorded_at.isoformat()
                    if event.recorded_at else None
                )
                state.created_by = event.metadata.actor

            elif et == EventType.PROJECT_GOAL_SET:
                state.goal = p.get("goal", "")

            elif et == EventType.PROJECT_FOCUS_CHANGED:
                state.current_focus = p.get("focus", "")

        return state


class TaskReducer:
    """
    Folds TASK_* events into a dict mapping task_id → TaskState.

    Relevant events:
        TASK_CREATED  payload: { task_id, details: { summary, body }, assignee?,
                                  priority?, tags?, blocked_by? }
        TASK_MUTATED  payload: { task_id, <any TaskState field to update> }
        TASK_COMPLETED payload: { task_id }

    Unknown task_ids in TASK_MUTATED / TASK_COMPLETED are silently skipped.
    Events missing task_id are silently skipped.
    All other event types are silently ignored.
    """

    @staticmethod
    def reduce(
        events: list[EventRecord],
        initial_state: Optional[dict[str, TaskState]] = None,
    ) -> dict[str, TaskState]:
        tasks: dict[str, TaskState] = (
            initial_state if initial_state is not None else {}
        )

        for event in events:
            et = event.event_type
            p = event.payload
            task_id = p.get("task_id")

            if et == EventType.TASK_CREATED:
                if not task_id:
                    continue
                details = p["details"]
                title = details["summary"]
                description = details["body"]

                tasks[task_id] = TaskState(
                    task_id=task_id,
                    title=title,
                    description=description,
                    status="open",
                    assignee=p.get("assignee"),
                    priority=p.get("priority", "normal"),
                    tags=list(p.get("tags", [])),
                    blocked_by=list(p.get("blocked_by", [])),
                    created_at=(
                        event.recorded_at.isoformat()
                        if event.recorded_at else None
                    ),
                    created_by=event.metadata.actor,
                )

            elif et == EventType.TASK_MUTATED:
                if not task_id or task_id not in tasks:
                    continue
                t = tasks[task_id]
                for k, v in p.items():
                    if k == "task_id":
                        continue
                    if hasattr(t, k):
                        setattr(t, k, v)
                t.updated_at = (
                    event.recorded_at.isoformat()
                    if event.recorded_at else None
                )

            elif et == EventType.TASK_COMPLETED:
                if not task_id or task_id not in tasks:
                    continue
                tasks[task_id].status = "completed"
                tasks[task_id].completed_at = (
                    event.recorded_at.isoformat()
                    if event.recorded_at else None
                )

            elif et == EventType.TASK_PROGRESS_NOTED:
                if not task_id or task_id not in tasks:
                    continue
                tasks[task_id].progress_notes.append({
                    "note": p.get("note", ""),
                    "timestamp": (
                        event.recorded_at.isoformat()
                        if event.recorded_at else None
                    ),
                    "actor": event.metadata.actor,
                    "source_event_seq": event.event_sequence,
                })


        return tasks


class DecisionReducer:
    """
    Folds DECISION_* events into a dict mapping decision_id → DecisionState.

    Relevant events:
        DECISION_PROPOSED   payload: { decision_id, title, description?,
                                        rationale?, context?, category? }
        DECISION_ACCEPTED   payload: { decision_id }
        DECISION_SUPERSEDED payload: { decision_id, superseded_by? }

    Unknown decision_ids in DECISION_ACCEPTED / DECISION_SUPERSEDED are skipped.
    Events missing decision_id are silently skipped.
    All other event types are silently ignored.
    """

    @staticmethod
    def reduce(
        events: list[EventRecord],
        initial_state: Optional[dict[str, DecisionState]] = None,
    ) -> dict[str, DecisionState]:
        decisions: dict[str, DecisionState] = (
            initial_state if initial_state is not None else {}
        )

        for event in events:
            et = event.event_type
            p = event.payload
            decision_id = p.get("decision_id")

            if et == EventType.DECISION_PROPOSED:
                if not decision_id:
                    continue
                decisions[decision_id] = DecisionState(
                    decision_id=decision_id,
                    title=p.get("title", ""),
                    description=p.get("description", ""),
                    status="proposed",
                    rationale=p.get("rationale", ""),
                    context=p.get("context", ""),
                    category=p.get("category", "general"),
                    superseded_by=None,
                    created_at=(
                        event.recorded_at.isoformat()
                        if event.recorded_at else None
                    ),
                    created_by=event.metadata.actor,
                )

            elif et == EventType.DECISION_ACCEPTED:
                if not decision_id or decision_id not in decisions:
                    continue
                decisions[decision_id].status = "accepted"
                decisions[decision_id].accepted_at = (
                    event.recorded_at.isoformat()
                    if event.recorded_at else None
                )

            elif et == EventType.DECISION_SUPERSEDED:
                if not decision_id or decision_id not in decisions:
                    continue
                decisions[decision_id].status = "superseded"
                decisions[decision_id].superseded_by = p.get("superseded_by")

        return decisions


class QuestionReducer:
    """
    Folds OPEN_QUESTION_* events into a dict mapping question_id → QuestionState.

    Relevant events:
        OPEN_QUESTION_RAISED   payload: { question_id, title, description?,
                                           priority?, blocks_task_ids? }
        OPEN_QUESTION_RESOLVED payload: { question_id, resolution? }

    Unknown question_ids in OPEN_QUESTION_RESOLVED are silently skipped.
    Events missing question_id are silently skipped.
    All other event types are silently ignored.
    """

    @staticmethod
    def reduce(
        events: list[EventRecord],
        initial_state: Optional[dict[str, QuestionState]] = None,
    ) -> dict[str, QuestionState]:
        questions: dict[str, QuestionState] = (
            initial_state if initial_state is not None else {}
        )

        for event in events:
            et = event.event_type
            p = event.payload
            question_id = p.get("question_id")

            if et == EventType.OPEN_QUESTION_RAISED:
                if not question_id:
                    continue
                questions[question_id] = QuestionState(
                    question_id=question_id,
                    title=p.get("title", ""),
                    description=p.get("description", ""),
                    status="open",
                    priority=p.get("priority", "normal"),
                    blocks_task_ids=list(p.get("blocks_task_ids", [])),
                    raised_at=(
                        event.recorded_at.isoformat()
                        if event.recorded_at else None
                    ),
                    raised_by=event.metadata.actor,
                )

            elif et == EventType.OPEN_QUESTION_RESOLVED:
                if not question_id or question_id not in questions:
                    continue
                questions[question_id].status = "resolved"
                questions[question_id].resolution = p.get("resolution", "")
                questions[question_id].resolved_at = (
                    event.recorded_at.isoformat()
                    if event.recorded_at else None
                )

        return questions
