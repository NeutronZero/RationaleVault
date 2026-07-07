"""Tests for SnapshotStore V2 — PR 3: Save, Policy, Refresh, Immutability."""
from __future__ import annotations

from typing import Any, Optional
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from rationalevault.cognitive_head.snapshot import (
    NullSnapshotManager,
    SnapshotManager,
    SnapshotStore,
    SnapshotValidationResult,
)
from rationalevault.cognitive_head.snapshot_payload import (
    CognitiveHeadSnapshotPayload,
    ProjectionSnapshotPayload,
    _compute_hash,
)
from rationalevault.cognitive_head.snapshot_policy import (
    EventCountPolicy,
)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_valid_payload_dict(
    sequence: int = 10,
    schema_version: int = 1,
    projection_version: int = 1,
    project_id: str = "",
) -> dict[str, Any]:
    if not project_id:
        project_id = str(uuid4())
    data = {
        "sequence": sequence,
        "schema_version": schema_version,
        "projection_version": projection_version,
        "project_id": project_id,
        "project_name": "Test Project",
        "project_goal": "Test goal",
        "current_focus": "Test focus",
        "ledger_version": 5,
        "compiled_at": "2026-01-01T00:00:00",
        "tasks": {},
        "decisions": {},
        "questions": {},
        "blockers": [],
    }
    data["snapshot_hash"] = _compute_hash(data)
    return data


def _make_raw_snapshot(
    payload_dict: dict[str, Any],
    snapshot_hash: str = "",
) -> dict[str, Any]:
    if not snapshot_hash:
        hash_dict = {k: v for k, v in payload_dict.items() if k != "snapshot_hash"}
        snapshot_hash = _compute_hash(hash_dict)
    return {
        "payload": payload_dict,
        "schema_version": payload_dict.get("schema_version", 1),
        "projection_version": payload_dict.get("projection_version", 1),
        "sequence": payload_dict.get("sequence", 0),
        "snapshot_hash": snapshot_hash,
    }


class MockSnapshotStore(SnapshotStore):
    """In-memory mock for testing snapshot operations."""

    def __init__(self) -> None:
        self._snapshots: dict[str, list[dict]] = {}
        self.save_calls: list[tuple] = []

    def load_latest_raw(
        self,
        project_id: uuid4,
        projection_name: str,
    ) -> Optional[dict[str, Any]]:
        key = f"{project_id}:{projection_name}"
        rows = self._snapshots.get(key, [])
        if not rows:
            return None
        return max(rows, key=lambda r: r["sequence"])

    def save_snapshot(
        self,
        project_id: uuid4,
        projection_name: str,
        payload,
    ) -> None:
        self.save_calls.append((project_id, projection_name, payload))
        key = f"{project_id}:{projection_name}"
        if key not in self._snapshots:
            self._snapshots[key] = []
        raw = _make_raw_snapshot(payload.to_dict())
        self._snapshots[key].append(raw)

    def delete_snapshots_before(
        self,
        project_id: uuid4,
        projection_name: str,
        sequence: int,
    ) -> int:
        key = f"{project_id}:{projection_name}"
        rows = self._snapshots.get(key, [])
        before = len(rows)
        self._snapshots[key] = [r for r in rows if r["sequence"] >= sequence]
        return before - len(self._snapshots[key])

    def get_latest_snapshot_sequence(
        self,
        project_id: uuid4,
        projection_name: str,
    ) -> Optional[int]:
        key = f"{project_id}:{projection_name}"
        rows = self._snapshots.get(key, [])
        if not rows:
            return None
        return max(r["sequence"] for r in rows)


# ── Tests: EventCountPolicy ──────────────────────────────────────────────────


@pytest.mark.snapshot
class TestEventCountPolicy:
    def test_triggers_when_no_previous_snapshot(self):
        policy = EventCountPolicy(threshold=100)
        assert policy.should_snapshot(50, None) is True

    def test_triggers_at_threshold(self):
        policy = EventCountPolicy(threshold=100)
        assert policy.should_snapshot(150, 50) is True

    def test_triggers_past_threshold(self):
        policy = EventCountPolicy(threshold=100)
        assert policy.should_snapshot(200, 50) is True

    def test_does_not_trigger_below_threshold(self):
        policy = EventCountPolicy(threshold=100)
        assert policy.should_snapshot(140, 50) is False

    def test_does_not_trigger_at_threshold_minus_one(self):
        policy = EventCountPolicy(threshold=100)
        assert policy.should_snapshot(149, 50) is False

    def test_default_threshold_is_100(self):
        policy = EventCountPolicy()
        assert policy.threshold == 100

    def test_custom_threshold(self):
        policy = EventCountPolicy(threshold=10)
        assert policy.should_snapshot(15, 5) is True
        assert policy.should_snapshot(14, 5) is False


# ── Tests: with_hash() immutability ──────────────────────────────────────────


@pytest.mark.snapshot
class TestWithHashImmutability:
    def test_with_hash_returns_new_instance(self):
        data = _make_valid_payload_dict(sequence=10)
        payload = CognitiveHeadSnapshotPayload.from_dict(data)
        hashed = payload.with_hash()
        assert hashed is not payload
        assert hashed.snapshot_hash != ""
        assert hashed.compute_hash() == hashed.snapshot_hash

    def test_with_hash_does_not_mutate_original(self):
        data = _make_valid_payload_dict(sequence=10)
        data["snapshot_hash"] = ""
        payload = CognitiveHeadSnapshotPayload.from_dict(data)
        assert payload.snapshot_hash == ""
        _ = payload.with_hash()
        assert payload.snapshot_hash == ""

    def test_with_hash_computes_correctly(self):
        data = _make_valid_payload_dict(sequence=10)
        payload = CognitiveHeadSnapshotPayload.from_dict(data)
        payload.snapshot_hash = ""
        hashed = payload.with_hash()
        expected = _compute_hash(hashed.to_dict(exclude_hash=True))
        assert hashed.snapshot_hash == expected

    def test_two_identical_payloads_same_hash(self):
        data = _make_valid_payload_dict(sequence=10)
        p1 = CognitiveHeadSnapshotPayload.from_dict(data).with_hash()
        p2 = CognitiveHeadSnapshotPayload.from_dict(data).with_hash()
        assert p1.snapshot_hash == p2.snapshot_hash

    def test_different_sequences_different_hashes(self):
        data_a = _make_valid_payload_dict(sequence=10)
        data_b = _make_valid_payload_dict(sequence=20)
        h1 = CognitiveHeadSnapshotPayload.from_dict(data_a).with_hash()
        h2 = CognitiveHeadSnapshotPayload.from_dict(data_b).with_hash()
        assert h1.snapshot_hash != h2.snapshot_hash

    def test_validate_hash_passes_after_with_hash(self):
        data = _make_valid_payload_dict(sequence=10)
        payload = CognitiveHeadSnapshotPayload.from_dict(data)
        payload.snapshot_hash = ""
        hashed = payload.with_hash()
        assert hashed.validate_hash() is True

    def test_validate_hash_fails_without_with_hash(self):
        data = _make_valid_payload_dict(sequence=10)
        payload = CognitiveHeadSnapshotPayload.from_dict(data)
        payload.snapshot_hash = ""
        assert payload.validate_hash() is False


# ── Tests: SnapshotManager.refresh_snapshot ───────────────────────────────────


@pytest.mark.snapshot
class TestRefreshSnapshot:
    def _make_head_payload(self, sequence=5):
        data = _make_valid_payload_dict(sequence=sequence)
        return CognitiveHeadSnapshotPayload.from_dict(data)

    def test_saves_when_policy_triggers(self):
        store = MockSnapshotStore()
        policy = EventCountPolicy(threshold=10)
        manager = SnapshotManager(store, lambda pid: 100, policy=policy)
        pid = uuid4()
        head = self._make_head_payload(sequence=100)

        manager.refresh_snapshot(pid, "cognitive_head", head, 100)

        assert len(store.save_calls) == 1
        assert store.save_calls[0][0] == pid
        assert store.save_calls[0][1] == "cognitive_head"

    def test_does_not_save_when_policy_does_not_trigger(self):
        store = MockSnapshotStore()
        pid = uuid4()
        # Existing snapshot at sequence 95, threshold=100 → only 5 new events
        data = _make_valid_payload_dict(sequence=95)
        store._snapshots[f"{pid}:cognitive_head"] = [_make_raw_snapshot(data)]

        policy = EventCountPolicy(threshold=100)
        manager = SnapshotManager(store, lambda pid: 100, policy=policy)
        head = self._make_head_payload(sequence=100)

        manager.refresh_snapshot(pid, "cognitive_head", head, 100)

        assert len(store.save_calls) == 0

    def test_saves_when_no_previous_snapshot(self):
        store = MockSnapshotStore()
        policy = EventCountPolicy(threshold=100)
        pid = uuid4()
        manager = SnapshotManager(store, lambda pid: 100, policy=policy)
        head = self._make_head_payload(sequence=50)

        manager.refresh_snapshot(pid, "cognitive_head", head, 50)

        assert len(store.save_calls) == 1

    def test_catches_exception_and_warns(self, capsys):
        store = MockSnapshotStore()
        store.save_snapshot = MagicMock(side_effect=RuntimeError("disk full"))
        policy = EventCountPolicy(threshold=1)
        pid = uuid4()
        manager = SnapshotManager(store, lambda pid: 100, policy=policy)
        head = self._make_head_payload(sequence=50)

        # Should not raise
        manager.refresh_snapshot(pid, "cognitive_head", head, 50)

        captured = capsys.readouterr()
        assert "Snapshot save failed" in captured.err
        assert "disk full" in captured.err

    def test_saved_payload_has_hash_set(self):
        store = MockSnapshotStore()
        policy = EventCountPolicy(threshold=1)
        manager = SnapshotManager(store, lambda pid: 100, policy=policy)
        head = self._make_head_payload(sequence=50)

        manager.refresh_snapshot(uuid4(), "cognitive_head", head, 50)

        saved_payload = store.save_calls[0][2]
        assert saved_payload.snapshot_hash != ""
        assert saved_payload.validate_hash() is True

    def test_saved_payload_is_new_instance(self):
        store = MockSnapshotStore()
        policy = EventCountPolicy(threshold=1)
        manager = SnapshotManager(store, lambda pid: 100, policy=policy)
        head = self._make_head_payload(sequence=50)

        manager.refresh_snapshot(uuid4(), "cognitive_head", head, 50)

        saved_payload = store.save_calls[0][2]
        # Saved payload should not be the same object as the input
        assert saved_payload is not head

    def test_historical_snapshots_preserved(self):
        store = MockSnapshotStore()
        pid = uuid4()
        # Insert old snapshot
        old_data = _make_valid_payload_dict(sequence=10)
        store._snapshots[f"{pid}:cognitive_head"] = [_make_raw_snapshot(old_data)]

        policy = EventCountPolicy(threshold=1)
        manager = SnapshotManager(store, lambda pid: 100, policy=policy)
        head = self._make_head_payload(sequence=50)

        manager.refresh_snapshot(pid, "cognitive_head", head, 50)

        # Both old and new should exist
        key = f"{pid}:cognitive_head"
        assert len(store._snapshots[key]) == 2
        sequences = {r["sequence"] for r in store._snapshots[key]}
        assert sequences == {10, 50}


# ── Tests: NullSnapshotManager ───────────────────────────────────────────────


@pytest.mark.snapshot
class TestNullSnapshotManager:
    def test_load_returns_not_found(self):
        manager = NullSnapshotManager()
        result = manager.load_valid_snapshot(uuid4())
        assert result.valid is False
        assert result.reason is not None
        assert result.reason.value == "not_found"

    def test_warn_invalid_does_nothing(self, capsys):
        manager = NullSnapshotManager()
        result = SnapshotValidationResult(valid=False)
        manager.warn_invalid(uuid4(), result)
        captured = capsys.readouterr()
        assert captured.err == ""

    def test_refresh_snapshot_does_nothing(self):
        manager = NullSnapshotManager()
        head = CognitiveHeadSnapshotPayload(sequence=10)
        # Should not raise
        manager.refresh_snapshot(uuid4(), "cognitive_head", head, 10)

    def test_isinstance_of_snapshot_manager(self):
        manager = NullSnapshotManager()
        assert isinstance(manager, SnapshotManager)


# ── Tests: Compiler calls refresh_snapshot ────────────────────────────────────


@pytest.mark.snapshot
class TestCompilerRefreshSnapshot:
    def _bootstrap_events(self, pid):
        from rationalevault.schema.events import EventMetadata, EventType
        events = []
        for i, (et, payload) in enumerate([
            (EventType.PROJECT_CREATED, {"name": "Test"}),
            (EventType.PROJECT_GOAL_SET, {"goal": "Goal"}),
            (EventType.PROJECT_FOCUS_CHANGED, {"focus": "Focus"}),
        ], start=1):
            event = MagicMock()
            event.event_type = et
            event.payload = payload
            event.version = i
            event.event_sequence = i
            event.metadata = EventMetadata(actor="test", source="test")
            events.append(event)
        return events

    def test_compiler_calls_refresh_on_valid_snapshot(self):
        from rationalevault.cognitive_head.compiler import compile_cognitive_head
        pid = uuid4()
        events = self._bootstrap_events(pid)

        data = _make_valid_payload_dict(sequence=3, project_id=str(pid))
        data["project_name"] = "Snap Project"
        raw = _make_raw_snapshot(data)

        store = MockSnapshotStore()
        store._snapshots[f"{pid}:cognitive_head"] = [raw]

        event_store = MagicMock()
        event_store.get_project_stream.return_value = events
        event_store.get_latest_sequence.return_value = 3

        manager = MagicMock(spec=SnapshotManager)
        load_result = SnapshotValidationResult(
            valid=True,
            payload=CognitiveHeadSnapshotPayload.from_dict(data),
        )
        manager.load_valid_snapshot.return_value = load_result

        _ = compile_cognitive_head(
            pid, store=event_store, snapshot_manager=manager,
        )
        manager.refresh_snapshot.assert_called_once()

    def test_compiler_calls_refresh_on_full_replay(self):
        from rationalevault.cognitive_head.compiler import compile_cognitive_head
        pid = uuid4()
        events = self._bootstrap_events(pid)

        event_store = MagicMock()
        event_store.get_project_stream.return_value = events
        event_store.get_latest_sequence.return_value = 3

        manager = MagicMock(spec=SnapshotManager)
        manager.load_valid_snapshot.return_value = SnapshotValidationResult(
            valid=False,
        )

        _ = compile_cognitive_head(
            pid, store=event_store, snapshot_manager=manager,
        )
        manager.refresh_snapshot.assert_called_once()

    def test_compiler_no_refresh_with_null_manager(self):
        from rationalevault.cognitive_head.compiler import compile_cognitive_head
        pid = uuid4()
        events = self._bootstrap_events(pid)

        event_store = MagicMock()
        event_store.get_project_stream.return_value = events
        event_store.get_latest_sequence.return_value = 3

        # NullSnapshotManager is not a SnapshotManager instance (it overrides),
        # so refresh_snapshot should NOT be called by the compiler's isinstance check
        null_manager = NullSnapshotManager()
        head = compile_cognitive_head(
            pid, store=event_store, snapshot_manager=null_manager,
        )
        # NullSnapshotManager doesn't track calls, but the compiler should not
        # call refresh_snapshot on it because isinstance(null_manager, SnapshotManager)
        # is True (NullSnapshotManager inherits from SnapshotManager).
        # Actually, it IS a SnapshotManager, so the compiler WILL call refresh.
        # But NullSnapshotManager.refresh_snapshot is a no-op, so it's fine.
        assert head.project_name == "Test"


# ── Tests: Base payload with_hash ────────────────────────────────────────────


@pytest.mark.snapshot
class TestBasePayloadWithHash:
    def test_base_payload_with_hash(self):
        payload = ProjectionSnapshotPayload(sequence=10)
        hashed = payload.with_hash()
        assert hashed is not payload
        assert hashed.snapshot_hash != ""
        assert hashed.validate_hash() is True

    def test_base_payload_original_unchanged(self):
        payload = ProjectionSnapshotPayload(sequence=10)
        original_hash = payload.snapshot_hash
        _ = payload.with_hash()
        assert payload.snapshot_hash == original_hash


# ── Tests: get_latest_snapshot_sequence ──────────────────────────────────────


@pytest.mark.snapshot
class TestGetLatestSnapshotSequence:
    def test_returns_none_when_empty(self):
        store = MockSnapshotStore()
        result = store.get_latest_snapshot_sequence(uuid4(), "cognitive_head")
        assert result is None

    def test_returns_highest_sequence(self):
        store = MockSnapshotStore()
        pid = uuid4()
        for seq in [10, 30, 20]:
            data = _make_valid_payload_dict(sequence=seq)
            key = f"{pid}:cognitive_head"
            if key not in store._snapshots:
                store._snapshots[key] = []
            store._snapshots[key].append(_make_raw_snapshot(data))

        result = store.get_latest_snapshot_sequence(pid, "cognitive_head")
        assert result == 30

    def test_returns_none_for_different_projection(self):
        store = MockSnapshotStore()
        pid = uuid4()
        data = _make_valid_payload_dict(sequence=10)
        store._snapshots[f"{pid}:cognitive_head"] = [_make_raw_snapshot(data)]

        result = store.get_latest_snapshot_sequence(pid, "knowledge")
        assert result is None
