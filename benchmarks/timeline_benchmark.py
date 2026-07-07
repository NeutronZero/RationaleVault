"""Timeline Projection Benchmarks.

Measures snapshot growth, append throughput, replay amplification,
entry density, and narrative coverage. Uses deterministic event generation.
"""
from __future__ import annotations

import time
from uuid import uuid4

from rationalevault.schema.events import EventMetadata, EventRecord, EventType
from rationalevault.timeline.projection import TimelineProjection


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


# Weighted event types for realistic distribution
_EVENT_WEIGHTS = [
    (EventType.TASK_CREATED, 20),
    (EventType.TASK_COMPLETED, 5),
    (EventType.KNOWLEDGE_CREATED, 15),
    (EventType.KNOWLEDGE_UPDATED, 10),
    (EventType.KNOWLEDGE_DELETED, 3),
    (EventType.DECISION_PROPOSED, 10),
    (EventType.DECISION_ACCEPTED, 5),
    (EventType.DECISION_SUPERSEDED, 3),
    (EventType.OPEN_QUESTION_RAISED, 5),
    (EventType.OPEN_QUESTION_RESOLVED, 5),
    (EventType.MEMORY_RECORDED, 10),
    (EventType.KNOWLEDGE_SYNTHESIZED, 5),
    (EventType.PROJECT_CREATED, 1),
    (EventType.PROJECT_GOAL_SET, 1),
    (EventType.PROJECT_FOCUS_CHANGED, 1),
    (EventType.SKILL_EXECUTED, 1),
]


def _generate_events(count: int) -> list[EventRecord]:
    """Generate a diverse stream of events."""
    events = []
    total_weight = sum(w for _, w in _EVENT_WEIGHTS)

    for i in range(count):
        # Deterministic selection based on index
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
                }, i + 1))
                break

    return events


# ── Benchmarks ───────────────────────────────────────────────────────────────


def bench_snapshot_growth(sizes: list[int] | None = None) -> list[dict]:
    """Measure snapshot size vs entry count.

    Returns a list of dicts with keys: entries, serialize_ms, snapshot_bytes,
    bytes_per_entry.
    """
    if sizes is None:
        sizes = [100, 500, 1000, 5000, 10000]

    proj = TimelineProjection()
    results = []

    for n in sizes:
        events = _generate_events(n)
        state = proj.reduce(events)

        start = time.perf_counter()
        serialized = proj.serialize(state)
        serialize_ms = (time.perf_counter() - start) * 1000

        import json
        snapshot_bytes = len(json.dumps(serialized).encode("utf-8"))
        bytes_per_entry = snapshot_bytes / max(len(state.entries), 1)

        results.append({
            "entries": len(state.entries),
            "events_processed": n,
            "serialize_ms": round(serialize_ms, 2),
            "snapshot_bytes": snapshot_bytes,
            "bytes_per_entry": round(bytes_per_entry, 1),
        })

    return results


def bench_append_throughput(sizes: list[int] | None = None) -> list[dict]:
    """Measure time to append events.

    Returns a list of dicts with keys: events, replay_ms, entries_per_ms.
    """
    if sizes is None:
        sizes = [1000, 5000, 10000, 50000]

    proj = TimelineProjection()
    results = []

    for n in sizes:
        events = _generate_events(n)

        start = time.perf_counter()
        state = proj.reduce(events)
        replay_ms = (time.perf_counter() - start) * 1000

        entries_per_ms = len(state.entries) / max(replay_ms, 0.001)

        results.append({
            "events": n,
            "entries_produced": len(state.entries),
            "replay_ms": round(replay_ms, 2),
            "entries_per_ms": round(entries_per_ms, 1),
        })

    return results


def bench_replay_amplification(sizes: list[int] | None = None) -> list[dict]:
    """Measure entries_produced / events_processed ratio.

    Returns a list of dicts with keys: events, entries, ratio, consumed_ratio.
    """
    if sizes is None:
        sizes = [1000, 5000, 10000, 50000]

    proj = TimelineProjection()
    results = []

    for n in sizes:
        events = _generate_events(n)
        state = proj.reduce(events)

        consumed_events = sum(
            1 for e in events
            if e.event_type in proj.metadata.consumed_events.types
        )

        results.append({
            "events": n,
            "entries": len(state.entries),
            "ratio": round(len(state.entries) / max(n, 1), 3),
            "consumed_events": consumed_events,
            "consumed_ratio": round(
                len(state.entries) / max(consumed_events, 1), 3,
            ),
        })

    return results


def bench_entry_density(n: int = 10000) -> dict:
    """Measure bytes per entry at scale.

    Returns a dict with keys: entries, snapshot_bytes, bytes_per_entry,
    avg_summary_length.
    """
    proj = TimelineProjection()
    events = _generate_events(n)
    state = proj.reduce(events)

    serialized = proj.serialize(state)
    import json
    snapshot_bytes = len(json.dumps(serialized).encode("utf-8"))
    bytes_per_entry = snapshot_bytes / max(len(state.entries), 1)

    avg_summary_len = (
        sum(len(e.summary) for e in state.entries)
        / max(len(state.entries), 1)
    )

    return {
        "entries": len(state.entries),
        "snapshot_bytes": snapshot_bytes,
        "bytes_per_entry": round(bytes_per_entry, 1),
        "avg_summary_length": round(avg_summary_len, 1),
    }


def bench_narrative_coverage(n: int = 10000) -> dict:
    """Measure what fraction of events become timeline entries.

    Returns a dict with keys: total_events, consumed_events, entries,
    coverage_ratio.
    """
    proj = TimelineProjection()
    events = _generate_events(n)
    state = proj.reduce(events)

    consumed = sum(
        1 for e in events
        if e.event_type in proj.metadata.consumed_events.types
    )

    return {
        "total_events": n,
        "consumed_events": consumed,
        "entries": len(state.entries),
        "coverage_ratio": round(len(state.entries) / max(n, 1), 3),
        "selectivity": round(consumed / max(n, 1), 3),
    }


# ── Runner ───────────────────────────────────────────────────────────────────


def run_benchmarks() -> None:
    """Run all timeline benchmarks and print results."""
    print("=" * 70)
    print("Timeline Projection Benchmarks")
    print("=" * 70)

    print("\n--- Snapshot Growth ---")
    growth = bench_snapshot_growth()
    print(f"{'Entries':>8} {'Events':>8} {'Ser(ms)':>10} {'Bytes':>10} {'B/Entry':>10}")
    for r in growth:
        print(
            f"{r['entries']:>8} {r['events_processed']:>8} "
            f"{r['serialize_ms']:>10.2f} {r['snapshot_bytes']:>10} "
            f"{r['bytes_per_entry']:>10.1f}"
        )

    print("\n--- Append Throughput ---")
    throughput = bench_append_throughput()
    print(f"{'Events':>8} {'Entries':>8} {'Time(ms)':>10} {'Ent/ms':>10}")
    for r in throughput:
        print(
            f"{r['events']:>8} {r['entries_produced']:>8} "
            f"{r['replay_ms']:>10.2f} {r['entries_per_ms']:>10.1f}"
        )

    print("\n--- Replay Amplification ---")
    amplification = bench_replay_amplification()
    print(f"{'Events':>8} {'Entries':>8} {'Ratio':>8} {'Consumed':>10} {'Sel.':>8}")
    for r in amplification:
        print(
            f"{r['events']:>8} {r['entries']:>8} "
            f"{r['ratio']:>8.3f} {r['consumed_events']:>10} "
            f"{r['consumed_ratio']:>8.3f}"
        )

    print("\n--- Entry Density (10k events) ---")
    density = bench_entry_density()
    print(f"  Entries:       {density['entries']}")
    print(f"  Snapshot:      {density['snapshot_bytes']} bytes")
    print(f"  Bytes/Entry:   {density['bytes_per_entry']}")
    print(f"  Avg Summary:   {density['avg_summary_length']} chars")

    print("\n--- Narrative Coverage (10k events) ---")
    coverage = bench_narrative_coverage()
    print(f"  Total events:  {coverage['total_events']}")
    print(f"  Consumed:      {coverage['consumed_events']}")
    print(f"  Entries:       {coverage['entries']}")
    print(f"  Coverage:      {coverage['coverage_ratio']:.1%}")
    print(f"  Selectivity:   {coverage['selectivity']:.1%}")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    run_benchmarks()
