"""Conformance tests for TimelineProjection against ADR-027 Projection Laws.

Verifies that TimelineProjection satisfies all 7 Projection Laws
through the generic Projection Conformance Suite.

This is the third archetype validation: if TimelineProjection passes the
unchanged Conformance Suite without modifying any platform abstractions,
ADR-027 is validated as supporting narrative projections in addition to
state-reducing and searchable projections.
"""
from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from rationalevault.db.sqlite_store import SQLiteEventStore
from rationalevault.projection_platform.conformance import ConformanceSuite
from rationalevault.projection_platform.context import (
    DependencyReader,
    MetricsCollector,
    ProjectionContext,
)
from rationalevault.cognitive_head.snapshot import NullSnapshotManager
from rationalevault.schema.events import EventMetadata, EventRecord, EventType
from rationalevault.timeline.projection import TimelineProjection
from rationalevault.timeline.state import TimelineState


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
        stream_id="main",
        version=seq,
        event_type=event_type,
        metadata=EventMetadata(actor="test", source="test"),
        payload=payload,
        parent_id=None,
        recorded_at=None,
    )


# ── Conformance Provider ────────────────────────────────────────────────────


class TimelineConformanceProvider:
    """ProjectionConformanceProvider for TimelineProjection."""

    def __init__(self, tmp_path=None) -> None:
        self._tmp_path = tmp_path
        self._pid = uuid4()

    def create_projection(self) -> TimelineProjection:
        return TimelineProjection()

    def events(self) -> list[EventRecord]:
        """Representative event stream with all 18 consumed event types."""
        pid = self._pid
        return [
            # Project milestones
            _event(EventType.PROJECT_CREATED, {
                "name": "RationaleVault",
            }, 1, pid),
            _event(EventType.PROJECT_GOAL_SET, {
                "goal": "Cognitive continuity across agent sessions",
            }, 2, pid),
            _event(EventType.PROJECT_FOCUS_CHANGED, {
                "focus": "projection platform",
            }, 3, pid),
            # Tasks
            _event(EventType.TASK_CREATED, {
                "task_id": "t1",
                "title": "Implement snapshot store",
                "actor": "alice",
            }, 4, pid),
            _event(EventType.TASK_COMPLETED, {
                "task_id": "t1",
                "title": "Implement snapshot store",
                "actor": "alice",
            }, 5, pid),
            # Decisions
            _event(EventType.DECISION_PROPOSED, {
                "decision_id": "d1",
                "title": "Use PostgreSQL for event store",
                "actor": "bob",
            }, 6, pid),
            _event(EventType.DECISION_ACCEPTED, {
                "decision_id": "d1",
                "title": "Use PostgreSQL for event store",
                "actor": "bob",
            }, 7, pid),
            _event(EventType.DECISION_SUPERSEDED, {
                "decision_id": "d1",
                "title": "Use PostgreSQL for event store",
                "actor": "bob",
            }, 8, pid),
            # Questions
            _event(EventType.OPEN_QUESTION_RAISED, {
                "question_id": "q1",
                "question": "Should projections support streaming?",
            }, 9, pid),
            _event(EventType.OPEN_QUESTION_RESOLVED, {
                "question_id": "q1",
                "question": "Should projections support streaming?",
            }, 10, pid),
            # Knowledge
            _event(EventType.KNOWLEDGE_CREATED, {
                "knowledge_id": "k1",
                "title": "Architecture Principle",
            }, 11, pid),
            _event(EventType.KNOWLEDGE_UPDATED, {
                "knowledge_id": "k1",
                "title": "Architecture Principle v2",
            }, 12, pid),
            _event(EventType.KNOWLEDGE_DELETED, {
                "knowledge_id": "k1",
            }, 13, pid),
            _event(EventType.KNOWLEDGE_SYNTHESIZED, {
                "knowledge_id": "k2",
                "title": "Research Finding",
            }, 14, pid),
            # Knowledge promotion milestones
            _event(EventType.KNOWLEDGE_PROMOTION_APPROVED, {
                "knowledge_id": "k2",
                "title": "Research Finding",
            }, 15, pid),
            _event(EventType.KNOWLEDGE_PROMOTION_REJECTED, {
                "knowledge_id": "k3",
                "title": "Rejected Finding",
            }, 16, pid),
            # Memory
            _event(EventType.MEMORY_RECORDED, {
                "memory_id": "m1",
                "content": "Snapshot store uses version-based validation.",
            }, 17, pid),
            # Governance
            _event(EventType.GOVERNANCE_DECISION_RECORDED, {
                "governance_id": "g1",
                "action": "ADJUSTED",
            }, 18, pid),
            # System
            _event(EventType.SKILL_EXECUTED, {
                "skill_name": "systematic-debugging",
            }, 19, pid),
        ]

    def edge_case_events(self) -> list[list[EventRecord]]:
        """Edge-case streams for the conformance suite."""
        pid = self._pid
        return [
            # Single event
            [_event(EventType.TASK_CREATED, {
                "task_id": "single",
                "title": "Solo task",
            }, 1, pid)],
            # Empty (no events)
            [],
        ]

    def snapshot_points(self, events: list[EventRecord]) -> list[int]:
        """Split points for incrementality tests."""
        n = len(events)
        if n < 4:
            return [0, n]
        return [0, n // 4, n // 2, 3 * n // 4, n]

    def supported_events(self) -> list[EventRecord]:
        """Events this projection consumes."""
        consumed = TimelineProjection().metadata.consumed_events.types
        return [e for e in self.events() if e.event_type in consumed]

    def unsupported_events(self) -> list[EventRecord]:
        """Events this projection does NOT consume."""
        pid = self._pid
        return [
            _event(EventType.TASK_MUTATED, {
                "task_id": "t1",
                "details": {"summary": "Updated"},
            }, 200, pid),
            _event(EventType.FACT_RECORDED, {
                "fact": "Some fact",
            }, 201, pid),
            _event(EventType.REFLECTION_GENERATED, {
                "reflection": "Some reflection",
            }, 202, pid),
        ]

    def state_equal(self, a: Any, b: Any) -> bool:
        """Compare two TimelineStates for equality.

        Compares entries by sequence, event_type, category, and summary.
        Ignores timestamp (which may differ due to None vs datetime).
        """
        if not isinstance(a, TimelineState) or not isinstance(b, TimelineState):
            return a == b

        if len(a.entries) != len(b.entries):
            return False

        a_sorted = sorted(a.entries, key=lambda e: e.sequence)
        b_sorted = sorted(b.entries, key=lambda e: e.sequence)

        for ae, be in zip(a_sorted, b_sorted, strict=True):
            if ae.sequence != be.sequence:
                return False
            if ae.event_type != be.event_type:
                return False
            if ae.category != be.category:
                return False
            if ae.summary != be.summary:
                return False
            if ae.actor != be.actor:
                return False
            if ae.subject_entity != be.subject_entity:
                return False

        return True

    def canonical_json(self, payload: dict) -> str:
        """Deterministic JSON string."""
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    def create_context(self, projection: TimelineProjection) -> ProjectionContext:
        """Create a valid ProjectionContext."""
        return ProjectionContext(
            projection_id="timeline",
            event_store=SQLiteEventStore() if self._tmp_path is None
            else SQLiteEventStore(db_path=str(self._tmp_path / "ctx.db")),
            snapshot_manager=NullSnapshotManager(),
            dependency_reader=DependencyReader(),
            logger=__import__("logging").getLogger("conformance"),
            metrics=MetricsCollector(),
        )


# ── Conformance Tests ────────────────────────────────────────────────────────


class TestTimelineConformance:
    """Run the full Projection Conformance Suite against TimelineProjection."""

    def test_all_laws_pass(self):
        provider = TimelineConformanceProvider()
        projection = provider.create_projection()
        suite = ConformanceSuite(projection, provider)
        report = suite.run()

        print("\n" + report.summary())

        assert report.all_passed, (
            f"TimelineProjection failed conformance: "
            f"{report.failed_laws}"
        )

    def test_determinism_law(self):
        provider = TimelineConformanceProvider()
        projection = provider.create_projection()
        from rationalevault.projection_platform.conformance.laws import (
            verify_determinism,
        )
        assert verify_determinism(projection, provider)

    def test_incrementality_law(self):
        provider = TimelineConformanceProvider()
        projection = provider.create_projection()
        from rationalevault.projection_platform.conformance.laws import (
            verify_incrementality,
        )
        assert verify_incrementality(projection, provider)

    def test_snapshot_roundtrip_law(self):
        provider = TimelineConformanceProvider()
        projection = provider.create_projection()
        from rationalevault.projection_platform.conformance.laws import (
            verify_snapshot_roundtrip,
        )
        assert verify_snapshot_roundtrip(projection, provider)

    def test_replay_equivalence_law(self):
        provider = TimelineConformanceProvider()
        projection = provider.create_projection()
        from rationalevault.projection_platform.conformance.laws import (
            verify_replay_equivalence,
        )
        assert verify_replay_equivalence(projection, provider)

    def test_serialization_roundtrip_law(self):
        provider = TimelineConformanceProvider()
        projection = provider.create_projection()
        from rationalevault.projection_platform.conformance.laws import (
            verify_serialization_roundtrip,
        )
        assert verify_serialization_roundtrip(projection, provider)

    def test_health_contract_law(self):
        provider = TimelineConformanceProvider()
        projection = provider.create_projection()
        from rationalevault.projection_platform.conformance.laws import (
            verify_health_contract,
        )
        assert verify_health_contract(projection, provider)

    def test_isolation_law(self):
        provider = TimelineConformanceProvider()
        projection = provider.create_projection()
        from rationalevault.projection_platform.conformance.laws import (
            verify_isolation,
        )
        assert verify_isolation(projection, provider)
