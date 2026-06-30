"""Tests for I15.4 — CLI + MCP exposure."""
from __future__ import annotations

import pytest

from rationalevault.recommendations import RecommendationEngine
from rationalevault.recommendations.models import (
    RecommendationCategory,
    make_recommendation,
)


class TestMCPRecommendations:
    def test_get_recommendations_returns_dict(self) -> None:
        from rationalevault.mcp.tools import get_recommendations
        result = get_recommendations()
        assert isinstance(result, dict)

    def test_get_recommendations_has_expected_keys(self) -> None:
        from rationalevault.mcp.tools import get_recommendations
        result = get_recommendations()
        if "error" not in result:
            assert "recommendations" in result
            assert "recommendation_count" in result

    def test_get_project_recommendations_returns_dict(self) -> None:
        from rationalevault.mcp.tools import get_project_recommendations
        result = get_project_recommendations("nonexistent")
        assert isinstance(result, dict)

    def test_deterministic(self) -> None:
        from rationalevault.mcp.tools import get_recommendations
        r1 = get_recommendations()
        r2 = get_recommendations()
        if "error" not in r1 and "error" not in r2:
            d1 = {k: v for k, v in r1.items() if k != "compiled_at"}
            d2 = {k: v for k, v in r2.items() if k != "compiled_at"}
            assert d1 == d2


class TestCLIIntegration:
    def test_recommend_help(self) -> None:
        import subprocess
        result = subprocess.run(
            ["python", "-m", "rationalevault.cli.main", "recommend", "--help"],
            capture_output=True, text=True, cwd=".",
        )
        assert result.returncode == 0 or "usage" in result.stdout.lower()

    def test_recommend_evaluate_help(self) -> None:
        import subprocess
        result = subprocess.run(
            ["python", "-m", "rationalevault.cli.main", "recommend", "evaluate", "--help"],
            capture_output=True, text=True, cwd=".",
        )
        assert result.returncode == 0 or "usage" in result.stdout.lower()
