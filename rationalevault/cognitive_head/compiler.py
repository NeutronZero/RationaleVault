"""
RationaleVault Cognitive Head Compiler.

compile_cognitive_head(project_id) → CognitiveHead

Compiles the current project state by replaying ALL events from the
ledger through the four state reducers. No cached state. Pure replay.
Same event sequence always produces identical output.

Bootstrap validation:
  Every project stream MUST begin with:
    PROJECT_CREATED → PROJECT_GOAL_SET → PROJECT_FOCUS_CHANGED
  Raises MissingProjectBootstrapError if any of these events are absent.
  This prevents partially initialized Cognitive Heads from being compiled.

Output — CognitiveHead:
  project_goal        from PROJECT_GOAL_SET
  current_focus       from PROJECT_FOCUS_CHANGED
  active_tasks        tasks with status != 'completed', sorted by priority
  active_decisions    decisions with status == 'accepted'
  open_questions      questions with status == 'open', sorted by priority
  blockers            tasks blocked by open questions (derived, not stored)
  ledger_version      max(version) across all events

Priority sort order: critical > high > normal > low
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from rationalevault.cognitive_head.reducers import (
    DecisionReducer,
    DecisionState,
    ProjectReducer,
    QuestionReducer,
    QuestionState,
    TaskReducer,
    TaskState,
)
from rationalevault.schema.events import EventType


class MissingProjectBootstrapError(Exception):
    """
    Raised when compile_cognitive_head() encounters a project stream that
    is missing one or more required bootstrap events.

    Required bootstrap sequence:
        PROJECT_CREATED → PROJECT_GOAL_SET → PROJECT_FOCUS_CHANGED

    These three events must appear in the stream before any task, decision,
    or question events. Their presence is validated before compilation begins.
    """


# Priority ranking for sorting (lower number = higher priority)
_PRIORITY_ORDER: dict[str, int] = {
    "critical": 0,
    "high": 1,
    "normal": 2,
    "low": 3,
}


@dataclass
class CognitiveHead:
    """
    The compiled current state of a RationaleVault project.

    Produced by replaying all project events through the four reducers.
    Deterministic: the same event sequence always produces an identical head.

    Fields:
        project_id:       UUID of the project.
        project_name:     From PROJECT_CREATED payload.
        project_goal:     From PROJECT_GOAL_SET payload (latest).
        current_focus:    From PROJECT_FOCUS_CHANGED payload (latest).
        ledger_version:   max(version) across all events — identifies position in ledger.
        compiled_at:      UTC ISO timestamp of when this head was compiled.
        active_tasks:     Tasks with status != 'completed', sorted priority DESC.
        active_decisions: Decisions with status == 'accepted'.
        open_questions:   Questions with status == 'open', sorted priority DESC.
        blockers:         Tasks blocked by open questions (derived).
    """
    project_id: UUID
    project_name: str
    project_goal: str
    current_focus: str
    ledger_version: int
    compiled_at: str

    active_tasks: list[TaskState] = field(default_factory=list)
    active_decisions: list[DecisionState] = field(default_factory=list)
    open_questions: list[QuestionState] = field(default_factory=list)
    blockers: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict for JSON output or comparison."""
        return {
            "project_id": str(self.project_id),
            "project_name": self.project_name,
            "project_goal": self.project_goal,
            "current_focus": self.current_focus,
            "ledger_version": self.ledger_version,
            "compiled_at": self.compiled_at,
            "active_tasks": [
                {
                    "task_id": t.task_id,
                    "title": t.title,
                    "description": t.description,
                    "status": t.status,
                    "priority": t.priority,
                    "assignee": t.assignee,
                    "tags": t.tags,
                    "blocked_by": t.blocked_by,
                    "created_by": t.created_by,
                }
                for t in self.active_tasks
            ],
            "active_decisions": [
                {
                    "decision_id": d.decision_id,
                    "title": d.title,
                    "description": d.description,
                    "rationale": d.rationale,
                    "status": d.status,
                    "created_by": d.created_by,
                }
                for d in self.active_decisions
            ],
            "open_questions": [
                {
                    "question_id": q.question_id,
                    "title": q.title,
                    "description": q.description,
                    "priority": q.priority,
                    "blocks_task_ids": q.blocks_task_ids,
                    "raised_by": q.raised_by,
                }
                for q in self.open_questions
            ],
            "blockers": self.blockers,
        }


def compile_cognitive_head(
    project_id: UUID,
    store: Optional[Any] = None,
) -> CognitiveHead:
    """
    Compile the current Cognitive Head for a project.

    Steps:
      1. Load all events from the ledger (or from EventStore if store not provided).
      2. Validate bootstrap sequence.
      3. Run all four reducers (ProjectReducer, TaskReducer, DecisionReducer, QuestionReducer).
      4. Derive active state: active_tasks, active_decisions, open_questions.
      5. Derive blockers (tasks blocked by open questions).
      6. Sort tasks and questions by priority.
      7. Return CognitiveHead.

    Args:
        project_id: UUID of the project to compile.
        store:      Optional EventStore instance. A new one is created if not provided.
                    Pass a mock in tests to avoid database calls.

    Returns:
        CognitiveHead with all derived state populated.

    Raises:
        MissingProjectBootstrapError: If the stream lacks required bootstrap events.
    """
    if store is None:
        from rationalevault.db.event_store import EventStore
        store = EventStore()

    events = store.get_project_stream(project_id)

    if not events:
        raise MissingProjectBootstrapError(
            f"No events found for project {project_id}. "
            "A project stream must begin with: "
            "PROJECT_CREATED → PROJECT_GOAL_SET → PROJECT_FOCUS_CHANGED."
        )

    # Validate that all three bootstrap event types are present
    event_types_seen = {e.event_type for e in events}
    for required_type in (
        EventType.PROJECT_CREATED,
        EventType.PROJECT_GOAL_SET,
        EventType.PROJECT_FOCUS_CHANGED,
    ):
        if required_type not in event_types_seen:
            raise MissingProjectBootstrapError(
                f"Project {project_id} stream is missing required bootstrap event: "
                f"{required_type.value}. "
                "Every project stream must begin with: "
                "PROJECT_CREATED → PROJECT_GOAL_SET → PROJECT_FOCUS_CHANGED."
            )

    # ── Run reducers ───────────────────────────────────────────────────────
    project_state = ProjectReducer.reduce(events)
    tasks = TaskReducer.reduce(events)
    decisions = DecisionReducer.reduce(events)
    questions = QuestionReducer.reduce(events)

    # ── Derive active state ────────────────────────────────────────────────
    active_tasks = [t for t in tasks.values() if t.status != "completed"]
    active_decisions = [d for d in decisions.values() if d.status == "accepted"]
    open_questions = [q for q in questions.values() if q.status == "open"]

    # Sort by priority: critical first
    open_questions.sort(key=lambda q: _PRIORITY_ORDER.get(q.priority, 2))
    active_tasks.sort(key=lambda t: _PRIORITY_ORDER.get(t.priority, 2))

    # ── Derive blockers ────────────────────────────────────────────────────
    # A task is blocked when:
    #   (a) its blocked_by list references an open question_id, OR
    #   (b) an open question's blocks_task_ids references this task_id
    open_question_ids = {q.question_id for q in open_questions}
    blocker_map: dict[str, set[str]] = {}  # task_id → set of blocking question_ids

    for task in active_tasks:
        for qid in task.blocked_by:
            if qid in open_question_ids:
                blocker_map.setdefault(task.task_id, set()).add(qid)

    for q in open_questions:
        for tid in q.blocks_task_ids:
            if tid in tasks:
                blocker_map.setdefault(tid, set()).add(q.question_id)

    blockers = [
        {
            "task_id": tid,
            "task_title": tasks[tid].title,
            "blocked_by_questions": sorted(qids),
        }
        for tid, qids in blocker_map.items()
        if tid in tasks
    ]

    # ── Ledger version ─────────────────────────────────────────────────────
    ledger_version = max(e.version for e in events)

    return CognitiveHead(
        project_id=project_id,
        project_name=project_state.name,
        project_goal=project_state.goal,
        current_focus=project_state.current_focus,
        ledger_version=ledger_version,
        compiled_at=datetime.now(timezone.utc).isoformat(),
        active_tasks=active_tasks,
        active_decisions=active_decisions,
        open_questions=open_questions,
        blockers=blockers,
    )
