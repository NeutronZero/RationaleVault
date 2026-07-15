"""Constitutional invariant tests for the Replay Engine (I-01 through I-12).

These tests verify that the core constitutional invariants hold
regardless of Ledger state, Projection configuration, or Replay mode.
"""

from __future__ import annotations

import copy

import pytest

from rationalevault.canonical.envelope import CanonicalEnvelope
from rationalevault.canonical.payload import CanonicalPayload
from rationalevault.canonical.timestamp import CanonicalTimestamp
from rationalevault.canonical.types import EventType
from rationalevault.ledger.commit import CommitBuilder
from rationalevault.ledger.storage.memory import MemoryLedger
from rationalevault.replay.engine.default import DefaultReplayer
from rationalevault.replay.registry import ProjectionRegistry
from rationalevault.replay.types import ReplayBoundary, ReplayMode, ReplayScope


def make_event(
    event_type: str = "decision_recorded",
    stream_id: str = "s",
    sequence: int = 1,
    payload: dict | None = None,
) -> CanonicalEnvelope:
    return CanonicalEnvelope(
        rvcj_version=1,
        event_schema_version=1,
        experience_id="exp-inv",
        event_type=EventType(event_type),
        stream_id=stream_id,
        sequence=sequence,
        timestamp=CanonicalTimestamp.from_iso8601("2026-07-14T00:00:00.000Z"),
        actor="invariant-test",
        payload=CanonicalPayload(payload or {"v": 1}),
    )


def populated_ledger() -> MemoryLedger:
    ledger = MemoryLedger()
    c1 = CommitBuilder.from_events("s", [make_event(payload={"v": 1}, sequence=1)])
    ledger.append(c1)
    c2 = CommitBuilder.from_events("s", [make_event(payload={"v": 2}, sequence=2)])
    ledger.append(c2)
    c3 = CommitBuilder.from_events("s", [make_event(payload={"v": 3}, sequence=3)])
    ledger.append(c3)
    return ledger


def two_stream_ledger() -> MemoryLedger:
    ledger = MemoryLedger()
    c1 = CommitBuilder.from_events("a", [make_event(stream_id="a", payload={"v": 1}, sequence=1)])
    ledger.append(c1)
    c2 = CommitBuilder.from_events("b", [make_event(stream_id="b", payload={"v": 2}, sequence=1)])
    ledger.append(c2)
    c3 = CommitBuilder.from_events("a", [make_event(stream_id="a", payload={"v": 3}, sequence=2)])
    ledger.append(c3)
    return ledger


def counter_reducer(state: dict, event: dict) -> dict:
    return {**state, "count": state.get("count", 0) + 1, "last_v": event.get("payload", {}).get("v")}


def make_registry() -> ProjectionRegistry:
    r = ProjectionRegistry()
    r.register("counter", counter_reducer)
    return r


# ---------------------------------------------------------------------------
# I-01: Replay Determinism
# Same Ledger + same Projections → same Understanding
# ---------------------------------------------------------------------------

class TestI01ReplayDeterminism:
    def test_same_ledger_produces_identical_understanding(self):
        ledger = populated_ledger()
        r = make_registry()
        replayer = DefaultReplayer(r)

        result1 = replayer.replay(ledger)
        result2 = replayer.replay(ledger)

        assert result1.understanding == result2.understanding

    def test_empty_ledger_deterministic(self):
        ledger = MemoryLedger()
        r = make_registry()
        replayer = DefaultReplayer(r)

        r1 = replayer.replay(ledger)
        r2 = replayer.replay(ledger)

        assert r1.understanding == r2.understanding

    def test_replay_to_deterministic(self):
        ledger = populated_ledger()
        r = make_registry()
        replayer = DefaultReplayer(r)

        r1 = replayer.replay_to(ledger, ReplayBoundary(1))
        r2 = replayer.replay_to(ledger, ReplayBoundary(1))

        assert r1.understanding == r2.understanding

    def test_replay_stream_deterministic(self):
        ledger = two_stream_ledger()
        r = make_registry()
        replayer = DefaultReplayer(r)

        r1 = replayer.replay_stream(ledger, "a")
        r2 = replayer.replay_stream(ledger, "a")

        assert r1.understanding == r2.understanding

    def test_different_mode_same_understanding(self):
        ledger = populated_ledger()
        r = make_registry()
        replayer = DefaultReplayer(r)

        r_auto = replayer.replay(ledger, mode=ReplayMode("auto"))
        r_full = replayer.replay(ledger, mode=ReplayMode("full"))

        assert r_auto.understanding == r_full.understanding


# ---------------------------------------------------------------------------
# I-01a: Replay Completeness
# Every event in scope is presented to every registered Reducer
# ---------------------------------------------------------------------------

class TestI01aReplayCompleteness:
    def test_all_events_reach_reducer(self):
        ledger = populated_ledger()
        seen = []

        def tracking(state, event):
            seen.append(event["event_type"])
            return {**state, "count": state.get("count", 0) + 1}

        r = ProjectionRegistry()
        r.register("tracker", tracking)
        replayer = DefaultReplayer(r)
        replayer.replay(ledger)

        assert len(seen) == 3

    def test_each_reducer_receives_all_events(self):
        ledger = populated_ledger()
        seen_a = []
        seen_b = []

        def tracker_a(state, event):
            seen_a.append(event["event_type"])
            return {**state, "count": state.get("count", 0) + 1}

        def tracker_b(state, event):
            seen_b.append(event["event_type"])
            return {**state, "count": state.get("count", 0) + 1}

        r = ProjectionRegistry()
        r.register("a", tracker_a)
        r.register("b", tracker_b)
        replayer = DefaultReplayer(r)
        replayer.replay(ledger)

        assert seen_a == seen_b
        assert len(seen_a) == 3

    def test_stream_scope_completeness(self):
        ledger = two_stream_ledger()
        seen = []

        def tracking(state, event):
            seen.append(event["stream_id"])
            return {**state, "count": state.get("count", 0) + 1}

        r = ProjectionRegistry()
        r.register("tracker", tracking)
        replayer = DefaultReplayer(r)
        replayer.replay_stream(ledger, "a")

        assert seen == ["a", "a"]

    def test_empty_scope_produces_zero_events(self):
        ledger = MemoryLedger()
        seen = []

        def tracking(state, event):
            seen.append(event)
            return state

        r = ProjectionRegistry()
        r.register("tracker", tracking)
        replayer = DefaultReplayer(r)
        result = replayer.replay(ledger)

        assert len(seen) == 0
        assert result.report.events_processed == 0

    def test_events_in_global_order(self):
        ledger = two_stream_ledger()
        orders = []

        def tracking(state, event):
            orders.append(event["global_order"])
            return {**state, "count": state.get("count", 0) + 1}

        r = ProjectionRegistry()
        r.register("tracker", tracking)
        replayer = DefaultReplayer(r)
        replayer.replay(ledger)

        assert orders == sorted(orders)


# ---------------------------------------------------------------------------
# I-07: Replay Equivalence — Full ≡ Delta ≡ Fast Path
# Requires snapshot infrastructure — skipped for now.
# ---------------------------------------------------------------------------

class TestI07ReplayEquivalence:
    def test_full_and_auto_are_equivalent(self):
        ledger = populated_ledger()
        r = make_registry()
        replayer = DefaultReplayer(r)

        r_full = replayer.replay(ledger, mode=ReplayMode("full"))
        r_auto = replayer.replay(ledger, mode=ReplayMode("auto"))

        assert r_full.understanding == r_auto.understanding

    def test_delta_skipped_requires_snapshot(self):
        pytest.skip("Delta replay requires SnapshotManager — not yet implemented")

    def test_fast_path_skipped_requires_fast_path(self):
        pytest.skip("Fast path requires FastPathReplayEngine — not yet implemented")


# ---------------------------------------------------------------------------
# I-08: Referential Transparency
# Canonical identifiers are deterministic — same input → same id
# ---------------------------------------------------------------------------

class TestI08ReferentialTransparency:
    def test_commit_id_deterministic(self):
        e1 = make_event(payload={"v": 1})
        e2 = make_event(payload={"v": 1})
        c1 = CommitBuilder.from_events("s", [e1])
        c2 = CommitBuilder.from_events("s", [e2])
        assert c1.commit_id == c2.commit_id

    def test_different_payload_different_commit_id(self):
        e1 = make_event(payload={"v": 1})
        e2 = make_event(payload={"v": 2})
        c1 = CommitBuilder.from_events("s", [e1])
        c2 = CommitBuilder.from_events("s", [e2])
        assert c1.commit_id != c2.commit_id

    def test_understanding_deterministic_across_replays(self):
        ledger = populated_ledger()
        r = make_registry()
        replayer = DefaultReplayer(r)

        understandings = [replayer.replay(ledger).understanding for _ in range(5)]
        for i in range(1, len(understandings)):
            assert understandings[i] == understandings[0]


# ---------------------------------------------------------------------------
# I-09: Projection Monotonicity
# Projections are composable and isolated — running separately and composing
# gives the same result as running together.
# ---------------------------------------------------------------------------

class TestI09ProjectionMonotonicity:
    def test_projections_are_isolated(self):
        ledger = populated_ledger()

        def counter(state, event):
            return {**state, "count": state.get("count", 0) + 1}

        def sum_v(state, event):
            v = event.get("payload", {}).get("v", 0)
            return {**state, "total": state.get("total", 0) + v}

        r_both = ProjectionRegistry()
        r_both.register("counter", counter)
        r_both.register("sum_v", sum_v)

        r_counter_only = ProjectionRegistry()
        r_counter_only.register("counter", counter)

        r_sum_only = ProjectionRegistry()
        r_sum_only.register("sum_v", sum_v)

        replayer = DefaultReplayer(r_both)
        result_both = replayer.replay(ledger)

        replayer_counter = DefaultReplayer(r_counter_only)
        result_counter = replayer_counter.replay(ledger)

        replayer_sum = DefaultReplayer(r_sum_only)
        result_sum = replayer_sum.replay(ledger)

        assert result_both.understanding.projections["counter"] == result_counter.understanding.projections["counter"]
        assert result_both.understanding.projections["sum_v"] == result_sum.understanding.projections["sum_v"]

    def test_registration_order_does_not_affect_result(self):
        ledger = MemoryLedger()
        c = CommitBuilder.from_events("s", [make_event(payload={"x": 10}, sequence=1)])
        ledger.append(c)

        def a(state, event):
            return {**state, "val": event.get("payload", {}).get("x", 0)}

        def b(state, event):
            return {**state, "seen": True}

        r_ab = ProjectionRegistry()
        r_ab.register("a", a)
        r_ab.register("b", b)

        r_ba = ProjectionRegistry()
        r_ba.register("b", b)
        r_ba.register("a", a)

        replayer_ab = DefaultReplayer(r_ab)
        replayer_ba = DefaultReplayer(r_ba)

        u_ab = replayer_ab.replay(ledger).understanding
        u_ba = replayer_ba.replay(ledger).understanding

        assert u_ab.projections["a"] == u_ba.projections["a"]
        assert u_ab.projections["b"] == u_ba.projections["b"]

    def test_empty_registry_is_valid(self):
        ledger = populated_ledger()
        r = ProjectionRegistry()
        replayer = DefaultReplayer(r)
        result = replayer.replay(ledger)
        assert result.understanding.projections == {}
        assert result.understanding.boundary == ReplayBoundary(2)


# ---------------------------------------------------------------------------
# I-11: Ledger Completeness
# All events committed to the Ledger are presented during Replay.
# ---------------------------------------------------------------------------

class TestI11LedgerCompleteness:
    def test_global_replay_sees_all_events(self):
        ledger = populated_ledger()
        r = make_registry()
        replayer = DefaultReplayer(r)
        result = replayer.replay(ledger)
        assert result.report.events_processed == 3

    def test_stream_replay_sees_only_stream_events(self):
        ledger = two_stream_ledger()
        r = make_registry()
        replayer = DefaultReplayer(r)

        global_result = replayer.replay(ledger)
        stream_a = replayer.replay_stream(ledger, "a")
        stream_b = replayer.replay_stream(ledger, "b")

        assert global_result.report.events_processed == 3
        assert stream_a.report.events_processed == 2
        assert stream_b.report.events_processed == 1

    def test_replay_to_limited_boundary(self):
        ledger = populated_ledger()
        r = make_registry()
        replayer = DefaultReplayer(r)

        result = replayer.replay_to(ledger, ReplayBoundary(0))
        assert result.report.events_processed == 1

        result = replayer.replay_to(ledger, ReplayBoundary(1))
        assert result.report.events_processed == 2

    def test_boundary_matches_ledger_head(self):
        ledger = populated_ledger()
        r = make_registry()
        replayer = DefaultReplayer(r)
        result = replayer.replay(ledger)
        assert result.replay_boundary == ReplayBoundary(2)

    def test_replay_after_more_commits(self):
        ledger = populated_ledger()
        r = make_registry()
        replayer = DefaultReplayer(r)

        result_before = replayer.replay(ledger)
        assert result_before.report.events_processed == 3

        c4 = CommitBuilder.from_events("s", [make_event(payload={"v": 4}, sequence=4)])
        ledger.append(c4)

        result_after = replayer.replay(ledger)
        assert result_after.report.events_processed == 4
        assert result_after.replay_boundary == ReplayBoundary(3)


# ---------------------------------------------------------------------------
# I-12: Reducer Purity
# Reducers MUST NOT mutate their inputs or have observable side effects.
# ---------------------------------------------------------------------------

class TestI12ReducerPurity:
    def test_pure_reducer_preserves_inputs(self):
        ledger = MemoryLedger()
        c = CommitBuilder.from_events("s", [make_event(payload={"v": 1}, sequence=1)])
        ledger.append(c)

        def pure(state, event):
            return {**state, "count": state.get("count", 0) + 1}

        from rationalevault.replay.reducer import verify_purity

        r = ProjectionRegistry()
        r.register("counter", verify_purity(pure))
        replayer = DefaultReplayer(r)
        result = replayer.replay(ledger)

        assert result.understanding.projections["counter"]["count"] == 1

    def test_impure_mutates_state_detected_at_runtime(self):
        ledger = MemoryLedger()
        c = CommitBuilder.from_events("s", [make_event(payload={"v": 1}, sequence=1)])
        ledger.append(c)

        def impure(state, event):
            state["tampered"] = True
            return state

        from rationalevault.replay.errors import PurityViolationError
        from rationalevault.replay.reducer import verify_purity

        r = ProjectionRegistry()
        r.register("counter", verify_purity(impure))
        replayer = DefaultReplayer(r)

        with pytest.raises(PurityViolationError):
            replayer.replay(ledger)

    def test_impure_mutates_event_detected_at_runtime(self):
        ledger = MemoryLedger()
        c = CommitBuilder.from_events("s", [make_event(payload={"v": 1}, sequence=1)])
        ledger.append(c)

        def impure(state, event):
            event["payload"]["tampered"] = True
            return state

        from rationalevault.replay.errors import PurityViolationError
        from rationalevault.replay.reducer import verify_purity

        r = ProjectionRegistry()
        r.register("counter", verify_purity(impure))
        replayer = DefaultReplayer(r)

        with pytest.raises(PurityViolationError):
            replayer.replay(ledger)

    def test_unknown_event_type_does_not_crash(self):
        ledger = MemoryLedger()
        e = make_event(event_type="evaluation_recorded", payload={"v": 99}, sequence=1)
        c = CommitBuilder.from_events("s", [e])
        ledger.append(c)

        def fragile(state, event):
            payload = event["payload"]
            return {**state, "v": payload["v"]}

        r = ProjectionRegistry()
        r.register("fragile", fragile)
        replayer = DefaultReplayer(r)
        result = replayer.replay(ledger)

        assert result.understanding.projections["fragile"]["v"] == 99

    def test_deterministic_across_calls(self):
        ledger = populated_ledger()
        r = make_registry()
        replayer = DefaultReplayer(r)

        r1 = replayer.replay(ledger)
        r2 = replayer.replay(ledger)

        assert r1 == r2
