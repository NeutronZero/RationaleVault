"""Integration test: retrieval pipeline emits telemetry end-to-end."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from rationalevault.telemetry.metrics import get_collector


class TestTelemetryIntegration:
    def test_full_compile_context_populates_dashboard(self) -> None:
        collector = get_collector()
        collector.clear()

        from rationalevault.knowledge.context_compiler import compile_context

        with patch("rationalevault.memory.retrieval.get_memory_provider") as mock_mem:
            mock_mem.return_value = MagicMock()
            mock_mem.return_value.search_records.return_value = []
            mock_mem.return_value.get_by_ids.return_value = []
            mock_mem.return_value.count.return_value = 0
            with patch("rationalevault.knowledge.knowledge_retrieval.get_knowledge_provider") as mock_know:
                mock_know.return_value = MagicMock()
                mock_know.return_value.get_knowledge_by_ids.return_value = []
                mock_know.return_value.get_all_knowledge.return_value = []
                try:
                    compile_context(query="How did we handle the migration?")
                except Exception:
                    pass

        snap = collector.snapshot()
        assert snap.total_requests >= 1
        assert snap.avg_total_ms > 0
        assert len(snap.profile_distribution) >= 1

    def test_multiple_queries_build_history(self) -> None:
        collector = get_collector()
        collector.clear()

        from rationalevault.memory.retrieval import retrieve_ranked_citations

        with patch("rationalevault.telemetry.metrics.get_collector", return_value=collector):
            for _ in range(5):
                mock_provider = MagicMock()
                mock_provider.search_records.return_value = []
                mock_provider.get_all_records.return_value = []
                mock_provider.count.return_value = 0
                try:
                    retrieve_ranked_citations(query="test", limit=5)
                except Exception:
                    pass

        snap = collector.snapshot()
        assert snap.total_requests >= 5
