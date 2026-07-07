"""CognitiveHeadProjection — first projection migrated to the Projection Platform.

Phase A migration: wraps existing CognitiveHead reducer logic in the
Projection protocol. Zero-behavior change — the compiler delegates to
the same reducers via the Projection interface.
"""
from __future__ import annotations

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
from rationalevault.cognitive_head.snapshot_payload import (
    CognitiveHeadSnapshotPayload,
)
from rationalevault.projection_platform.context import ProjectionContext
from rationalevault.projection_platform.models import (
    EventSelector,
    ProjectionCapabilities,
    ProjectionHealth,
    ProjectionMetadata,
)
from rationalevault.schema.events import EventRecord, EventType


class CognitiveHeadProjection:
    """Projection that compiles a CognitiveHead from the event stream.

    Implements the Projection protocol. State is a CognitiveHead dataclass.
    Snapshot payload is CognitiveHeadSnapshotPayload.
    """

    def __init__(self) -> None:
        self._health = ProjectionHealth.UNKNOWN
        self._ctx: Optional[ProjectionContext] = None

    @property
    def metadata(self) -> ProjectionMetadata:
        return ProjectionMetadata(
            id="cognitive_head",
            version=1,
            schema_version=CognitiveHeadSnapshotPayload.SCHEMA_VERSION,
            consumed_events=EventSelector(
                types=frozenset({
                    EventType.PROJECT_CREATED,
                    EventType.PROJECT_GOAL_SET,
                    EventType.PROJECT_FOCUS_CHANGED,
                    EventType.TASK_CREATED,
                    EventType.TASK_MUTATED,
                    EventType.TASK_COMPLETED,
                    EventType.TASK_PROGRESS_NOTED,
                    EventType.DECISION_PROPOSED,
                    EventType.DECISION_ACCEPTED,
                    EventType.DECISION_SUPERSEDED,
                    EventType.OPEN_QUESTION_RAISED,
                    EventType.OPEN_QUESTION_RESOLVED,
                    EventType.FACT_RECORDED,
                }),
            ),
            capabilities=ProjectionCapabilities(
                searchable=False,
                snapshotable=True,
                observable=True,
                exportable=False,
                mutable=False,
            ),
            dependencies=(),
            description=(
                "Append-only projection of agent task/decision/question "
                "state from the event stream."
            ),
        )

    def initialize(self, ctx: ProjectionContext) -> None:
        self._ctx = ctx
        self._health = ProjectionHealth.INITIALIZING

    def reduce(
        self,
        events: list[EventRecord],
        initial_state: Optional[Any] = None,
    ) -> CognitiveHead:
        """Pure event → CognitiveHead transformer.

        This is the single reducer execution path. The ProjectionCompiler
        decides what events to pass and whether to supply initial_state.
        """
        self._health = ProjectionHealth.BUILDING

        if not events and initial_state is not None:
            # Fast path or delta with no new events — return existing state
            self._health = ProjectionHealth.READY
            return initial_state  # type: ignore[return-value]

        # Determine if this is a full replay or delta
        is_full = initial_state is None

        if is_full:
            if not events:
                raise MissingProjectBootstrapError(
                    "No events provided and no initial state. "
                    "A project stream must begin with: "
                    "PROJECT_CREATED → PROJECT_GOAL_SET → "
                    "PROJECT_FOCUS_CHANGED."
                )

            # Validate bootstrap sequence for full replay
            event_types_seen = {e.event_type for e in events}
            for required_type in (
                EventType.PROJECT_CREATED,
                EventType.PROJECT_GOAL_SET,
                EventType.PROJECT_FOCUS_CHANGED,
            ):
                if required_type not in event_types_seen:
                    raise MissingProjectBootstrapError(
                        f"Stream is missing required bootstrap event: "
                        f"{required_type.value}. Every project stream must "
                        f"begin with: PROJECT_CREATED → PROJECT_GOAL_SET → "
                        f"PROJECT_FOCUS_CHANGED."
                    )

            proj_state = ProjectReducer.reduce(events)
            all_tasks = TaskReducer.reduce(events)
            all_decisions = DecisionReducer.reduce(events)
            all_questions = QuestionReducer.reduce(events)
        else:
            # Delta replay — start from existing CognitiveHead
            head = initial_state
            # Reconstruct reducer states from head, then apply delta
            proj_state = ProjectReducer.reduce(
                [], initial_state=_head_to_project_state(head),
            )
            all_tasks = TaskReducer.reduce(
                [], initial_state=_head_to_tasks_dict(head),
            )
            all_decisions = DecisionReducer.reduce(
                [], initial_state=_head_to_decisions_dict(head),
            )
            all_questions = QuestionReducer.reduce(
                [], initial_state=_head_to_questions_dict(head),
            )

            # Apply delta events
            proj_state = ProjectReducer.reduce(
                events, initial_state=proj_state,
            )
            all_tasks = TaskReducer.reduce(
                events, initial_state=all_tasks,
            )
            all_decisions = DecisionReducer.reduce(
                events, initial_state=all_decisions,
            )
            all_questions = QuestionReducer.reduce(
                events, initial_state=all_questions,
            )

        # Build head (shared logic)
        head = _build_cognitive_head(
            project_id=events[0].project_id if events else UUID(int=0),
            proj_state=proj_state,
            all_tasks=all_tasks,
            all_decisions=all_decisions,
            all_questions=all_questions,
            events=events,
        )

        self._health = ProjectionHealth.READY
        return head

    def serialize(self, state: CognitiveHead) -> dict:
        """Serialize CognitiveHead to dict (snapshot payload format)."""
        return {
            "project_id": str(state.project_id),
            "project_name": state.project_name,
            "project_goal": state.project_goal,
            "current_focus": state.current_focus,
            "ledger_version": state.ledger_version,
            "compiled_at": state.compiled_at,
            "active_tasks": [_task_to_dict(t) for t in state.active_tasks],
            "active_decisions": [
                _decision_to_dict(d) for d in state.active_decisions
            ],
            "open_questions": [
                _question_to_dict(q) for q in state.open_questions
            ],
            "blockers": state.blockers,
        }

    def deserialize(self, payload: dict) -> CognitiveHead:
        """Deserialize dict to CognitiveHead (from snapshot payload)."""
        # If it's a CognitiveHeadSnapshotPayload dict, convert
        if "tasks" in payload and isinstance(payload["tasks"], dict):
            return _payload_dict_to_head(payload)
        # Otherwise it's a serialized CognitiveHead
        return _serialized_dict_to_head(payload)

    def health(self) -> ProjectionHealth:
        return self._health

    def shutdown(self) -> None:
        self._health = ProjectionHealth.SHUTDOWN
        self._ctx = None


# ── Helper functions ──────────────────────────────────────────────────────────


def _build_cognitive_head(
    project_id: UUID,
    proj_state: Any,
    all_tasks: dict,
    all_decisions: dict,
    all_questions: dict,
    events: list,
) -> CognitiveHead:
    """Build a CognitiveHead from reducer outputs."""

    active_tasks = [
        t for t in all_tasks.values() if t.status != "completed"
    ]
    active_decisions = [
        d for d in all_decisions.values() if d.status == "accepted"
    ]
    open_questions = [
        q for q in all_questions.values() if q.status == "open"
    ]

    open_questions.sort(
        key=lambda q: _PRIORITY_ORDER.get(q.priority, 2),
    )
    active_tasks.sort(
        key=lambda t: _PRIORITY_ORDER.get(t.priority, 2),
    )

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
        project_name=proj_state.name,
        project_goal=proj_state.goal,
        current_focus=proj_state.current_focus,
        ledger_version=ledger_version,
        compiled_at="",
        active_tasks=active_tasks,
        active_decisions=active_decisions,
        open_questions=open_questions,
        blockers=blockers,
    )


def _head_to_project_state(head: CognitiveHead) -> Any:
    """Convert CognitiveHead back to ProjectState for delta replay."""
    from rationalevault.cognitive_head.reducers import ProjectState

    return ProjectState(
        name=head.project_name,
        goal=head.project_goal,
        current_focus=head.current_focus,
    )


def _head_to_tasks_dict(head: CognitiveHead) -> dict:
    """Convert CognitiveHead active_tasks back to dict for delta replay."""

    result = {}
    for t in head.active_tasks:
        result[t.task_id] = t
    # Also include completed tasks from blockers context
    # (they won't be in active_tasks but reducers need them)
    return result


def _head_to_decisions_dict(head: CognitiveHead) -> dict:
    """Convert CognitiveHead active_decisions back to dict."""
    result = {}
    for d in head.active_decisions:
        result[d.decision_id] = d
    return result


def _head_to_questions_dict(head: CognitiveHead) -> dict:
    """Convert CognitiveHead open_questions back to dict."""
    result = {}
    for q in head.open_questions:
        result[q.question_id] = q
    return result


def _task_to_dict(t: Any) -> dict:
    from dataclasses import asdict
    return asdict(t)


def _decision_to_dict(d: Any) -> dict:
    from dataclasses import asdict
    return asdict(d)


def _question_to_dict(q: Any) -> dict:
    from dataclasses import asdict
    return asdict(q)


def _payload_dict_to_head(d: dict) -> CognitiveHead:
    """Convert a CognitiveHeadSnapshotPayload dict to CognitiveHead."""
    from rationalevault.cognitive_head.reducers import (
        DecisionState,
        QuestionState,
        TaskState,
    )

    tasks = []
    for tid, td in d.get("tasks", {}).items():
        tasks.append(TaskState(
            task_id=td.get("task_id", tid),
            title=td.get("title", ""),
            description=td.get("description", ""),
            status=td.get("status", "open"),
            assignee=td.get("assignee"),
            priority=td.get("priority", "normal"),
            tags=list(td.get("tags", [])),
            blocked_by=list(td.get("blocked_by", [])),
            created_at=td.get("created_at"),
            updated_at=td.get("updated_at"),
            completed_at=td.get("completed_at"),
            created_by=td.get("created_by", ""),
            progress_notes=list(td.get("progress_notes", [])),
            related_knowledge_ids=list(
                td.get("related_knowledge_ids", []),
            ),
        ))

    decisions = []
    for did, dd in d.get("decisions", {}).items():
        decisions.append(DecisionState(
            decision_id=dd.get("decision_id", did),
            title=dd.get("title", ""),
            description=dd.get("description", ""),
            status=dd.get("status", "proposed"),
            rationale=dd.get("rationale", ""),
            context=dd.get("context", ""),
            category=dd.get("category", "general"),
            superseded_by=dd.get("superseded_by"),
            created_at=dd.get("created_at"),
            accepted_at=dd.get("accepted_at"),
            created_by=dd.get("created_by", ""),
        ))

    questions = []
    for qid, qd in d.get("questions", {}).items():
        questions.append(QuestionState(
            question_id=qd.get("question_id", qid),
            title=qd.get("title", ""),
            description=qd.get("description", ""),
            status=qd.get("status", "open"),
            priority=qd.get("priority", "normal"),
            resolution=qd.get("resolution"),
            blocks_task_ids=list(qd.get("blocks_task_ids", [])),
            raised_at=qd.get("raised_at"),
            resolved_at=qd.get("resolved_at"),
            raised_by=qd.get("raised_by", ""),
        ))

    return CognitiveHead(
        project_id=UUID(d.get("project_id", "00000000-0000-0000-0000-000000000000")),
        project_name=d.get("project_name", ""),
        project_goal=d.get("project_goal", ""),
        current_focus=d.get("current_focus", ""),
        ledger_version=d.get("ledger_version", 0),
        compiled_at=d.get("compiled_at", ""),
        active_tasks=tasks,
        active_decisions=decisions,
        open_questions=questions,
        blockers=d.get("blockers", []),
    )


def _serialized_dict_to_head(d: dict) -> CognitiveHead:
    """Convert a serialized CognitiveHead dict to CognitiveHead."""
    from rationalevault.cognitive_head.reducers import (
        DecisionState,
        QuestionState,
        TaskState,
    )

    tasks = []
    for td in d.get("active_tasks", []):
        tasks.append(TaskState(
            task_id=td.get("task_id", ""),
            title=td.get("title", ""),
            description=td.get("description", ""),
            status=td.get("status", "open"),
            assignee=td.get("assignee"),
            priority=td.get("priority", "normal"),
            tags=list(td.get("tags", [])),
            blocked_by=list(td.get("blocked_by", [])),
            created_at=td.get("created_at"),
            updated_at=td.get("updated_at"),
            completed_at=td.get("completed_at"),
            created_by=td.get("created_by", ""),
            progress_notes=list(td.get("progress_notes", [])),
            related_knowledge_ids=list(
                td.get("related_knowledge_ids", []),
            ),
        ))

    decisions = []
    for dd in d.get("active_decisions", []):
        decisions.append(DecisionState(
            decision_id=dd.get("decision_id", ""),
            title=dd.get("title", ""),
            description=dd.get("description", ""),
            status=dd.get("status", "proposed"),
            rationale=dd.get("rationale", ""),
            context=dd.get("context", ""),
            category=dd.get("category", "general"),
            superseded_by=dd.get("superseded_by"),
            created_at=dd.get("created_at"),
            accepted_at=dd.get("accepted_at"),
            created_by=dd.get("created_by", ""),
        ))

    questions = []
    for qd in d.get("open_questions", []):
        questions.append(QuestionState(
            question_id=qd.get("question_id", ""),
            title=qd.get("title", ""),
            description=qd.get("description", ""),
            status=qd.get("status", "open"),
            priority=qd.get("priority", "normal"),
            resolution=qd.get("resolution"),
            blocks_task_ids=list(qd.get("blocks_task_ids", [])),
            raised_at=qd.get("raised_at"),
            resolved_at=qd.get("resolved_at"),
            raised_by=qd.get("raised_by", ""),
        ))

    return CognitiveHead(
        project_id=UUID(d.get("project_id", "00000000-0000-0000-0000-000000000000")),
        project_name=d.get("project_name", ""),
        project_goal=d.get("project_goal", ""),
        current_focus=d.get("current_focus", ""),
        ledger_version=d.get("ledger_version", 0),
        compiled_at=d.get("compiled_at", ""),
        active_tasks=tasks,
        active_decisions=decisions,
        open_questions=questions,
        blockers=d.get("blockers", []),
    )
