"""
RationaleVault Cognitive Head Compiler.

compile_cognitive_head(project_id) → CognitiveHead

Delegates all replay strategy to ReplayEngine. The compiler owns
orchestration only: it calls the engine, then notifies the snapshot
manager to refresh.

Bootstrap validation:
  Every project stream MUST begin with:
    PROJECT_CREATED → PROJECT_GOAL_SET → PROJECT_FOCUS_CHANGED
  Raises MissingProjectBootstrapError if any of these events are absent.

Output — CognitiveHead:
  project_goal        from PROJECT_GOAL_SET
  current_focus       from PROJECT_FOCUS_CHANGED
  active_tasks        tasks with status != 'completed', sorted by priority
  active_decisions    decisions with status == 'accepted'
  open_questions      questions with status == 'open', sorted by priority
  blockers            tasks blocked by open questions (derived, not stored)
  ledger_version      max(version) across all events
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from rationalevault.cognitive_head.reducers import (
    DecisionState,
    QuestionState,
    TaskState,
)


class MissingProjectBootstrapError(Exception):
    """
    Raised when compile_cognitive_head() encounters a project stream that
    is missing one or more required bootstrap events.

    Required bootstrap sequence:
        PROJECT_CREATED → PROJECT_GOAL_SET → PROJECT_FOCUS_CHANGED
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
                    "progress_notes": t.progress_notes,
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
    store: Any = None,
    snapshot_manager: Any = None,
) -> CognitiveHead:
    """
    Compile the current Cognitive Head for a project.

    Delegates replay strategy to ReplayEngine. After compilation,
    notifies snapshot_manager.refresh_snapshot().

    Args:
        project_id:        UUID of the project to compile.
        store:             Optional EventStore instance.
        snapshot_manager:  SnapshotManager instance. If None, a NullSnapshotManager
                           is used (no snapshot operations).

    Returns:
        CognitiveHead with all derived state populated.

    Raises:
        MissingProjectBootstrapError: If the stream lacks required bootstrap events.
    """
    from rationalevault.cognitive_head.replay_engine import ReplayEngine
    from rationalevault.cognitive_head.snapshot import (
        NullSnapshotManager,
        SnapshotManager,
    )

    if store is None:
        from rationalevault.db.event_store import EventStore
        store = EventStore()

    if snapshot_manager is None:
        snapshot_manager = NullSnapshotManager()

    # Delegate all replay logic to the engine
    engine = ReplayEngine(event_store=store, snapshot_manager=snapshot_manager)
    result = engine.build_projection(project_id, "cognitive_head")

    # After compilation, let the snapshot manager decide whether to save
    if isinstance(snapshot_manager, SnapshotManager):
        from rationalevault.cognitive_head.snapshot_payload import (
            CognitiveHeadSnapshotPayload,
        )

        # Rebuild reducer state for snapshot (full state for delta replay)
        from rationalevault.cognitive_head.reducers import (
            DecisionReducer,
            QuestionReducer,
            TaskReducer,
        )
        events = store.get_project_stream(project_id)
        all_tasks = TaskReducer.reduce(events)
        all_decisions = DecisionReducer.reduce(events)
        all_questions = QuestionReducer.reduce(events)

        all_tasks_dict = {
            k: {
                "task_id": t.task_id, "title": t.title,
                "description": t.description, "status": t.status,
                "assignee": t.assignee, "priority": t.priority,
                "tags": t.tags, "blocked_by": t.blocked_by,
                "created_at": t.created_at, "updated_at": t.updated_at,
                "completed_at": t.completed_at, "created_by": t.created_by,
                "progress_notes": t.progress_notes,
                "related_knowledge_ids": t.related_knowledge_ids,
            }
            for k, t in all_tasks.items()
        }
        all_decisions_dict = {
            k: {
                "decision_id": d.decision_id, "title": d.title,
                "description": d.description, "status": d.status,
                "rationale": d.rationale, "context": d.context,
                "category": d.category, "superseded_by": d.superseded_by,
                "created_at": d.created_at, "accepted_at": d.accepted_at,
                "created_by": d.created_by,
            }
            for k, d in all_decisions.items()
        }
        all_questions_dict = {
            k: {
                "question_id": q.question_id, "title": q.title,
                "description": q.description, "status": q.status,
                "priority": q.priority, "resolution": q.resolution,
                "blocks_task_ids": q.blocks_task_ids,
                "raised_at": q.raised_at, "resolved_at": q.resolved_at,
                "raised_by": q.raised_by,
            }
            for k, q in all_questions.items()
        }

        current_seq = store.get_latest_sequence(project_id)
        payload = CognitiveHeadSnapshotPayload.from_cognitive_head(
            result.head, current_seq,
            all_tasks=all_tasks_dict,
            all_decisions=all_decisions_dict,
            all_questions=all_questions_dict,
        )
        snapshot_manager.refresh_snapshot(
            project_id, "cognitive_head", payload, current_seq,
        )

    return result.head
