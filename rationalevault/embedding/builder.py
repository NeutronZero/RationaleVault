"""EmbeddingBuilder — incremental vector generation from EmbeddingState.

The builder maintains a cache of node_id -> (content_hash, provider, model, version).
On each build(), it diffs current state against cache and only re-embeds changed nodes.
If provider or model changes, all embeddings are invalidated automatically.

Metrics are tracked for observability and benchmarking.
"""
from __future__ import annotations

from dataclasses import dataclass

from rationalevault.embedding.provider import EmbeddingProvider
from rationalevault.embedding.state import EmbeddingState


@dataclass
class BuildMetrics:
    """Metrics from the last build() call."""

    cache_hits: int = 0
    cache_misses: int = 0
    rebuilt_nodes: int = 0
    total_nodes: int = 0
    rebuild_reason: str = "startup"


class EmbeddingBuilder:
    """Incremental vector builder.

    Maintains a cache keyed by (node_id, content_hash, provider, model, version).
    Only nodes whose content_hash, provider, model, or version have changed
    are re-embedded.
    """

    def __init__(self, provider: EmbeddingProvider) -> None:
        self._provider = provider
        self._cache: dict[str, tuple[str, str, str, int]] = {}
        self._vectors: dict[str, list[float]] = {}
        self._last_provider: str = ""
        self._last_model: str = ""
        self._last_version: int = 0
        self.metrics = BuildMetrics()

    @property
    def provider(self) -> EmbeddingProvider:
        return self._provider

    def build(self, state: EmbeddingState) -> dict[str, list[float]]:
        """Build vectors for all nodes. Only re-embeds changed nodes.

        Returns the full vector dictionary.
        """
        self.metrics = BuildMetrics(total_nodes=state.node_count)
        provider_changed = (
            state.provider != self._last_provider
            or state.model != self._last_model
            or state.version != self._last_version
        )

        if provider_changed:
            self.metrics.rebuild_reason = "provider_change"
            self._cache.clear()
            self._vectors.clear()
            self._last_provider = state.provider
            self._last_model = state.model
            self._last_version = state.version

        changed_nodes: list[str] = []
        for node_id, node_info in state.nodes.items():
            new_hash = node_info.get("content_hash", "")
            cache_entry = self._cache.get(node_id)

            if cache_entry is None:
                changed_nodes.append(node_id)
                self.metrics.cache_misses += 1
            else:
                cached_hash, cached_prov, cached_model, cached_ver = cache_entry
                if (
                    cached_hash != new_hash
                    or cached_prov != state.provider
                    or cached_model != state.model
                    or cached_ver != state.version
                ):
                    changed_nodes.append(node_id)
                    self.metrics.cache_misses += 1
                else:
                    self.metrics.cache_hits += 1

        if not changed_nodes:
            return self._vectors

        texts = [state.nodes[nid].get("canonical_text", "") for nid in changed_nodes]
        new_vectors = self._provider.embed(texts)

        for nid, vec in zip(changed_nodes, new_vectors):
            self._vectors[nid] = vec
            self._cache[nid] = (
                state.nodes[nid].get("content_hash", ""),
                state.provider,
                state.model,
                state.version,
            )

        self.metrics.rebuilt_nodes = len(changed_nodes)
        return self._vectors

    def embed_query(self, query: str) -> list[float]:
        """Embed a single query string for search."""
        result = self._provider.embed([query])
        return result[0] if result else []
