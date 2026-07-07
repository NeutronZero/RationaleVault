"""
RationaleVault Replay Engine — Owns all replay strategy.

ReplayEngine encapsulates the decision logic for fast-path, delta, and full replay.
The compiler delegates entirely to replay_engine.build_projection().

Invariant: There is exactly one reducer execution path. The only permitted
difference between full and delta replay is the initial state and the
starting event sequence. ReplayEngine is the ONLY component permitted
to supply initial_state to reducers.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from rationalevault.cognitive_head.compiler import (
    CognitiveHead,
    MissingProjectBootstrapError,
    _PRIORITY_ORDER,
)
from rationalevault.cognitive_head.reducers import (
    DecisionReducer,
    ProjectReducer,
    QuestionReducer,
    TaskReducer,
)
from rationalevault.cognitive_head.snapshot import (
    NullSnapshotManager,
    SnapshotManager,
)
from rationalevault.cognitive_head.snapshot_payload import (
    CognitiveHeadSnapshotPayload,
)
from rationalevault.schema.events import EventType


class ReplayMode(Enum):
    FULL = "full"
    DELTA = "delta"
    FAST_PATH = "fast_path"


@dataclass
class ReplayResult:
    """Result from ReplayEngine.build_projection()."""
    head: CognitiveHead
    mode: ReplayMode
    events_replayed: int
    events_reused: int
    snapshot_valid: bool
    snapshot_used: bool
    snapshot_sequence: int
    latest_sequence: int


def _build_head(
    project_id: UUID,
    project_state: Any,
    tasks: dict,
    decisions: dict,
    questions: dict,
    events: list,
    all_tasks: dict,
    all_decisions: dict,
    all_questions: dict,
) -> CognitiveHead:
    """Build a CognitiveHead from reducer outputs. Shared by all replay paths."""
    active_tasks = [t for t in tasks.values() if t.status != "completed"]
    active_decisions = [d for d in decisions.values() if d.status == "accepted"]
    open_questions = [q for q in questions.values() if q.status == "open"]

    open_questions.sort(key=lambda q: _PRIORITY_ORDER.get(q.priority, 2))
    active_tasks.sort(key=lambda t: _PRIORITY_ORDER.get(t.priority, 2))

    open_question_ids = {q.question_id for q in open_questions}
    blocker_map: dict[str, set[str]] = {}

    for task in active_tasks:
        for qid in task.blocked_by:
            if qid in open_question_ids:
                blocker_map.setdefault(task.task_id, set()).add(qid)

    for q in open_questions:
        for tid in q.blocks_task_ids:
            if tid in all_tasks:
                blocker_map.setdefault(tid, set()).add(q.question_id)

    blockers = [
        {
            "task_id": tid,
            "task_title": all_tasks[tid].title,
            "blocked_by_questions": sorted(qids),
        }
        for tid, qids in blocker_map.items()
        if tid in all_tasks
    ]

    ledger_version = max(e.version for e in events) if events else 0

    return CognitiveHead(
        project_id=project_id,
        project_name=project_state.name,
        project_goal=project_state.goal,
        current_focus=project_state.current_focus,
        ledger_version=ledger_version,
        compiled_at="",
        active_tasks=active_tasks,
        active_decisions=active_decisions,
        open_questions=open_questions,
        blockers=blockers,
    )


class ReplayEngine:
    """
    Owns all replay strategy. The compiler calls build_projection()
    and receives a ReplayResult. The engine decides fast-path, delta,
    or full replay internally.

    ReplayEngine is the ONLY component permitted to supply initial_state
    to reducers. No other code path may call reduce(events, initial_state=...).
    """

    def __init__(
        self,
        event_store: Any,
        snapshot_manager: Any = None,
    ) -> None:
        self._event_store = event_store
        self._snapshot_manager = snapshot_manager or NullSnapshotManager()

    def build_projection(
        self,
        project_id: UUID,
        projection_name: str = "cognitive_head",
    ) -> ReplayResult:
        """
        Build the CognitiveHead projection for a project.

        Decides between fast-path, delta, and full replay based on
        snapshot availability and staleness.
        """

        # ── Load snapshot ────────────────────────────────────────────────────
        snapshot_valid = False
        snapshot_used = False
        snapshot_sequence = 0
        payload: Optional[CognitiveHeadSnapshotPayload] = None

        if isinstance(self._snapshot_manager, SnapshotManager):
            result = self._snapshot_manager.load_valid_snapshot(
                project_id, projection_name,
            )
            snapshot_valid = result.valid
            if not result.valid:
                self._snapshot_manager.warn_invalid(project_id, result)
            elif result.payload is not None and isinstance(
                result.payload, CognitiveHeadSnapshotPayload
            ):
                payload = result.payload
                snapshot_sequence = payload.sequence

        # ── Get latest sequence ──────────────────────────────────────────────
        latest_seq = self._event_store.get_latest_sequence(project_id)

        # ── Fast path: snapshot is current ───────────────────────────────────
        if payload is not None and snapshot_sequence >= latest_seq:
            head = payload.to_cognitive_head()
            return ReplayResult(
                head=head,
                mode=ReplayMode.FAST_PATH,
                events_replayed=0,
                events_reused=snapshot_sequence,
                snapshot_valid=snapshot_valid,
                snapshot_used=True,
                snapshot_sequence=snapshot_sequence,
                latest_sequence=latest_seq,
            )

        # ── Delta or full replay ─────────────────────────────────────────────
        if payload is not None and snapshot_sequence > 0:
            # Delta: replay only events after snapshot
            events = self._event_store.get_project_stream(
                project_id, since_sequence=snapshot_sequence,
            )
            events_reused = snapshot_sequence

            # Reconstruct initial state from snapshot full reducer state
            proj_state = ProjectReducer.reduce([], initial_state=ProjectState(
                name=payload.project_name,
                goal=payload.project_goal,
                current_focus=payload.current_focus,
            ))
            all_tasks = TaskReducer.reduce([], initial_state={
                k: _dict_to_task_state(v)
                for k, v in payload.tasks.items()
            })
            all_decisions = DecisionReducer.reduce([], initial_state={
                k: _dict_to_decision_state(v)
                for k, v in payload.decisions.items()
            })
            all_questions = QuestionReducer.reduce([], initial_state={
                k: _dict_to_question_state(v)
                for k, v in payload.questions.items()
            })

            # Apply delta events
            proj_state = ProjectReducer.reduce(events, initial_state=proj_state)
            all_tasks = TaskReducer.reduce(events, initial_state=all_tasks)
            all_decisions = DecisionReducer.reduce(events, initial_state=all_decisions)
            all_questions = QuestionReducer.reduce(events, initial_state=all_questions)

            snapshot_used = True
            mode = ReplayMode.DELTA
        else:
            # Full replay
            events = self._event_store.get_project_stream(project_id)
            events_reused = 0

            if not events:
                raise MissingProjectBootstrapError(
                    f"No events found for project {project_id}. "
                    "A project stream must begin with: "
                    "PROJECT_CREATED → PROJECT_GOAL_SET → PROJECT_FOCUS_CHANGED."
                )

            event_types_seen = {e.event_type for e in events}
            for required_type in (
                EventType.PROJECT_CREATED,
                EventType.PROJECT_GOAL_SET,
                EventType.PROJECT_FOCUS_CHANGED,
            ):
                if required_type not in event_types_seen:
                    raise MissingProjectBootstrapError(
                        f"Project {project_id} stream is missing required "
                        f"bootstrap event: {required_type.value}. "
                        "Every project stream must begin with: "
                        "PROJECT_CREATED → PROJECT_GOAL_SET → PROJECT_FOCUS_CHANGED."
                    )

            proj_state = ProjectReducer.reduce(events)
            all_tasks = TaskReducer.reduce(events)
            all_decisions = DecisionReducer.reduce(events)
            all_questions = QuestionReducer.reduce(events)

            snapshot_used = False
            mode = ReplayMode.FULL

        # ── Build head ───────────────────────────────────────────────────────
        from rationalevault.cognitive_head.compiler import CognitiveHead
        from datetime import datetime, timezone

        active_tasks = [t for t in all_tasks.values() if t.status != "completed"]
        active_decisions = [d for d in all_decisions.values() if d.status == "accepted"]
        open_questions = [q for q in all_questions.values() if q.status == "open"]

        open_questions.sort(key=lambda q: _PRIORITY_ORDER.get(q.priority, 2))
        active_tasks.sort(key=lambda t: _PRIORITY_ORDER.get(t.priority, 2))

        open_question_ids = {q.question_id for q in open_questions}
        blocker_map: dict[str, set[str]] = {}

        for task in active_tasks:
            for qid in task.blocked_by:
                if qid in open_question_ids:
                    blocker_map.setdefault(task.task_id, set()).add(qid)

        for q in open_questions:
            for tid in q.blocks_task_ids:
                if tid in all_tasks:
                    blocker_map.setdefault(tid, set()).add(q.question_id)

        blockers = [
            {
                "task_id": tid,
                "task_title": all_tasks[tid].title,
                "blocked_by_questions": sorted(qids),
            }
            for tid, qids in blocker_map.items()
            if tid in all_tasks
        ]

        ledger_version = max(e.version for e in events) if events else 0

        head = CognitiveHead(
            project_id=project_id,
            project_name=proj_state.name,
            project_goal=proj_state.goal,
            current_focus=proj_state.current_focus,
            ledger_version=ledger_version,
            compiled_at=datetime.now(timezone.utc).isoformat(),
            active_tasks=active_tasks,
            active_decisions=active_decisions,
            open_questions=open_questions,
            blockers=blockers,
        )

        return ReplayResult(
            head=head,
            mode=mode,
            events_replayed=len(events),
            events_reused=events_reused,
            snapshot_valid=snapshot_valid,
            snapshot_used=snapshot_used,
            snapshot_sequence=snapshot_sequence,
            latest_sequence=latest_seq,
        )


# ── Helpers for reconstructing reducer state from snapshot dicts ──────────────

def _dict_to_task_state(d: dict) -> TaskState:
    from rationalevault.cognitive_head.reducers import TaskState
    return TaskState(
        task_id=d.get("task_id", ""),
        title=d.get("title", ""),
        description=d.get("description", ""),
        status=d.get("status", "open"),
        assignee=d.get("assignee"),
        priority=d.get("priority", "normal"),
        tags=list(d.get("tags", [])),
        blocked_by=list(d.get("blocked_by", [])),
        created_at=d.get("created_at"),
        updated_at=d.get("updated_at"),
        completed_at=d.get("completed_at"),
        created_by=d.get("created_by", ""),
        progress_notes=list(d.get("progress_notes", [])),
        related_knowledge_ids=list(d.get("related_knowledge_ids", [])),
    )


def _dict_to_decision_state(d: dict) -> DecisionState:
    from rationalevault.cognitive_head.reducers import DecisionState
    return DecisionState(
        decision_id=d.get("decision_id", ""),
        title=d.get("title", ""),
        description=d.get("description", ""),
        status=d.get("status", "proposed"),
        rationale=d.get("rationale", ""),
        context=d.get("context", ""),
        category=d.get("category", "general"),
        superseded_by=d.get("superseded_by"),
        created_at=d.get("created_at"),
        accepted_at=d.get("accepted_at"),
        created_by=d.get("created_by", ""),
    )


def _dict_to_question_state(d: dict) -> QuestionState:
    from rationalevault.cognitive_head.reducers import QuestionState
    return QuestionState(
        question_id=d.get("question_id", ""),
        title=d.get("title", ""),
        description=d.get("description", ""),
        status=d.get("status", "open"),
        priority=d.get("priority", "normal"),
        resolution=d.get("resolution"),
        blocks_task_ids=list(d.get("blocks_task_ids", [])),
        raised_at=d.get("raised_at"),
        resolved_at=d.get("resolved_at"),
        raised_by=d.get("raised_by", ""),
    )


# Need ProjectState import for delta path
from rationalevault.cognitive_head.reducers import ProjectState  # noqa: E402
from rationalevault.cognitive_head.reducers import DecisionState  # noqa: E402
from rationalevault.cognitive_head.reducers import QuestionState  # noqa: E402
from rationalevault.cognitive_head.reducers import TaskState  # noqa: E402
