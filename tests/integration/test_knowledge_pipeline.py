"""
Integration tests for the full knowledge pipeline:
Event ingestion -> Knowledge projection -> Epistemic status derivation.
"""
from __future__ import annotations

import os
import tempfile
import uuid
from datetime import datetime, timezone

import pytest

from rationalevault.db.sqlite_store import SQLiteEventStore
from rationalevault.schema.events import EventMetadata, EventType
from rationalevault.knowledge.models import (
    EpistemicStatus,
    KnowledgeConfidence,
    KnowledgeLifecycle,
    KnowledgeObject,
    KnowledgeType,
    KnowledgeDomain,
    KnowledgeTransferability,
    ProvenanceChain,
)
from rationalevault.projections.knowledge import KnowledgeProjection, KnowledgeState


@pytest.fixture
def temp_db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    try:
        os.unlink(path)
    except OSError:
        pass


def _make_knowledge(
    title: str,
    content: str,
    ktype: KnowledgeType = KnowledgeType.LESSON,
    domain: KnowledgeDomain = KnowledgeDomain.ARCHITECTURE,
    confidence_score: float = 0.7,
    memory_count: int = 1,
    lifecycle: str = KnowledgeLifecycle.ACTIVE.value,
    supporting_ids: list[str] | None = None,
    contradicting_ids: list[str] | None = None,
) -> KnowledgeObject:
    kid = f"k-{uuid.uuid4().hex[:8]}"
    conf = KnowledgeConfidence(
        memory_count=memory_count,
        source_event_count=0,
        contradiction_count=len(contradicting_ids or []),
        average_memory_confidence=confidence_score,
    )
    return KnowledgeObject(
        id=kid,
        version=1,
        title=title,
        content=content,
        knowledge_type=ktype,
        knowledge_domain=domain,
        confidence=conf,
        importance="medium",
        provenance=ProvenanceChain(
            knowledge_id=kid,
            source_memory_ids=[],
            source_event_ids=[],
            synthesis_event_id="",
            confidence=conf,
            evidence_count=0,
        ),
        tags=["integration"],
        supporting_memory_ids=supporting_ids or [],
        contradicting_memory_ids=contradicting_ids or [],
        lifecycle_status=lifecycle,
        created_at=datetime.now(timezone.utc).isoformat(),
        updated_at=datetime.now(timezone.utc).isoformat(),
        project_id="test-project",
        transferability=KnowledgeTransferability.LOCAL_ONLY.value,
    )


class TestKnowledgePipelineIntegration:
    """End-to-end tests for Event -> Knowledge -> KnowledgeProjection pipeline."""

    def test_event_store_append_and_replay(self, temp_db_path):
        """Verify events can be appended and replayed from SQLite."""
        store = SQLiteEventStore(db_path=temp_db_path)
        pid = uuid.uuid4()
        meta = EventMetadata(actor="agent", source="integration_test", session_id="s1")

        store.append_event(pid, "main", EventType.PROJECT_CREATED, {"name": "Test"}, meta)
        store.append_event(pid, "main", EventType.PROJECT_GOAL_SET, {"goal": "Test goal"}, meta)

        events = list(store.replay_stream(pid))
        assert len(events) == 2
        assert events[0].event_type == EventType.PROJECT_CREATED
        assert events[1].event_type == EventType.PROJECT_GOAL_SET

    def test_event_record_has_schema_version(self, temp_db_path):
        """Verify EventRecord includes schema_version field (P0 fix)."""
        store = SQLiteEventStore(db_path=temp_db_path)
        pid = uuid.uuid4()
        meta = EventMetadata(actor="agent", source="integration_test", session_id="s1")

        store.append_event(pid, "main", EventType.PROJECT_CREATED, {"name": "Test"}, meta)
        events = list(store.replay_stream(pid))

        assert hasattr(events[0], "schema_version")
        assert events[0].schema_version == 1

    def test_knowledge_projection_epistemic_classification(self):
        """Verify KnowledgeProjection correctly classifies epistemic statuses."""
        knowledge = [
            _make_knowledge("Low conf", "content", confidence_score=0.3),
            _make_knowledge("High conf", "content", confidence_score=0.8),
            _make_knowledge(
                "Invariant", "content",
                ktype=KnowledgeType.PROJECT_INVARIANT,
                confidence_score=0.95,
                memory_count=5,
            ),
            _make_knowledge(
                "Conflict", "content",
                confidence_score=0.9,
                contradicting_ids=["mem-1"],
            ),
            _make_knowledge(
                "Old", "content",
                lifecycle=KnowledgeLifecycle.SUPERSEDED.value,
            ),
        ]

        state = KnowledgeProjection.project(
            project_id="test-project",
            knowledge=knowledge,
            reference_time=datetime(2026, 7, 1, tzinfo=timezone.utc),
        )

        assert isinstance(state, KnowledgeState)
        assert len(state.proposed) >= 1
        assert len(state.validated) >= 1
        assert len(state.invariants) >= 1
        assert len(state.conflicted) >= 1
        assert len(state.tombstoned) >= 1

    def test_knowledge_projection_health_metrics(self):
        """Verify KnowledgeProjection computes health metrics."""
        knowledge = [
            _make_knowledge("Active 1", "content", confidence_score=0.8),
            _make_knowledge("Active 2", "content", confidence_score=0.7),
            _make_knowledge(
                "Stale", "content",
                lifecycle=KnowledgeLifecycle.STALE.value,
                confidence_score=0.6,
            ),
        ]

        state = KnowledgeProjection.project(
            project_id="test-project",
            knowledge=knowledge,
            reference_time=datetime(2026, 7, 1, tzinfo=timezone.utc),
        )

        assert state.health.active_count == 2
        assert state.health.total_count == 3
        assert 0 <= state.health.confidence <= 1
        assert 0 <= state.health.stale_ratio <= 1

    def test_knowledge_projection_determinism(self):
        """Verify same knowledge produces identical KnowledgeState."""
        knowledge = [
            _make_knowledge("Deterministic", "content", confidence_score=0.8),
            _make_knowledge("Also deterministic", "content", confidence_score=0.6),
        ]
        ref_time = datetime(2026, 7, 1, tzinfo=timezone.utc)

        state_a = KnowledgeProjection.project(
            project_id="test-project",
            knowledge=knowledge,
            reference_time=ref_time,
        )
        state_b = KnowledgeProjection.project(
            project_id="test-project",
            knowledge=knowledge,
            reference_time=ref_time,
        )

        assert state_a.health.overall == state_b.health.overall
        assert len(state_a.active_knowledge) == len(state_b.active_knowledge)
        assert len(state_a.proposed) == len(state_b.proposed)

    def test_knowledge_serialization_roundtrip_through_projection(self):
        """Verify KnowledgeObjects survive serialization roundtrip and projection."""
        k = _make_knowledge("Roundtrip", "content", confidence_score=0.9)
        d = k.to_dict()
        k2 = KnowledgeObject.from_dict(d)

        state = KnowledgeProjection.project(
            project_id="test-project",
            knowledge=[k2],
            reference_time=datetime(2026, 7, 1, tzinfo=timezone.utc),
        )

        assert len(state.active_knowledge) == 1
        assert state.active_knowledge[0].title == "Roundtrip"
