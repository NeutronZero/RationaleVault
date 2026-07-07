"""RationaleVault Embedding Projection — Semantic search over knowledge.

EmbeddingProjection consumes knowledge lifecycle events, produces
EmbeddingState (canonical text + metadata), and leaves vector materialization
to the runtime layer (EmbeddingBuilder, FAISSAdapter).
"""
