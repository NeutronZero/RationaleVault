import hashlib

from rationalevault.skill_platform.provenance import Provenance, compute_snapshot_hash


class TestComputeSnapshotHash:
    def test_deterministic(self):
        inputs = {"a": 1, "b": "hello"}
        h1 = compute_snapshot_hash(inputs)
        h2 = compute_snapshot_hash(inputs)
        assert h1 == h2

    def test_sorted_keys(self):
        h1 = compute_snapshot_hash({"b": 2, "a": 1})
        h2 = compute_snapshot_hash({"a": 1, "b": 2})
        assert h1 == h2

    def test_different_inputs_differ(self):
        h1 = compute_snapshot_hash({"x": 1})
        h2 = compute_snapshot_hash({"x": 2})
        assert h1 != h2

    def test_empty_dict(self):
        h = compute_snapshot_hash({})
        assert isinstance(h, str)
        assert len(h) == 16

    def test_truncated_to_16_chars(self):
        h = compute_snapshot_hash({"key": "value"})
        assert len(h) == 16
        assert h == h.upper()

    def test_nested_dict(self):
        inputs = {"outer": {"inner": [1, 2, 3]}}
        h = compute_snapshot_hash(inputs)
        assert isinstance(h, str)
        assert len(h) == 16


class TestProvenance:
    def _make_provenance(self) -> Provenance:
        return Provenance(
            execution_id="SKE-abc123",
            decision_id="DEC-def456",
            synthesis_id="SYN-ghi789",
            belief_id="BEL-jkl012",
            source_event_ids=["evt1", "evt2"],
            skill_version="1.0.0",
            gate_policy_version="1.0.0",
            input_snapshot_hash="ABCD1234",
            timestamp="2026-01-01T00:00:00Z",
        )

    def test_to_dict(self):
        p = self._make_provenance()
        d = p.to_dict()
        assert d["execution_id"] == "SKE-abc123"
        assert d["decision_id"] == "DEC-def456"
        assert d["synthesis_id"] == "SYN-ghi789"
        assert d["belief_id"] == "BEL-jkl012"
        assert d["source_event_ids"] == ["evt1", "evt2"]
        assert d["skill_version"] == "1.0.0"
        assert d["gate_policy_version"] == "1.0.0"
        assert d["input_snapshot_hash"] == "ABCD1234"
        assert d["timestamp"] == "2026-01-01T00:00:00Z"

    def test_from_dict_roundtrip(self):
        original = self._make_provenance()
        restored = Provenance.from_dict(original.to_dict())
        assert restored == original

    def test_from_dict_defaults(self):
        d = {
            "execution_id": "SKE-x",
            "decision_id": "DEC-x",
            "synthesis_id": "SYN-x",
            "belief_id": "BEL-x",
        }
        p = Provenance.from_dict(d)
        assert p.source_event_ids == []
        assert p.skill_version == ""
        assert p.gate_policy_version == ""
        assert p.input_snapshot_hash == ""
        assert p.timestamp == ""

    def test_frozen(self):
        p = self._make_provenance()
        import pytest
        with pytest.raises(AttributeError):
            p.execution_id = "changed"

    def test_to_dict_is_json_serializable(self):
        import json
        d = self._make_provenance().to_dict()
        serialized = json.dumps(d)
        assert isinstance(serialized, str)
