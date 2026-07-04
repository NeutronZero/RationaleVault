"""
RationaleVault Unit Tests — Execution State Projection.

Tests for:
  - Reducer correctness (fold SKILL_EXECUTED events)
  - Pending detection (decisions with no execution)
  - Classification (completed, failed, timeout, denied)
  - Replay determinism (same events → same state)
  - Duration tracking per skill
"""
from datetime import datetime, timezone
from uuid import UUID

from rationalevault.projections.base import ProjectionKind
from rationalevault.skill_platform.execution_state import (
    ExecutionEntry,
    ExecutionState,
    ExecutionStateProjection,
)
from rationalevault.schema.events import EventMetadata, EventRecord, EventType


def _make_skill_executed_event(
    execution_id: str = "SKE-AAAAAAAA",
    decision_id: str = "DEC-BBBBBBBB",
    skill_id: str = "SKL-11111111",
    state: str = "COMPLETED",
    error: str | None = None,
    duration_ms: int = 100,
    seq: int = 1,
) -> EventRecord:
    return EventRecord(
        event_sequence=seq,
        id=UUID("00000000-0000-0000-0000-000000000001"),
        project_id=UUID("00000000-0000-0000-0000-000000000000"),
        stream_id="skills",
        version=1,
        event_type=EventType.SKILL_EXECUTED,
        metadata=EventMetadata(actor="test", source="test"),
        payload={
            "execution_id": execution_id,
            "decision_id": decision_id,
            "skill_id": skill_id,
            "state": state,
            "input_hash": "INHASH",
            "output_hash": "OUTHASH",
            "error": error,
            "started_at": "2026-01-01T00:00:00Z",
            "completed_at": "2026-01-01T00:00:01Z",
            "duration_ms": duration_ms,
            "permission_decision": {"allowed": True, "missing_capabilities": [], "denial_reason": "", "evaluation_version": "1.0"},
            "provenance": {"execution_id": execution_id, "decision_id": decision_id, "synthesis_id": "SYN-X", "belief_id": "BEL-X", "source_event_ids": [], "skill_version": "1.0.0", "gate_policy_version": "1.0", "input_snapshot_hash": "X", "timestamp": "2026-01-01T00:00:00Z"},
            "timeout_seconds": 30,
        },
        parent_id=None,
        recorded_at=datetime.now(timezone.utc),
    )


def _make_non_skill_event(seq: int = 1) -> EventRecord:
    return EventRecord(
        event_sequence=seq,
        id=UUID("00000000-0000-0000-0000-000000000002"),
        project_id=UUID("00000000-0000-0000-0000-000000000000"),
        stream_id="main",
        version=1,
        event_type=EventType.TASK_CREATED,
        metadata=EventMetadata(actor="test", source="test"),
        payload={},
        parent_id=None,
        recorded_at=datetime.now(timezone.utc),
    )


class TestExecutionStateProjection:
    def test_empty_events(self):
        state = ExecutionStateProjection.reduce([])
        assert state.total_executions == 0
        assert state.completed_executions == []
        assert state.failed_executions == []

    def test_completed_execution(self):
        events = [_make_skill_executed_event(state="COMPLETED")]
        state = ExecutionStateProjection.reduce(events)
        assert state.total_executions == 1
        assert state.total_completed == 1
        assert len(state.completed_executions) == 1
        assert state.completed_executions[0].state == "COMPLETED"

    def test_failed_execution(self):
        events = [_make_skill_executed_event(state="FAILED", error="oops")]
        state = ExecutionStateProjection.reduce(events)
        assert state.total_failed == 1
        assert len(state.failed_executions) == 1
        assert state.failed_executions[0].error == "oops"

    def test_timeout_execution(self):
        events = [_make_skill_executed_event(state="TIMEOUT", error="timeout")]
        state = ExecutionStateProjection.reduce(events)
        assert state.total_timeout == 1
        assert len(state.timeout_executions) == 1

    def test_denied_execution(self):
        events = [_make_skill_executed_event(state="DENIED", error="permission denied")]
        state = ExecutionStateProjection.reduce(events)
        assert state.total_denied == 1
        assert len(state.denied_executions) == 1

    def test_pending_decisions(self):
        events = [_make_skill_executed_event(decision_id="DEC-11111111")]
        state = ExecutionStateProjection.reduce(
            events, known_decision_ids=["DEC-11111111", "DEC-22222222"]
        )
        assert state.pending_decisions == ["DEC-22222222"]

    def test_non_skill_events_ignored(self):
        events = [_make_non_skill_event(), _make_skill_executed_event()]
        state = ExecutionStateProjection.reduce(events)
        assert state.total_executions == 1

    def test_multiple_executions_per_skill(self):
        events = [
            _make_skill_executed_event(skill_id="SKL-AAA", state="COMPLETED", duration_ms=100, seq=1),
            _make_skill_executed_event(skill_id="SKL-AAA", state="FAILED", duration_ms=50, seq=2),
            _make_skill_executed_event(skill_id="SKL-BBB", state="COMPLETED", duration_ms=200, seq=3),
        ]
        state = ExecutionStateProjection.reduce(events)
        assert state.execution_counts == {"SKL-AAA": 2, "SKL-BBB": 1}
        assert state.success_counts == {"SKL-AAA": 1, "SKL-BBB": 1}
        assert state.durations["SKL-AAA"] == [100, 50]
        assert state.durations["SKL-BBB"] == [200]


class TestReplayDeterminism:
    def test_same_events_same_state(self):
        events = [
            _make_skill_executed_event(execution_id="SKE-1", decision_id="DEC-1", state="COMPLETED", seq=1),
            _make_skill_executed_event(execution_id="SKE-2", decision_id="DEC-2", state="FAILED", seq=2),
            _make_skill_executed_event(execution_id="SKE-3", decision_id="DEC-3", state="TIMEOUT", seq=3),
        ]
        state1 = ExecutionStateProjection.reduce(events)
        state2 = ExecutionStateProjection.reduce(events)
        assert state1.to_dict() == state2.to_dict()

    def test_event_reordering_same_result(self):
        events = [
            _make_skill_executed_event(execution_id="SKE-1", decision_id="DEC-1", state="COMPLETED", seq=2),
            _make_skill_executed_event(execution_id="SKE-2", decision_id="DEC-2", state="FAILED", seq=1),
        ]
        state1 = ExecutionStateProjection.reduce(events)
        # Reorder events — totals should be the same
        events_reversed = list(reversed(events))
        state2 = ExecutionStateProjection.reduce(events_reversed)
        assert state1.total_executions == state2.total_executions
        assert state1.total_completed == state2.total_completed
        assert state1.total_failed == state2.total_failed


class TestExecutionEntry:
    def test_to_dict(self):
        entry = ExecutionEntry(
            execution_id="SKE-AAAAAAAA",
            decision_id="DEC-BBBBBBBB",
            skill_id="SKL-11111111",
            state="COMPLETED",
            input_hash="IN",
            output_hash="OUT",
            error=None,
            started_at="2026-01-01T00:00:00Z",
            completed_at="2026-01-01T00:00:01Z",
            duration_ms=100,
        )
        d = entry.to_dict()
        assert d["execution_id"] == "SKE-AAAAAAAA"
        assert d["state"] == "COMPLETED"
        assert d["duration_ms"] == 100


class TestProjectionMetadata:
    def test_projection_kind_is_base(self):
        assert ExecutionStateProjection.projection_kind == ProjectionKind.BASE

    def test_projection_name(self):
        assert ExecutionStateProjection.projection_name == "execution_state"
