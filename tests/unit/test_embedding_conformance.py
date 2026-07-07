"""Conformance tests for EmbeddingProjection against ADR-027 Projection Laws.

Verifies that EmbeddingProjection satisfies all 7 Projection Laws
through the generic Projection Conformance Suite.

This is the validation milestone: if EmbeddingProjection passes the
unchanged Conformance Suite without modifying any platform abstractions,
ADR-027 is validated as a genuinely reusable projection architecture.
"""
from __future__ import annotations

from typing import Any
from uuid import uuid4

from rationalevault.embedding.projection import EmbeddingProjection
from rationalevault.embedding.state import EmbeddingState
from rationalevault.db.sqlite_store import SQLiteEventStore
from rationalevault.projection_platform.conformance import ConformanceSuite
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
        stream_id="knowledge",
        version=seq,
        event_type=event_type,
        metadata=EventMetadata(actor="test", source="test"),
        payload=payload,
        parent_id=None,
        recorded_at=None,
    )


# ── Fixture Provider ─────────────────────────────────────────────────────────


class EmbeddingConformanceProvider:
    """ProjectionConformanceProvider for EmbeddingProjection."""

    def __init__(self, tmp_path=None) -> None:
        self._tmp_path = tmp_path
        self._pid = uuid4()

    def create_projection(self) -> EmbeddingProjection:
        return EmbeddingProjection()

    def events(self) -> list[EventRecord]:
        """Representative event stream with knowledge lifecycle events."""
        pid = self._pid
        return [
            # Create three knowledge nodes
            _event(EventType.KNOWLEDGE_CREATED, {
                "knowledge_id": "k1",
                "title": "Architecture Principle",
                "content": "State is derived from events.",
                "knowledge_type": "ARCHITECTURE_PRINCIPLE",
                "tags": ["architecture", "invariant"],
                "importance": "critical",
                "knowledge_domain": "ARCHITECTURE",
            }, 1, pid),
            _event(EventType.KNOWLEDGE_CREATED, {
                "knowledge_id": "k2",
                "title": "Lesson Learned",
                "content": (
                    "Always run benchmarks before claiming "
                    "performance improvements."
                ),
                "knowledge_type": "LESSON",
                "tags": ["performance", "process"],
                "importance": "high",
                "knowledge_domain": "PROCESS",
            }, 2, pid),
            _event(EventType.KNOWLEDGE_CREATED, {
                "knowledge_id": "k3",
                "title": "Workflow Pattern",
                "content": "Use TDD for all new features.",
                "knowledge_type": "WORKFLOW_PATTERN",
                "tags": ["testing", "workflow"],
                "importance": "medium",
                "knowledge_domain": "QUALITY",
            }, 3, pid),
            # Update k1
            _event(EventType.KNOWLEDGE_UPDATED, {
                "knowledge_id": "k1",
                "title": "Architecture Principle",
                "content": (
                    "State is derived from events. "
                    "No derived state is authoritative."
                ),
                "knowledge_type": "ARCHITECTURE_PRINCIPLE",
                "tags": ["architecture", "invariant", "core"],
                "importance": "critical",
                "knowledge_domain": "ARCHITECTURE",
            }, 4, pid),
            # Synthesize k4 (backward compat)
            _event(EventType.KNOWLEDGE_SYNTHESIZED, {
                "knowledge_id": "k4",
                "title": "Research Finding",
                "content": "FAISS provides sub-linear search for dense vectors.",
                "knowledge_type": "RESEARCH_FINDING",
                "tags": ["search", "vectors"],
                "importance": "medium",
                "knowledge_domain": "RESEARCH",
            }, 5, pid),
            # Delete k2
            _event(EventType.KNOWLEDGE_DELETED, {
                "knowledge_id": "k2",
            }, 6, pid),
            # Supersede k3 (backward compat delete)
            _event(EventType.KNOWLEDGE_SUPERSEDED, {
                "knowledge_id": "k3",
                "superseded_by": "k4",
            }, 7, pid),
        ]

    def edge_case_events(self) -> list[list[EventRecord]]:
        """Edge-case streams for the conformance suite."""
        pid = self._pid
        return [
            # Single creation
            [_event(EventType.KNOWLEDGE_CREATED, {
                "knowledge_id": "k_single",
                "title": "Solo",
                "content": "One knowledge object.",
                "knowledge_type": "LESSON",
            }, 1, pid)],
            # Empty (no events for this projection)
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
        return [
            e for e in self.events()
            if e.event_type in EmbeddingProjection().metadata.consumed_events.types
        ]

    def unsupported_events(self) -> list[EventRecord]:
        """Events this projection does NOT consume."""
        pid = self._pid
        return [
            _event(EventType.MEMORY_RECORDED, {"content": "mem"}, 100, pid),
            _event(EventType.TASK_CREATED, {
                "task_id": "t1",
                "details": {"summary": "Task"},
            }, 101, pid),
            _event(EventType.DECISION_PROPOSED, {
                "decision_id": "d1",
                "title": "Use Rust",
            }, 102, pid),
        ]

    def state_equal(self, a: Any, b: Any) -> bool:
        """Compare two EmbeddingStates for equality.

        Compares nodes (canonical text and content_hash),
        ignoring sequence which depends on event ordering.
        """
        if not isinstance(a, EmbeddingState) or not isinstance(b, EmbeddingState):
            return a == b

        if set(a.nodes.keys()) != set(b.nodes.keys()):
            return False

        for node_id in a.nodes:
            a_node = a.nodes[node_id]
            b_node = b.nodes[node_id]
            if a_node.get("canonical_text") != b_node.get("canonical_text"):
                return False
            if a_node.get("content_hash") != b_node.get("content_hash"):
                return False

        return True

    def canonical_json(self, payload: dict) -> str:
        """Deterministic JSON string."""
        import json
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    def create_context(self, projection: EmbeddingProjection) -> ProjectionContext:
        """Create a valid ProjectionContext."""
        return ProjectionContext(
            projection_id="embedding",
            event_store=SQLiteEventStore() if self._tmp_path is None
            else SQLiteEventStore(db_path=str(self._tmp_path / "ctx.db")),
            snapshot_manager=NullSnapshotManager(),
            dependency_reader=DependencyReader(),
            logger=__import__("logging").getLogger("conformance"),
            metrics=MetricsCollector(),
        )


# ── Conformance Tests ────────────────────────────────────────────────────────


class TestEmbeddingConformance:
    """Run the full Projection Conformance Suite against EmbeddingProjection."""

    def test_all_laws_pass(self):
        provider = EmbeddingConformanceProvider()
        projection = provider.create_projection()
        suite = ConformanceSuite(projection, provider)
        report = suite.run()

        print("\n" + report.summary())

        assert report.all_passed, (
            f"EmbeddingProjection failed conformance: "
            f"{report.failed_laws}"
        )

    def test_determinism_law(self):
        provider = EmbeddingConformanceProvider()
        projection = provider.create_projection()
        from rationalevault.projection_platform.conformance.laws import (
            verify_determinism,
        )
        assert verify_determinism(projection, provider)

    def test_incrementality_law(self):
        provider = EmbeddingConformanceProvider()
        projection = provider.create_projection()
        from rationalevault.projection_platform.conformance.laws import (
            verify_incrementality,
        )
        assert verify_incrementality(projection, provider)

    def test_snapshot_roundtrip_law(self):
        provider = EmbeddingConformanceProvider()
        projection = provider.create_projection()
        from rationalevault.projection_platform.conformance.laws import (
            verify_snapshot_roundtrip,
        )
        assert verify_snapshot_roundtrip(projection, provider)

    def test_replay_equivalence_law(self):
        provider = EmbeddingConformanceProvider()
        projection = provider.create_projection()
        from rationalevault.projection_platform.conformance.laws import (
            verify_replay_equivalence,
        )
        assert verify_replay_equivalence(projection, provider)

    def test_serialization_roundtrip_law(self):
        provider = EmbeddingConformanceProvider()
        projection = provider.create_projection()
        from rationalevault.projection_platform.conformance.laws import (
            verify_serialization_roundtrip,
        )
        assert verify_serialization_roundtrip(projection, provider)

    def test_health_contract_law(self):
        provider = EmbeddingConformanceProvider()
        projection = provider.create_projection()
        from rationalevault.projection_platform.conformance.laws import (
            verify_health_contract,
        )
        assert verify_health_contract(projection, provider)

    def test_isolation_law(self):
        provider = EmbeddingConformanceProvider()
        projection = provider.create_projection()
        from rationalevault.projection_platform.conformance.laws import (
            verify_isolation,
        )
        assert verify_isolation(projection, provider)
