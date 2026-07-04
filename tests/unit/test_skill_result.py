"""
RationaleVault Unit Tests — SkillResult.

Tests for:
  - SkillResult ID determinism
  - SkillResult success / failure / denied factory methods
  - to_dict / from_dict round-trip
  - Failure shapes (outputs={}, artifacts=[], error present)
"""
from rationalevault.skill_platform.provenance import Provenance
from rationalevault.skill_platform.result import SkillResult, SkillResultStatus


def _make_provenance(**overrides) -> Provenance:
    defaults = dict(
        execution_id="SKE-AAAAAAAA",
        decision_id="DEC-BBBBBBBB",
        synthesis_id="SYN-CCCCCCCC",
        belief_id="BEL-DDDDDDDD",
        source_event_ids=["evt-1", "evt-2"],
        skill_version="1.0.0",
        gate_policy_version="1.0",
        input_snapshot_hash="HASH1234",
        timestamp="2026-01-01T00:00:00Z",
    )
    defaults.update(overrides)
    return Provenance(**defaults)


class TestSkillResultID:
    def test_deterministic_id(self):
        prov = _make_provenance()
        r1 = SkillResult.success(
            execution_id="SKE-AAAAAAAA",
            decision_id="DEC-BBBBBBBB",
            skill_id="SKL-11111111",
            outputs={"key": "value"},
            artifacts=[],
            metrics={"duration_ms": 100},
            warnings=[],
            duration_ms=100,
            provenance=prov,
        )
        r2 = SkillResult.success(
            execution_id="SKE-AAAAAAAA",
            decision_id="DEC-BBBBBBBB",
            skill_id="SKL-11111111",
            outputs={"key": "value"},
            artifacts=[],
            metrics={"duration_ms": 100},
            warnings=[],
            duration_ms=100,
            provenance=prov,
        )
        assert r1.result_id == r2.result_id
        assert r1.result_id.startswith("SRT-")

    def test_different_outputs_different_id(self):
        prov = _make_provenance()
        r1 = SkillResult.success(
            execution_id="SKE-AAAAAAAA",
            decision_id="DEC-BBBBBBBB",
            skill_id="SKL-11111111",
            outputs={"key": "value1"},
            artifacts=[],
            metrics={},
            warnings=[],
            duration_ms=100,
            provenance=prov,
        )
        r2 = SkillResult.success(
            execution_id="SKE-AAAAAAAA",
            decision_id="DEC-BBBBBBBB",
            skill_id="SKL-11111111",
            outputs={"key": "value2"},
            artifacts=[],
            metrics={},
            warnings=[],
            duration_ms=100,
            provenance=prov,
        )
        assert r1.result_id != r2.result_id


class TestSkillResultSuccess:
    def test_success_shape(self):
        prov = _make_provenance()
        r = SkillResult.success(
            execution_id="SKE-AAAAAAAA",
            decision_id="DEC-BBBBBBBB",
            skill_id="SKL-11111111",
            outputs={"result": "ok"},
            artifacts=["/tmp/out.md"],
            metrics={"duration_ms": 150},
            warnings=["minor warning"],
            duration_ms=150,
            provenance=prov,
        )
        assert r.status == SkillResultStatus.COMPLETED
        assert r.outputs == {"result": "ok"}
        assert r.artifacts == ["/tmp/out.md"]
        assert r.metrics == {"duration_ms": 150}
        assert r.warnings == ["minor warning"]
        assert r.error is None
        assert r.duration_ms == 150


class TestSkillResultFailure:
    def test_failure_shape(self):
        prov = _make_provenance()
        r = SkillResult.failure(
            execution_id="SKE-AAAAAAAA",
            decision_id="DEC-BBBBBBBB",
            skill_id="SKL-11111111",
            error="something broke",
            duration_ms=50,
            provenance=prov,
        )
        assert r.status == SkillResultStatus.FAILED
        assert r.outputs == {}
        assert r.artifacts == []
        assert r.error == "something broke"
        assert r.duration_ms == 50

    def test_timeout_shape(self):
        prov = _make_provenance()
        r = SkillResult.failure(
            execution_id="SKE-AAAAAAAA",
            decision_id="DEC-BBBBBBBB",
            skill_id="SKL-11111111",
            error="execution exceeded timeout",
            duration_ms=30000,
            provenance=prov,
            status=SkillResultStatus.TIMEOUT,
        )
        assert r.status == SkillResultStatus.TIMEOUT


class TestSkillResultDenied:
    def test_denied_shape(self):
        prov = _make_provenance()
        r = SkillResult.denied(
            execution_id="SKE-AAAAAAAA",
            decision_id="DEC-BBBBBBBB",
            skill_id="SKL-11111111",
            denial_reason="Missing capabilities: ledger:write",
            provenance=prov,
        )
        assert r.status == SkillResultStatus.DENIED
        assert r.outputs == {}
        assert r.artifacts == []
        assert r.error == "Missing capabilities: ledger:write"
        assert r.duration_ms == 0


class TestSkillResultSerialisation:
    def test_to_dict_contains_all_fields(self):
        prov = _make_provenance()
        r = SkillResult.success(
            execution_id="SKE-AAAAAAAA",
            decision_id="DEC-BBBBBBBB",
            skill_id="SKL-11111111",
            outputs={"key": "value"},
            artifacts=[],
            metrics={"duration_ms": 100},
            warnings=[],
            duration_ms=100,
            provenance=prov,
        )
        d = r.to_dict()
        assert d["result_id"] == r.result_id
        assert d["status"] == "COMPLETED"
        assert d["outputs"] == {"key": "value"}
        assert "provenance" in d

    def test_from_dict_round_trip(self):
        prov = _make_provenance()
        r = SkillResult.success(
            execution_id="SKE-AAAAAAAA",
            decision_id="DEC-BBBBBBBB",
            skill_id="SKL-11111111",
            outputs={"key": "value"},
            artifacts=[],
            metrics={},
            warnings=[],
            duration_ms=100,
            provenance=prov,
        )
        d = r.to_dict()
        r2 = SkillResult.from_dict(d)
        assert r2.result_id == r.result_id
        assert r2.status == r.status
        assert r2.outputs == r.outputs

    def test_frozen(self):
        prov = _make_provenance()
        r = SkillResult.denied(
            execution_id="SKE-AAAAAAAA",
            decision_id="DEC-BBBBBBBB",
            skill_id="SKL-11111111",
            denial_reason="test",
            provenance=prov,
        )
        try:
            r.status = SkillResultStatus.COMPLETED  # type: ignore
            assert False, "Should be frozen"
        except AttributeError:
            pass
