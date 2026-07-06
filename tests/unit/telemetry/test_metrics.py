"""Tests for RetrievalMetricsCollector."""
from __future__ import annotations

from rationalevault.telemetry.metrics import (
    RetrievalMetricsCollector,
    RetrievalMetricsSnapshot,
    get_collector,
)


class TestRetrievalMetricsSnapshot:
    def test_empty_snapshot(self) -> None:
        snap = RetrievalMetricsSnapshot.empty()
        assert snap.total_requests == 0
        assert snap.avg_total_ms == 0.0
        assert snap.p50_total_ms == 0.0
        assert snap.p95_total_ms == 0.0
        assert snap.p99_total_ms == 0.0
        assert snap.profile_distribution == {}

    def test_snapshot_from_records(self) -> None:
        records = [
            {"total_ms": 10.0, "profile": "GENERAL_SEARCH"},
            {"total_ms": 20.0, "profile": "GENERAL_SEARCH"},
            {"total_ms": 30.0, "profile": "FAILURE_ANALYSIS"},
        ]
        snap = RetrievalMetricsSnapshot.from_records(records)
        assert snap.total_requests == 3
        assert snap.avg_total_ms == 20.0
        assert snap.p50_total_ms == 20.0
        assert snap.profile_distribution == {"GENERAL_SEARCH": 2, "FAILURE_ANALYSIS": 1}


class TestRetrievalMetricsCollector:
    def test_singleton(self) -> None:
        c1 = get_collector()
        c2 = get_collector()
        assert c1 is c2

    def test_record_and_snapshot(self) -> None:
        collector = get_collector()
        collector.clear()
        collector.record(
            total_ms=15.0,
            profile="GENERAL_SEARCH",
            provider_latency_ms=5.0,
            candidate_count=100,
            retrieved_count=18,
            timing_breakdown={"query_analysis_ms": 1.0, "search_ms": 3.0},
        )
        snap = collector.snapshot()
        assert snap.total_requests == 1
        assert snap.avg_total_ms == 15.0
        assert snap.avg_provider_latency_ms == 5.0
        assert snap.avg_candidate_count == 100.0
        assert snap.avg_retrieved_count == 18.0

    def test_ring_buffer_respects_maxlen(self) -> None:
        collector = RetrievalMetricsCollector(maxlen=3)
        for i in range(5):
            collector.record(total_ms=float(i), profile="GENERAL_SEARCH")
        snap = collector.snapshot()
        assert snap.total_requests == 3
        # Should keep last 3: 2.0, 3.0, 4.0
        assert snap.avg_total_ms == 3.0

    def test_percentiles(self) -> None:
        collector = RetrievalMetricsCollector(maxlen=100)
        collector.clear()
        for i in range(1, 101):
            collector.record(total_ms=float(i), profile="GENERAL_SEARCH")
        snap = collector.snapshot()
        assert snap.p50_total_ms == 50.5
        assert snap.p95_total_ms == 95.0
        assert snap.p99_total_ms == 99.0

    def test_clear(self) -> None:
        collector = get_collector()
        collector.record(total_ms=10.0, profile="GENERAL_SEARCH")
        collector.clear()
        snap = collector.snapshot()
        assert snap.total_requests == 0
