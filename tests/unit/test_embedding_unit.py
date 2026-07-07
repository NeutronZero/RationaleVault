"""Unit tests for EmbeddingProjection, CanonicalKnowledgeRenderer,
EmbeddingState, EmbeddingBuilder, and FAISSAdapter.

Tests the embedding package independently of the conformance suite.
"""
from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4


from rationalevault.embedding.canonicalizer import CanonicalKnowledgeRenderer
from rationalevault.embedding.state import EmbeddingState
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


def _mock_provider(dimension: int = 384):
    """Create a mock EmbeddingProvider that returns deterministic vectors."""
    provider = MagicMock()
    provider.dimension = dimension
    provider.model_name = "mock-model"
    provider.provider_name = "mock-provider"
    call_count = [0]

    def _embed(texts):
        import hashlib
        result = []
        for text in texts:
            h = hashlib.sha256(text.encode()).digest()
            vec = [float(b) / 255.0 for b in h]
            while len(vec) < dimension:
                vec.extend(vec[:dimension - len(vec)])
            result.append(vec[:dimension])
            call_count[0] += 1
        return result

    provider.embed = _embed
    return provider


# ── CanonicalKnowledgeRenderer Tests ────────────────────────────────────────


class TestCanonicalKnowledgeRenderer:

    def test_deterministic(self):
        t1 = CanonicalKnowledgeRenderer.render(
            node_id="k1", title="Test", content="Hello world",
            knowledge_type="LESSON", tags=["a", "b"],
        )
        t2 = CanonicalKnowledgeRenderer.render(
            node_id="k1", title="Test", content="Hello world",
            knowledge_type="LESSON", tags=["a", "b"],
        )
        assert t1 == t2

    def test_tags_sorted(self):
        t1 = CanonicalKnowledgeRenderer.render(
            node_id="k1", title="T", content="C", tags=["z", "a", "m"],
        )
        t2 = CanonicalKnowledgeRenderer.render(
            node_id="k1", title="T", content="C", tags=["a", "m", "z"],
        )
        assert t1 == t2

    def test_whitespace_normalized(self):
        t1 = CanonicalKnowledgeRenderer.render(
            node_id="k1", title="  Test  ", content="  Hello   world  ",
        )
        t2 = CanonicalKnowledgeRenderer.render(
            node_id="k1", title="Test", content="Hello world",
        )
        assert t1 == t2

    def test_content_hash_deterministic(self):
        h1 = CanonicalKnowledgeRenderer.content_hash("hello")
        h2 = CanonicalKnowledgeRenderer.content_hash("hello")
        assert h1 == h2
        assert len(h1) == 64  # SHA256 hex

    def test_content_hash_differs(self):
        h1 = CanonicalKnowledgeRenderer.content_hash("hello")
        h2 = CanonicalKnowledgeRenderer.content_hash("world")
        assert h1 != h2


# ── EmbeddingState Tests ────────────────────────────────────────────────────


class TestEmbeddingState:

    def test_default_values(self):
        state = EmbeddingState()
        assert state.nodes == {}
        assert state.provider == "sentence-transformers"
        assert state.model == "all-MiniLM-L6-v2"
        assert state.version == 1
        assert state.dimension == 384
        assert state.sequence == 0

    def test_node_ids_sorted(self):
        state = EmbeddingState()
        state.nodes = {"c": {}, "a": {}, "b": {}}
        assert state.node_ids == ["a", "b", "c"]

    def test_node_count(self):
        state = EmbeddingState()
        state.nodes = {"a": {}, "b": {}}
        assert state.node_count == 2


# ── EmbeddingProjection Tests ──────────────────────────────────────────────


class TestEmbeddingProjection:

    def _get_projection(self):
        from rationalevault.embedding.projection import EmbeddingProjection
        return EmbeddingProjection()

    def test_metadata(self):
        proj = self._get_projection()
        m = proj.metadata
        assert m.id == "embedding"
        assert m.version == 1
        assert m.capabilities.searchable is True
        assert m.capabilities.snapshotable is True
        assert EventType.KNOWLEDGE_CREATED in m.consumed_events.types
        assert EventType.KNOWLEDGE_UPDATED in m.consumed_events.types
        assert EventType.KNOWLEDGE_DELETED in m.consumed_events.types
        assert EventType.KNOWLEDGE_SYNTHESIZED in m.consumed_events.types
        assert EventType.KNOWLEDGE_SUPERSEDED in m.consumed_events.types

    def test_health_lifecycle(self):
        proj = self._get_projection()
        from rationalevault.projection_platform.models import ProjectionHealth
        assert proj.health() == ProjectionHealth.UNKNOWN

    def test_add_node(self):
        proj = self._get_projection()
        events = [
            _event(EventType.KNOWLEDGE_CREATED, {
                "knowledge_id": "k1",
                "title": "Test",
                "content": "Hello world",
                "knowledge_type": "LESSON",
                "tags": ["a"],
            }),
        ]
        state = proj.reduce(events)
        assert "k1" in state.nodes
        assert state.nodes["k1"]["knowledge_type"] == "LESSON"
        assert "a" in state.nodes["k1"]["tags"]

    def test_update_node(self):
        proj = self._get_projection()
        events = [
            _event(EventType.KNOWLEDGE_CREATED, {
                "knowledge_id": "k1",
                "title": "Test",
                "content": "Original",
            }, 1),
            _event(EventType.KNOWLEDGE_UPDATED, {
                "knowledge_id": "k1",
                "title": "Test",
                "content": "Updated content",
            }, 2),
        ]
        state = proj.reduce(events)
        assert "Updated content" in state.nodes["k1"]["canonical_text"]

    def test_delete_node(self):
        proj = self._get_projection()
        events = [
            _event(EventType.KNOWLEDGE_CREATED, {
                "knowledge_id": "k1",
                "title": "Test",
                "content": "Hello",
            }, 1),
            _event(EventType.KNOWLEDGE_DELETED, {
                "knowledge_id": "k1",
            }, 2),
        ]
        state = proj.reduce(events)
        assert "k1" not in state.nodes

    def test_synthesized_compat(self):
        proj = self._get_projection()
        events = [
            _event(EventType.KNOWLEDGE_SYNTHESIZED, {
                "knowledge_id": "k1",
                "title": "Synthesized",
                "content": "From synthesis",
            }),
        ]
        state = proj.reduce(events)
        assert "k1" in state.nodes

    def test_superseded_removes(self):
        proj = self._get_projection()
        events = [
            _event(EventType.KNOWLEDGE_CREATED, {
                "knowledge_id": "k1",
                "title": "Old",
                "content": "Old content",
            }, 1),
            _event(EventType.KNOWLEDGE_SUPERSEDED, {
                "knowledge_id": "k1",
                "superseded_by": "k2",
            }, 2),
        ]
        state = proj.reduce(events)
        assert "k1" not in state.nodes

    def test_serialize_roundtrip(self):
        proj = self._get_projection()
        events = [
            _event(EventType.KNOWLEDGE_CREATED, {
                "knowledge_id": "k1",
                "title": "Test",
                "content": "Hello",
                "tags": ["a"],
            }),
        ]
        state = proj.reduce(events)
        serialized = proj.serialize(state)
        restored = proj.deserialize(serialized)
        expected = state.nodes["k1"]["canonical_text"]
        actual = restored.nodes["k1"]["canonical_text"]
        assert actual == expected

    def test_delta_replay(self):
        proj = self._get_projection()
        full_events = [
            _event(EventType.KNOWLEDGE_CREATED, {
                "knowledge_id": "k1",
                "title": "T1",
                "content": "C1",
            }, 1),
            _event(EventType.KNOWLEDGE_CREATED, {
                "knowledge_id": "k2",
                "title": "T2",
                "content": "C2",
            }, 2),
        ]
        full_state = proj.reduce(full_events)

        prefix_events = full_events[:1]
        proj2 = self._get_projection()
        prefix_state = proj2.reduce(prefix_events)

        proj3 = self._get_projection()
        delta_state = proj3.reduce(full_events[1:], initial_state=prefix_state)

        assert set(full_state.nodes.keys()) == set(delta_state.nodes.keys())


# ── EmbeddingBuilder Tests ──────────────────────────────────────────────────


class TestEmbeddingBuilder:

    def test_basic_build(self):
        from rationalevault.embedding.builder import EmbeddingBuilder
        provider = _mock_provider()
        builder = EmbeddingBuilder(provider)

        state = EmbeddingState()
        state.nodes = {
            "k1": {"canonical_text": "Hello", "content_hash": "abc"},
            "k2": {"canonical_text": "World", "content_hash": "def"},
        }
        vectors = builder.build(state)
        assert len(vectors) == 2
        assert "k1" in vectors
        assert "k2" in vectors

    def test_incremental_build(self):
        from rationalevault.embedding.builder import EmbeddingBuilder
        provider = _mock_provider()
        builder = EmbeddingBuilder(provider)

        state1 = EmbeddingState()
        state1.nodes = {
            "k1": {"canonical_text": "Hello", "content_hash": "abc"},
        }
        builder.build(state1)
        assert builder.metrics.cache_misses == 1

        # Same state — should hit cache
        state2 = EmbeddingState()
        state2.nodes = {
            "k1": {"canonical_text": "Hello", "content_hash": "abc"},
        }
        builder.build(state2)
        assert builder.metrics.cache_hits == 1
        assert builder.metrics.cache_misses == 0

    def test_changed_node_rebuilds(self):
        from rationalevault.embedding.builder import EmbeddingBuilder
        provider = _mock_provider()
        builder = EmbeddingBuilder(provider)

        state1 = EmbeddingState()
        state1.nodes = {
            "k1": {"canonical_text": "Hello", "content_hash": "abc"},
        }
        builder.build(state1)

        state2 = EmbeddingState()
        state2.nodes = {
            "k1": {"canonical_text": "Updated", "content_hash": "xyz"},
        }
        builder.build(state2)
        assert builder.metrics.rebuilt_nodes == 1

    def test_provider_change_invalidates(self):
        from rationalevault.embedding.builder import EmbeddingBuilder
        provider = _mock_provider()
        builder = EmbeddingBuilder(provider)

        state1 = EmbeddingState(provider="old", model="old-model", version=1)
        state1.nodes = {"k1": {"canonical_text": "Hello", "content_hash": "abc"}}
        builder.build(state1)

        state2 = EmbeddingState(provider="new", model="new-model", version=2)
        state2.nodes = {"k1": {"canonical_text": "Hello", "content_hash": "abc"}}
        builder.build(state2)
        assert builder.metrics.rebuild_reason == "provider_change"
        assert builder.metrics.rebuilt_nodes == 1

    def test_empty_state(self):
        from rationalevault.embedding.builder import EmbeddingBuilder
        provider = _mock_provider()
        builder = EmbeddingBuilder(provider)

        state = EmbeddingState()
        vectors = builder.build(state)
        assert vectors == {}

    def test_embed_query(self):
        from rationalevault.embedding.builder import EmbeddingBuilder
        provider = _mock_provider()
        builder = EmbeddingBuilder(provider)

        vec = builder.embed_query("test query")
        assert len(vec) == 384
