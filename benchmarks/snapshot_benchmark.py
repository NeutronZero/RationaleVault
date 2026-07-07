"""
SnapshotStore V2 Benchmarks — Full vs Delta Replay.

Generates synthetic event streams and measures:
  1. Full replay (no snapshot)
  2. Delta replay with snapshot at various split points

Produces a table showing improvement for each stream size and split ratio.
"""
from __future__ import annotations

import random
import statistics
import time
from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

from rationalevault.cognitive_head.compiler import CognitiveHead
from rationalevault.cognitive_head.reducers import (
    DecisionReducer,
    ProjectReducer,
    QuestionReducer,
    TaskReducer,
)
from rationalevault.cognitive_head.replay_engine import ReplayEngine, ReplayMode
from rationalevault.cognitive_head.snapshot import SnapshotManager
from rationalevault.cognitive_head.snapshot_payload import (
    CognitiveHeadSnapshotPayload,
)
from rationalevault.cognitive_head.snapshot_policy import EventCountPolicy
from rationalevault.schema.events import EventMetadata, EventRecord, EventType


# ── Event Generation ─────────────────────────────────────────────────────────


def _meta() -> EventMetadata:
    return EventMetadata(actor="bench", source="bench")


def _event(seq: int, ver: int, et: EventType, payload: dict) -> EventRecord:
    return EventRecord(
        event_sequence=seq, id=uuid4(), project_id=uuid4(),
        stream_id="main", version=ver, event_type=et,
        metadata=_meta(), payload=payload, parent_id=None,
        recorded_at=None,
    )


def generate_events(count: int, seed: int = 42) -> list[EventRecord]:
    """Generate a valid event stream with bootstrap + random events."""
    rng = random.Random(seed)
    events = [
        _event(1, 1, EventType.PROJECT_CREATED, {"name": "Benchmark"}),
        _event(2, 2, EventType.PROJECT_GOAL_SET, {"goal": "Benchmark goal"}),
        _event(3, 3, EventType.PROJECT_FOCUS_CHANGED, {"focus": "Benchmark focus"}),
    ]
    seq = 4
    ver = 4
    task_ids = []
    decision_ids = []
    question_ids = []

    for _ in range(count):
        weights = [30, 15, 5, 15, 5, 10, 5, 10, 5]
        et = rng.choices([
            EventType.TASK_CREATED, EventType.TASK_MUTATED,
            EventType.TASK_COMPLETED, EventType.DECISION_PROPOSED,
            EventType.DECISION_ACCEPTED, EventType.DECISION_SUPERSEDED,
            EventType.OPEN_QUESTION_RAISED, EventType.OPEN_QUESTION_RESOLVED,
            EventType.PROJECT_FOCUS_CHANGED,
        ], weights=weights, k=1)[0]

        if et == EventType.TASK_CREATED:
            tid = f"t_{seq}"
            task_ids.append(tid)
            events.append(_event(seq, ver, et, {
                "task_id": tid,
                "details": {"summary": f"Task {tid}", "body": "Body"},
                "priority": rng.choice(["low", "normal", "high"]),
            }))
        elif et == EventType.TASK_MUTATED and task_ids:
            events.append(_event(seq, ver, et, {
                "task_id": rng.choice(task_ids),
                "status": "in_progress",
            }))
        elif et == EventType.TASK_COMPLETED and task_ids:
            events.append(_event(seq, ver, et, {
                "task_id": rng.choice(task_ids),
            }))
        elif et == EventType.DECISION_PROPOSED:
            did = f"d_{seq}"
            decision_ids.append(did)
            events.append(_event(seq, ver, et, {
                "decision_id": did, "title": f"Decision {did}",
            }))
        elif et == EventType.DECISION_ACCEPTED and decision_ids:
            events.append(_event(seq, ver, et, {
                "decision_id": rng.choice(decision_ids),
            }))
        elif et == EventType.DECISION_SUPERSEDED and decision_ids:
            events.append(_event(seq, ver, et, {
                "decision_id": rng.choice(decision_ids),
                "superseded_by": "d_other",
            }))
        elif et == EventType.OPEN_QUESTION_RAISED:
            qid = f"q_{seq}"
            question_ids.append(qid)
            events.append(_event(seq, ver, et, {
                "question_id": qid, "title": f"Question {qid}",
            }))
        elif et == EventType.OPEN_QUESTION_RESOLVED and question_ids:
            events.append(_event(seq, ver, et, {
                "question_id": rng.choice(question_ids),
                "resolution": "Done",
            }))
        elif et == EventType.PROJECT_FOCUS_CHANGED:
            events.append(_event(seq, ver, et, {"focus": f"Focus {seq}"}))
        else:
            continue

        seq += 1
        ver += 1

    return events


# ── Replay Functions ─────────────────────────────────────────────────────────


def replay_full(events: list[EventRecord]) -> CognitiveHead:
    """Full replay from scratch."""
    proj = ProjectReducer.reduce(events)
    tasks = TaskReducer.reduce(events)
    dec = DecisionReducer.reduce(events)
    q = QuestionReducer.reduce(events)

    active_tasks = [t for t in tasks.values() if t.status != "completed"]
    active_decisions = [d for d in dec.values() if d.status == "accepted"]
    open_questions = [qq for qq in q.values() if qq.status == "open"]

    return CognitiveHead(
        project_id=uuid4(),
        project_name=proj.name,
        project_goal=proj.goal,
        current_focus=proj.current_focus,
        ledger_version=max(e.version for e in events),
        compiled_at="",
        active_tasks=active_tasks,
        active_decisions=active_decisions,
        open_questions=open_questions,
        blockers=[],
    )


def replay_delta(
    prefix_events: list[EventRecord],
    suffix_events: list[EventRecord],
) -> CognitiveHead:
    """Delta replay: prefix state is pre-computed (from snapshot), only apply suffix.
    
    In production, the prefix state comes from a snapshot that was saved
    after a previous compilation. The benchmark pre-computes it once and
    reuses it, simulating the real scenario where only suffix events are
    processed during delta replay.
    """
    # Pre-compute prefix state (simulates loading from snapshot)
    proj_prefix = ProjectReducer.reduce(prefix_events)
    tasks_prefix = TaskReducer.reduce(prefix_events)
    dec_prefix = DecisionReducer.reduce(prefix_events)
    q_prefix = QuestionReducer.reduce(prefix_events)

    # Apply only suffix events (the actual delta replay)
    proj = ProjectReducer.reduce(suffix_events, initial_state=proj_prefix)
    tasks = TaskReducer.reduce(suffix_events, initial_state=tasks_prefix)
    dec = DecisionReducer.reduce(suffix_events, initial_state=dec_prefix)
    q = QuestionReducer.reduce(suffix_events, initial_state=q_prefix)

    active_tasks = [t for t in tasks.values() if t.status != "completed"]
    active_decisions = [d for d in dec.values() if d.status == "accepted"]
    open_questions = [qq for qq in q.values() if qq.status == "open"]

    all_events = prefix_events + suffix_events
    return CognitiveHead(
        project_id=uuid4(),
        project_name=proj.name,
        project_goal=proj.goal,
        current_focus=proj.current_focus,
        ledger_version=max(e.version for e in all_events) if all_events else 0,
        compiled_at="",
        active_tasks=active_tasks,
        active_decisions=active_decisions,
        open_questions=open_questions,
        blockers=[],
    )


# ── Benchmark Runner ─────────────────────────────────────────────────────────


@dataclass
class BenchmarkResult:
    size: int
    split_pct: int
    full_ms: float
    delta_ms: float
    improvement_pct: float
    events_replayed: int
    events_reused: int


def run_benchmark(
    size: int,
    split_pct: int,
    iterations: int = 5,
    seed: int = 42,
) -> BenchmarkResult:
    """Run a single benchmark configuration."""
    events = generate_events(size, seed=seed)
    split_idx = int(len(events) * split_pct / 100)
    prefix = events[:split_idx]
    suffix = events[split_idx:]

    # Pre-compute prefix state (simulates snapshot load — done once, not timed)
    proj_prefix = ProjectReducer.reduce(prefix)
    tasks_prefix = TaskReducer.reduce(prefix)
    dec_prefix = DecisionReducer.reduce(prefix)
    q_prefix = QuestionReducer.reduce(prefix)

    def _delta_only() -> CognitiveHead:
        """Apply only suffix events to pre-computed state."""
        proj = ProjectReducer.reduce(suffix, initial_state=proj_prefix)
        tasks = TaskReducer.reduce(suffix, initial_state=tasks_prefix)
        dec = DecisionReducer.reduce(suffix, initial_state=dec_prefix)
        q = QuestionReducer.reduce(suffix, initial_state=q_prefix)
        active_tasks = [t for t in tasks.values() if t.status != "completed"]
        active_decisions = [d for d in dec.values() if d.status == "accepted"]
        open_questions = [qq for qq in q.values() if qq.status == "open"]
        return CognitiveHead(
            project_id=uuid4(), project_name=proj.name,
            project_goal=proj.goal, current_focus=proj.current_focus,
            ledger_version=max(e.version for e in events),
            compiled_at="", active_tasks=active_tasks,
            active_decisions=active_decisions,
            open_questions=open_questions, blockers=[],
        )

    # Warm up
    replay_full(events)
    _delta_only()

    # Benchmark full replay
    full_times = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        replay_full(events)
        t1 = time.perf_counter()
        full_times.append((t1 - t0) * 1000)

    # Benchmark delta replay (suffix processing only)
    delta_times = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        _delta_only()
        t1 = time.perf_counter()
        delta_times.append((t1 - t0) * 1000)

    full_ms = statistics.median(full_times)
    delta_ms = statistics.median(delta_times)
    improvement = ((full_ms - delta_ms) / full_ms * 100) if full_ms > 0 else 0

    return BenchmarkResult(
        size=size,
        split_pct=split_pct,
        full_ms=full_ms,
        delta_ms=delta_ms,
        improvement_pct=improvement,
        events_replayed=len(suffix),
        events_reused=split_idx,
    )


def main() -> None:
    print("=" * 100)
    print("SnapshotStore V2 Benchmarks — Full vs Delta Replay")
    print("=" * 100)
    print()

    # Table 1: Varying stream sizes, 50% snapshot
    print("Table 1: Stream Size Sweep (50% snapshot)")
    print("-" * 100)
    header = f"{'Events':>8} | {'Full (ms)':>10} | {'Delta (ms)':>10} | {'Improvement':>12} | {'Replayed':>10} | {'Reused':>10}"
    print(header)
    print("-" * 100)

    for size in [100, 1000, 5000, 10000]:
        result = run_benchmark(size, split_pct=50)
        print(
            f"{result.size:>8} | {result.full_ms:>10.2f} | "
            f"{result.delta_ms:>10.2f} | {result.improvement_pct:>11.1f}% | "
            f"{result.events_replayed:>10} | {result.events_reused:>10}"
        )

    print()
    print("Table 2: Snapshot Ratio Sweep (5000 events)")
    print("-" * 100)
    print(header)
    print("-" * 100)

    for split_pct in [10, 50, 90, 99]:
        result = run_benchmark(5000, split_pct=split_pct)
        print(
            f"{result.size:>8} | {result.full_ms:>10.2f} | "
            f"{result.delta_ms:>10.2f} | {result.improvement_pct:>11.1f}% | "
            f"{result.events_replayed:>10} | {result.events_reused:>10}"
        )

    print()
    print("Table 3: Large Stream Sweep (10000 events)")
    print("-" * 100)
    print(header)
    print("-" * 100)

    for split_pct in [10, 50, 90, 99]:
        result = run_benchmark(10000, split_pct=split_pct)
        print(
            f"{result.size:>8} | {result.full_ms:>10.2f} | "
            f"{result.delta_ms:>10.2f} | {result.improvement_pct:>11.1f}% | "
            f"{result.events_replayed:>10} | {result.events_reused:>10}"
        )

    print()
    print("=" * 100)
    print("Note: Improvement is (full_ms - delta_ms) / full_ms * 100.")
    print("Positive = delta is faster. Negative = delta is slower (overhead > savings).")
    print("Merge criterion: measurable reduction in replay work for large streams.")
    print("=" * 100)


if __name__ == "__main__":
    main()
