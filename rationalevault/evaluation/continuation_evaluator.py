from __future__ import annotations

from dataclasses import dataclass
from rationalevault.projections.continuation import ContinuationState

@dataclass
class ContinuationEvalResult:
    goal_recovered: bool
    decisions_recovered: bool
    rationale_recovered: bool
    task_recall: bool
    progress_notes_recovered: bool
    question_recall: bool
    context_snapshot_recovered: bool
    last_session_recovered: bool
    blocked_on_recovered: bool

    @property
    def continuation_success_rate(self) -> float:
        """Fraction of 9 recovery checks that passed. Sprint I7 gate: >= 0.95."""
        checks = [
            self.goal_recovered, self.decisions_recovered, self.rationale_recovered,
            self.task_recall, self.progress_notes_recovered, self.question_recall,
            self.context_snapshot_recovered, self.last_session_recovered,
            self.blocked_on_recovered,
        ]
        return sum(1 for c in checks if c) / len(checks)

    def passes_exit_gate(self) -> tuple[bool, list[str]]:
        """Sprint I7 exit gate: continuation_success_rate >= 0.95."""
        failures = []
        rate = self.continuation_success_rate
        if rate < 0.95:
            failures.append(f"continuation_success_rate={rate:.2%} < 95%")
        return len(failures) == 0, failures

    def to_dict(self) -> dict:
        return {
            "goal_recovered": self.goal_recovered,
            "decisions_recovered": self.decisions_recovered,
            "rationale_recovered": self.rationale_recovered,
            "task_recall": self.task_recall,
            "progress_notes_recovered": self.progress_notes_recovered,
            "question_recall": self.question_recall,
            "context_snapshot_recovered": self.context_snapshot_recovered,
            "last_session_recovered": self.last_session_recovered,
            "blocked_on_recovered": self.blocked_on_recovered,
            "continuation_success_rate": self.continuation_success_rate,
        }


class ContinuationEvaluator:
    def evaluate(
        self,
        state: ContinuationState,
        rendered_output: str,
    ) -> ContinuationEvalResult:
        # Check goal
        goal_recovered = True
        if state.project_goal:
            goal_recovered = state.project_goal.lower() in rendered_output.lower()

        # Check decisions
        decisions_recovered = True
        for d in state.recent_decisions:
            if d.title and d.title.lower() not in rendered_output.lower():
                decisions_recovered = False
                break

        # Check rationale
        rationale_recovered = True
        for d in state.recent_decisions:
            if d.rationale and d.rationale.lower() not in rendered_output.lower():
                rationale_recovered = False
                break

        # Check tasks (in progress + open)
        task_recall = True
        for t in (state.in_progress_tasks + state.open_tasks):
            if t.title and t.title.lower() not in rendered_output.lower():
                task_recall = False
                break

        # Check progress notes
        progress_notes_recovered = True
        for t in state.in_progress_tasks:
            for note_dict in t.progress_notes:
                note = note_dict.get("note", "")
                if note and note.lower() not in rendered_output.lower():
                    progress_notes_recovered = False
                    break

        # Check questions
        question_recall = True
        for q in state.open_questions:
            if q.title and q.title.lower() not in rendered_output.lower():
                question_recall = False
                break

        # Check context snapshot
        context_snapshot_recovered = True
        if state.context_snapshots:
            latest = state.context_snapshots[-1]
            summary = latest.get("summary", "")
            if summary and summary.lower() not in rendered_output.lower():
                context_snapshot_recovered = False

        # Check last session
        last_session_recovered = True
        if state.last_session:
            sid = state.last_session.session_id
            if sid and sid.lower() not in rendered_output.lower():
                last_session_recovered = False

        # Check blocked on
        blocked_on_recovered = True
        if state.context_snapshots:
            latest = state.context_snapshots[-1]
            blocked_on = latest.get("blocked_on")
            if blocked_on and blocked_on.lower() not in rendered_output.lower():
                blocked_on_recovered = False

        return ContinuationEvalResult(
            goal_recovered=goal_recovered,
            decisions_recovered=decisions_recovered,
            rationale_recovered=rationale_recovered,
            task_recall=task_recall,
            progress_notes_recovered=progress_notes_recovered,
            question_recall=question_recall,
            context_snapshot_recovered=context_snapshot_recovered,
            last_session_recovered=last_session_recovered,
            blocked_on_recovered=blocked_on_recovered,
        )
