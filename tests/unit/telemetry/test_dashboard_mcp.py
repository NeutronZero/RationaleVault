"""Tests for the retrieval_dashboard MCP tool."""
from __future__ import annotations

import pytest

from rationalevault.mcp.tools import retrieval_dashboard


class TestRetrievalDashboardMCP:
    def test_returns_snapshot_dict(self) -> None:
        result = retrieval_dashboard()
        assert isinstance(result, dict)
        assert "total_requests" in result
        assert "avg_total_ms" in result

    def test_empty_state(self) -> None:
        from rationalevault.telemetry.metrics import get_collector
        get_collector().clear()
        result = retrieval_dashboard()
        assert result["total_requests"] == 0
