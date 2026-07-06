"""Tests that compile_context and retrieve_ranked_citations emit telemetry."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from rationalevault.telemetry.metrics import get_collector


class TestTelemetryEmission:
    def test_compile_context_emits_metrics(self) -> None:
        collector = get_collector()
        collector.clear()

        from rationalevault.knowledge.context_compiler import compile_context

        with patch("rationalevault.telemetry.metrics.get_collector", return_value=collector):
            with patch("rationalevault.memory.factory.get_memory_provider") as mock_mem:
                mock_mem.return_value = MagicMock()
                mock_mem.return_value.search_records.return_value = []
                mock_mem.return_value.get_by_ids.return_value = []
                with patch("rationalevault.knowledge.factory.get_knowledge_provider") as mock_know:
                    mock_know.return_value = MagicMock()
                    mock_know.return_value.get_knowledge_by_ids.return_value = []
                    try:
                        compile_context(query="test query")
                    except Exception:
                        pass  # Some internal calls may fail, that's fine

        snap = collector.snapshot()
        assert snap.total_requests >= 1

    def test_retrieve_ranked_citations_emits_metrics(self) -> None:
        collector = get_collector()
        collector.clear()

        from rationalevault.memory.retrieval import retrieve_ranked_citations

        with patch("rationalevault.telemetry.metrics.get_collector", return_value=collector):
            mock_provider = MagicMock()
            mock_provider.search_records.return_value = []
            mock_provider.get_all_records.return_value = []
            mock_provider.count.return_value = 0
            with patch("rationalevault.memory.retrieval.get_memory_provider", return_value=mock_provider):
                try:
                    retrieve_ranked_citations(
                        query="test",
                        limit=5,
                    )
                except Exception:
                    pass

        snap = collector.snapshot()
        assert snap.total_requests >= 1
