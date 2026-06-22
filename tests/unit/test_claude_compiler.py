"""
ClaudeCompiler unit tests.

Pure unit tests — no database required.
Builds CognitiveHead objects directly and verifies compiler output.

Coverage:
  - agent_name is "Claude"
  - Open Questions appear before Active Tasks (Change 6)
  - RESOLVE instruction present when questions exist
  - DO NOT REVERSE warning present for decisions
  - Resumption prompt targets open question first (over tasks)
  - Resumption prompt targets task when no questions remain
  - Priority icons in question section (🔴 critical, 🟡 high, 🔵 normal)
  - Blocked tasks section appears when blockers present
  - Compiler is deterministic (modulo compiled_at timestamp)
  - Project context (goal + focus) always included
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from rationalevault.cognitive_head.compiler import CognitiveHead
from rationalevault.cognitive_head.reducers import DecisionState, QuestionState, TaskState
from rationalevault.compilers.claude import ClaudeCompiler


# ── Helpers ────────────────────────────────────────────────────────────────────

def _head(
    *,
    name: str = "Relay",
    goal: str = "Build continuity",
    focus: str = "Event ledger",
    tasks: list[TaskState] | None = None,
    decisions: list[DecisionState] | None = None,
    questions: list[QuestionState] | None = None,
    blockers: list[dict] | None = None,
    ledger_version: int = 10,
) -> CognitiveHead:
    return CognitiveHead(
        project_id=uuid.uuid4(),
        project_name=name,
        project_goal=goal,
        current_focus=focus,
        ledger_version=ledger_version,
        compiled_at=datetime.now(timezone.utc).isoformat(),
        active_tasks=tasks or [],
        active_decisions=decisions or [],
        open_questions=questions or [],
        blockers=blockers or [],
    )


def _task(task_id: str, title: str, priority: str = "normal",
          status: str = "open") -> TaskState:
    return TaskState(task_id=task_id, title=title,
                     priority=priority, status=status)


def _decision(decision_id: str, title: str,
              rationale: str = "") -> DecisionState:
    return DecisionState(decision_id=decision_id, title=title,
                         status="accepted", rationale=rationale)


def _question(question_id: str, title: str, priority: str = "normal",
              blocks: list[str] | None = None,
              raised_by: str = "Claude") -> QuestionState:
    return QuestionState(question_id=question_id, title=title,
                         priority=priority,
                         blocks_task_ids=blocks or [],
                         raised_by=raised_by)


@pytest.fixture
def compiler() -> ClaudeCompiler:
    return ClaudeCompiler()


# ── Basic output ───────────────────────────────────────────────────────────────

class TestBasicOutput:
    def test_agent_name(self, compiler: ClaudeCompiler):
        assert compiler.agent_name == "Claude"

    def test_header_contains_project_name(self, compiler: ClaudeCompiler):
        output = compiler.compile(_head(name="MyProject"))
        assert "MyProject" in output

    def test_header_contains_ledger_version(self, compiler: ClaudeCompiler):
        output = compiler.compile(_head(ledger_version=42))
        assert "Ledger v42" in output

    def test_project_context_always_included(self, compiler: ClaudeCompiler):
        output = compiler.compile(_head(goal="The goal", focus="The focus"))
        assert "The goal" in output
        assert "The focus" in output

    def test_resumption_prompt_always_present(self, compiler: ClaudeCompiler):
        output = compiler.compile(_head())
        assert "Resumption Prompt" in output
        assert "Relay" in output


# ── Section ordering (Change 6) ────────────────────────────────────────────────

class TestSectionOrdering:
    def test_open_questions_before_active_tasks(self, compiler: ClaudeCompiler):
        head = _head(
            questions=[_question("q1", "Which driver?", priority="high")],
            tasks=[_task("t1", "Implement EventStore")],
        )
        output = compiler.compile(head)
        q_pos = output.index("Open Questions")
        t_pos = output.index("Active Tasks")
        assert q_pos < t_pos, "Open Questions must appear before Active Tasks"

    def test_blocked_tasks_before_active_tasks(self, compiler: ClaudeCompiler):
        head = _head(
            tasks=[_task("t1", "Blocked Task")],
            questions=[_question("q1", "Q", blocks=["t1"])],
            blockers=[{"task_id": "t1", "task_title": "Blocked Task",
                       "blocked_by_questions": ["q1"]}],
        )
        output = compiler.compile(head)
        blocked_pos = output.index("Blocked Tasks")
        active_pos = output.index("Active Tasks")
        assert blocked_pos < active_pos

    def test_decisions_after_active_tasks(self, compiler: ClaudeCompiler):
        head = _head(
            tasks=[_task("t1", "Task")],
            decisions=[_decision("d1", "Use psycopg3")],
        )
        output = compiler.compile(head)
        t_pos = output.index("Active Tasks")
        d_pos = output.index("Accepted Decisions")
        assert t_pos < d_pos


# ── Open questions section ────────────────────────────────────────────────────

class TestOpenQuestionsSection:
    def test_resolve_instruction_present_when_questions_exist(self, compiler: ClaudeCompiler):
        head = _head(questions=[_question("q1", "Some question")])
        output = compiler.compile(head)
        assert "RESOLVE THESE BEFORE" in output

    def test_no_questions_shows_none_message(self, compiler: ClaudeCompiler):
        output = compiler.compile(_head())
        assert "None." in output

    def test_critical_question_has_red_icon(self, compiler: ClaudeCompiler):
        head = _head(questions=[_question("q1", "Critical Q", priority="critical")])
        output = compiler.compile(head)
        assert "🔴" in output

    def test_high_question_has_yellow_icon(self, compiler: ClaudeCompiler):
        head = _head(questions=[_question("q1", "High Q", priority="high")])
        output = compiler.compile(head)
        assert "🟡" in output

    def test_normal_question_has_blue_icon(self, compiler: ClaudeCompiler):
        head = _head(questions=[_question("q1", "Normal Q", priority="normal")])
        output = compiler.compile(head)
        assert "🔵" in output

    def test_question_id_in_output(self, compiler: ClaudeCompiler):
        head = _head(questions=[_question("q_abc_123", "Question")])
        output = compiler.compile(head)
        assert "q_abc_123" in output

    def test_blocks_task_ids_shown_when_present(self, compiler: ClaudeCompiler):
        head = _head(questions=[_question("q1", "Q", blocks=["t1", "t2"])])
        output = compiler.compile(head)
        assert "t1" in output
        assert "t2" in output


# ── Decisions section ──────────────────────────────────────────────────────────

class TestDecisionsSection:
    def test_do_not_reverse_warning_present(self, compiler: ClaudeCompiler):
        head = _head(decisions=[_decision("d1", "Use psycopg3")])
        output = compiler.compile(head)
        assert "DO NOT REVERSE" in output

    def test_decision_title_in_output(self, compiler: ClaudeCompiler):
        head = _head(decisions=[_decision("d1", "Use psycopg3 sync")])
        output = compiler.compile(head)
        assert "Use psycopg3 sync" in output

    def test_rationale_in_output(self, compiler: ClaudeCompiler):
        head = _head(decisions=[_decision("d1", "Decision", rationale="The rationale")])
        output = compiler.compile(head)
        assert "The rationale" in output

    def test_no_decisions_shows_none_message(self, compiler: ClaudeCompiler):
        output = compiler.compile(_head())
        assert "No accepted decisions yet" in output


# ── Resumption prompt ──────────────────────────────────────────────────────────

class TestResumptionPrompt:
    def test_targets_first_open_question_when_present(self, compiler: ClaudeCompiler):
        head = _head(
            questions=[
                _question("q1", "Critical Question", priority="critical"),
                _question("q2", "Another Question", priority="normal"),
            ],
            tasks=[_task("t1", "Some Task")],
        )
        output = compiler.compile(head)
        prompt_start = output.index("Resumption Prompt")
        prompt_section = output[prompt_start:]
        assert "Critical Question" in prompt_section

    def test_targets_first_task_when_no_questions(self, compiler: ClaudeCompiler):
        head = _head(
            tasks=[_task("t1", "Implement EventStore", priority="high")],
        )
        output = compiler.compile(head)
        prompt_start = output.index("Resumption Prompt")
        prompt_section = output[prompt_start:]
        assert "Implement EventStore" in prompt_section

    def test_review_prompt_when_nothing_to_do(self, compiler: ClaudeCompiler):
        output = compiler.compile(_head())
        assert "Resumption Prompt" in output

    def test_instructions_numbered(self, compiler: ClaudeCompiler):
        output = compiler.compile(_head())
        assert "1." in output
        assert "2." in output

    def test_do_not_re_derive_instruction(self, compiler: ClaudeCompiler):
        output = compiler.compile(_head())
        assert "re-derive" in output.lower() or "re-derive" in output


# ── Determinism ────────────────────────────────────────────────────────────────

class TestDeterminism:
    def test_compile_twice_same_output(self, compiler: ClaudeCompiler):
        head = _head(
            questions=[_question("q1", "Q1", priority="high")],
            tasks=[_task("t1", "T1")],
            decisions=[_decision("d1", "D1")],
        )
        out1 = compiler.compile(head)
        out2 = compiler.compile(head)
        # compiled_at is frozen in the head, so output should be identical
        assert out1 == out2
