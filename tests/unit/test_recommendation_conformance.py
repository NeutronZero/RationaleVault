"""Conformance tests for RecommendationProjection against ADR-027 Projection Laws.

Verifies that RecommendationProjection satisfies all 7 Projection Laws
through the generic Projection Conformance Suite.

This is the fourth archetype validation: if RecommendationProjection
passes the unchanged Conformance Suite without modifying any platform
abstractions, ADR-027 is validated as supporting derived/analytical
projections in addition to state-reducing, searchable, and narrative.
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
from rationalevault.recommendation.projection import RecommendationProjection
from rationalevault.recommendation.state import RecommendationState
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
        stream_id="main",
        version=seq,
        event_type=event_type,
        metadata=EventMetadata(actor="test", source="test"),
        payload=payload,
        parent_id=None,
        recorded_at=None,
    )


# ── Conformance Provider ────────────────────────────────────────────────────


class RecommendationConformanceProvider:
    """ProjectionConformanceProvider for RecommendationProjection."""

    def __init__(self, tmp_path=None) -> None:
        self._tmp_path = tmp_path
        self._pid = uuid4()

    def create_projection(self) -> RecommendationProjection:
        return RecommendationProjection()

    def events(self) -> list[EventRecord]:
        """Representative event stream with all consumed event types."""
        pid = self._pid
        return [
            # Knowledge created (triggers knowledge_gap_rule)
            _event(EventType.KNOWLEDGE_CREATED, {
                "knowledge_id": "k1",
                "title": "Architecture Principle",
            }, 1, pid),
            # Knowledge created with related_to (no rule hit)
            _event(EventType.KNOWLEDGE_CREATED, {
                "knowledge_id": "k2",
                "title": "Related Finding",
                "related_to": "k1",
            }, 2, pid),
            # Task completed (triggers task_follow_up_rule)
            _event(EventType.TASK_COMPLETED, {
                "task_id": "t1",
                "title": "Implement snapshot store",
            }, 3, pid),
            # Decision accepted (triggers decision_review_rule)
            _event(EventType.DECISION_ACCEPTED, {
                "decision_id": "d1",
                "title": "Use PostgreSQL",
            }, 4, pid),
            # Question resolved (triggers question_resolution_rule)
            _event(EventType.OPEN_QUESTION_RESOLVED, {
                "question_id": "q1",
                "question": "Should projections support streaming?",
            }, 5, pid),
            # Knowledge updated twice (triggers knowledge_update_risk_rule)
            _event(EventType.KNOWLEDGE_UPDATED, {
                "knowledge_id": "k1",
                "title": "Architecture Principle v2",
            }, 6, pid),
            _event(EventType.KNOWLEDGE_UPDATED, {
                "knowledge_id": "k1",
                "title": "Architecture Principle v3",
            }, 7, pid),
            # Knowledge deleted (no specific rule, but consumed)
            _event(EventType.KNOWLEDGE_DELETED, {
                "knowledge_id": "k2",
            }, 8, pid),
        ]

    def edge_case_events(self) -> list[list[EventRecord]]:
        """Edge-case streams for the conformance suite."""
        pid = self._pid
        return [
            # Single event that triggers a rule
            [_event(EventType.TASK_COMPLETED, {
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
        consumed = RecommendationProjection().metadata.consumed_events.types
        return [e for e in self.events() if e.event_type in consumed]

    def unsupported_events(self) -> list[EventRecord]:
        """Events this projection does NOT consume."""
        pid = self._pid
        return [
            _event(EventType.MEMORY_RECORDED, {
                "memory_id": "m1",
                "content": "Some memory",
            }, 200, pid),
            _event(EventType.PROJECT_CREATED, {
                "name": "Test Project",
            }, 201, pid),
            _event(EventType.SKILL_EXECUTED, {
                "skill_name": "test_skill",
            }, 202, pid),
        ]

    def state_equal(self, a: Any, b: Any) -> bool:
        """Compare two RecommendationStates for equality.

        Compares recommendations by id, rule_id, rule_version,
        target_entity, category, and rationale.
        """
        if not isinstance(a, RecommendationState) or not isinstance(
            b, RecommendationState,
        ):
            return a == b

        if len(a.recommendations) != len(b.recommendations):
            return False

        a_sorted = sorted(a.recommendations, key=lambda r: r.id)
        b_sorted = sorted(b.recommendations, key=lambda r: r.id)

        for ar, br in zip(a_sorted, b_sorted, strict=True):
            if ar.id != br.id:
                return False
            if ar.rule_id != br.rule_id:
                return False
            if ar.rule_version != br.rule_version:
                return False
            if ar.target_entity != br.target_entity:
                return False
            if ar.category != br.category:
                return False
            if ar.rationale != br.rationale:
                return False

        return True

    def canonical_json(self, payload: dict) -> str:
        """Deterministic JSON string."""
        return json.dumps(
            payload, sort_keys=True, separators=(",", ":"),
        )

    def create_context(
        self, projection: RecommendationProjection,
    ) -> ProjectionContext:
        """Create a valid ProjectionContext."""
        return ProjectionContext(
            projection_id="recommendation",
            event_store=SQLiteEventStore()
            if self._tmp_path is None
            else SQLiteEventStore(
                db_path=str(self._tmp_path / "ctx.db"),
            ),
            snapshot_manager=NullSnapshotManager(),
            dependency_reader=DependencyReader(),
            logger=__import__("logging").getLogger("conformance"),
            metrics=MetricsCollector(),
        )


# ── Conformance Tests ────────────────────────────────────────────────────────


class TestRecommendationConformance:
    """Run the full Conformance Suite against RecommendationProjection."""

    def test_all_laws_pass(self):
        provider = RecommendationConformanceProvider()
        projection = provider.create_projection()
        suite = ConformanceSuite(projection, provider)
        report = suite.run()

        print("\n" + report.summary())

        assert report.all_passed, (
            f"RecommendationProjection failed conformance: "
            f"{report.failed_laws}"
        )

    def test_determinism_law(self):
        provider = RecommendationConformanceProvider()
        projection = provider.create_projection()
        from rationalevault.projection_platform.conformance.laws import (
            verify_determinism,
        )
        assert verify_determinism(projection, provider)

    def test_incrementality_law(self):
        provider = RecommendationConformanceProvider()
        projection = provider.create_projection()
        from rationalevault.projection_platform.conformance.laws import (
            verify_incrementality,
        )
        assert verify_incrementality(projection, provider)

    def test_snapshot_roundtrip_law(self):
        provider = RecommendationConformanceProvider()
        projection = provider.create_projection()
        from rationalevault.projection_platform.conformance.laws import (
            verify_snapshot_roundtrip,
        )
        assert verify_snapshot_roundtrip(projection, provider)

    def test_replay_equivalence_law(self):
        provider = RecommendationConformanceProvider()
        projection = provider.create_projection()
        from rationalevault.projection_platform.conformance.laws import (
            verify_replay_equivalence,
        )
        assert verify_replay_equivalence(projection, provider)

    def test_serialization_roundtrip_law(self):
        provider = RecommendationConformanceProvider()
        projection = provider.create_projection()
        from rationalevault.projection_platform.conformance.laws import (
            verify_serialization_roundtrip,
        )
        assert verify_serialization_roundtrip(projection, provider)

    def test_health_contract_law(self):
        provider = RecommendationConformanceProvider()
        projection = provider.create_projection()
        from rationalevault.projection_platform.conformance.laws import (
            verify_health_contract,
        )
        assert verify_health_contract(projection, provider)

    def test_isolation_law(self):
        provider = RecommendationConformanceProvider()
        projection = provider.create_projection()
        from rationalevault.projection_platform.conformance.laws import (
            verify_isolation,
        )
        assert verify_isolation(projection, provider)
