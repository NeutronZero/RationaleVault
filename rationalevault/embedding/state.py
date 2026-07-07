"""EmbeddingState — canonical text and provenance metadata for knowledge nodes.

EmbeddingState is the authoritative reducer output. It contains no vectors.
Vectors are materialized from state by the EmbeddingBuilder at runtime.

The embedding specification is defined by the combination of:
  provider, model, version, dimension.
When any of these change, all cached vectors are invalidated.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EmbeddingState:
    """Canonical text and metadata for knowledge nodes.

    Attributes:
        nodes:       node_id -> {canonical_text, content_hash, ...}
        provider:    embedding provider name (e.g. "sentence-transformers")
        model:       model identifier (e.g. "all-MiniLM-L6-v2")
        version:     embedding specification version (increment on
                     model/provider/format change)
        dimension:   vector dimensionality
        sequence:    last event_sequence processed (for snapshot invalidation)
    """

    nodes: dict[str, dict] = field(default_factory=dict)
    provider: str = "sentence-transformers"
    model: str = "all-MiniLM-L6-v2"
    version: int = 1
    dimension: int = 384
    sequence: int = 0

    @property
    def node_ids(self) -> list[str]:
        """Sorted node IDs for deterministic iteration."""
        return sorted(self.nodes.keys())

    @property
    def node_count(self) -> int:
        return len(self.nodes)
