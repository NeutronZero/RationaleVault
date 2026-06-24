"""Tests for I12.D — CLI and MCP Exposure."""
from __future__ import annotations

import json

import pytest

from rationalevault.mcp.tools import build_retrieval_plan


class TestMCPRetrievalPlan:
    def test_basic_plan(self) -> None:
        result = build_retrieval_plan("continue sprint 34")
        assert result["primary_intent"] == "continuation"
        assert result["confidence"] > 0
        assert isinstance(result["projections"], dict)

    def test_knowledge_plan(self) -> None:
        result = build_retrieval_plan("what knowledge principle governs this")
        assert result["primary_intent"] == "knowledge_query"

    def test_cross_project_plan(self) -> None:
        result = build_retrieval_plan("what knowledge is shared across projects")
        assert "cross_project" in [i["primary_intent"] for i in [{"primary_intent": result["primary_intent"]}]]

    def test_plan_deterministic(self) -> None:
        r1 = build_retrieval_plan("continue sprint 34")
        r2 = build_retrieval_plan("continue sprint 34")
        assert r1["primary_intent"] == r2["primary_intent"]
        assert r1["projections"] == r2["projections"]

    def test_plan_serializable(self) -> None:
        result = build_retrieval_plan("continue sprint 34")
        serialized = json.dumps(result)
        parsed = json.loads(serialized)
        assert parsed["primary_intent"] == "continuation"


class TestCLIIntegration:
    def test_cli_retrieval_plan_help(self) -> None:
        import subprocess
        result = subprocess.run(
            ["python", "-m", "rationalevault.cli.main", "retrieval", "plan", "--help"],
            capture_output=True, text=True, cwd=".",
        )
        assert result.returncode == 0 or "usage" in result.stdout.lower() or "help" in result.stdout.lower()

    def test_cli_retrieval_evaluate_help(self) -> None:
        import subprocess
        result = subprocess.run(
            ["python", "-m", "rationalevault.cli.main", "retrieval", "evaluate", "--help"],
            capture_output=True, text=True, cwd=".",
        )
        assert result.returncode == 0 or "usage" in result.stdout.lower() or "help" in result.stdout.lower()
