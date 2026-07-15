"""Tests for Reducer Protocol, purity enforcement, and determinism (I-12)."""

from __future__ import annotations

import pytest

from rationalevault.replay.errors import PurityViolationError
from rationalevault.replay.reducer import (
    Reducer,
    ReducerFunc,
    ignore_unknown_types,
    verify_determinism,
    verify_purity,
)


class TestReducerProtocol:
    def test_reducer_is_callable(self):
        def my_reducer(state, event):
            return state

        assert callable(my_reducer)

    def test_reducer_signature(self):
        def counter(state, event):
            state["count"] = state.get("count", 0) + 1
            return state

        state = {}
        event = {"event_type": "test", "payload": {}}
        result = counter(state, event)
        assert result is state
        assert result["count"] == 1

    def test_reducer_returns_dict(self):
        def identity(state, event):
            return state

        result = identity({}, {"event_type": "test"})
        assert isinstance(result, dict)

    def test_reducer_protocol_compatible(self):
        def valid(state: dict, event: dict) -> dict:
            return state

        assert isinstance(valid, Reducer)
        assert callable(valid)


class TestReducerDeterminism:
    def test_deterministic_reducer_passes(self):
        def counter(state, event):
            c = state.get("count", 0) + 1
            return {**state, "count": c}

        wrapped = verify_determinism(counter)
        state = {"count": 0}
        event = {"event_type": "test", "payload": {"value": 1}}
        result = wrapped(state, event)
        assert result["count"] == 1

    def test_nondeterministic_reducer_detected(self):
        import random

        def flaky(state, event):
            return {**state, "val": random.randint(0, 100)}

        wrapped = verify_determinism(flaky)
        with pytest.raises(AssertionError):
            wrapped({}, {"event_type": "test"})

    def test_determinism_identity_state(self):
        ident = verify_determinism(lambda s, e: s)
        event = {"event_type": "test", "payload": {"x": 1}}
        r1 = ident({"a": 1}, event)
        r2 = ident({"a": 1}, event)
        assert r1 == r2


class TestReducerPurity:
    def test_pure_reducer_passes(self):
        def pure(state, event):
            return {**state, "count": state.get("count", 0) + 1}

        wrapped = verify_purity(pure)
        state = {"count": 0}
        event = {"event_type": "test"}
        result = wrapped(state, event)
        assert result["count"] == 1
        assert state["count"] == 0

    def test_impure_mutates_state_raises(self):
        def impure(state, event):
            state["mutated"] = True
            return state

        wrapped = verify_purity(impure)
        with pytest.raises(PurityViolationError, match="mutated input state"):
            wrapped({}, {"event_type": "test"})

    def test_impure_mutates_event_raises(self):
        def impure(state, event):
            event["tampered"] = True
            return state

        wrapped = verify_purity(impure)
        with pytest.raises(PurityViolationError, match="mutated input event"):
            wrapped({}, {"event_type": "test"})

    def test_pure_copies_inputs(self):
        def reading(state, event):
            return {"type": event["event_type"], "count": state.get("c", 0)}

        wrapped = verify_purity(reading)
        state = {"c": 5}
        event = {"event_type": "test", "payload": {}}
        result = wrapped(state, event)
        assert result["type"] == "test"

    def test_purity_detects_nested_mutation(self):
        def nested_impure(state, event):
            event["payload"]["tampered"] = True
            return state

        wrapped = verify_purity(nested_impure)
        with pytest.raises(PurityViolationError):
            wrapped({}, {"event_type": "test", "payload": {"original": "data"}})

    def test_purity_detects_list_mutation(self):
        def list_impure(state, event):
            event["items"].append("tampered")
            return state

        wrapped = verify_purity(list_impure)
        with pytest.raises(PurityViolationError):
            wrapped({}, {"event_type": "test", "items": []})


class TestIgnoreUnknownTypes:
    def test_known_type_processed(self):
        def handler(state, event):
            et = event.get("event_type", "")
            if et == "known":
                return {"processed": True}
            return state

        wrapped = ignore_unknown_types(handler, known_types={"known"})
        result = wrapped({}, {"event_type": "known"})
        assert result.get("processed")

    def test_unknown_type_ignored(self):
        def handler(state, event):
            et = event.get("event_type", "")
            if et == "known":
                return {"processed": True}
            return state

        wrapped = ignore_unknown_types(handler, known_types={"known"})
        result = wrapped({}, {"event_type": "unknown_type"})
        assert result == {}

    def test_unknown_type_does_not_crash(self):
        def fragile(state, event):
            value = event["payload"]["must_exist"]
            return {**state, "val": value}

        wrapped = ignore_unknown_types(fragile, known_types={"safe"})
        result = wrapped({}, {"event_type": "totally_unknown", "payload": {}})
        assert result == {}

    def test_empty_known_types_ignores_all(self):
        def handler(state, event):
            return {"processed": True}

        wrapped = ignore_unknown_types(handler, known_types=set())
        result = wrapped({}, {"event_type": "anything"})
        assert result == {}

    def test_known_types_set_passed(self):
        def handler(state, event):
            return {"processed": True}

        wrapped = ignore_unknown_types(handler, known_types={"a", "b", "c"})
        result_a = wrapped({}, {"event_type": "a"})
        result_d = wrapped({}, {"event_type": "d"})
        assert result_a.get("processed")
        assert result_d == {}


class TestReducerTypeAlias:
    @staticmethod
    def test_reducer_func_type():
        fn: ReducerFunc = lambda s, e: s
        assert callable(fn)

    @staticmethod
    def test_reducer_func_usage():
        def count(state: dict, event: dict) -> dict:
            return {**state, "count": state.get("count", 0) + 1}

        fn: ReducerFunc = count
        result = fn({"count": 0}, {"event_type": "test"})
        assert result["count"] == 1


class TestErrors:
    def test_purity_violation_is_reducer_error(self):
        from rationalevault.replay.errors import PurityViolationError, ReducerError

        assert issubclass(PurityViolationError, ReducerError)

    def test_reducer_error_message(self):
        from rationalevault.replay.errors import ReducerError

        err = ReducerError("test message")
        assert str(err) == "test message"

    def test_purity_violation_message(self):
        from rationalevault.replay.errors import PurityViolationError

        err = PurityViolationError("mutated input state")
        assert "mutated" in str(err)
