"""Tests for SnapshotStore V2 — Load, Validation, Fast Path, and Regression."""
from __future__ import annotations

from typing import Any, Optional
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest


from rationalevault.cognitive_head.compiler import (
    compile_cognitive_head,
)
from rationalevault.cognitive_head.snapshot import (
    SnapshotManager,
    SnapshotStore,
    SnapshotValidationReason,
    SnapshotValidationResult,
)
from rationalevault.cognitive_head.snapshot_payload import (
    CognitiveHeadSnapshotPayload,
    _compute_hash,
)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_raw_snapshot(
    payload_dict: dict[str, Any],
    snapshot_hash: str = "",
) -> dict[str, Any]:
    """Create a raw snapshot row as returned by load_latest_raw()."""
    if not snapshot_hash:
        # Compute hash excluding the snapshot_hash field (matches payload logic)
        hash_dict = {k: v for k, v in payload_dict.items() if k != "snapshot_hash"}
        snapshot_hash = _compute_hash(hash_dict)
    return {
        "payload": payload_dict,
        "schema_version": payload_dict.get("schema_version", 1),
        "projection_version": payload_dict.get("projection_version", 1),
        "sequence": payload_dict.get("sequence", 0),
        "snapshot_hash": snapshot_hash,
    }


def _make_valid_payload_dict(
    sequence: int = 10,
    schema_version: int = 1,
    projection_version: int = 1,
    project_id: str = "",
) -> dict[str, Any]:
    """Create a valid CognitiveHeadSnapshotPayload as a dict."""
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
    # Compute hash excluding snapshot_hash field
    data["snapshot_hash"] = _compute_hash(data)
    return data


class MockSnapshotStore(SnapshotStore):
    """In-memory mock for testing snapshot load/save."""

    def __init__(self) -> None:
        self._snapshots: dict[str, list[dict]] = {}

    def load_latest_raw(
        self,
        project_id: UUID,
        projection_name: str,
    ) -> Optional[dict[str, Any]]:
        key = f"{project_id}:{projection_name}"
        rows = self._snapshots.get(key, [])
        if not rows:
            return None
        return max(rows, key=lambda r: r["sequence"])

    def save_snapshot(
        self,
        project_id: UUID,
        projection_name: str,
        payload,
    ) -> None:
        key = f"{project_id}:{projection_name}"
        if key not in self._snapshots:
            self._snapshots[key] = []
        raw = _make_raw_snapshot(payload.to_dict())
        self._snapshots[key].append(raw)

    def delete_snapshots_before(
        self,
        project_id: UUID,
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
        project_id: UUID,
        projection_name: str,
    ) -> Optional[int]:
        key = f"{project_id}:{projection_name}"
        rows = self._snapshots.get(key, [])
        if not rows:
            return None
        return max(r["sequence"] for r in rows)


def _mock_event_store(events=None, latest_sequence=0):
    """Create a mock EventStore for testing."""
    store = MagicMock()
    store.get_project_stream.return_value = events or []
    store.get_latest_sequence.return_value = latest_sequence
    return store


# ── Tests: load_latest_raw ───────────────────────────────────────────────────


@pytest.mark.snapshot
class TestLoadLatestRaw:
    def test_returns_none_when_no_snapshot(self):
        store = MockSnapshotStore()
        result = store.load_latest_raw(uuid4(), "cognitive_head")
        assert result is None

    def test_returns_most_recent_snapshot(self):
        store = MockSnapshotStore()
        pid = uuid4()
        # Insert snapshots at sequences 10, 20, 30
        for seq in [10, 20, 30]:
            data = _make_valid_payload_dict(sequence=seq)
            store._snapshots[f"{pid}:cognitive_head"] = (
                store._snapshots.get(f"{pid}:cognitive_head", [])
            )
            store._snapshots[f"{pid}:cognitive_head"].append(
                _make_raw_snapshot(data)
            )
        result = store.load_latest_raw(pid, "cognitive_head")
        assert result is not None
        assert result["sequence"] == 30

    def test_returns_none_for_different_projection(self):
        store = MockSnapshotStore()
        pid = uuid4()
        data = _make_valid_payload_dict(sequence=10)
        store._snapshots[f"{pid}:cognitive_head"] = [
            _make_raw_snapshot(data)
        ]
        result = store.load_latest_raw(pid, "knowledge")
        assert result is None


# ── Tests: SnapshotManager validation ────────────────────────────────────────


@pytest.mark.snapshot
class TestSnapshotManagerValidation:
    def _make_manager(self, raw=None, latest_seq=100):
        store = MockSnapshotStore()
        if raw is not None:
            pid = uuid4()
            store._snapshots[f"{pid}:cognitive_head"] = [raw]
        else:
            pid = uuid4()

        def get_latest(project_id):
            return latest_seq

        manager = SnapshotManager(store, get_latest)
        return manager, pid

    def test_not_found(self):
        manager, pid = self._make_manager(raw=None)
        result = manager.load_valid_snapshot(pid)
        assert result.valid is False
        assert result.reason == SnapshotValidationReason.NOT_FOUND

    def test_valid_snapshot(self):
        data = _make_valid_payload_dict(sequence=50)
        raw = _make_raw_snapshot(data)
        manager, pid = self._make_manager(raw=raw, latest_seq=100)
        result = manager.load_valid_snapshot(pid)
        assert result.valid is True
        assert result.payload is not None
        assert result.payload.sequence == 50

    def test_hash_mismatch(self):
        data = _make_valid_payload_dict(sequence=50)
        data["snapshot_hash"] = "bad_hash"
        raw = _make_raw_snapshot(data, snapshot_hash="bad_hash")
        manager, pid = self._make_manager(raw=raw, latest_seq=100)
        result = manager.load_valid_snapshot(pid)
        assert result.valid is False
        assert result.reason == SnapshotValidationReason.HASH_MISMATCH

    def test_schema_version_mismatch(self):
        data = _make_valid_payload_dict(sequence=50, schema_version=999)
        raw = _make_raw_snapshot(data)
        manager, pid = self._make_manager(raw=raw, latest_seq=100)
        result = manager.load_valid_snapshot(pid)
        assert result.valid is False
        assert result.reason == SnapshotValidationReason.SCHEMA_VERSION

    def test_projection_version_mismatch(self):
        data = _make_valid_payload_dict(sequence=50, projection_version=999)
        raw = _make_raw_snapshot(data)
        manager, pid = self._make_manager(raw=raw, latest_seq=100)
        result = manager.load_valid_snapshot(pid)
        assert result.valid is False
        assert result.reason == SnapshotValidationReason.PROJECTION_VERSION

    def test_future_sequence(self):
        data = _make_valid_payload_dict(sequence=200)
        raw = _make_raw_snapshot(data)
        manager, pid = self._make_manager(raw=raw, latest_seq=100)
        result = manager.load_valid_snapshot(pid)
        assert result.valid is False
        assert result.reason == SnapshotValidationReason.FUTURE_SEQUENCE

    def test_deserialization_failure(self):
        raw = {
            "payload": {"not_a_valid": "payload"},
            "schema_version": 1,
            "projection_version": 1,
            "sequence": 50,
            "snapshot_hash": "does_not_match",
        }
        manager, pid = self._make_manager(raw=raw, latest_seq=100)
        result = manager.load_valid_snapshot(pid)
        # Deserialization succeeds (from_dict is lenient) but hash fails
        assert result.valid is False
        assert result.reason == SnapshotValidationReason.HASH_MISMATCH


# ── Tests: compile_cognitive_head with snapshots ─────────────────────────────


@pytest.mark.snapshot
class TestCompileWithSnapshots:
    def _bootstrap_events(self, pid):
        """Create minimal bootstrap events."""
        from rationalevault.schema.events import (
            EventMetadata,
            EventType,
        )

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

    def test_valid_current_snapshot_returns_from_snapshot(self):
        pid = uuid4()
        events = self._bootstrap_events(pid)

        # Create a valid snapshot at sequence 3 (matches latest)
        data = _make_valid_payload_dict(sequence=3, project_id=str(pid))
        data["project_name"] = "Snapshot Project"
        data["project_goal"] = "Snapshot Goal"
        data["current_focus"] = "Snapshot Focus"
        # Recompute hash after modifying fields
        data["snapshot_hash"] = _compute_hash(
            {k: v for k, v in data.items() if k != "snapshot_hash"}
        )
        raw = _make_raw_snapshot(data)

        store = MockSnapshotStore()
        store._snapshots[f"{pid}:cognitive_head"] = [raw]

        event_store = _mock_event_store(events, latest_sequence=3)
        manager = SnapshotManager(store, event_store.get_latest_sequence)

        head = compile_cognitive_head(
            pid, store=event_store, snapshot_manager=manager
        )
        # Should come from snapshot, not from replay
        assert head.project_name == "Snapshot Project"
        assert head.project_goal == "Snapshot Goal"

    def test_stale_snapshot_falls_back_to_full_replay(self):
        pid = uuid4()
        events = self._bootstrap_events(pid)

        # Snapshot at sequence 2, but latest is 3
        data = _make_valid_payload_dict(sequence=2, project_id=str(pid))
        data["project_name"] = "Old Snapshot"
        raw = _make_raw_snapshot(data)

        store = MockSnapshotStore()
        store._snapshots[f"{pid}:cognitive_head"] = [raw]

        event_store = _mock_event_store(events, latest_sequence=3)
        manager = SnapshotManager(store, event_store.get_latest_sequence)

        head = compile_cognitive_head(
            pid, store=event_store, snapshot_manager=manager
        )
        # Should come from full replay, not snapshot
        assert head.project_name == "Test"

    def test_invalid_snapshot_warns_and_does_full_replay(self):
        pid = uuid4()
        events = self._bootstrap_events(pid)

        # Invalid snapshot (bad hash)
        data = _make_valid_payload_dict(sequence=5, project_id=str(pid))
        data["snapshot_hash"] = "invalid"
        raw = _make_raw_snapshot(data, snapshot_hash="invalid")

        store = MockSnapshotStore()
        store._snapshots[f"{pid}:cognitive_head"] = [raw]

        event_store = _mock_event_store(events, latest_sequence=10)
        manager = SnapshotManager(store, event_store.get_latest_sequence)

        # Should warn and fall back to full replay
        head = compile_cognitive_head(
            pid, store=event_store, snapshot_manager=manager
        )
        assert head.project_name == "Test"

    def test_no_snapshot_manager_does_full_replay(self):
        """Existing behavior: no snapshot_manager → full replay."""
        pid = uuid4()
        events = self._bootstrap_events(pid)
        event_store = _mock_event_store(events, latest_sequence=3)

        head = compile_cognitive_head(pid, store=event_store)
        assert head.project_name == "Test"
        assert head.project_goal == "Goal"


# ── Tests: Hash order independence ───────────────────────────────────────────


@pytest.mark.snapshot
class TestHashOrderIndependence:
    def test_same_data_different_order_produces_same_hash(self):
        data_a = {"b": 2, "a": 1, "c": 3}
        data_b = {"a": 1, "c": 3, "b": 2}
        assert _compute_hash(data_a) == _compute_hash(data_b)

    def test_payload_hash_ignores_snapshot_hash_field(self):
        data = _make_valid_payload_dict(sequence=10)
        payload = CognitiveHeadSnapshotPayload.from_dict(data)
        hash1 = payload.compute_hash()

        # Changing snapshot_hash should NOT change computed hash
        payload.snapshot_hash = "different"
        hash2 = payload.compute_hash()
        assert hash1 == hash2


# ── Tests: Historical snapshots ──────────────────────────────────────────────


@pytest.mark.snapshot
class TestHistoricalSnapshots:
    def test_load_returns_highest_sequence(self):
        store = MockSnapshotStore()
        pid = uuid4()
        for seq in [10, 20, 30]:
            data = _make_valid_payload_dict(sequence=seq)
            key = f"{pid}:cognitive_head"
            if key not in store._snapshots:
                store._snapshots[key] = []
            store._snapshots[key].append(_make_raw_snapshot(data))

        result = store.load_latest_raw(pid, "cognitive_head")
        assert result is not None
        assert result["sequence"] == 30

    def test_delete_preserves_newer(self):
        store = MockSnapshotStore()
        pid = uuid4()
        for seq in [10, 20, 30]:
            data = _make_valid_payload_dict(sequence=seq)
            key = f"{pid}:cognitive_head"
            if key not in store._snapshots:
                store._snapshots[key] = []
            store._snapshots[key].append(_make_raw_snapshot(data))

        deleted = store.delete_snapshots_before(pid, "cognitive_head", 25)
        assert deleted == 2  # sequences 10 and 20 deleted

        result = store.load_latest_raw(pid, "cognitive_head")
        assert result is not None
        assert result["sequence"] == 30


# ── Tests: SnapshotValidationResult ──────────────────────────────────────────


@pytest.mark.snapshot
class TestSnapshotValidationResult:
    def test_valid_result_has_payload(self):
        data = _make_valid_payload_dict(sequence=10)
        payload = CognitiveHeadSnapshotPayload.from_dict(data)
        result = SnapshotValidationResult(valid=True, payload=payload)
        assert result.valid is True
        assert result.payload is payload
        assert result.reason is None

    def test_invalid_result_has_reason(self):
        result = SnapshotValidationResult(
            valid=False,
            reason=SnapshotValidationReason.HASH_MISMATCH,
        )
        assert result.valid is False
        assert result.payload is None
        assert result.reason == SnapshotValidationReason.HASH_MISMATCH


# ── Tests: SnapshotManager.warn_invalid ──────────────────────────────────────


@pytest.mark.snapshot
class TestWarnInvalid:
    def test_warns_on_invalid(self, capsys):
        store = MockSnapshotStore()
        manager = SnapshotManager(store, lambda pid: 100)
        pid = uuid4()
        result = SnapshotValidationResult(
            valid=False,
            reason=SnapshotValidationReason.HASH_MISMATCH,
        )
        manager.warn_invalid(pid, result)
        captured = capsys.readouterr()
        assert "Ignoring invalid snapshot" in captured.err
        assert "hash_mismatch" in captured.err

    def test_no_warn_on_valid(self, capsys):
        store = MockSnapshotStore()
        manager = SnapshotManager(store, lambda pid: 100)
        result = SnapshotValidationResult(valid=True)
        manager.warn_invalid(uuid4(), result)
        captured = capsys.readouterr()
        assert captured.err == ""
