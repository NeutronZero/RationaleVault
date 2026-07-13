"""Tests for Replay domain value objects (ReplayScope, ReplayMode, ReplayBoundary, Understanding, ReplayResult)."""

from __future__ import annotations

import pytest

from rationalevault.replay.types import (
    ReplayBoundary,
    ReplayMode,
    ReplayReport,
    ReplayResult,
    ReplayScope,
    Understanding,
)


class TestReplayBoundary:
    def test_holds_global_order(self):
        b = ReplayBoundary(42)
        assert b.global_order == 42

    def test_immutable(self):
        b = ReplayBoundary(1)
        with pytest.raises(AttributeError):
            b.global_order = 2

    def test_equality(self):
        assert ReplayBoundary(5) == ReplayBoundary(5)
        assert ReplayBoundary(5) != ReplayBoundary(6)

    def test_ordering(self):
        assert ReplayBoundary(1) < ReplayBoundary(2)
        assert ReplayBoundary(10) > ReplayBoundary(5)

    def test_hashable(self):
        s = {ReplayBoundary(1), ReplayBoundary(1), ReplayBoundary(2)}
        assert len(s) == 2

    def test_negative_boundary_raises(self):
        with pytest.raises(ValueError, match="must be non-negative"):
            ReplayBoundary(-1)

    def test_zero_is_valid(self):
        b = ReplayBoundary(0)
        assert b.global_order == 0


class TestReplayScope:
    def test_default_global(self):
        scope = ReplayScope()
        assert scope.kind == "global"
        assert scope.stream_id is None

    def test_global_explicit(self):
        scope = ReplayScope("global")
        assert scope.kind == "global"

    def test_stream_requires_stream_id(self):
        scope = ReplayScope("stream", "my-stream")
        assert scope.kind == "stream"
        assert scope.stream_id == "my-stream"

    def test_immutable(self):
        scope = ReplayScope()
        with pytest.raises(AttributeError):
            scope.kind = "stream"

    def test_equality(self):
        assert ReplayScope("global") == ReplayScope("global")
        assert ReplayScope("stream", "a") == ReplayScope("stream", "a")
        assert ReplayScope("global") != ReplayScope("stream", "a")

    def test_invalid_kind_raises(self):
        with pytest.raises(ValueError, match="must be 'global' or 'stream'"):
            ReplayScope("invalid")

    def test_global_with_stream_id_raises(self):
        with pytest.raises(ValueError, match="global scope must have stream_id=None"):
            ReplayScope("global", "extra-id")

    def test_stream_without_stream_id_raises(self):
        with pytest.raises(ValueError, match="stream scope requires a stream_id"):
            ReplayScope("stream")


class TestReplayMode:
    def test_default_auto(self):
        mode = ReplayMode()
        assert mode.value == "auto"

    def test_valid_modes(self):
        for v in ("auto", "full", "delta", "fast_path"):
            mode = ReplayMode(v)
            assert mode.value == v

    def test_immutable(self):
        mode = ReplayMode()
        with pytest.raises(AttributeError):
            mode.value = "full"

    def test_equality(self):
        assert ReplayMode("auto") == ReplayMode("auto")
        assert ReplayMode("full") != ReplayMode("delta")

    def test_invalid_mode_raises(self):
        with pytest.raises(ValueError, match="must be one of"):
            ReplayMode("invalid")


class TestUnderstanding:
    def test_stores_projections(self):
        u = Understanding(projections={"mem": {"count": 1}}, boundary=ReplayBoundary(5))
        assert u.projections == {"mem": {"count": 1}}
        assert u.boundary == ReplayBoundary(5)

    def test_empty_projections(self):
        u = Understanding(projections={}, boundary=ReplayBoundary(0))
        assert u.projections == {}

    def test_immutable(self):
        u = Understanding(projections={}, boundary=ReplayBoundary(0))
        with pytest.raises(AttributeError):
            u.projections = {"x": 1}

    def test_equality_structural(self):
        a = Understanding(projections={"p": 1}, boundary=ReplayBoundary(3))
        b = Understanding(projections={"p": 1}, boundary=ReplayBoundary(3))
        assert a == b

    def test_inequality(self):
        a = Understanding(projections={"p": 1}, boundary=ReplayBoundary(3))
        b = Understanding(projections={"p": 2}, boundary=ReplayBoundary(3))
        assert a != b


class TestReplayReport:
    def test_stores_fields(self):
        r = ReplayReport(
            mode="full",
            events_processed=10,
            snapshot_used=False,
            replay_position=ReplayBoundary(10),
            version=1,
        )
        assert r.mode == "full"
        assert r.events_processed == 10
        assert not r.snapshot_used
        assert r.replay_position == ReplayBoundary(10)
        assert r.version == 1

    def test_immutable(self):
        r = ReplayReport(
            mode="auto", events_processed=0, snapshot_used=False,
            replay_position=ReplayBoundary(0), version=1,
        )
        with pytest.raises(AttributeError):
            r.mode = "full"


class TestReplayResult:
    def test_packages_understanding(self):
        u = Understanding(projections={"p": {}}, boundary=ReplayBoundary(5))
        report = ReplayReport(
            mode="full", events_processed=0, snapshot_used=False,
            replay_position=ReplayBoundary(5), version=1,
        )
        result = ReplayResult(
            understanding=u,
            report=report,
            version=1,
            replay_boundary=ReplayBoundary(5),
        )
        assert result.understanding is u
        assert result.report is report
        assert result.version == 1
        assert result.replay_boundary == ReplayBoundary(5)

    def test_immutable(self):
        u = Understanding(projections={}, boundary=ReplayBoundary(0))
        report = ReplayReport(
            mode="auto", events_processed=0, snapshot_used=False,
            replay_position=ReplayBoundary(0), version=1,
        )
        result = ReplayResult(
            understanding=u, report=report,
            version=1, replay_boundary=ReplayBoundary(0),
        )
        with pytest.raises(AttributeError):
            result.version = 2

    def test_equality_structural(self):
        u = Understanding(projections={}, boundary=ReplayBoundary(0))
        report = ReplayReport(
            mode="auto", events_processed=0, snapshot_used=False,
            replay_position=ReplayBoundary(0), version=1,
        )
        a = ReplayResult(
            understanding=u, report=report,
            version=1, replay_boundary=ReplayBoundary(0),
        )
        b = ReplayResult(
            understanding=u, report=report,
            version=1, replay_boundary=ReplayBoundary(0),
        )
        assert a == b
