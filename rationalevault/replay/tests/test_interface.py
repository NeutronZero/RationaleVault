"""Tests for ReplayEngine ABC — verifies the abstract contract cannot be instantiated directly."""

from __future__ import annotations

import pytest

from rationalevault.replay.interface import ReplayEngine


class TestReplayEngineABC:
    def test_cannot_instantiate_abc(self):
        with pytest.raises(TypeError, match="abstract"):
            ReplayEngine()  # type: ignore[abstract]

    def test_abc_has_replay_method(self):
        assert hasattr(ReplayEngine, "replay")

    def test_abc_has_replay_to_method(self):
        assert hasattr(ReplayEngine, "replay_to")

    def test_abc_has_replay_stream_method(self):
        assert hasattr(ReplayEngine, "replay_stream")

    def test_methods_are_abstract(self):
        for name in ("replay", "replay_to", "replay_stream"):
            method = getattr(ReplayEngine, name)
            assert getattr(method, "__isabstractmethod__", False)
