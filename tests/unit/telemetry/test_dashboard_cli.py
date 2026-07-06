"""Tests for the retrieval dashboard CLI command."""
from __future__ import annotations

import subprocess
import sys

import pytest


class TestRetrievalDashboardCLI:
    def test_dashboard_shows_header(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "rationalevault.cli.main", "retrieval-dashboard"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        assert "Retrieval Dashboard" in result.stdout or "retrieval" in result.stdout.lower()

    def test_dashboard_empty_state(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "rationalevault.cli.main", "retrieval-dashboard"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert "No requests recorded" in result.stdout or "0" in result.stdout
