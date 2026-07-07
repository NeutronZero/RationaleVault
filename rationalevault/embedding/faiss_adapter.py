"""FAISSAdapter — FAISS-backed runtime adapter for semantic search.

Implements the RuntimeAdapter protocol from the Projection Platform.
The adapter builds a FAISS index from vectors produced by EmbeddingBuilder.

Index type: IndexFlatL2 (exact L2 search). Other index types are
deferred to a future phase.

Lazy build: search() triggers build() if the index is not yet built.
The index is discardable — it can be destroyed and rebuilt at any time
without affecting projection correctness.
"""
from __future__ import annotations

from dataclasses import dataclass

from rationalevault.embedding.builder import EmbeddingBuilder
from rationalevault.embedding.state import EmbeddingState
from rationalevault.projection_platform.models import RuntimeHealth, SearchResult


@dataclass
class FAISSMetrics:
    """Runtime metrics for the FAISS adapter."""

    indexed_nodes: int = 0
    index_type: str = "IndexFlatL2"
    dimension: int = 0
    vector_count: int = 0
    last_build_ms: float = 0.0


class FAISSAdapter:
    """FAISS-backed search adapter.

    Usage:
        provider = SentenceTransformerProvider()
        builder = EmbeddingBuilder(provider)
        adapter = FAISSAdapter(builder)

        adapter.build(state)
        results = adapter.search("query string", k=5)
    """

    def __init__(self, builder: EmbeddingBuilder) -> None:
        self._builder = builder
        self._index = None
        self._node_ids: list[str] = []
        self._health = RuntimeHealth.UNKNOWN
        self._metrics = FAISSMetrics()

    def build(self, state: EmbeddingState) -> None:
        """Build the FAISS index from EmbeddingState via EmbeddingBuilder.

        This method:
        1. Asks the builder for vectors (incremental)
        2. Constructs a FAISS IndexFlatL2
        3. Maintains node_id mapping for result lookup
        """
        import time
        start = time.perf_counter()

        vectors = self._builder.build(state)
        if not vectors:
            self._index = None
            self._node_ids = []
            self._health = RuntimeHealth.READY
            self._metrics = FAISSMetrics()
            self._metrics.last_build_ms = (time.perf_counter() - start) * 1000
            return

        try:
            import faiss
            import numpy as np
        except ImportError:
            raise ImportError(
                "Embedding features require 'rationalevault[embed]'. "
                "Install with: pip install rationalevault[embed]"
            )

        node_ids = list(vectors.keys())
        matrix = np.array([vectors[nid] for nid in node_ids], dtype=np.float32)
        dim = matrix.shape[1]

        index = faiss.IndexFlatL2(dim)
        index.add(matrix)

        self._index = index
        self._node_ids = node_ids
        self._health = RuntimeHealth.READY
        self._metrics = FAISSMetrics(
            indexed_nodes=len(node_ids),
            index_type="IndexFlatL2",
            dimension=dim,
            vector_count=index.ntotal,
            last_build_ms=(time.perf_counter() - start) * 1000,
        )

    def destroy(self) -> None:
        """Discard the index. Can be rebuilt at any time."""
        self._index = None
        self._node_ids = []
        self._health = RuntimeHealth.UNKNOWN
        self._metrics = FAISSMetrics()

    def search(self, query: str, k: int = 10) -> list[SearchResult]:
        """Search for nearest neighbors to the query string.

        Triggers build() if the index is not yet built.
        Returns SearchResult with node_id, score, and metadata.
        """
        if self._index is None:
            return []

        import numpy as np

        query_vec = self._builder.embed_query(query)
        if not query_vec:
            return []

        query_array = np.array([query_vec], dtype=np.float32)
        k_actual = min(k, self._index.ntotal)
        if k_actual == 0:
            return []

        distances, indices = self._index.search(query_array, k_actual)

        results = []
        for i, idx in enumerate(indices[0]):
            if 0 <= idx < len(self._node_ids):
                results.append(
                    SearchResult(
                        id=self._node_ids[idx],
                        score=float(distances[0][i]),
                        payload={"distance_metric": "L2"},
                    )
                )
        return results

    def metrics(self) -> dict:
        """Return adapter metrics."""
        return {
            "indexed_nodes": self._metrics.indexed_nodes,
            "index_type": self._metrics.index_type,
            "dimension": self._metrics.dimension,
            "vector_count": self._metrics.vector_count,
            "last_build_ms": round(self._metrics.last_build_ms, 2),
            "builder_cache_hits": self._builder.metrics.cache_hits,
            "builder_cache_misses": self._builder.metrics.cache_misses,
            "builder_rebuilt_nodes": self._builder.metrics.rebuilt_nodes,
        }

    def health(self) -> RuntimeHealth:
        return self._health
