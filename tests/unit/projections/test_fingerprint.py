import hashlib
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from rationalevault.projections.base import SemVer
from rationalevault.projections.fingerprint import (
    compute_composite_fingerprint,
    compute_event_stream_fingerprint,
    compute_knowledge_fingerprint,
)
from rationalevault.schema.events import EventMetadata, EventType, EventRecord


def _make_event(seq: int, recorded_at: datetime | None = None) -> EventRecord:
    return EventRecord(
        event_sequence=seq,
        id=uuid4(),
        project_id=uuid4(),
        stream_id="main",
        version=1,
        event_type=EventType.TASK_CREATED,
        metadata=EventMetadata(actor="test", source="test"),
        payload={"task_id": f"t{seq}", "title": f"Task {seq}"},
        parent_id=None,
        recorded_at=recorded_at or datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


class TestComputeEventStreamFingerprint:
    def test_empty_events(self):
        fp = compute_event_stream_fingerprint([], "proj", SemVer(1, 0, 0))
        assert isinstance(fp, str)
        assert len(fp) == 64

    def test_deterministic(self):
        events = [_make_event(1), _make_event(2)]
        fp1 = compute_event_stream_fingerprint(events, "proj", SemVer(1, 0, 0))
        fp2 = compute_event_stream_fingerprint(events, "proj", SemVer(1, 0, 0))
        assert fp1 == fp2

    def test_different_project_ids_differ(self):
        events = [_make_event(1)]
        fp1 = compute_event_stream_fingerprint(events, "a", SemVer(1, 0, 0))
        fp2 = compute_event_stream_fingerprint(events, "b", SemVer(1, 0, 0))
        assert fp1 != fp2

    def test_different_versions_differ(self):
        events = [_make_event(1)]
        fp1 = compute_event_stream_fingerprint(events, "proj", SemVer(1, 0, 0))
        fp2 = compute_event_stream_fingerprint(events, "proj", SemVer(1, 1, 0))
        assert fp1 != fp2

    def test_uses_max_sequence(self):
        e1 = _make_event(1)
        e2 = _make_event(5)
        fp1 = compute_event_stream_fingerprint([e1, e2], "proj", SemVer(1, 0, 0))
        fp2 = compute_event_stream_fingerprint([e1], "proj", SemVer(1, 0, 0))
        assert fp1 != fp2

    def test_events_without_recorded_at(self):
        e = _make_event(1)
        e.recorded_at = None
        fp = compute_event_stream_fingerprint([e], "proj", SemVer(1, 0, 0))
        assert isinstance(fp, str)
        assert len(fp) == 64


class TestComputeKnowledgeFingerprint:
    def test_empty_knowledge(self):
        fp = compute_knowledge_fingerprint([], "proj", SemVer(1, 0, 0))
        assert isinstance(fp, str)
        assert len(fp) == 64

    def test_deterministic(self):
        from rationalevault.knowledge.models import KnowledgeObject, KnowledgeType, KnowledgeDomain, KnowledgeConfidence, ProvenanceChain

        conf = KnowledgeConfidence(memory_count=1, source_event_count=1, contradiction_count=0, average_memory_confidence=0.9)
        k = KnowledgeObject(
            id="k1", version=1, title="T", content="C",
            knowledge_type=KnowledgeType.LESSON,
            knowledge_domain=KnowledgeDomain.ARCHITECTURE,
            confidence=conf,
            importance="high",
            provenance=ProvenanceChain(
                knowledge_id="k1", source_memory_ids=[], source_event_ids=[],
                synthesis_event_id="syn-1", confidence=conf, evidence_count=1,
            ),
        )
        fp1 = compute_knowledge_fingerprint([k], "proj", SemVer(1, 0, 0))
        fp2 = compute_knowledge_fingerprint([k], "proj", SemVer(1, 0, 0))
        assert fp1 == fp2

    def test_sorted_by_id_and_version(self):
        from rationalevault.knowledge.models import KnowledgeObject, KnowledgeType, KnowledgeDomain, KnowledgeConfidence, ProvenanceChain

        conf = KnowledgeConfidence(memory_count=1, source_event_count=1, contradiction_count=0, average_memory_confidence=0.9)
        k1 = KnowledgeObject(
            id="b", version=2, title="T", content="C",
            knowledge_type=KnowledgeType.LESSON,
            knowledge_domain=KnowledgeDomain.ARCHITECTURE,
            confidence=conf,
            importance="high",
            provenance=ProvenanceChain(
                knowledge_id="b", source_memory_ids=[], source_event_ids=[],
                synthesis_event_id="syn-1", confidence=conf, evidence_count=1,
            ),
        )
        k2 = KnowledgeObject(
            id="a", version=1, title="T", content="C",
            knowledge_type=KnowledgeType.LESSON,
            knowledge_domain=KnowledgeDomain.ARCHITECTURE,
            confidence=conf,
            importance="high",
            provenance=ProvenanceChain(
                knowledge_id="a", source_memory_ids=[], source_event_ids=[],
                synthesis_event_id="syn-2", confidence=conf, evidence_count=1,
            ),
        )
        fp1 = compute_knowledge_fingerprint([k1, k2], "proj", SemVer(1, 0, 0))
        fp2 = compute_knowledge_fingerprint([k2, k1], "proj", SemVer(1, 0, 0))
        assert fp1 == fp2


class TestComputeCompositeFingerprint:
    def test_deterministic(self):
        deps = {"proj_a": "abc123", "proj_b": "def456"}
        fp1 = compute_composite_fingerprint(SemVer(1, 0, 0), deps, "hash1")
        fp2 = compute_composite_fingerprint(SemVer(1, 0, 0), deps, "hash1")
        assert fp1 == fp2

    def test_sorted_dependencies(self):
        fp1 = compute_composite_fingerprint(SemVer(1, 0, 0), {"b": "1", "a": "2"})
        fp2 = compute_composite_fingerprint(SemVer(1, 0, 0), {"a": "2", "b": "1"})
        assert fp1 == fp2

    def test_none_raw_input_hash(self):
        fp = compute_composite_fingerprint(SemVer(1, 0, 0), {})
        assert isinstance(fp, str)
        assert len(fp) == 64

    def test_different_input_hashes_differ(self):
        fp1 = compute_composite_fingerprint(SemVer(1, 0, 0), {}, "a")
        fp2 = compute_composite_fingerprint(SemVer(1, 0, 0), {}, "b")
        assert fp1 != fp2
