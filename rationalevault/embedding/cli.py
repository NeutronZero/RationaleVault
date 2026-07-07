"""CLI handler for `rv embedding` subcommands.

Foreign imports (sentence-transformers, faiss) are deferred to avoid
startup overhead when embedding features are not used.
"""
from __future__ import annotations

import argparse
import sys


def cmd_embedding(args: argparse.Namespace) -> None:
    """Handle `rv embedding` subcommands."""
    if args.embedding_command == "search":
        _cmd_embedding_search(args)
    else:
        print(f"Error: Unknown embedding command '{args.embedding_command}'")
        sys.exit(1)


def _cmd_embedding_search(args: argparse.Namespace) -> None:
    """Search knowledge embeddings by query string."""
    try:
        from rationalevault.embedding.provider import SentenceTransformerProvider
        from rationalevault.embedding.builder import EmbeddingBuilder
        from rationalevault.embedding.faiss_adapter import FAISSAdapter
        from rationalevault.embedding.state import EmbeddingState
        from rationalevault.knowledge.factory import get_knowledge_provider
        from rationalevault.embedding.canonicalizer import CanonicalKnowledgeRenderer
    except ImportError as e:
        print(f"Error: {e}")
        sys.exit(1)

    provider = SentenceTransformerProvider()
    builder = EmbeddingBuilder(provider)
    adapter = FAISSAdapter(builder)

    # Build EmbeddingState from knowledge store
    knowledge_provider = get_knowledge_provider()
    knowledge = knowledge_provider.get_all_knowledge()

    state = EmbeddingState(
        provider=provider.provider_name,
        model=provider.model_name,
        dimension=provider.dimension,
    )

    for k in knowledge:
        canonical_text = CanonicalKnowledgeRenderer.render(
            node_id=k.id,
            title=k.title,
            content=k.content,
            knowledge_type=k.knowledge_type.value,
            tags=k.tags,
            importance=k.importance,
            domain=k.knowledge_domain.value,
        )
        content_hash = CanonicalKnowledgeRenderer.content_hash(canonical_text)
        state.nodes[k.id] = {
            "canonical_text": canonical_text,
            "content_hash": content_hash,
            "knowledge_type": k.knowledge_type.value,
            "importance": k.importance,
            "tags": sorted(k.tags),
            "lifecycle": k.lifecycle_status,
        }

    adapter.build(state)

    k = getattr(args, "k", 5)
    results = adapter.search(args.query, k=k)

    if not results:
        print("No matching knowledge found.")
        return

    print(f"Embedding Search: '{args.query}'")
    print(f"  Knowledge nodes indexed: {state.node_count}")
    print(f"  Results: {len(results)}")
    print("=" * 70)

    for i, r in enumerate(results, 1):
        node = state.nodes.get(r.id, {})
        title = node.get("canonical_text", "").split("\n")[0].lstrip("# ").strip()
        ktype = node.get("knowledge_type", "")
        score = r.score
        print(f"  {i:2d}. [{ktype:<25}] L2={score:.4f} | {title}")
        print(f"      ID: {r.id}")

    print("=" * 70)
