"""Tests for I13.C — CLI, MCP, and retrieval integration."""
from __future__ import annotations

import json

import pytest

from rationalevault.mcp.tools import get_organization_graph_state, query_organization_graph


class TestMCPOrganizationGraphState:
    def test_returns_dict(self) -> None:
        result = get_organization_graph_state()
        # May have no registered projects in test env
        assert isinstance(result, dict)

    def test_deterministic(self) -> None:
        r1 = get_organization_graph_state()
        r2 = get_organization_graph_state()
        # Compare structure, not timestamps
        if "error" not in r1:
            d1 = {k: v for k, v in r1.items() if k != "compiled_at"}
            d2 = {k: v for k, v in r2.items() if k != "compiled_at"}
            assert d1 == d2


class TestMCPOrganizationGraphQuery:
    def test_returns_dict(self) -> None:
        result = query_organization_graph("nonexistent")
        assert isinstance(result, dict)
        assert "error" in result


class TestCLIIntegration:
    def test_org_graph_stats_help(self) -> None:
        import subprocess
        result = subprocess.run(
            ["python", "-m", "rationalevault.cli.main", "organization", "graph", "stats", "--help"],
            capture_output=True, text=True, cwd=".",
        )
        assert result.returncode == 0 or "usage" in result.stdout.lower() or "help" in result.stdout.lower()

    def test_org_graph_query_help(self) -> None:
        import subprocess
        result = subprocess.run(
            ["python", "-m", "rationalevault.cli.main", "organization", "graph", "query", "--help"],
            capture_output=True, text=True, cwd=".",
        )
        assert result.returncode == 0 or "usage" in result.stdout.lower() or "help" in result.stdout.lower()

    def test_org_graph_evaluate_help(self) -> None:
        import subprocess
        result = subprocess.run(
            ["python", "-m", "rationalevault.cli.main", "organization", "graph", "evaluate", "--help"],
            capture_output=True, text=True, cwd=".",
        )
        assert result.returncode == 0 or "usage" in result.stdout.lower() or "help" in result.stdout.lower()

    def test_org_graph_flow_balance_help(self) -> None:
        import subprocess
        result = subprocess.run(
            ["python", "-m", "rationalevault.cli.main", "organization", "graph", "flow-balance", "--help"],
            capture_output=True, text=True, cwd=".",
        )
        assert result.returncode == 0 or "usage" in result.stdout.lower() or "help" in result.stdout.lower()

    def test_org_graph_shortest_path_help(self) -> None:
        import subprocess
        result = subprocess.run(
            ["python", "-m", "rationalevault.cli.main", "organization", "graph", "shortest-path", "--help"],
            capture_output=True, text=True, cwd=".",
        )
        assert result.returncode == 0 or "usage" in result.stdout.lower() or "help" in result.stdout.lower()


class TestRetrievalIntegration:
    def test_organizational_includes_org_graph(self) -> None:
        from rationalevault.retrieval.models import INTENT_PROJECTION_MAP, RetrievalIntent
        projs = INTENT_PROJECTION_MAP[RetrievalIntent.ORGANIZATIONAL]
        assert "organization_graph" in projs

    def test_impact_includes_org_graph(self) -> None:
        from rationalevault.retrieval.models import INTENT_PROJECTION_MAP, RetrievalIntent
        projs = INTENT_PROJECTION_MAP[RetrievalIntent.IMPACT_ANALYSIS]
        assert "organization_graph" in projs

    def test_organizational_keywords_extended(self) -> None:
        from rationalevault.retrieval.models import INTENT_KEYWORDS, RetrievalIntent
        keywords = INTENT_KEYWORDS[RetrievalIntent.ORGANIZATIONAL]
        assert "project" in keywords
        assert "producer" in keywords
        assert "consumer" in keywords
        assert "hotspot" in keywords
        assert "graph" in keywords

    def test_impact_keywords_extended(self) -> None:
        from rationalevault.retrieval.models import INTENT_KEYWORDS, RetrievalIntent
        keywords = INTENT_KEYWORDS[RetrievalIntent.IMPACT_ANALYSIS]
        assert "blast" in keywords
        assert "radius" in keywords
        assert "producer" in keywords
        assert "consumer" in keywords
        assert "downstream" in keywords
        assert "upstream" in keywords

    def test_weights_normalize(self) -> None:
        from rationalevault.retrieval.models import INTENT_WEIGHT_MAP, RetrievalIntent
        for intent, weights in INTENT_WEIGHT_MAP.items():
            total = sum(weights.values())
            assert abs(total - 1.0) < 0.02, f"{intent} weights sum to {total}"
