"""Tests for ProjectionRegistry and ProjectionIdentity."""

from __future__ import annotations

import pytest

from rationalevault.replay.registry import ProjectionIdentity, ProjectionRegistry, ReducerFunc


class TestProjectionIdentity:
    def test_holds_name(self):
        pid = ProjectionIdentity("counter")
        assert pid.name == "counter"

    def test_immutable(self):
        pid = ProjectionIdentity("counter")
        with pytest.raises(AttributeError):
            pid.name = "other"

    def test_equality(self):
        assert ProjectionIdentity("a") == ProjectionIdentity("a")
        assert ProjectionIdentity("a") != ProjectionIdentity("b")

    def test_hashable(self):
        s = {ProjectionIdentity("a"), ProjectionIdentity("a"), ProjectionIdentity("b")}
        assert len(s) == 2

    def test_repr(self):
        pid = ProjectionIdentity("counter")
        assert "counter" in repr(pid)


class TestProjectionRegistry:
    def test_register_and_get_reducer(self):
        registry = ProjectionRegistry()

        def count(state, event):
            state["count"] = state.get("count", 0) + 1
            return state

        identity = registry.register("counter", count)
        assert isinstance(identity, ProjectionIdentity)
        assert identity.name == "counter"

        retrieved = registry.get_reducer("counter")
        assert retrieved is count

    def test_register_duplicate_raises(self):
        registry = ProjectionRegistry()

        def r1(state, event):
            return state

        def r2(state, event):
            return state

        registry.register("proj", r1)
        with pytest.raises(ValueError, match="already registered"):
            registry.register("proj", r2)

    def test_get_unknown_raises(self):
        registry = ProjectionRegistry()
        with pytest.raises(KeyError, match="Unknown projection"):
            registry.get_reducer("nonexistent")

    def test_list_projections_empty(self):
        registry = ProjectionRegistry()
        assert registry.list_projections() == []

    def test_list_projections_returns_registration_order(self):
        registry = ProjectionRegistry()

        def empty(state, event):
            return state

        registry.register("a", empty)
        registry.register("b", empty)
        registry.register("c", empty)

        assert registry.list_projections() == ["a", "b", "c"]

    def test_has_projection(self):
        registry = ProjectionRegistry()

        def empty(state, event):
            return state

        assert not registry.has("xyz")
        registry.register("xyz", empty)
        assert registry.has("xyz")

    def test_reducer_func_type(self):
        """Verify that a ReducerFunc-compliant function works."""
        def accumulate(state: dict, event: dict) -> dict:
            state["events"] = state.get("events", []) + [event["event_type"]]
            return state

        state = {}
        state = accumulate(state, {"event_type": "foo"})
        state = accumulate(state, {"event_type": "bar"})
        assert state["events"] == ["foo", "bar"]
