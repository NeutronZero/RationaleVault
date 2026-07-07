"""EmbeddingProjection — pure reducer for knowledge embedding state.

Consumes knowledge lifecycle events and produces EmbeddingState containing
canonical text and provenance metadata. No ML inference during replay.

Events consumed:
  - KNOWLEDGE_CREATED: add node
  - KNOWLEDGE_UPDATED: update node (if text changed)
  - KNOWLEDGE_DELETED: remove node
  - KNOWLEDGE_SYNTHESIZED: add/update node (backward compat)
  - KNOWLEDGE_SUPERSEDED: remove node

The reducer applies events in ledger order. When multiple events exist
for the same node, the last applicable event determines final state.
"""
from __future__ import annotations

from typing import Any, Optional

from rationalevault.embedding.canonicalizer import CanonicalKnowledgeRenderer
from rationalevault.embedding.state import EmbeddingState
from rationalevault.projection_platform.context import ProjectionContext
from rationalevault.projection_platform.models import (
    EventSelector,
    ProjectionCapabilities,
    ProjectionHealth,
    ProjectionMetadata,
)
from rationalevault.schema.events import EventRecord, EventType


class EmbeddingProjection:
    """Projection that compiles EmbeddingState from knowledge events.

    Implements the Projection protocol. State is an EmbeddingState dataclass.
    The reducer is pure — no side effects, no I/O, no ML inference.
    """

    SCHEMA_VERSION = 1

    def __init__(self) -> None:
        self._health = ProjectionHealth.UNKNOWN
        self._ctx: Optional[ProjectionContext] = None

    @property
    def metadata(self) -> ProjectionMetadata:
        return ProjectionMetadata(
            id="embedding",
            version=1,
            schema_version=self.SCHEMA_VERSION,
            consumed_events=EventSelector(
                types=frozenset({
                    EventType.KNOWLEDGE_CREATED,
                    EventType.KNOWLEDGE_UPDATED,
                    EventType.KNOWLEDGE_DELETED,
                    EventType.KNOWLEDGE_SYNTHESIZED,
                    EventType.KNOWLEDGE_SUPERSEDED,
                }),
            ),
            capabilities=ProjectionCapabilities(
                searchable=True,
                snapshotable=True,
                observable=True,
                exportable=False,
                mutable=False,
            ),
            dependencies=(),
            description=(
                "Deterministic projection of knowledge nodes into "
                "canonical text and provenance metadata for embedding."
            ),
        )

    def initialize(self, ctx: ProjectionContext) -> None:
        self._ctx = ctx
        self._health = ProjectionHealth.INITIALIZING

    def reduce(
        self,
        events: list[EventRecord],
        initial_state: Optional[Any] = None,
    ) -> EmbeddingState:
        """Pure event -> EmbeddingState transformer.

        Applies events in ledger order. The final state reflects the
        last applicable event for each node.
        """
        self._health = ProjectionHealth.BUILDING

        if not events and initial_state is not None:
            self._health = ProjectionHealth.READY
            return initial_state  # type: ignore[return-value]

        state = initial_state if initial_state is not None else EmbeddingState()

        for event in events:
            self._apply_event(state, event)

        if events:
            last_seq = max(e.event_sequence for e in events)
            state.sequence = max(state.sequence, last_seq)

        self._health = ProjectionHealth.READY
        return state

    def serialize(self, state: EmbeddingState) -> dict:
        """Serialize EmbeddingState to dict (snapshot payload format)."""
        nodes_sorted = dict(sorted(state.nodes.items()))
        return {
            "nodes": nodes_sorted,
            "provider": state.provider,
            "model": state.model,
            "version": state.version,
            "dimension": state.dimension,
            "sequence": state.sequence,
            "schema_version": self.SCHEMA_VERSION,
        }

    def deserialize(self, payload: dict) -> EmbeddingState:
        """Deserialize dict to EmbeddingState."""
        return EmbeddingState(
            nodes=dict(payload.get("nodes", {})),
            provider=payload.get("provider", "sentence-transformers"),
            model=payload.get("model", "all-MiniLM-L6-v2"),
            version=payload.get("version", 1),
            dimension=payload.get("dimension", 384),
            sequence=payload.get("sequence", 0),
        )

    def health(self) -> ProjectionHealth:
        return self._health

    def shutdown(self) -> None:
        self._health = ProjectionHealth.SHUTDOWN
        self._ctx = None

    def _apply_event(self, state: EmbeddingState, event: EventRecord) -> None:
        """Apply a single event to the state."""
        et = event.event_type

        if et == EventType.KNOWLEDGE_CREATED:
            self._add_node(state, event)
        elif et == EventType.KNOWLEDGE_UPDATED:
            self._update_node(state, event)
        elif et == EventType.KNOWLEDGE_DELETED:
            self._remove_node(state, event)
        elif et == EventType.KNOWLEDGE_SYNTHESIZED:
            self._add_node(state, event)
        elif et == EventType.KNOWLEDGE_SUPERSEDED:
            self._remove_node(state, event)

    def _add_node(self, state: EmbeddingState, event: EventRecord) -> None:
        """Add a node from a knowledge creation event."""
        payload = event.payload
        node_id = payload.get("knowledge_id", payload.get("id", ""))
        if not node_id:
            return

        canonical_text = CanonicalKnowledgeRenderer.render(
            node_id=node_id,
            title=payload.get("title", ""),
            content=payload.get("content", ""),
            knowledge_type=payload.get("knowledge_type", ""),
            tags=payload.get("tags", []),
            importance=payload.get("importance", ""),
            domain=payload.get("knowledge_domain", payload.get("domain", "")),
        )
        content_hash = CanonicalKnowledgeRenderer.content_hash(canonical_text)

        state.nodes[node_id] = {
            "canonical_text": canonical_text,
            "content_hash": content_hash,
            "knowledge_type": payload.get("knowledge_type", ""),
            "importance": payload.get("importance", ""),
            "tags": sorted(payload.get("tags", [])),
            "lifecycle": "active",
        }

    def _update_node(self, state: EmbeddingState, event: EventRecord) -> None:
        """Update a node if its text has changed."""
        payload = event.payload
        node_id = payload.get("knowledge_id", payload.get("id", ""))
        if not node_id or node_id not in state.nodes:
            return

        existing = state.nodes[node_id]
        default_title = existing.get("canonical_text", "").split("\n")[0]
        default_title = default_title.lstrip("# ").strip()
        new_canonical = CanonicalKnowledgeRenderer.render(
            node_id=node_id,
            title=payload.get("title", default_title),
            content=payload.get("content", ""),
            knowledge_type=payload.get(
                "knowledge_type", existing.get("knowledge_type", ""),
            ),
            tags=payload.get("tags", existing.get("tags", [])),
            importance=payload.get("importance", existing.get("importance", "")),
            domain=payload.get("knowledge_domain", payload.get("domain", "")),
        )
        new_hash = CanonicalKnowledgeRenderer.content_hash(new_canonical)

        if new_hash != existing.get("content_hash"):
            state.nodes[node_id] = {
                "canonical_text": new_canonical,
                "content_hash": new_hash,
                "knowledge_type": payload.get(
                    "knowledge_type", existing.get("knowledge_type", ""),
                ),
                "importance": payload.get(
                    "importance", existing.get("importance", ""),
                ),
                "tags": sorted(payload.get("tags", existing.get("tags", []))),
                "lifecycle": "active",
            }

    def _remove_node(self, state: EmbeddingState, event: EventRecord) -> None:
        """Remove a node from the state."""
        node_id = event.payload.get("knowledge_id", event.payload.get("id", ""))
        if node_id and node_id in state.nodes:
            del state.nodes[node_id]
