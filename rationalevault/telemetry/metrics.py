"""Retrieval telemetry collector — in-memory ring buffer for query metrics.

No disk I/O, no locks. Designed for single-process use.
"""
from __future__ import annotations

import statistics
from collections import deque
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RetrievalMetricsSnapshot:
    """Immutable snapshot of accumulated retrieval metrics."""
    total_requests: int
    avg_total_ms: float
    p50_total_ms: float
    p95_total_ms: float
    p99_total_ms: float
    avg_provider_latency_ms: float
    avg_candidate_count: float
    avg_retrieved_count: float
    profile_distribution: dict[str, int]
    stage_averages: dict[str, float]

    @classmethod
    def empty(cls) -> RetrievalMetricsSnapshot:
        return cls(
            total_requests=0,
            avg_total_ms=0.0,
            p50_total_ms=0.0,
            p95_total_ms=0.0,
            p99_total_ms=0.0,
            avg_provider_latency_ms=0.0,
            avg_candidate_count=0.0,
            avg_retrieved_count=0.0,
            profile_distribution={},
            stage_averages={},
        )

    @classmethod
    def from_records(cls, records: list[dict[str, Any]]) -> RetrievalMetricsSnapshot:
        if not records:
            return cls.empty()

        total_ms_values = [r["total_ms"] for r in records]
        provider_values = [r.get("provider_latency_ms", 0.0) for r in records]
        candidate_values = [r.get("candidate_count", 0) for r in records]
        retrieved_values = [r.get("retrieved_count", 0) for r in records]

        profile_dist: dict[str, int] = {}
        for r in records:
            p = r.get("profile", "unknown")
            profile_dist[p] = profile_dist.get(p, 0) + 1

        stage_keys = set()
        for r in records:
            stage_keys.update(r.get("timing_breakdown", {}).keys())
        stage_avgs = {}
        for key in sorted(stage_keys):
            values = [r.get("timing_breakdown", {}).get(key, 0.0) for r in records]
            stage_avgs[key] = statistics.mean(values)

        sorted_total = sorted(total_ms_values)
        n = len(sorted_total)

        def percentile(data: list[float], p: float) -> float:
            k = (n - 1) * p
            f = int(k)
            c = f + 1
            if c >= n:
                return data[-1]
            if k - f >= 0.5:
                return (data[f] + data[c]) / 2
            return data[f]

        return cls(
            total_requests=n,
            avg_total_ms=statistics.mean(total_ms_values),
            p50_total_ms=percentile(sorted_total, 0.5),
            p95_total_ms=percentile(sorted_total, 0.95),
            p99_total_ms=percentile(sorted_total, 0.99),
            avg_provider_latency_ms=statistics.mean(provider_values),
            avg_candidate_count=statistics.mean(candidate_values),
            avg_retrieved_count=statistics.mean(retrieved_values),
            profile_distribution=profile_dist,
            stage_averages=stage_avgs,
        )


class RetrievalMetricsCollector:
    """In-memory ring buffer collecting retrieval telemetry."""

    def __init__(self, maxlen: int = 100) -> None:
        self._maxlen = maxlen
        self._records: deque[dict[str, Any]] = deque(maxlen=maxlen)

    def record(
        self,
        total_ms: float,
        profile: str,
        provider_latency_ms: float = 0.0,
        candidate_count: int = 0,
        retrieved_count: int = 0,
        timing_breakdown: dict[str, float] | None = None,
    ) -> None:
        self._records.append({
            "total_ms": total_ms,
            "profile": profile,
            "provider_latency_ms": provider_latency_ms,
            "candidate_count": candidate_count,
            "retrieved_count": retrieved_count,
            "timing_breakdown": timing_breakdown or {},
        })

    def snapshot(self) -> RetrievalMetricsSnapshot:
        return RetrievalMetricsSnapshot.from_records(list(self._records))

    def clear(self) -> None:
        self._records.clear()


_collector: RetrievalMetricsCollector | None = None


def get_collector(maxlen: int = 100) -> RetrievalMetricsCollector:
    global _collector
    if _collector is None:
        _collector = RetrievalMetricsCollector(maxlen=maxlen)
    return _collector
