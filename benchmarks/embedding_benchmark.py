"""Embedding Projection Benchmarks.

Measures cold build, delta rebuild, snapshot roundtrip, search latency,
and memory footprint. Uses mock provider for deterministic results.
"""
from __future__ import annotations

import hashlib
import time
from unittest.mock import MagicMock

from rationalevault.embedding.projection import EmbeddingProjection
from rationalevault.schema.events import EventMetadata, EventRecord, EventType
from uuid import uuid4


def _mock_provider(dimension: int = 384):
    """Deterministic mock provider for benchmarking."""
    provider = MagicMock()
    provider.dimension = dimension
    provider.model_name = "mock-model"
    provider.provider_name = "mock-provider"

    def _embed(texts):
        result = []
        for text in texts:
            h = hashlib.sha256(text.encode()).digest()
            vec = [float(b) / 255.0 for b in h]
            while len(vec) < dimension:
                vec.extend(vec[:dimension - len(vec)])
            result.append(vec[:dimension])
        return result

    provider.embed = _embed
    return provider


def _event(event_type: EventType, payload: dict, seq: int) -> EventRecord:
    return EventRecord(
        event_sequence=seq,
        id=uuid4(),
        project_id=uuid4(),
        stream_id="knowledge",
        version=seq,
        event_type=event_type,
        metadata=EventMetadata(actor="bench", source="bench"),
        payload=payload,
        parent_id=None,
        recorded_at=None,
    )


def _generate_events(count: int) -> list[EventRecord]:
    """Generate a stream of knowledge creation events."""
    events = []
    for i in range(count):
        events.append(_event(EventType.KNOWLEDGE_CREATED, {
            "knowledge_id": f"k{i:06d}",
            "title": f"Knowledge {i}",
            "content": f"Content for knowledge object {i}. "
                       f"This is a benchmark node with enough text "
                       f"to simulate realistic canonicalization. "
                       f"Topic {i % 10}.",
            "knowledge_type": "LESSON",
            "tags": [f"tag{i % 5}", f"group{i % 3}"],
            "importance": "medium",
            "knowledge_domain": "PROCESS",
        }, i + 1))
    return events


def bench_cold_build(n: int = 1000) -> dict:
    """Measure cold build: full replay from scratch."""
    events = _generate_events(n)
    proj = EmbeddingProjection()
    provider = _mock_provider()

    start = time.perf_counter()
    state = proj.reduce(events)
    replay_ms = (time.perf_counter() - start) * 1000

    from rationalevault.embedding.builder import EmbeddingBuilder
    builder = EmbeddingBuilder(provider)

    start = time.perf_counter()
    vectors = builder.build(state)
    build_ms = (time.perf_counter() - start) * 1000

    return {
        "nodes": n,
        "replay_ms": round(replay_ms, 2),
        "build_ms": round(build_ms, 2),
        "total_ms": round(replay_ms + build_ms, 2),
        "vectors_produced": len(vectors),
    }


def bench_delta_rebuild(n: int = 1000, delta: int = 50) -> dict:
    """Measure delta rebuild: update delta nodes on existing state."""
    events = _generate_events(n)
    proj = EmbeddingProjection()
    state = proj.reduce(events)

    from rationalevault.embedding.builder import EmbeddingBuilder
    provider = _mock_provider()
    builder = EmbeddingBuilder(provider)
    builder.build(state)

    # Create delta events (updates to existing nodes)
    delta_events = []
    for i in range(delta):
        delta_events.append(_event(EventType.KNOWLEDGE_UPDATED, {
            "knowledge_id": f"k{i:06d}",
            "title": f"Knowledge {i} Updated",
            "content": f"Updated content for node {i}.",
        }, n + i + 1))

    start = time.perf_counter()
    delta_state = proj.reduce(delta_events, initial_state=state)
    replay_ms = (time.perf_counter() - start) * 1000

    start = time.perf_counter()
    builder.build(delta_state)
    build_ms = (time.perf_counter() - start) * 1000

    return {
        "total_nodes": n,
        "delta_nodes": delta,
        "replay_ms": round(replay_ms, 2),
        "build_ms": round(build_ms, 2),
        "total_ms": round(replay_ms + build_ms, 2),
        "cache_hits": builder.metrics.cache_hits,
        "cache_misses": builder.metrics.cache_misses,
        "rebuilt_nodes": builder.metrics.rebuilt_nodes,
    }


def bench_snapshot_roundtrip(n: int = 1000) -> dict:
    """Measure snapshot serialize + deserialize time."""
    events = _generate_events(n)
    proj = EmbeddingProjection()
    state = proj.reduce(events)

    start = time.perf_counter()
    serialized = proj.serialize(state)
    serialize_ms = (time.perf_counter() - start) * 1000

    import json
    json_bytes = len(json.dumps(serialized).encode("utf-8"))

    start = time.perf_counter()
    restored = proj.deserialize(serialized)
    deserialize_ms = (time.perf_counter() - start) * 1000

    return {
        "nodes": n,
        "serialize_ms": round(serialize_ms, 2),
        "deserialize_ms": round(deserialize_ms, 2),
        "snapshot_bytes": json_bytes,
        "restored_nodes": restored.node_count,
    }


def bench_search_latency(n: int = 1000, queries: int = 100) -> dict:
    """Measure search latency over an index of n nodes."""
    from rationalevault.embedding.builder import EmbeddingBuilder
    from rationalevault.embedding.faiss_adapter import FAISSAdapter

    events = _generate_events(n)
    proj = EmbeddingProjection()
    state = proj.reduce(events)

    provider = _mock_provider()
    builder = EmbeddingBuilder(provider)
    adapter = FAISSAdapter(builder)
    adapter.build(state)

    latencies = []
    for i in range(queries):
        start = time.perf_counter()
        adapter.search(f"query {i}", k=10)
        latencies.append((time.perf_counter() - start) * 1000)

    return {
        "nodes": n,
        "queries": queries,
        "avg_latency_ms": round(sum(latencies) / len(latencies), 3),
        "p50_latency_ms": round(sorted(latencies)[len(latencies) // 2], 3),
        "p95_latency_ms": round(sorted(latencies)[int(len(latencies) * 0.95)], 3),
        "index_build_ms": adapter.metrics().get("last_build_ms", 0),
    }


def run_benchmarks() -> None:
    """Run all benchmarks and print results."""
    print("=" * 70)
    print("Embedding Projection Benchmarks")
    print("=" * 70)

    print("\n--- Cold Build (1000 nodes) ---")
    r = bench_cold_build(1000)
    for k, v in r.items():
        print(f"  {k:<20} {v}")

    print("\n--- Delta Rebuild (1000 nodes, 50 updated) ---")
    r = bench_delta_rebuild(1000, 50)
    for k, v in r.items():
        print(f"  {k:<20} {v}")

    print("\n--- Snapshot Roundtrip (1000 nodes) ---")
    r = bench_snapshot_roundtrip(1000)
    for k, v in r.items():
        print(f"  {k:<20} {v}")

    print("\n--- Search Latency (1000 nodes, 100 queries) ---")
    r = bench_search_latency(1000, 100)
    for k, v in r.items():
        print(f"  {k:<20} {v}")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    run_benchmarks()
