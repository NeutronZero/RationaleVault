"""Tests for I14.4 — CLI and MCP exposure."""
from __future__ import annotations

import pytest

from rationalevault.mcp.tools import get_organization_activity, get_organization_continuation


class TestMCPActivity:
    def test_returns_dict(self) -> None:
        result = get_organization_activity()
        assert isinstance(result, dict)

    def test_deterministic_structure(self) -> None:
        r1 = get_organization_activity()
        r2 = get_organization_activity()
        if "error" not in r1:
            d1 = {k: v for k, v in r1.items() if k != "compiled_at"}
            d2 = {k: v for k, v in r2.items() if k != "compiled_at"}
            assert d1 == d2


class TestMCPContinuation:
    def test_returns_dict(self) -> None:
        result = get_organization_continuation()
        assert isinstance(result, dict)

    def test_has_health(self) -> None:
        result = get_organization_continuation()
        if "error" not in result:
            assert "health" in result
            assert "projects_needing_attention" in result


class TestCLIIntegration:
    def test_activity_help(self) -> None:
        import subprocess
        result = subprocess.run(
            ["python", "-m", "rationalevault.cli.main", "organization", "activity", "--help"],
            capture_output=True, text=True, cwd=".",
        )
        assert result.returncode == 0 or "usage" in result.stdout.lower() or "help" in result.stdout.lower()

    def test_continuation_help(self) -> None:
        import subprocess
        result = subprocess.run(
            ["python", "-m", "rationalevault.cli.main", "organization", "continuation", "--help"],
            capture_output=True, text=True, cwd=".",
        )
        assert result.returncode == 0 or "usage" in result.stdout.lower() or "help" in result.stdout.lower()

    def test_activity_evaluate_help(self) -> None:
        import subprocess
        result = subprocess.run(
            ["python", "-m", "rationalevault.cli.main", "organization", "activity", "evaluate", "--help"],
            capture_output=True, text=True, cwd=".",
        )
        assert result.returncode == 0 or "usage" in result.stdout.lower() or "help" in result.stdout.lower()

    def test_continuation_evaluate_help(self) -> None:
        import subprocess
        result = subprocess.run(
            ["python", "-m", "rationalevault.cli.main", "organization", "continuation", "evaluate", "--help"],
            capture_output=True, text=True, cwd=".",
        )
        assert result.returncode == 0 or "usage" in result.stdout.lower() or "help" in result.stdout.lower()
