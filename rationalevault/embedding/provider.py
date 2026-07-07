"""EmbeddingProvider — abstract interface and sentence-transformers implementation.

The EmbeddingProvider protocol decouples the embedding builder from any
specific ML model. Multiple providers can satisfy the same contract:

  - SentenceTransformerProvider (default, local)
  - OpenAIProvider (API)
  - VoyageProvider (API)
  - NomicProvider (local or API)
  - LocalONNXProvider (quantized)
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Protocol for embedding model providers."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts into vectors."""
        ...

    @property
    def dimension(self) -> int:
        """Vector dimensionality."""
        ...

    @property
    def model_name(self) -> str:
        """Model identifier."""
        ...

    @property
    def provider_name(self) -> str:
        """Provider name (e.g. 'sentence-transformers')."""
        ...


class SentenceTransformerProvider:
    """EmbeddingProvider backed by sentence-transformers.

    Lazily imports sentence-transformers to avoid startup overhead
    when embedding features are not used.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError(
                "Embedding features require 'rationalevault[embed]'. "
                "Install with: pip install rationalevault[embed]"
            )
        self._model_name = model_name
        self._model = SentenceTransformer(model_name)
        self._dim: int | None = None

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        embeddings = self._model.encode(texts, show_progress_bar=False)
        return embeddings.tolist()

    @property
    def dimension(self) -> int:
        if self._dim is None:
            self._dim = self._model.get_sentence_embedding_dimension()
        return self._dim

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def provider_name(self) -> str:
        return "sentence-transformers"
