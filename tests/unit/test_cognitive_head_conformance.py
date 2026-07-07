"""Conformance tests for CognitiveHeadProjection against ADR-027 Projection Laws.

Verifies that CognitiveHeadProjection satisfies all 8 Projection Laws
through the generic Projection Conformance Suite.
"""
from __future__ import annotations

from typing import Any
from uuid import uuid4


from rationalevault.cognitive_head.cognitive_head_projection import (
    CognitiveHeadProjection,
)
from rationalevault.cognitive_head.compiler import CognitiveHead
from rationalevault.db.sqlite_store import SQLiteEventStore
from rationalevault.projection_platform.conformance import (
    ConformanceSuite,
)
from rationalevault.projection_platform.context import (
    DependencyReader,
    MetricsCollector,
    ProjectionContext,
)
from rationalevault.cognitive_head.snapshot import NullSnapshotManager
from rationalevault.schema.events import EventMetadata, EventRecord, EventType


# ── Helpers ──────────────────────────────────────────────────────────────────


def _event(
    event_type: EventType,
    payload: dict,
    seq: int = 1,
    project_id=None,
) -> EventRecord:
    return EventRecord(
        event_sequence=seq,
        id=uuid4(),
        project_id=project_id or uuid4(),
        stream_id="default",
        version=seq,
        event_type=event_type,
        metadata=EventMetadata(actor="test", source="test"),
        payload=payload,
        parent_id=None,
        recorded_at=None,
    )


# ── Fixture Provider ─────────────────────────────────────────────────────────


class CognitiveHeadConformanceProvider:
    """ProjectionConformanceProvider for CognitiveHeadProjection."""

    def __init__(self, tmp_path=None) -> None:
        self._tmp_path = tmp_path
        self._pid = uuid4()

    def create_projection(self) -> CognitiveHeadProjection:
        return CognitiveHeadProjection()

    def events(self) -> list[EventRecord]:
        """Representative event stream with all reducer types."""
        pid = self._pid
        return [
            _event(EventType.PROJECT_CREATED, {"name": "Test"}, 1, pid),
            _event(EventType.PROJECT_GOAL_SET, {"goal": "Goal"}, 2, pid),
            _event(EventType.PROJECT_FOCUS_CHANGED, {"focus": "Focus"}, 3, pid),
            _event(EventType.TASK_CREATED, {
                "task_id": "t1",
                "details": {"summary": "Task 1", "body": "Body 1"},
                "priority": "high",
            }, 4, pid),
            _event(EventType.TASK_CREATED, {
                "task_id": "t2",
                "details": {"summary": "Task 2", "body": "Body 2"},
                "priority": "low",
            }, 5, pid),
            _event(EventType.TASK_MUTATED, {
                "task_id": "t1", "status": "in_progress",
            }, 6, pid),
            _event(EventType.TASK_COMPLETED, {"task_id": "t2"}, 7, pid),
            _event(EventType.TASK_PROGRESS_NOTED, {
                "task_id": "t1", "note": "Half done",
            }, 8, pid),
            _event(EventType.DECISION_PROPOSED, {
                "decision_id": "d1",
                "title": "Use Python",
                "rationale": "Because",
            }, 9, pid),
            _event(EventType.DECISION_ACCEPTED, {
                "decision_id": "d1",
            }, 10, pid),
            _event(EventType.DECISION_PROPOSED, {
                "decision_id": "d2",
                "title": "Use Rust",
            }, 11, pid),
            _event(EventType.DECISION_SUPERSEDED, {
                "decision_id": "d2",
                "superseded_by": "d1",
            }, 12, pid),
            _event(EventType.OPEN_QUESTION_RAISED, {
                "question_id": "q1",
                "title": "Why?",
                "priority": "critical",
                "blocks_task_ids": ["t1"],
            }, 13, pid),
            _event(EventType.OPEN_QUESTION_RAISED, {
                "question_id": "q2",
                "title": "How?",
            }, 14, pid),
            _event(EventType.OPEN_QUESTION_RESOLVED, {
                "question_id": "q2",
                "resolution": "Like this",
            }, 15, pid),
        ]

    def edge_case_events(self) -> list[list[EventRecord]]:
        """Edge-case streams for the conformance suite."""
        pid = self._pid
        return [
            # Single bootstrap event
            [_event(EventType.PROJECT_CREATED, {"name": "X"}, 1, pid)],
            # Minimal valid stream
            [
                _event(EventType.PROJECT_CREATED, {"name": "X"}, 1, pid),
                _event(EventType.PROJECT_GOAL_SET, {"goal": "G"}, 2, pid),
                _event(EventType.PROJECT_FOCUS_CHANGED, {"focus": "F"}, 3, pid),
            ],
        ]

    def snapshot_points(self, events: list[EventRecord]) -> list[int]:
        """Split points for incrementality tests."""
        n = len(events)
        if n < 4:
            return [0, n]
        return [0, n // 4, n // 2, 3 * n // 4, n]

    def supported_events(self) -> list[EventRecord]:
        """Events this projection consumes."""
        return [
            e for e in self.events()
            if e.event_type in CognitiveHeadProjection().metadata.consumed_events.types
        ]

    def unsupported_events(self) -> list[EventRecord]:
        """Events this projection does NOT consume."""
        pid = self._pid
        return [
            _event(EventType.MEMORY_RECORDED, {"content": "mem"}, 100, pid),
            _event(EventType.KNOWLEDGE_SYNTHESIZED, {"content": "k"}, 101, pid),
            _event(EventType.SKILL_EXECUTED, {"skill": "s"}, 102, pid),
        ]

    def state_equal(self, a: Any, b: Any) -> bool:
        """Compare two CognitiveHead states for equality.

        Compares all fields except compiled_at (non-deterministic) and
        ledger_version (depends on event stream, not projection state).
        """
        if not isinstance(a, CognitiveHead) or not isinstance(b, CognitiveHead):
            return a == b

        return (
            a.project_id == b.project_id
            and a.project_name == b.project_name
            and a.project_goal == b.project_goal
            and a.current_focus == b.current_focus
            and len(a.active_tasks) == len(b.active_tasks)
            and len(a.active_decisions) == len(b.active_decisions)
            and len(a.open_questions) == len(b.open_questions)
            and len(a.blockers) == len(b.blockers)
            and _tasks_equal(a.active_tasks, b.active_tasks)
            and _decisions_equal(a.active_decisions, b.active_decisions)
            and _questions_equal(a.open_questions, b.open_questions)
        )

    def canonical_json(self, payload: dict) -> str:
        """Deterministic JSON string."""
        import json
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    def create_context(self, projection: CognitiveHeadProjection) -> ProjectionContext:
        """Create a valid ProjectionContext."""
        return ProjectionContext(
            projection_id="cognitive_head",
            event_store=SQLiteEventStore() if self._tmp_path is None
            else SQLiteEventStore(db_path=str(self._tmp_path / "ctx.db")),
            snapshot_manager=NullSnapshotManager(),
            dependency_reader=DependencyReader(),
            logger=__import__("logging").getLogger("conformance"),
            metrics=MetricsCollector(),
        )


def _tasks_equal(a: list, b: list) -> bool:
    if len(a) != len(b):
        return False
    a_sorted = sorted(a, key=lambda t: t.task_id)
    b_sorted = sorted(b, key=lambda t: t.task_id)
    for ta, tb in zip(a_sorted, b_sorted):
        if ta.task_id != tb.task_id or ta.title != tb.title:
            return False
    return True


def _decisions_equal(a: list, b: list) -> bool:
    if len(a) != len(b):
        return False
    a_sorted = sorted(a, key=lambda d: d.decision_id)
    b_sorted = sorted(b, key=lambda d: d.decision_id)
    for da, db in zip(a_sorted, b_sorted):
        if da.decision_id != db.decision_id or da.title != db.title:
            return False
    return True


def _questions_equal(a: list, b: list) -> bool:
    if len(a) != len(b):
        return False
    a_sorted = sorted(a, key=lambda q: q.question_id)
    b_sorted = sorted(b, key=lambda q: q.question_id)
    for qa, qb in zip(a_sorted, b_sorted):
        if qa.question_id != qb.question_id or qa.title != qb.title:
            return False
    return True


# ── Conformance Tests ────────────────────────────────────────────────────────


class TestCognitiveHeadConformance:
    """Run the full Projection Conformance Suite against CognitiveHeadProjection."""

    def test_all_laws_pass(self):
        provider = CognitiveHeadConformanceProvider()
        projection = provider.create_projection()
        suite = ConformanceSuite(projection, provider)
        report = suite.run()

        # Print report for debugging
        print("\n" + report.summary())

        assert report.all_passed, (
            f"CognitiveHeadProjection failed conformance: "
            f"{report.failed_laws}"
        )

    def test_determinism_law(self):
        provider = CognitiveHeadConformanceProvider()
        projection = provider.create_projection()
        from rationalevault.projection_platform.conformance.laws import (
            verify_determinism,
        )
        assert verify_determinism(projection, provider)

    def test_incrementality_law(self):
        provider = CognitiveHeadConformanceProvider()
        projection = provider.create_projection()
        from rationalevault.projection_platform.conformance.laws import (
            verify_incrementality,
        )
        assert verify_incrementality(projection, provider)

    def test_snapshot_roundtrip_law(self):
        provider = CognitiveHeadConformanceProvider()
        projection = provider.create_projection()
        from rationalevault.projection_platform.conformance.laws import (
            verify_snapshot_roundtrip,
        )
        assert verify_snapshot_roundtrip(projection, provider)

    def test_replay_equivalence_law(self):
        provider = CognitiveHeadConformanceProvider()
        projection = provider.create_projection()
        from rationalevault.projection_platform.conformance.laws import (
            verify_replay_equivalence,
        )
        assert verify_replay_equivalence(projection, provider)

    def test_serialization_roundtrip_law(self):
        provider = CognitiveHeadConformanceProvider()
        projection = provider.create_projection()
        from rationalevault.projection_platform.conformance.laws import (
            verify_serialization_roundtrip,
        )
        assert verify_serialization_roundtrip(projection, provider)

    def test_health_contract_law(self):
        provider = CognitiveHeadConformanceProvider()
        projection = provider.create_projection()
        from rationalevault.projection_platform.conformance.laws import (
            verify_health_contract,
        )
        assert verify_health_contract(projection, provider)

    def test_isolation_law(self):
        provider = CognitiveHeadConformanceProvider()
        projection = provider.create_projection()
        from rationalevault.projection_platform.conformance.laws import (
            verify_isolation,
        )
        assert verify_isolation(projection, provider)
