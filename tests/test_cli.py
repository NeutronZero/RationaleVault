"""Tests for rationalevault CLI entry point."""
from __future__ import annotations

import sys
from io import StringIO
from unittest.mock import patch

import pytest


class TestCliMain:
    def test_main_help_exits_cleanly(self) -> None:
        """CLI --help should exit 0."""
        with patch("sys.argv", ["rationalevault", "--help"]):
            with pytest.raises(SystemExit) as exc_info:
                from rationalevault.cli.main import main
                main()
            assert exc_info.value.code == 0

    def test_main_no_args_shows_usage(self) -> None:
        """CLI with no args should show usage and exit with error code."""
        captured = StringIO()
        with patch("sys.argv", ["rationalevault"]):
            with patch("sys.stderr", captured):
                with pytest.raises(SystemExit) as exc_info:
                    from rationalevault.cli.main import main
                    main()
                assert exc_info.value.code == 2
                output = captured.getvalue()
                assert "usage:" in output
