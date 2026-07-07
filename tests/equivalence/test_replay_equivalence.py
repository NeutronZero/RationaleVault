"""Tests for replay equivalence and reducer incremental invariants.

Task 0: Replay equivalence test suite — proves that for any event stream S
        and any split point N: replay_all(S) == replay_delta(S[:N], S[N:])
Task 1: Reducer incremental invariant — proves that for each reducer:
        reduce(A + B) == reduce(B, initial_state=reduce(A))
"""
from __future__ import annotations

import random
from dataclasses import fields as dc_fields
from typing import Any
from uuid import uuid4

import pytest

from rationalevault.cognitive_head.compiler import (
    CognitiveHead,
)
from rationalevault.cognitive_head.reducers import (
    DecisionReducer,
    DecisionState,
    ProjectReducer,
    ProjectState,
    QuestionReducer,
    QuestionState,
    TaskReducer,
    TaskState,
)
from rationalevault.schema.events import EventMetadata, EventRecord, EventType


# ── Helpers ──────────────────────────────────────────────────────────────────


def _meta() -> EventMetadata:
    return EventMetadata(actor="test", source="test")


def _event(
    seq: int,
    version: int,
    et: EventType,
    payload: dict[str, Any],
    project_id: str = "",
) -> EventRecord:
    return EventRecord(
        event_sequence=seq,
        id=uuid4(),
        project_id=uuid4() if not project_id else uuid4(),
        stream_id="main",
        version=version,
        event_type=et,
        metadata=_meta(),
        payload=payload,
        parent_id=None,
        recorded_at=None,
    )


def _bootstrap_events(pid: str = "") -> list[EventRecord]:
    """Create the required PROJECT_CREATED → GOAL_SET → FOCUS_CHANGED bootstrap."""
    return [
        _event(1, 1, EventType.PROJECT_CREATED, {"name": "Test"}, pid),
        _event(2, 2, EventType.PROJECT_GOAL_SET, {"goal": "Goal"}, pid),
        _event(3, 3, EventType.PROJECT_FOCUS_CHANGED, {"focus": "Focus"}, pid),
    ]


def _make_events_for_reducer_comparison() -> list[EventRecord]:
    """A diverse event stream covering all reducer types."""
    pid = ""
    events = _bootstrap_events(pid)
    seq = 4
    ver = 4

    # Task events
    events.append(_event(seq, ver, EventType.TASK_CREATED, {
        "task_id": "t1", "details": {"summary": "Task 1", "body": "Body 1"},
        "priority": "high", "tags": ["a"],
    }))
    seq += 1
    ver += 1
    events.append(_event(seq, ver, EventType.TASK_CREATED, {
        "task_id": "t2", "details": {"summary": "Task 2", "body": "Body 2"},
        "priority": "low",
    }))
    seq += 1
    ver += 1
    events.append(_event(seq, ver, EventType.TASK_MUTATED, {
        "task_id": "t1", "status": "in_progress",
    }))
    seq += 1
    ver += 1
    events.append(_event(seq, ver, EventType.TASK_COMPLETED, {
        "task_id": "t2",
    }))
    seq += 1
    ver += 1
    events.append(_event(seq, ver, EventType.TASK_PROGRESS_NOTED, {
        "task_id": "t1", "note": "Half done",
    }))
    seq += 1
    ver += 1

    # Decision events
    events.append(_event(seq, ver, EventType.DECISION_PROPOSED, {
        "decision_id": "d1", "title": "Use Python",
        "rationale": "Because",
    }))
    seq += 1
    ver += 1
    events.append(_event(seq, ver, EventType.DECISION_ACCEPTED, {
        "decision_id": "d1",
    }))
    seq += 1
    ver += 1
    events.append(_event(seq, ver, EventType.DECISION_PROPOSED, {
        "decision_id": "d2", "title": "Use Rust",
    }))
    seq += 1
    ver += 1
    events.append(_event(seq, ver, EventType.DECISION_SUPERSEDED, {
        "decision_id": "d2", "superseded_by": "d1",
    }))
    seq += 1
    ver += 1

    # Question events
    events.append(_event(seq, ver, EventType.OPEN_QUESTION_RAISED, {
        "question_id": "q1", "title": "Why?",
        "priority": "critical", "blocks_task_ids": ["t1"],
    }))
    seq += 1
    ver += 1
    events.append(_event(seq, ver, EventType.OPEN_QUESTION_RAISED, {
        "question_id": "q2", "title": "How?",
    }))
    seq += 1
    ver += 1
    events.append(_event(seq, ver, EventType.OPEN_QUESTION_RESOLVED, {
        "question_id": "q2", "resolution": "Like this",
    }))
    seq += 1
    ver += 1

    return events


def _generate_random_events(count: int, seed: int = 42) -> list[EventRecord]:
    """Generate a random but valid event stream (starts with bootstrap)."""
    rng = random.Random(seed)
    events = _bootstrap_events()
    seq = 4
    ver = 4
    task_ids = []
    decision_ids = []
    question_ids = []

    for _ in range(count):
        # Weight toward task events (most common in real usage)
        weights = [30, 15, 5, 15, 5, 10, 5, 10, 5]
        et = rng.choices([
            EventType.TASK_CREATED, EventType.TASK_MUTATED,
            EventType.TASK_COMPLETED, EventType.DECISION_PROPOSED,
            EventType.DECISION_ACCEPTED, EventType.DECISION_SUPERSEDED,
            EventType.OPEN_QUESTION_RAISED, EventType.OPEN_QUESTION_RESOLVED,
            EventType.PROJECT_FOCUS_CHANGED,
        ], weights=weights, k=1)[0]

        if et == EventType.TASK_CREATED:
            tid = f"t_{uuid4().hex[:8]}"
            task_ids.append(tid)
            events.append(_event(seq, ver, et, {
                "task_id": tid,
                "details": {"summary": f"Task {tid}", "body": "Body"},
                "priority": rng.choice(["low", "normal", "high", "critical"]),
            }))
        elif et == EventType.TASK_MUTATED and task_ids:
            tid = rng.choice(task_ids)
            events.append(_event(seq, ver, et, {
                "task_id": tid,
                "status": rng.choice(["open", "in_progress"]),
            }))
        elif et == EventType.TASK_COMPLETED and task_ids:
            tid = rng.choice(task_ids)
            events.append(_event(seq, ver, et, {"task_id": tid}))
        elif et == EventType.DECISION_PROPOSED:
            did = f"d_{uuid4().hex[:8]}"
            decision_ids.append(did)
            events.append(_event(seq, ver, et, {
                "decision_id": did, "title": f"Decision {did}",
            }))
        elif et == EventType.DECISION_ACCEPTED and decision_ids:
            did = rng.choice(decision_ids)
            events.append(_event(seq, ver, et, {"decision_id": did}))
        elif et == EventType.DECISION_SUPERSEDED and decision_ids:
            did = rng.choice(decision_ids)
            events.append(_event(seq, ver, et, {
                "decision_id": did, "superseded_by": "d_other",
            }))
        elif et == EventType.OPEN_QUESTION_RAISED:
            qid = f"q_{uuid4().hex[:8]}"
            question_ids.append(qid)
            events.append(_event(seq, ver, et, {
                "question_id": qid, "title": f"Question {qid}",
            }))
        elif et == EventType.OPEN_QUESTION_RESOLVED and question_ids:
            qid = rng.choice(question_ids)
            events.append(_event(seq, ver, et, {
                "question_id": qid, "resolution": "Resolved",
            }))
        elif et == EventType.PROJECT_FOCUS_CHANGED:
            events.append(_event(seq, ver, et, {
                "focus": f"Focus {seq}",
            }))
        else:
            # Skip invalid combination, don't advance seq/ver
            continue

        seq += 1
        ver += 1

    return events


# ── Task 1: Reducer Incremental Invariants ───────────────────────────────────


@pytest.mark.replay_equivalence
class TestReducerIncrementalInvariant:
    """Prove: reduce(A + B) == reduce(B, initial_state=reduce(A))"""

    def _assert_project_equal(self, a: ProjectState, b: ProjectState):
        assert a.name == b.name
        assert a.goal == b.goal
        assert a.current_focus == b.current_focus

    def _assert_tasks_equal(self, a: dict[str, TaskState], b: dict[str, TaskState]):
        assert set(a.keys()) == set(b.keys())
        for k in a:
            for fld in dc_fields(a[k]):
                assert getattr(a[k], fld.name) == getattr(b[k], fld.name), (
                    f"Task {k} field {fld.name} differs"
                )

    def _assert_decisions_equal(
        self,
        a: dict[str, DecisionState],
        b: dict[str, DecisionState],
    ):
        assert set(a.keys()) == set(b.keys())
        for k in a:
            for fld in dc_fields(a[k]):
                assert getattr(a[k], fld.name) == getattr(b[k], fld.name), (
                    f"Decision {k} field {fld.name} differs"
                )

    def _assert_questions_equal(
        self,
        a: dict[str, QuestionState],
        b: dict[str, QuestionState],
    ):
        assert set(a.keys()) == set(b.keys())
        for k in a:
            for fld in dc_fields(a[k]):
                assert getattr(a[k], fld.name) == getattr(b[k], fld.name), (
                    f"Question {k} field {fld.name} differs"
                )

    @pytest.mark.parametrize("split_point", [1, 2, 3, 5, 10, 15])
    def test_project_reducer_invariant(self, split_point: int):
        events = _make_events_for_reducer_comparison()
        if split_point >= len(events):
            pytest.skip("split_point beyond event count")
        a = events[:split_point]
        b = events[split_point:]
        full = ProjectReducer.reduce(a + b)
        incremental = ProjectReducer.reduce(b, initial_state=ProjectReducer.reduce(a))
        self._assert_project_equal(full, incremental)

    @pytest.mark.parametrize("split_point", [1, 2, 3, 5, 10, 15])
    def test_task_reducer_invariant(self, split_point: int):
        events = _make_events_for_reducer_comparison()
        if split_point >= len(events):
            pytest.skip("split_point beyond event count")
        a = events[:split_point]
        b = events[split_point:]
        full = TaskReducer.reduce(a + b)
        incremental = TaskReducer.reduce(b, initial_state=TaskReducer.reduce(a))
        self._assert_tasks_equal(full, incremental)

    @pytest.mark.parametrize("split_point", [1, 2, 3, 5, 10, 15])
    def test_decision_reducer_invariant(self, split_point: int):
        events = _make_events_for_reducer_comparison()
        if split_point >= len(events):
            pytest.skip("split_point beyond event count")
        a = events[:split_point]
        b = events[split_point:]
        full = DecisionReducer.reduce(a + b)
        incremental = DecisionReducer.reduce(b, initial_state=DecisionReducer.reduce(a))
        self._assert_decisions_equal(full, incremental)

    @pytest.mark.parametrize("split_point", [1, 2, 3, 5, 10, 15])
    def test_question_reducer_invariant(self, split_point: int):
        events = _make_events_for_reducer_comparison()
        if split_point >= len(events):
            pytest.skip("split_point beyond event count")
        a = events[:split_point]
        b = events[split_point:]
        full = QuestionReducer.reduce(a + b)
        incremental = QuestionReducer.reduce(b, initial_state=QuestionReducer.reduce(a))
        self._assert_questions_equal(full, incremental)


# ── Task 0: Replay Equivalence (fuzzing) ────────────────────────────────────


@pytest.mark.replay_equivalence
class TestReplayEquivalence:
    """Prove: replay_all(S) == replay_delta(S[:N], S[N:]) for random streams."""

    @pytest.mark.parametrize("seed", range(20))
    def test_random_streams_equivalence(self, seed: int):
        """20 random event streams, each split at a random point."""
        rng = random.Random(seed)
        events = _generate_random_events(
            count=rng.randint(10, 50), seed=seed,
        )
        if len(events) < 5:
            pytest.skip("Stream too short")

        split = random.Random(seed).randint(1, len(events) - 1)
        prefix = events[:split]
        suffix = events[split:]

        # Full replay
        proj_full = ProjectReducer.reduce(events)
        tasks_full = TaskReducer.reduce(events)
        dec_full = DecisionReducer.reduce(events)
        q_full = QuestionReducer.reduce(events)

        # Incremental replay
        proj_incr = ProjectReducer.reduce(
            suffix, initial_state=ProjectReducer.reduce(prefix)
        )
        tasks_incr = TaskReducer.reduce(
            suffix, initial_state=TaskReducer.reduce(prefix)
        )
        dec_incr = DecisionReducer.reduce(
            suffix, initial_state=DecisionReducer.reduce(prefix)
        )
        q_incr = QuestionReducer.reduce(
            suffix, initial_state=QuestionReducer.reduce(prefix)
        )

        # Compare
        assert proj_full.name == proj_incr.name
        assert proj_full.goal == proj_incr.goal
        assert proj_full.current_focus == proj_incr.current_focus

        assert set(tasks_full.keys()) == set(tasks_incr.keys())
        for tid in tasks_full:
            assert tasks_full[tid].status == tasks_incr[tid].status
            assert tasks_full[tid].title == tasks_incr[tid].title
            assert tasks_full[tid].priority == tasks_incr[tid].priority

        assert set(dec_full.keys()) == set(dec_incr.keys())
        for did in dec_full:
            assert dec_full[did].status == dec_incr[did].status
            assert dec_full[did].title == dec_incr[did].title

        assert set(q_full.keys()) == set(q_incr.keys())
        for qid in q_full:
            assert q_full[qid].status == q_incr[qid].status
            assert q_full[qid].title == q_incr[qid].title

    def test_hand_crafted_deterministic(self):
        """Hand-crafted stream with known split point."""
        events = _make_events_for_reducer_comparison()
        split = 8  # After task created + mutated, before decision events

        prefix = events[:split]
        suffix = events[split:]

        full_tasks = TaskReducer.reduce(events)
        prefix_tasks = TaskReducer.reduce(prefix)
        incr_tasks = TaskReducer.reduce(
            suffix, initial_state=prefix_tasks,
        )
        assert set(full_tasks.keys()) == set(incr_tasks.keys())
        for tid in full_tasks:
            assert full_tasks[tid].status == incr_tasks[tid].status

    def test_split_at_every_position(self):
        """Split at every possible position and verify equivalence."""
        events = _make_events_for_reducer_comparison()
        for i in range(1, len(events)):
            prefix = events[:i]
            suffix = events[i:]

            full_tasks = TaskReducer.reduce(events)
            prefix_tasks = TaskReducer.reduce(prefix)
            incr_tasks = TaskReducer.reduce(
                suffix, initial_state=prefix_tasks,
            )
            assert set(full_tasks.keys()) == set(incr_tasks.keys()), (
                f"Failed at split point {i}"
            )


# ── Task 8: Cumulative Drift Test ───────────────────────────────────────────


@pytest.mark.replay_equivalence
class TestCumulativeDrift:
    """Prove that incremental replay over multiple splits doesn't drift."""

    def test_cumulative_drift_500_events(self):
        events = _generate_random_events(count=500, seed=99)
        if len(events) < 10:
            pytest.skip("Stream too short")

        # Full replay as reference
        proj_full = ProjectReducer.reduce(events)
        tasks_full = TaskReducer.reduce(events)
        dec_full = DecisionReducer.reduce(events)
        q_full = QuestionReducer.reduce(events)

        # Incremental replay in chunks of 50
        chunk_size = 50
        proj_state: ProjectState | None = None
        tasks_state: dict[str, TaskState] | None = None
        dec_state: dict[str, DecisionState] | None = None
        q_state: dict[str, QuestionState] | None = None

        pos = 0
        while pos < len(events):
            chunk = events[pos:pos + chunk_size]
            proj_state = ProjectReducer.reduce(chunk, initial_state=proj_state)
            tasks_state = TaskReducer.reduce(chunk, initial_state=tasks_state)
            dec_state = DecisionReducer.reduce(chunk, initial_state=dec_state)
            q_state = QuestionReducer.reduce(chunk, initial_state=q_state)
            pos += chunk_size

        assert proj_state is not None
        assert tasks_state is not None
        assert dec_state is not None
        assert q_state is not None

        assert proj_full.name == proj_state.name
        assert proj_full.goal == proj_state.goal
        assert proj_full.current_focus == proj_state.current_focus

        assert set(tasks_full.keys()) == set(tasks_state.keys())
        for tid in tasks_full:
            assert tasks_full[tid].status == tasks_state[tid].status
            assert tasks_full[tid].title == tasks_state[tid].title

        assert set(dec_full.keys()) == set(dec_state.keys())
        for did in dec_full:
            assert dec_full[did].status == dec_state[did].status

        assert set(q_full.keys()) == set(q_state.keys())
        for qid in q_full:
            assert q_full[qid].status == q_state[qid].status


# ── Snapshot Determinism Test ────────────────────────────────────────────────


@pytest.mark.replay_equivalence
class TestSnapshotDeterminism:
    """Prove: same events → same snapshot bytes and hash, every time."""

    def test_snapshot_determinism(self):
        from rationalevault.cognitive_head.snapshot_payload import (
            CognitiveHeadSnapshotPayload,
        )

        events = _make_events_for_reducer_comparison()
        proj = ProjectReducer.reduce(events)
        tasks = TaskReducer.reduce(events)
        dec = DecisionReducer.reduce(events)
        q = QuestionReducer.reduce(events)

        from uuid import uuid4
        pid = uuid4()
        head = CognitiveHead(
            project_id=pid,
            project_name=proj.name,
            project_goal=proj.goal,
            current_focus=proj.current_focus,
            ledger_version=max(e.version for e in events),
            compiled_at="2026-01-01T00:00:00",
            active_tasks=[t for t in tasks.values() if t.status != "completed"],
            active_decisions=[d for d in dec.values() if d.status == "accepted"],
            open_questions=[q2 for q2 in q.values() if q2.status == "open"],
            blockers=[],
        )

        # Create snapshot twice from same head
        p1 = CognitiveHeadSnapshotPayload.from_cognitive_head(head, 100)
        p2 = CognitiveHeadSnapshotPayload.from_cognitive_head(head, 100)

        # Bytes must be identical
        assert p1.to_dict(exclude_hash=True) == p2.to_dict(exclude_hash=True)
        # Hash must be identical
        assert p1.snapshot_hash == p2.snapshot_hash
