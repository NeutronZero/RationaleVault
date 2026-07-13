"""Tests for DefaultReplayer — the reference ReplayEngine implementation."""

from __future__ import annotations

import pytest

from rationalevault.canonical.envelope import CanonicalEnvelope
from rationalevault.canonical.payload import CanonicalPayload
from rationalevault.canonical.timestamp import CanonicalTimestamp
from rationalevault.canonical.types import EventType
from rationalevault.ledger.commit import CommitBuilder
from rationalevault.ledger.storage.memory import MemoryLedger
from rationalevault.replay.engine.default import DefaultReplayer
from rationalevault.replay.interface import ReplayEngine
from rationalevault.replay.registry import ProjectionRegistry
from rationalevault.replay.types import ReplayBoundary, ReplayMode, ReplayScope, Understanding


def make_event(
    event_type: str = "decision_recorded",
    stream_id: str = "test-stream",
    sequence: int = 1,
    payload: dict | None = None,
) -> CanonicalEnvelope:
    return CanonicalEnvelope(
        rvcj_version=1,
        event_schema_version=1,
        experience_id="exp-1",
        event_type=EventType(event_type),
        stream_id=stream_id,
        sequence=sequence,
        timestamp=CanonicalTimestamp.from_iso8601("2026-07-14T00:00:00.000Z"),
        actor="test-actor",
        payload=CanonicalPayload(payload or {"value": 1}),
    )


@pytest.fixture
def ledger_with_events():
    """A MemoryLedger with 3 events across 2 commits in one stream."""
    ledger = MemoryLedger()

    commit1 = CommitBuilder.from_events("stats", [make_event(payload={"value": 1})])
    ledger.append(commit1)

    commit2 = CommitBuilder.from_events("stats", [
        make_event(payload={"value": 2}, sequence=2),
        make_event(payload={"value": 3}, sequence=3),
    ])
    ledger.append(commit2)

    return ledger


@pytest.fixture
def ledger_two_streams():
    """A MemoryLedger with events in two different streams."""
    ledger = MemoryLedger()

    c1 = CommitBuilder.from_events("stream-a", [
        make_event(stream_id="stream-a", payload={"msg": "a1"}, sequence=1),
    ])
    ledger.append(c1)

    c2 = CommitBuilder.from_events("stream-b", [
        make_event(stream_id="stream-b", payload={"msg": "b1"}, sequence=1),
    ])
    ledger.append(c2)

    c3 = CommitBuilder.from_events("stream-a", [
        make_event(stream_id="stream-a", payload={"msg": "a2"}, sequence=2),
    ])
    ledger.append(c3)

    return ledger


@pytest.fixture
def counter_reducer():
    """Reducer that counts events and tracks the last payload value."""
    def counter(state, event):
        state["count"] = state.get("count", 0) + 1
        state["last_value"] = event["payload"]["value"]
        return state
    return counter


@pytest.fixture
def event_type_reducer():
    """Reducer that tracks event types seen."""
    def tracker(state, event):
        types = state.get("types", [])
        types.append(event["event_type"])
        state["types"] = types
        return state
    return tracker


@pytest.fixture
def registry(counter_reducer, event_type_reducer):
    r = ProjectionRegistry()
    r.register("counter", counter_reducer)
    r.register("type_tracker", event_type_reducer)
    return r


@pytest.fixture
def replayer(registry):
    return DefaultReplayer(registry)


class TestDefaultReplayerIsReplayEngine:
    def test_implements_abc(self, replayer):
        assert isinstance(replayer, ReplayEngine)

    def test_has_replay_method(self, replayer):
        assert callable(replayer.replay)

    def test_has_replay_to_method(self, replayer):
        assert callable(replayer.replay_to)

    def test_has_replay_stream_method(self, replayer):
        assert callable(replayer.replay_stream)


class TestDefaultReplayerContract:
    """Contract tests: replay produces correct ReplayResult structures."""

    def test_replay_returns_replay_result(self, replayer, ledger_with_events):
        result = replayer.replay(ledger_with_events)
        assert result.report.events_processed == 3
        assert result.replay_boundary == ReplayBoundary(1)

    def test_replay_produces_understanding(self, replayer, ledger_with_events):
        result = replayer.replay(ledger_with_events)
        u = result.understanding
        assert isinstance(u, Understanding)
        assert u.boundary == ReplayBoundary(1)
        assert "counter" in u.projections
        assert "type_tracker" in u.projections

    def test_counter_reducer_counts_all_events(self, replayer, ledger_with_events):
        result = replayer.replay(ledger_with_events)
        assert result.understanding.projections["counter"]["count"] == 3

    def test_replay_boundary_matches_max_global_order(self, replayer, ledger_with_events):
        result = replayer.replay(ledger_with_events)
        assert result.replay_boundary == ReplayBoundary(1)

    def test_empty_ledger_returns_empty_understanding(self):
        ledger = MemoryLedger()
        r = ProjectionRegistry()
        r.register("counter", lambda s, e: {**s, "count": s.get("count", 0) + 1})
        replayer = DefaultReplayer(r)
        result = replayer.replay(ledger)
        assert result.understanding.projections == {"counter": {}}
        assert result.understanding.boundary == ReplayBoundary(0)
        assert result.report.events_processed == 0

    def test_replay_without_projections_skips_reducers(self):
        ledger = MemoryLedger()
        c1 = CommitBuilder.from_events("s", [make_event()])
        ledger.append(c1)
        registry = ProjectionRegistry()
        replayer = DefaultReplayer(registry)
        result = replayer.replay(ledger)
        assert result.understanding.projections == {}
        assert result.report.events_processed == 1


class TestDefaultReplayerProjectionDeterminism:
    """Reducers are applied in projection registration order."""

    def test_reducer_order_matches_registration(self):
        ledger = MemoryLedger()
        c1 = CommitBuilder.from_events("s", [make_event(payload={"val": 42})])
        ledger.append(c1)

        r = ProjectionRegistry()
        order = []

        def first(state, event):
            order.append("first")
            return state

        def second(state, event):
            order.append("second")
            return state

        def third(state, event):
            order.append("third")
            return state

        r.register("a", first)
        r.register("b", second)
        r.register("c", third)

        replayer = DefaultReplayer(r)
        replayer.replay(ledger)
        assert order == ["first", "second", "third"]

    def test_projections_receive_events_in_global_order(self):
        ledger = MemoryLedger()
        c1 = CommitBuilder.from_events("s", [make_event(payload={"seq": 1}, sequence=1)])
        ledger.append(c1)
        c2 = CommitBuilder.from_events("s", [make_event(payload={"seq": 2}, sequence=2)])
        ledger.append(c2)
        c3 = CommitBuilder.from_events("s", [make_event(payload={"seq": 3}, sequence=3)])
        ledger.append(c3)

        r = ProjectionRegistry()
        seen = []

        def tracker(state, event):
            seen.append(event["payload"]["seq"])
            return state

        r.register("t", tracker)
        replayer = DefaultReplayer(r)
        replayer.replay(ledger)
        assert seen == [1, 2, 3]


class TestDefaultReplayerScope:
    """ReplayScope filtering behavior."""

    def test_global_scope_includes_all_streams(self, ledger_two_streams):
        r = ProjectionRegistry()
        r.register("counter", lambda s, e: {**s, "count": s.get("count", 0) + 1})
        replayer = DefaultReplayer(r)
        result = replayer.replay(ledger_two_streams, scope=ReplayScope("global"))
        assert result.report.events_processed == 3
        assert result.understanding.projections["counter"]["count"] == 3

    def test_stream_scope_filters_by_stream(self, ledger_two_streams):
        r = ProjectionRegistry()
        r.register("counter", lambda s, e: {**s, "count": s.get("count", 0) + 1})
        replayer = DefaultReplayer(r)
        result = replayer.replay(
            ledger_two_streams, scope=ReplayScope("stream", "stream-a")
        )
        assert result.report.events_processed == 2
        assert result.understanding.projections["counter"]["count"] == 2


class TestDefaultReplayerReplayTo:
    """replay_to replays up to a specific boundary."""

    def test_replay_to_boundary_includes_up_to(self, ledger_with_events):
        r = ProjectionRegistry()
        r.register("counter", lambda s, e: {**s, "count": s.get("count", 0) + 1})
        replayer = DefaultReplayer(r)
        result = replayer.replay_to(ledger_with_events, ReplayBoundary(0))
        assert result.report.events_processed == 1
        assert result.replay_boundary == ReplayBoundary(0)
        assert result.understanding.projections["counter"]["count"] == 1

    def test_replay_to_past_end_returns_all(self, ledger_with_events):
        r = ProjectionRegistry()
        r.register("counter", lambda s, e: {**s, "count": s.get("count", 0) + 1})
        replayer = DefaultReplayer(r)
        result = replayer.replay_to(ledger_with_events, ReplayBoundary(99))
        assert result.report.events_processed == 3

    def test_replay_to_zero_returns_empty(self):
        ledger = MemoryLedger()
        r = ProjectionRegistry()
        r.register("counter", lambda s, e: {**s, "count": s.get("count", 0) + 1})
        replayer = DefaultReplayer(r)
        result = replayer.replay_to(ledger, ReplayBoundary(0))
        assert result.report.events_processed == 0
        assert result.replay_boundary == ReplayBoundary(0)


class TestDefaultReplayerReplayStream:
    """replay_stream is a convenience wrapper for stream scope."""

    def test_replay_stream_filters_by_stream(self, ledger_two_streams):
        r = ProjectionRegistry()
        r.register("counter", lambda s, e: {**s, "count": s.get("count", 0) + 1})
        replayer = DefaultReplayer(r)
        result = replayer.replay_stream(ledger_two_streams, "stream-b")
        assert result.report.events_processed == 1
        assert result.understanding.projections["counter"]["count"] == 1


class TestDefaultReplayerReports:
    """ReplayReport correctness."""

    def test_report_matches_mode(self, replayer, ledger_with_events):
        result = replayer.replay(ledger_with_events, mode=ReplayMode("full"))
        assert result.report.mode == "full"

    def test_report_replay_position_matches_boundary(self, replayer, ledger_with_events):
        result = replayer.replay(ledger_with_events)
        assert result.report.replay_position == result.replay_boundary

    def test_report_snapshot_used_false_by_default(self, replayer, ledger_with_events):
        result = replayer.replay(ledger_with_events)
        assert not result.report.snapshot_used

    def test_report_version_present(self, replayer, ledger_with_events):
        result = replayer.replay(ledger_with_events)
        assert result.report.version == 1
