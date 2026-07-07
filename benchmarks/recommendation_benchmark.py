"""Recommendation Projection Benchmarks.

Measures generation time, search latency, scalability, snapshot size,
recommendation density, and rule hit rate.
"""
from __future__ import annotations

import time
from uuid import uuid4

from rationalevault.recommendation.projection import RecommendationProjection
from rationalevault.recommendation.runtime import RecommendationRuntime
from rationalevault.recommendation.state import (
    RecommendationCategory,
)
from rationalevault.schema.events import EventMetadata, EventRecord, EventType


# ── Helpers ──────────────────────────────────────────────────────────────────


def _event(event_type: EventType, payload: dict, seq: int) -> EventRecord:
    return EventRecord(
        event_sequence=seq,
        id=uuid4(),
        project_id=uuid4(),
        stream_id="main",
        version=seq,
        event_type=event_type,
        metadata=EventMetadata(actor="bench", source="bench"),
        payload=payload,
        parent_id=None,
        recorded_at=None,
    )


_EVENT_WEIGHTS = [
    (EventType.KNOWLEDGE_CREATED, 15),
    (EventType.KNOWLEDGE_UPDATED, 5),
    (EventType.KNOWLEDGE_DELETED, 3),
    (EventType.TASK_COMPLETED, 10),
    (EventType.DECISION_ACCEPTED, 8),
    (EventType.OPEN_QUESTION_RESOLVED, 7),
    (EventType.TASK_CREATED, 20),
    (EventType.DECISION_PROPOSED, 10),
    (EventType.MEMORY_RECORDED, 10),
    (EventType.PROJECT_CREATED, 1),
    (EventType.PROJECT_GOAL_SET, 1),
    (EventType.SKILL_EXECUTED, 1),
]


def _generate_events(count: int) -> list[EventRecord]:
    """Generate a diverse stream of events."""
    events = []
    total_weight = sum(w for _, w in _EVENT_WEIGHTS)

    for i in range(count):
        idx = i % total_weight
        cumulative = 0
        for event_type, weight in _EVENT_WEIGHTS:
            cumulative += weight
            if idx < cumulative:
                events.append(_event(event_type, {
                    "title": f"Item {i}",
                    "task_id": f"t{i}",
                    "knowledge_id": f"k{i}",
                    "decision_id": f"d{i}",
                    "question_id": f"q{i}",
                    "memory_id": f"m{i}",
                    "skill_name": f"skill_{i}",
                    "goal": f"Goal {i}",
                    "focus": f"Focus {i}",
                    "content": f"Content for item {i}",
                    "question": f"Question {i}",
                }, i + 1))
                break

    return events


# ── Benchmarks ───────────────────────────────────────────────────────────────


def bench_generation_time(
    sizes: list[int] | None = None,
) -> list[dict]:
    """Measure time to generate recommendations from events."""
    if sizes is None:
        sizes = [1000, 5000, 10000, 50000]

    results = []
    for n in sizes:
        events = _generate_events(n)
        proj = RecommendationProjection()

        start = time.perf_counter()
        state = proj.reduce(events)
        gen_ms = (time.perf_counter() - start) * 1000

        results.append({
            "events": n,
            "recommendations": state.recommendation_count,
            "generation_ms": round(gen_ms, 2),
            "recs_per_ms": round(
                state.recommendation_count / max(gen_ms, 0.001), 1,
            ),
            "rule_hit_rate": round(proj.rule_hit_rate, 3),
        })

    return results


def bench_search_latency(
    n: int = 10000,
    queries: int = 100,
) -> dict:
    """Measure runtime search latency."""
    events = _generate_events(n)
    proj = RecommendationProjection()
    state = proj.reduce(events)
    runtime = RecommendationRuntime()

    categories = list(RecommendationCategory)
    latencies = []

    for i in range(queries):
        cat = categories[i % len(categories)]
        start = time.perf_counter()
        runtime.search(state, category=cat, k=10)
        latencies.append((time.perf_counter() - start) * 1000)

    latencies.sort()
    return {
        "events": n,
        "recommendations": state.recommendation_count,
        "queries": queries,
        "avg_latency_ms": round(
            sum(latencies) / len(latencies), 3,
        ),
        "p50_latency_ms": round(
            latencies[len(latencies) // 2], 3,
        ),
        "p95_latency_ms": round(
            latencies[int(len(latencies) * 0.95)], 3,
        ),
    }


def bench_scalability(sizes: list[int] | None = None) -> list[dict]:
    """Measure growth of recommendation state vs events."""
    if sizes is None:
        sizes = [1000, 5000, 10000, 50000, 100000]

    results = []
    for n in sizes:
        events = _generate_events(n)
        proj = RecommendationProjection()
        state = proj.reduce(events)

        import json
        serialized = proj.serialize(state)
        snapshot_bytes = len(
            json.dumps(serialized).encode("utf-8"),
        )

        results.append({
            "events": n,
            "recommendations": state.recommendation_count,
            "density": round(
                state.recommendation_count / max(n, 1), 4,
            ),
            "snapshot_bytes": snapshot_bytes,
            "bytes_per_rec": round(
                snapshot_bytes / max(state.recommendation_count, 1),
                1,
            ),
        })

    return results


def bench_rule_hit_rate(n: int = 10000) -> dict:
    """Measure rule hit rate (recommendations / evaluations)."""
    events = _generate_events(n)
    proj = RecommendationProjection()
    state = proj.reduce(events)

    return {
        "events": n,
        "recommendations": state.recommendation_count,
        "evaluations": proj._evaluations,
        "hits": proj._hits,
        "hit_rate": round(proj.rule_hit_rate, 3),
    }


def bench_enrichment_ratio(n: int = 10000) -> dict:
    """Measure runtime enrichment ratio."""
    from datetime import datetime
    from rationalevault.recommendation.runtime import (
        RecommendationRuntime,
    )
    from rationalevault.recommendation.state import (
        RecommendationQueryContext,
    )

    events = _generate_events(n)
    proj = RecommendationProjection()
    state = proj.reduce(events)
    runtime = RecommendationRuntime()

    ctx = RecommendationQueryContext(query_time=datetime.now())
    enriched = runtime.search(state, k=state.recommendation_count, context=ctx)

    total = len(enriched)
    with_knowledge = sum(
        1 for e in enriched if e.knowledge_context is not None
    )
    with_similarity = sum(
        1 for e in enriched if e.semantic_similarity < 1.0
    )

    return {
        "events": n,
        "recommendations": state.recommendation_count,
        "enriched": total,
        "with_knowledge_context": with_knowledge,
        "with_semantic_similarity": with_similarity,
        "enrichment_ratio": round(
            total / max(state.recommendation_count, 1), 3,
        ),
    }


# ── Runner ───────────────────────────────────────────────────────────────────


def run_benchmarks() -> None:
    """Run all recommendation benchmarks and print results."""
    print("=" * 70)
    print("Recommendation Projection Benchmarks")
    print("=" * 70)

    print("\n--- Generation Time ---")
    gen = bench_generation_time()
    print(
        f"{'Events':>8} {'Recs':>8} {'Time(ms)':>10} "
        f"{'Recs/ms':>10} {'HitRate':>8}"
    )
    for r in gen:
        print(
            f"{r['events']:>8} {r['recommendations']:>8} "
            f"{r['generation_ms']:>10.2f} "
            f"{r['recs_per_ms']:>10.1f} "
            f"{r['rule_hit_rate']:>8.3f}"
        )

    print("\n--- Search Latency (10k events, 100 queries) ---")
    search = bench_search_latency()
    print(f"  Recommendations: {search['recommendations']}")
    print(f"  Avg latency:     {search['avg_latency_ms']:.3f} ms")
    print(f"  P50 latency:     {search['p50_latency_ms']:.3f} ms")
    print(f"  P95 latency:     {search['p95_latency_ms']:.3f} ms")

    print("\n--- Scalability ---")
    scale = bench_scalability()
    print(
        f"{'Events':>8} {'Recs':>8} {'Density':>10} "
        f"{'SnapBytes':>10} {'B/Rec':>10}"
    )
    for r in scale:
        print(
            f"{r['events']:>8} {r['recommendations']:>8} "
            f"{r['density']:>10.4f} "
            f"{r['snapshot_bytes']:>10} "
            f"{r['bytes_per_rec']:>10.1f}"
        )

    print("\n--- Rule Hit Rate (10k events) ---")
    hit = bench_rule_hit_rate()
    print(f"  Events:       {hit['events']}")
    print(f"  Recs:         {hit['recommendations']}")
    print(f"  Evaluations:  {hit['evaluations']}")
    print(f"  Hits:         {hit['hits']}")
    print(f"  Hit rate:     {hit['hit_rate']:.1%}")

    print("\n--- Enrichment Ratio (10k events) ---")
    enrich = bench_enrichment_ratio()
    print(f"  Events:             {enrich['events']}")
    print(f"  Recs:               {enrich['recommendations']}")
    print(f"  Enriched:           {enrich['enriched']}")
    print(f"  With knowledge ctx: {enrich['with_knowledge_context']}")
    print(f"  With similarity:    {enrich['with_semantic_similarity']}")
    print(f"  Enrichment ratio:   {enrich['enrichment_ratio']:.3f}")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    run_benchmarks()
