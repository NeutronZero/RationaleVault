#!/usr/bin/env python3
from __future__ import annotations

import time
import uuid
import sys
from pathlib import Path
from datetime import datetime, timezone

# Ensure project is in path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from rationalevault.schema.events import EventMetadata, EventRecord, EventType
from rationalevault.schema.policy import SchemaPolicy
from rationalevault.projections.context import ReplayContext
from rationalevault.projections.pipeline import ReplayPipeline
from rationalevault.projections.service import ReplayService


class MockEventStore:
    def __init__(self, count: int) -> None:
        self.events = [
            EventRecord(
                event_sequence=i,
                id=uuid.uuid4(),
                project_id=uuid.uuid4(),
                stream_id="main",
                version=i,
                event_type=EventType.PROJECT_CREATED if i == 1 else EventType.TASK_CREATED,
                metadata=EventMetadata(actor="bench", source="bench"),
                payload={"name": f"task_{i}"} if i == 1 else {"title": f"Task {i}", "content": f"Desc {i}"},
                parent_id=None,
                recorded_at=datetime.now(timezone.utc),
                schema_version=1,
            )
            for i in range(1, count + 1)
        ]

    def get_project_stream(self, project_id: uuid.UUID, since_sequence: int = 0) -> list[EventRecord]:
        return self.events


def run_benchmark(event_count: int = 1000) -> dict[str, float]:
    store = MockEventStore(event_count)
    context = ReplayContext()
    service = ReplayService(store)
    project_id = uuid.uuid4()

    # 1. Warm up
    service.load_project_events(project_id, context)

    # 2. Benchmark raw storage retrieval simulation
    start_store = time.perf_counter()
    raw_events = store.get_project_stream(project_id)
    end_store = time.perf_counter()
    store_latency_ms = (end_store - start_store) * 1000.0

    # 3. Benchmark full service load (load + pipeline)
    start_service = time.perf_counter()
    processed_events = service.load_project_events(project_id, context)
    end_service = time.perf_counter()
    service_latency_ms = (end_service - start_service) * 1000.0

    # Calculate metrics
    pipeline_overhead_ms = max(0.0, service_latency_ms - store_latency_ms)
    throughput = event_count / (service_latency_ms / 1000.0) if service_latency_ms > 0 else 0.0
    pipeline_overhead_pct = (pipeline_overhead_ms / service_latency_ms * 1000.0) / 10.0 if service_latency_ms > 0 else 0.0

    return {
        "event_count": event_count,
        "store_latency_ms": store_latency_ms,
        "service_latency_ms": service_latency_ms,
        "pipeline_overhead_ms": pipeline_overhead_ms,
        "pipeline_overhead_pct": pipeline_overhead_pct,
        "throughput_eps": throughput,
    }


def main() -> None:
    results_1k = run_benchmark(1000)
    results_10k = run_benchmark(10000)

    report_path = project_root / "docs" / "contributing" / "replay_benchmark.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# S13.3 Replay Benchmark Report\n\n")
        f.write("This report captures baseline performance metrics of the Replay Infrastructure.\n\n")
        f.write("## Baseline Metrics\n\n")
        f.write("| Metric | Baseline (1k events) | Baseline (10k events) |\n")
        f.write("| :--- | :---: | :---: |\n")
        f.write(f"| Replay Throughput (events/sec) | {results_1k['throughput_eps']:,.2f} eps | {results_10k['throughput_eps']:,.2f} eps |\n")
        f.write(f"| Replay Latency | {results_1k['service_latency_ms']:.2f} ms | {results_10k['service_latency_ms']:.2f} ms |\n")
        f.write(f"| Simulated Storage Loading Latency | {results_1k['store_latency_ms']:.2f} ms | {results_10k['store_latency_ms']:.2f} ms |\n")
        f.write(f"| Pipeline & Resolver Overhead | {results_1k['pipeline_overhead_ms']:.2f} ms | {results_10k['pipeline_overhead_ms']:.2f} ms |\n")
        f.write(f"| Pipeline Overhead Pct | {results_1k['pipeline_overhead_pct']:.2f} % | {results_10k['pipeline_overhead_pct']:.2f} % |\n")

    print("Replay benchmark complete. Report written to docs/contributing/replay_benchmark.md")


if __name__ == "__main__":
    main()
