from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from rationalevault.cognitive_head.compiler import MissingProjectBootstrapError
from rationalevault.cognitive_head.reducers import (
    ProjectReducer,
    TaskReducer,
    DecisionReducer,
    QuestionReducer,
    TaskState,
    DecisionState,
    QuestionState,
)
from rationalevault.schema.events import EventRecord, EventType
from rationalevault.projections.session import SessionSummary, SessionProjection

_PRIORITY_ORDER: dict[str, int] = {
    "critical": 0,
    "high": 1,
    "normal": 2,
    "low": 3,
}

@dataclass
class ContinuationState:
    """
    Compiled continuation state of a project.
    """
    project_id: str
    project_name: str
    project_goal: str
    current_focus: str
    compiled_at: str

    # Session context
    last_session: Optional[SessionSummary]

    # Work state
    in_progress_tasks: list[TaskState]      # status == "in_progress", priority-sorted
    open_tasks: list[TaskState]             # status == "open", priority-sorted
    recent_decisions: list[DecisionState]   # last 5 accepted decisions
    open_questions: list[QuestionState]     # all open, priority-sorted
    blockers: list[dict]                    # same structure as CognitiveHead.blockers

    # Activity
    recent_events: list[dict]              # last 10 events as summary dicts
    context_snapshots: list[dict]          # CONTEXT_SNAPSHOT_RECORDED, LAST 10 ONLY

    # Derived resumption
    next_actions: list[str]                # ordered: blocked_on → questions → in_progress → open

    # Provenance
    provenance: dict[str, list[int]]       # key → list of source event_sequence values

    def to_dict(self) -> dict:
        return {
            "project_id": str(self.project_id),
            "project_name": self.project_name,
            "project_goal": self.project_goal,
            "current_focus": self.current_focus,
            "compiled_at": self.compiled_at,
            "last_session": self.last_session.to_dict() if self.last_session else None,
            "in_progress_tasks": [
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
                for t in self.in_progress_tasks
            ],
            "open_tasks": [
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
                for t in self.open_tasks
            ],
            "recent_decisions": [
                {
                    "decision_id": d.decision_id,
                    "title": d.title,
                    "description": d.description,
                    "rationale": d.rationale,
                    "status": d.status,
                    "created_by": d.created_by,
                }
                for d in self.recent_decisions
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
            "recent_events": self.recent_events,
            "context_snapshots": self.context_snapshots,
            "next_actions": self.next_actions,
            "provenance": self.provenance,
        }


class ContinuationProjection:
    @staticmethod
    def project(project_id: UUID, store=None, reference_time: Optional[datetime] = None) -> ContinuationState:
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

        # ── Derive active/work state ──────────────────────────────────────────
        in_progress_tasks = [t for t in tasks.values() if t.status == "in_progress"]
        open_tasks = [t for t in tasks.values() if t.status == "open"]
        accepted_decisions = [d for d in decisions.values() if d.status == "accepted"]
        open_questions = [q for q in questions.values() if q.status == "open"]

        # Sort tasks and questions by priority
        in_progress_tasks.sort(key=lambda t: _PRIORITY_ORDER.get(t.priority, 2))
        open_tasks.sort(key=lambda t: _PRIORITY_ORDER.get(t.priority, 2))
        open_questions.sort(key=lambda q: _PRIORITY_ORDER.get(q.priority, 2))

        # Recent decisions: keep last 5 accepted decisions (by event sequence / insertion order)
        # We can map accepted_decisions back to their creation/acceptance sequence, or just sort them
        # Let's find the events where decisions were accepted/proposed and order by event_sequence DESC.
        decision_last_seq: dict[str, int] = {}
        for ev in events:
            if ev.event_type in (EventType.DECISION_PROPOSED, EventType.DECISION_ACCEPTED) and "decision_id" in ev.payload:
                decision_last_seq[ev.payload["decision_id"]] = ev.event_sequence
        
        accepted_decisions.sort(key=lambda d: decision_last_seq.get(d.decision_id, 0), reverse=True)
        recent_decisions = accepted_decisions[:5]
        # Keep recent_decisions chronological (reverse the slice back to chronological order or keep it DESC?)
        # Let's keep it DESC for recent, or ASC? Let's just keep them sorted DESC or ASC.
        # "last 5 accepted decisions" -> standard is chronological (ASC) or reverse chronological (DESC). Let's keep chronological.
        recent_decisions.reverse()

        # ── Derive blockers ────────────────────────────────────────────────────
        open_question_ids = {q.question_id for q in open_questions}
        blocker_map: dict[str, set[str]] = {}
        for task in (in_progress_tasks + open_tasks):
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

        # ── Sessions ───────────────────────────────────────────────────────────
        last_session = SessionProjection.last_session(events)

        # ── Context Snapshots ──────────────────────────────────────────────────
        # Find CONTEXT_SNAPSHOT_RECORDED events
        snapshot_records = [
            ev for ev in events if ev.event_type == EventType.CONTEXT_SNAPSHOT_RECORDED
        ]
        # sort by event_sequence ASC, keep last 10
        snapshot_records.sort(key=lambda e: e.event_sequence)
        recent_snapshots = snapshot_records[-10:]
        
        context_snapshots = []
        for e in recent_snapshots:
            context_snapshots.append({
                "summary": e.payload.get("summary", ""),
                "next_action": e.payload.get("next_action"),
                "blocked_on": e.payload.get("blocked_on"),
                "event_sequence": e.event_sequence,
                "recorded_at": e.recorded_at.isoformat() if e.recorded_at else None,
                "actor": e.metadata.actor if e.metadata else "unknown",
            })

        # ── Recent Events ──────────────────────────────────────────────────────
        # Last 10 events by sequence
        sorted_events = sorted(events, key=lambda e: e.event_sequence)
        recent_records = sorted_events[-10:]
        recent_events = []
        for e in recent_records:
            recent_events.append({
                "event_sequence": e.event_sequence,
                "event_type": e.event_type.value if hasattr(e.event_type, "value") else str(e.event_type),
                "recorded_at": e.recorded_at.isoformat() if e.recorded_at else None,
                "actor": e.metadata.actor if e.metadata else "unknown",
            })

        # ── Derived Resumption (Next Actions) ──────────────────────────────────
        next_actions: list[str] = []
        latest_snapshot = context_snapshots[-1] if context_snapshots else None
        
        # 1. If latest context_snapshot.blocked_on exists -> "Unblock: {blocked_on}"
        if latest_snapshot and latest_snapshot.get("blocked_on"):
            next_actions.append(f"Unblock: {latest_snapshot['blocked_on']}")
            
        # 2. If open_questions exist -> "Resolve: {question.title}" (priority-sorted)
        for q in open_questions:
            next_actions.append(f"Resolve: {q.title}")
            
        # 3. If latest context_snapshot.next_action exists -> "{next_action}"
        if latest_snapshot and latest_snapshot.get("next_action"):
            next_actions.append(latest_snapshot["next_action"])
            
        # 4. If in_progress_tasks exist -> "Continue: {task.title}" (priority-sorted)
        for t in in_progress_tasks:
            next_actions.append(f"Continue: {t.title}")
            
        # 5. If open_tasks exist -> "Start: {task.title}" (highest priority)
        for t in open_tasks:
            next_actions.append(f"Start: {t.title}")
            
        # 6. Fallback -> "Review project state and propose the next sprint."
        if not next_actions:
            next_actions.append("Review project state and propose the next sprint.")

        # ── Provenance ─────────────────────────────────────────────────────────
        # Keys: "in_progress_tasks", "open_questions", "recent_decisions",
        #       "context_snapshots", "recent_events", "last_session"
        
        in_progress_ids = {t.task_id for t in in_progress_tasks}
        open_question_ids_set = {q.question_id for q in open_questions}
        recent_decision_ids = {d.decision_id for d in recent_decisions}
        
        prov_tasks = []
        prov_questions = []
        prov_decisions = []
        
        for ev in events:
            p_tid = ev.payload.get("task_id")
            if p_tid and p_tid in in_progress_ids:
                prov_tasks.append(ev.event_sequence)
                
            p_qid = ev.payload.get("question_id")
            if p_qid and p_qid in open_question_ids_set:
                prov_questions.append(ev.event_sequence)
                
            p_did = ev.payload.get("decision_id")
            if p_did and p_did in recent_decision_ids:
                prov_decisions.append(ev.event_sequence)
                
        provenance = {
            "in_progress_tasks": sorted(prov_tasks),
            "open_questions": sorted(prov_questions),
            "recent_decisions": sorted(prov_decisions),
            "context_snapshots": sorted([s["event_sequence"] for s in context_snapshots]),
            "recent_events": sorted([e["event_sequence"] for e in recent_events]),
            "last_session": last_session.source_event_seqs if last_session else [],
        }

        from rationalevault.organization.utils import resolve_compiled_at

        return ContinuationState(
            project_id=str(project_id),
            project_name=project_state.name,
            project_goal=project_state.goal,
            current_focus=project_state.current_focus,
            compiled_at=resolve_compiled_at(reference_time),
            last_session=last_session,
            in_progress_tasks=in_progress_tasks,
            open_tasks=open_tasks,
            recent_decisions=recent_decisions,
            open_questions=open_questions,
            blockers=blockers,
            recent_events=recent_events,
            context_snapshots=context_snapshots,
            next_actions=next_actions,
            provenance=provenance,
        )
